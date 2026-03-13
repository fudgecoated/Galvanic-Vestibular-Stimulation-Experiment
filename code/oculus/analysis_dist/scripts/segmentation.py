import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Parameters (from analyze_reaches_cli.py)
# ---------------------------------------------------------------------------
REACH_THRESHOLD = 0.93
TRIAL_BREAK_THRESHOLD = 11.0
VELOCITY_THRESHOLD_PERCENTILE = 15
DISTANCE_THRESHOLD_PERCENT = 10
FILTER_ORDER = 4
FILTER_CUTOFF_HZ = 12.0

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = PIPELINE_ROOT.parents[2]
INPUT_DIR = REPO_ROOT / "data" / "raw" / "oculus"
OUTPUT_DIR = REPO_ROOT / "results" / "oculus" / "analysis_dist" / "tables"

def _butter_lowpass_filter(data, cutoff_hz, fs, order=4):
    nyquist = 0.5 * fs
    normal_cutoff = min(cutoff_hz, nyquist * 0.9) / nyquist
    b, a = butter(order, normal_cutoff, btype='low')
    return filtfilt(b, a, data)

def analyze_st_pilot_reaches(input_file):
    print(f"Processing {input_file}...")
    
    # --- Load data ---
    df = pd.read_csv(input_file)
    
    # --- Handle Time Column ---
    # Check if 'seconds' exists and is valid
    time_valid = False
    if 'seconds' in df.columns:
        # Check if we have enough unique values and they are not all 0
        if df['seconds'].nunique() > 100 and df['seconds'].max() > 0:
            time_valid = True
            
    if not time_valid:
        print("Warning: 'seconds' column is missing or invalid. Attempting to reconstruct from 'timestamp'...")
        if 'timestamp' in df.columns:
            try:
                # Parse timestamp: "Day: 2025-07-05 Time: 01:03:22"
                # Clean up the string first
                clean_timestamps = df['timestamp'].astype(str).str.replace('Day: ', '').str.replace(' Time: ', ' ')
                parsed_time = pd.to_datetime(clean_timestamps)
                
                # Calculate duration
                start_time = parsed_time.min()
                end_time = parsed_time.max()
                duration = (end_time - start_time).total_seconds()
                
                print(f"Reconstructed duration: {duration} seconds")
                
                # Create linear time vector
                # We assume constant sampling rate over the duration
                df['seconds'] = np.linspace(0, duration, len(df))
                print("Successfully reconstructed 'seconds' column.")
                
            except Exception as e:
                print(f"Error parsing timestamps: {e}")
                return False
        else:
            print("Error: No 'timestamp' column found to reconstruct time.")
            return False

    # Ensure numeric and sort
    df['seconds'] = pd.to_numeric(df['seconds'], errors='coerce')
    df['HandZ'] = pd.to_numeric(df['HandZ'], errors='coerce')
    df = df.dropna(subset=['seconds', 'HandZ']).reset_index(drop=True)
    df = df.sort_values('seconds').reset_index(drop=True)

    timestamps = df['seconds'].values
    
    # Calculate sampling rate
    dt = np.mean(np.diff(timestamps))
    if dt == 0:
        # Fallback if linspace somehow produced duplicates (unlikely) or single point
        raise ValueError("Duplicate timestamps or zero time difference detected.")
    sampling_rate = 1.0 / dt
    print(f"Estimated sampling rate: {sampling_rate:.2f} Hz")

    # --- Filter ---
    handz_filtered = _butter_lowpass_filter(df['HandZ'].values, FILTER_CUTOFF_HZ, sampling_rate, order=FILTER_ORDER)
    df['HandZ_filtered'] = handz_filtered

    # --- Velocity ---
    velocity = np.gradient(handz_filtered, timestamps)
    df['Velocity'] = velocity
    velocity_abs = np.abs(velocity)

    # --- Peak detection ---
    handz_range = np.ptp(handz_filtered)
    min_prominence = handz_range * 0.05
    
    # Distance between peaks (0.2s)
    distance_samples = int(sampling_rate * 0.2)
    
    all_peaks, _ = find_peaks(handz_filtered, prominence=max(0.005, min_prominence), distance=distance_samples)
    valid_peaks = all_peaks[handz_filtered[all_peaks] > REACH_THRESHOLD]

    print(f"Found {len(valid_peaks)} valid peaks above threshold {REACH_THRESHOLD}")

    if len(valid_peaks) == 0:
        print("WARNING: No peaks found. Check threshold or data.")
        return False

    df['Is_Peak'] = False
    df.loc[valid_peaks, 'Is_Peak'] = True

    # --- Trial segmentation (Gap-based) ---
    peak_times = timestamps[valid_peaks]
    peak_gaps = np.diff(peak_times) if len(peak_times) > 1 else np.array([])
    trial_break_indices = np.where(peak_gaps > TRIAL_BREAK_THRESHOLD)[0]
    num_trials = len(trial_break_indices) + 1

    peak_trial_numbers = np.ones(len(valid_peaks), dtype=int)
    current_trial = 1
    for break_idx in trial_break_indices:
        current_trial += 1
        peak_trial_numbers[break_idx + 1:] = current_trial

    print(f"Identified {num_trials} trials based on {TRIAL_BREAK_THRESHOLD}s gaps.")

    # --- Segment reaches (Geometric) ---
    df['Reach_Number'] = 0
    df['Trial_Number'] = 0
    df['Reach_In_Trial'] = 0

    reach_info = []
    reach_number = 0

    for peak_idx_in_array, peak_sample_idx in enumerate(valid_peaks):
        reach_number += 1
        trial_num = int(peak_trial_numbers[peak_idx_in_array])

        # Find local trough before peak
        # Look back up to 5 seconds
        back_limit = max(0, peak_sample_idx - int(sampling_rate * 5))
        
        # Find minimum value in the window before peak
        window_before = handz_filtered[back_limit:peak_sample_idx+1]
        if len(window_before) == 0: continue
        
        trough_idx_before = peak_sample_idx
        min_handz_before = handz_filtered[peak_sample_idx]
        
        for i in range(peak_sample_idx - 1, back_limit - 1, -1):
            if handz_filtered[i] < min_handz_before:
                min_handz_before = handz_filtered[i]
                trough_idx_before = i

        reach_amplitude = handz_filtered[peak_sample_idx] - min_handz_before
        distance_threshold = reach_amplitude * (DISTANCE_THRESHOLD_PERCENT / 100.0)
        
        # Find start point: first point where value rises above min + 10% amp
        start_idx = peak_sample_idx
        for i in range(trough_idx_before, peak_sample_idx):
            if handz_filtered[i] - min_handz_before >= distance_threshold:
                start_idx = i
                break

        # Find trough after peak
        forward_limit = min(len(df) - 1, peak_sample_idx + int(sampling_rate * 5))
        trough_idx_after = peak_sample_idx
        min_handz_after = handz_filtered[peak_sample_idx]
        
        for i in range(peak_sample_idx + 1, forward_limit + 1):
            if handz_filtered[i] < min_handz_after:
                min_handz_after = handz_filtered[i]
                trough_idx_after = i

        reach_amplitude_after = handz_filtered[peak_sample_idx] - min_handz_after
        distance_threshold_after = reach_amplitude_after * (DISTANCE_THRESHOLD_PERCENT / 100.0)
        
        # Find end point: first point where value drops below min + 10% amp
        end_idx = peak_sample_idx
        for i in range(peak_sample_idx + 1, forward_limit + 1):
            if handz_filtered[i] - min_handz_after <= distance_threshold_after:
                end_idx = i
                break

        # Mark in DataFrame
        df.loc[start_idx:end_idx, 'Reach_Number'] = reach_number
        df.loc[start_idx:end_idx, 'Trial_Number'] = trial_num

        reach_info.append({
            'reach_number': reach_number,
            'trial_number': trial_num,
            'start_idx': start_idx,
            'end_idx': end_idx,
            'peak_idx': peak_sample_idx
        })

    # Assign reach-in-trial
    for trial_num in range(1, num_trials + 1):
        trial_reaches = [r for r in reach_info if r['trial_number'] == trial_num]
        for local_num, reach in enumerate(trial_reaches, start=1):
            mask = df['Reach_Number'] == reach['reach_number']
            df.loc[mask, 'Reach_In_Trial'] = local_num

    # --- Save Outputs ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    
    # 1. Full segmented data
    out_full = OUTPUT_DIR / f"{base_name}_scientific_segmented.csv"
    df.to_csv(out_full, index=False)
    print(f"Saved segmented data to: {out_full}")

    # 2. Reach Summary
    reach_stats = []
    for reach in reach_info:
        reach_data = df[df['Reach_Number'] == reach['reach_number']]
        if len(reach_data) == 0: continue
        
        stats = {
            'Reach_Number': reach['reach_number'],
            'Trial_Number': reach['trial_number'],
            'Reach_In_Trial': reach_data['Reach_In_Trial'].iloc[0],
            'Start_Time': reach_data['seconds'].iloc[0],
            'End_Time': reach_data['seconds'].iloc[-1],
            'Duration': reach_data['seconds'].iloc[-1] - reach_data['seconds'].iloc[0],
            'Peak_Time': timestamps[reach['peak_idx']],
            'Peak_Value': handz_filtered[reach['peak_idx']],
            'Start_Value': handz_filtered[reach['start_idx']],
            'End_Value': handz_filtered[reach['end_idx']],
            'Amplitude': handz_filtered[reach['peak_idx']] - min(handz_filtered[reach['start_idx']], handz_filtered[reach['end_idx']]),
            'Mean_Velocity': reach_data['Velocity'].abs().mean(),
            'Max_Velocity': reach_data['Velocity'].abs().max(),
        }
        reach_stats.append(stats)

    reach_summary = pd.DataFrame(reach_stats)
    out_reach = OUTPUT_DIR / f"{base_name}_reach_summary.csv"
    reach_summary.to_csv(out_reach, index=False)
    print(f"Saved reach summary to: {out_reach}")

    # 3. Trial Summary
    trial_stats = []
    for trial_num in range(1, num_trials + 1):
        trial_reaches = reach_summary[reach_summary['Trial_Number'] == trial_num]
        trial_data = df[df['Trial_Number'] == trial_num]
        
        if len(trial_data) == 0: continue
        
        stats = {
            'Trial_Number': trial_num,
            'Num_Reaches': len(trial_reaches),
            'Start_Time': trial_data['seconds'].iloc[0],
            'End_Time': trial_data['seconds'].iloc[-1],
            'Duration': trial_data['seconds'].iloc[-1] - trial_data['seconds'].iloc[0],
            'Mean_Reach_Duration': trial_reaches['Duration'].mean() if not trial_reaches.empty else 0,
            'Mean_Peak_Value': trial_reaches['Peak_Value'].mean() if not trial_reaches.empty else 0,
            'Mean_Amplitude': trial_reaches['Amplitude'].mean() if not trial_reaches.empty else 0,
        }
        trial_stats.append(stats)

    trial_summary = pd.DataFrame(trial_stats)
    out_trial = OUTPUT_DIR / f"{base_name}_trial_summary.csv"
    trial_summary.to_csv(out_trial, index=False)
    print(f"Saved trial summary to: {out_trial}")
    return True


def _is_compatible_input_file(file_path: Path) -> bool:
    try:
        df = pd.read_csv(file_path, nrows=2)
    except Exception:
        return False

    cols = set(df.columns)
    has_signal = "HandZ" in cols
    has_time = "seconds" in cols or "timestamp" in cols
    return has_signal and has_time

def process_directory(directory_path):
    print(f"Processing directory: {directory_path}")
    
    # Get all CSV files
    files = [f for f in os.listdir(directory_path) if f.lower().endswith('.csv')]
    
    # Filter out output files to avoid re-processing results
    candidate_files = [
        f for f in files
        if "_segmented" not in f
        and "_summary" not in f
        and "data_dictionary" not in f.lower()
    ]
    input_files = [
        f for f in candidate_files
        if _is_compatible_input_file(Path(directory_path) / f)
    ]

    print(f"Found {len(input_files)} input files to process: {input_files}")
    
    for filename in input_files:
        file_path = os.path.join(directory_path, filename)
        try:
            ok = analyze_st_pilot_reaches(file_path)
            if ok:
                print(f"Successfully processed {filename}\n" + "-"*50)
            else:
                print(f"Skipped {filename}: incompatible data or no detectable reaches\n" + "-"*50)
        except Exception as e:
            print(f"Error processing {filename}: {e}\n" + "-"*50)

if __name__ == "__main__":
    data_dir = INPUT_DIR

    if data_dir.exists():
        process_directory(str(data_dir))
    else:
        print(f"Error: Directory {data_dir} not found.")
