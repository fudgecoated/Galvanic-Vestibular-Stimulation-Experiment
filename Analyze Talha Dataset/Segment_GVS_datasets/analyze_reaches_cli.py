#!/usr/bin/env python3

"""analyze_reaches_cli.py
Command-line interface for the hand reach analysis.

This script wraps the existing analysis logic so you can run on a single file
or batch-process a directory. By default it will try to use an unfiltered
(interpolated) raw file if provided via --unfiltered; otherwise the visualization
will be generated without the raw overlay.
"""

import argparse
import os
import glob
import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks, savgol_filter
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Defaults and analysis parameters (tweakable)
# ---------------------------------------------------------------------------
REACH_THRESHOLD = 0.93
TRIAL_BREAK_THRESHOLD = 10.0
VELOCITY_THRESHOLD_PERCENTILE = 15
DISTANCE_THRESHOLD_PERCENT = 10
FILTER_ORDER = 4
FILTER_CUTOFF_HZ = 12.0

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _butter_lowpass_filter(data, cutoff_hz, fs, order=4):
    nyquist = 0.5 * fs
    normal_cutoff = min(cutoff_hz, nyquist * 0.9) / nyquist
    b, a = butter(order, normal_cutoff, btype='low')
    return filtfilt(b, a, data)


def safe_lowpass_filter(x, cutoff_hz, fs, order=4):
    """Try Butterworth filtfilt first; if it fails (short signal), fall back to savgol or moving average."""
    try:
        return _butter_lowpass_filter(x, cutoff_hz, fs, order=order)
    except Exception as e:
        # filtfilt may fail for very short signals because padlen is too large
        n = len(x)
        # Try Savitzky-Golay if we have enough points
        try:
            if n >= 7:
                window = 7 if n >= 7 else (n if n % 2 == 1 else n - 1)
                if window > n:
                    window = n if n % 2 == 1 else n - 1
                return savgol_filter(x, window_length=window, polyorder=2)
        except Exception:
            pass
        # Moving average fallback
        if n >= 3:
            kernel = np.ones(3) / 3.0
            y = np.convolve(x, kernel, mode='same')
            return y
        # Too short: return original
        return x


def analyze_hand_reaches(input_file, unfiltered_file=None, output_dir=None,
                         reach_threshold=REACH_THRESHOLD,
                         trial_break_threshold=TRIAL_BREAK_THRESHOLD,
                         velocity_threshold_percentile=VELOCITY_THRESHOLD_PERCENTILE,
                         distance_threshold_percent=DISTANCE_THRESHOLD_PERCENT,
                         filter_order=FILTER_ORDER,
                         filter_cutoff_hz=FILTER_CUTOFF_HZ):
    """Run the reach analysis on a single input CSV and write outputs.

    Returns paths to generated files (full_csv, reach_summary_csv, trial_summary_csv, html)
    """
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(input_file)) or os.getcwd()
    os.makedirs(output_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(input_file))[0]
    out_full = os.path.join(output_dir, f"{base}_segmented.csv")
    out_reach = os.path.join(output_dir, f"{base}_reach_summary.csv")
    out_trial = os.path.join(output_dir, f"{base}_trial_summary.csv")
    out_html = os.path.join(output_dir, f"{base}_visualization.html")

    # --- Load data (auto-prefer an elapsed-seconds column, else datetime) ---
    raw_df = pd.read_csv(input_file)

    time_candidates_elapsed = ['ElapsedSeconds', 'elapsedseconds', 'elapsed_seconds', 'seconds', 'secs', 'sec', 'time_s', 'time_seconds']
    time_candidates_datetime = ['Timestamp', 'timestamp', 'Time', 'time', 'truetime', 'TrueTime', 'TF', 'TimeStamp']
    handz_candidates = ['HandZ', 'handz', 'Hand_Z', 'Hand_Z_mm', 'hand_z', 'HandZPosition', 'HandZ_pos', 'HandZ_mm', 'Z', 'z']

    def _find_column(columns, candidates):
        for c in candidates:
            if c in columns:
                return c
        # case-insensitive match
        cols_lower = {col.lower(): col for col in columns}
        for c in candidates:
            if c.lower() in cols_lower:
                return cols_lower[c.lower()]
        return None

    # Prefer elapsed numeric time column if present
    time_col = _find_column(raw_df.columns, time_candidates_elapsed)
    time_type = 'elapsed' if time_col is not None else None
    if time_col is None:
        time_col = _find_column(raw_df.columns, time_candidates_datetime)
        time_type = 'datetime' if time_col is not None else None

    handz_col = _find_column(raw_df.columns, handz_candidates)

    if time_col is None or handz_col is None:
        raise RuntimeError(f"Could not find required columns in {input_file}. Found columns: {list(raw_df.columns)}.\n"
                           f"Expected an elapsed-time column (e.g. 'seconds') or datetime (e.g. 'Timestamp'), plus a HandZ column.")

    # Reduce to only the two columns we need and standardize their names
    df = raw_df[[time_col, handz_col]].rename(columns={time_col: 'Timestamp', handz_col: 'HandZ'}).copy()

    # Load unfiltered if provided and exists (apply same flexible mapping)
    df_unfiltered = None
    if unfiltered_file is not None and os.path.exists(unfiltered_file):
        raw_unf = pd.read_csv(unfiltered_file)
        time_col_unf = _find_column(raw_unf.columns, time_candidates_elapsed) or _find_column(raw_unf.columns, time_candidates_datetime)
        handz_col_unf = _find_column(raw_unf.columns, handz_candidates)
        if time_col_unf is not None and handz_col_unf is not None:
            df_unfiltered = raw_unf[[time_col_unf, handz_col_unf]].rename(columns={time_col_unf: 'Timestamp', handz_col_unf: 'HandZ'}).copy()
        else:
            # if the unfiltered file doesn't contain the expected columns, ignore overlay but warn
            print(f"Warning: unfiltered file {unfiltered_file} missing expected columns; skipping overlay.")

    # Convert timestamp to elapsed seconds. Prefer numeric elapsed, else parse datetime strings.
    if time_type == 'elapsed' or np.issubdtype(df['Timestamp'].dtype, np.number):
        df['Timestamp'] = pd.to_numeric(df['Timestamp'], errors='coerce')
        df = df.dropna(subset=['Timestamp']).reset_index(drop=True)
        df['Timestamp'] = df['Timestamp'].astype(float)
        # If timestamps are very large (likely milliseconds), attempt to detect and convert
        if df['Timestamp'].max() > 1e6:
            # likely milliseconds or microseconds; scale down if plausible
            print(f"Warning: time values appear large (max={df['Timestamp'].max()}); assuming milliseconds and dividing by 1000.")
            df['Timestamp'] = df['Timestamp'] / 1000.0
        df['Timestamp'] = df['Timestamp'] - df['Timestamp'].iloc[0]
    else:
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        df['Timestamp'] = (df['Timestamp'] - df['Timestamp'].iloc[0]).dt.total_seconds()

    if df_unfiltered is not None:
        if np.issubdtype(df_unfiltered['Timestamp'].dtype, np.number):
            df_unfiltered['Timestamp'] = pd.to_numeric(df_unfiltered['Timestamp'], errors='coerce')
            df_unfiltered = df_unfiltered.dropna(subset=['Timestamp']).reset_index(drop=True)
            df_unfiltered['Timestamp'] = df_unfiltered['Timestamp'].astype(float)
            if df_unfiltered['Timestamp'].max() > 1e6:
                df_unfiltered['Timestamp'] = df_unfiltered['Timestamp'] / 1000.0
            df_unfiltered['Timestamp'] = df_unfiltered['Timestamp'] - df_unfiltered['Timestamp'].iloc[0]
        else:
            df_unfiltered['Timestamp'] = pd.to_datetime(df_unfiltered['Timestamp'])
            df_unfiltered['Timestamp'] = (df_unfiltered['Timestamp'] - df_unfiltered['Timestamp'].iloc[0]).dt.total_seconds()

    # Ensure HandZ numeric and drop rows with NaNs
    df['HandZ'] = pd.to_numeric(df['HandZ'], errors='coerce')
    df = df.dropna().reset_index(drop=True)
    if df_unfiltered is not None:
        df_unfiltered['HandZ'] = pd.to_numeric(df_unfiltered['HandZ'], errors='coerce')
        df_unfiltered = df_unfiltered.dropna().reset_index(drop=True)

    timestamps = df['Timestamp'].values
    dt = np.mean(np.diff(timestamps))
    sampling_rate = 1.0 / dt

    # --- Filter ---
    handz_filtered = safe_lowpass_filter(df['HandZ'].values, filter_cutoff_hz, sampling_rate, order=filter_order)
    df['HandZ_filtered'] = handz_filtered

    # --- Velocity ---
    velocity = np.gradient(handz_filtered, timestamps)
    df['Velocity'] = velocity
    velocity_abs = np.abs(velocity)
    velocity_threshold = np.percentile(velocity_abs, velocity_threshold_percentile)

    # --- Peak detection ---
    handz_range = np.ptp(handz_filtered)
    min_prominence = handz_range * 0.05
    all_peaks, _ = find_peaks(handz_filtered, prominence=min_prominence,
                              distance=int(sampling_rate * 0.2))
    
    # Auto-adjust threshold if necessary: if no peaks found or very few, use data-driven threshold
    valid_peaks = all_peaks[handz_filtered[all_peaks] > reach_threshold]

    if len(valid_peaks) == 0:
        # Try auto-threshold at 85th percentile of the filtered data
        auto_threshold = np.percentile(handz_filtered, 85)
        print(f"Warning: No peaks found with threshold {reach_threshold}. Trying auto-threshold at 85th percentile = {auto_threshold:.3f}")
        valid_peaks = all_peaks[handz_filtered[all_peaks] > auto_threshold]
        reach_threshold = auto_threshold  # Update for reporting
        
    if len(valid_peaks) == 0:
        raise RuntimeError(f"No peaks found even with auto-threshold {reach_threshold:.3f}. Check your data.")
    
    print(f"Found {len(valid_peaks)} peaks above threshold {reach_threshold:.3f}")

    df['Is_Peak'] = False
    df.loc[valid_peaks, 'Is_Peak'] = True

    # --- Trial segmentation ---
    peak_times = timestamps[valid_peaks]
    peak_gaps = np.diff(peak_times) if len(peak_times) > 1 else np.array([])
    trial_break_indices = np.where(peak_gaps > trial_break_threshold)[0]
    num_trials = len(trial_break_indices) + 1

    peak_trial_numbers = np.ones(len(valid_peaks), dtype=int)
    current_trial = 1
    for break_idx in trial_break_indices:
        current_trial += 1
        peak_trial_numbers[break_idx + 1:] = current_trial

    # --- Segment reaches ---
    df['Reach_Number'] = 0
    df['Trial_Number'] = 0
    df['Reach_In_Trial'] = 0

    reach_info = []
    reach_number = 0

    for peak_idx_in_array, peak_sample_idx in enumerate(valid_peaks):
        reach_number += 1
        trial_num = int(peak_trial_numbers[peak_idx_in_array])

        # Find local trough before peak
        back_limit = max(0, peak_sample_idx - int(sampling_rate * 5))
        trough_idx_before = peak_sample_idx
        min_handz_before = handz_filtered[peak_sample_idx]
        for i in range(peak_sample_idx - 1, back_limit - 1, -1):
            if handz_filtered[i] < min_handz_before:
                min_handz_before = handz_filtered[i]
                trough_idx_before = i

        reach_amplitude = handz_filtered[peak_sample_idx] - min_handz_before
        distance_threshold = reach_amplitude * (distance_threshold_percent / 100.0)
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
        distance_threshold_after = reach_amplitude_after * (distance_threshold_percent / 100.0)
        end_idx = peak_sample_idx
        for i in range(peak_sample_idx + 1, forward_limit + 1):
            if handz_filtered[i] - min_handz_after <= distance_threshold_after:
                end_idx = i
                break

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

    # --- Summaries and outputs ---
    df.to_csv(out_full, index=False)

    reach_stats = []
    for reach in reach_info:
        reach_data = df[df['Reach_Number'] == reach['reach_number']]
        if len(reach_data) == 0:
            continue
        stats = {
            'Reach_Number': reach['reach_number'],
            'Trial_Number': reach['trial_number'],
            'Reach_In_Trial': reach_data['Reach_In_Trial'].iloc[0],
            'Start_Time': reach_data['Timestamp'].iloc[0],
            'End_Time': reach_data['Timestamp'].iloc[-1],
            'Duration': reach_data['Timestamp'].iloc[-1] - reach_data['Timestamp'].iloc[0],
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
    reach_summary.to_csv(out_reach, index=False)

    trial_stats = []
    for trial_num in range(1, num_trials + 1):
        trial_reaches = reach_summary[reach_summary['Trial_Number'] == trial_num]
        trial_data = df[df['Trial_Number'] == trial_num]
        stats = {
            'Trial_Number': trial_num,
            'Num_Reaches': len(trial_reaches),
            'Start_Time': trial_data['Timestamp'].iloc[0] if len(trial_data) > 0 else np.nan,
            'End_Time': trial_data['Timestamp'].iloc[-1] if len(trial_data) > 0 else np.nan,
            'Duration': (trial_data['Timestamp'].iloc[-1] - trial_data['Timestamp'].iloc[0]) if len(trial_data) > 0 else np.nan,
            'Mean_Reach_Duration': trial_reaches['Duration'].mean(),
            'Mean_Peak_Value': trial_reaches['Peak_Value'].mean(),
            'Mean_Amplitude': trial_reaches['Amplitude'].mean(),
        }
        trial_stats.append(stats)

    trial_summary = pd.DataFrame(trial_stats)
    trial_summary.to_csv(out_trial, index=False)

    # Visualization
    _create_visualization(df, handz_filtered, timestamps, reach_info, reach_summary, trial_summary,
                          velocity_abs, velocity_threshold, out_html, df_unfiltered)

    return out_full, out_reach, out_trial, out_html


def _create_visualization(df, handz_filtered, timestamps, reach_info, reach_summary, trial_summary,
                          velocity_abs, velocity_threshold, output_path, df_unfiltered=None):
    fig = make_subplots(rows=3, cols=1,
                        subplot_titles=(
                            'HandZ Position - Raw vs Filtered by Trial',
                            'Reach Segmentation by Trial',
                            'Velocity Profile'
                        ),
                        vertical_spacing=0.08,
                        row_heights=[0.5, 0.25, 0.25])

    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']

    if df_unfiltered is not None:
        fig.add_trace(
            go.Scatter(x=df_unfiltered['Timestamp'], y=df_unfiltered['HandZ'], mode='lines', name='Unfiltered',
                       line=dict(color='orange', width=1.5), opacity=0.7),
            row=1, col=1)

    for trial_num in range(1, trial_summary['Trial_Number'].max() + 1 if not trial_summary.empty else 1):
        trial_data = df[df['Trial_Number'] == trial_num]
        if trial_data.empty:
            continue
        color = colors[(trial_num - 1) % len(colors)]
        fig.add_trace(go.Scatter(x=trial_data['Timestamp'], y=trial_data['HandZ_filtered'], mode='lines',
                                 name=f'Trial {trial_num}', line=dict(color=color, width=2)), row=1, col=1)

    peak_data = df[df['Is_Peak']]
    if not peak_data.empty:
        fig.add_trace(go.Scatter(x=peak_data['Timestamp'], y=peak_data['HandZ_filtered'], mode='markers',
                                 name='Peaks', marker=dict(color='black', size=8, symbol='star')), row=1, col=1)

    # Starts and ends
    starts_t, starts_v, ends_t, ends_v = [], [], [], []
    for r in reach_info:
        starts_t.append(timestamps[r['start_idx']])
        starts_v.append(handz_filtered[r['start_idx']])
        ends_t.append(timestamps[r['end_idx']])
        ends_v.append(handz_filtered[r['end_idx']])

    if starts_t:
        fig.add_trace(go.Scatter(x=starts_t, y=starts_v, mode='markers', name='Start',
                                 marker=dict(color='green', size=6, symbol='triangle-up')), row=1, col=1)
    if ends_t:
        fig.add_trace(go.Scatter(x=ends_t, y=ends_v, mode='markers', name='End',
                                 marker=dict(color='red', size=6, symbol='triangle-down')), row=1, col=1)

    fig.add_hline(y=REACH_THRESHOLD, line_dash='dash', line_color='red', annotation_text=f'Threshold={REACH_THRESHOLD}', row=1, col=1)

    # Plot reach-in-trial
    for trial_num in range(1, trial_summary['Trial_Number'].max() + 1 if not trial_summary.empty else 1):
        trial_data = df[df['Trial_Number'] == trial_num]
        if trial_data.empty:
            continue
        color = colors[(trial_num - 1) % len(colors)]
        fig.add_trace(go.Scatter(x=trial_data['Timestamp'], y=trial_data['Reach_In_Trial'], mode='lines',
                                 name=f'Trial {trial_num} Reaches', line=dict(color=color, width=2), showlegend=False), row=2, col=1)

    fig.add_trace(go.Scatter(x=df['Timestamp'], y=velocity_abs, mode='lines', name='|Velocity|',
                             line=dict(color='purple', width=1)), row=3, col=1)
    fig.add_hline(y=velocity_threshold, line_dash='dash', line_color='red', annotation_text=f'Thresh={velocity_threshold:.4f}', row=3, col=1)

    fig.update_xaxes(title_text='Time (s)', row=3, col=1)
    fig.update_yaxes(title_text='HandZ', row=1, col=1)
    fig.update_yaxes(title_text='Reach #', row=2, col=1)
    fig.update_yaxes(title_text='|Velocity|', row=3, col=1)

    fig.update_layout(height=1000, title_text='Hand Reach Analysis', hovermode='closest')
    fig.write_html(output_path)


def process_batch_directory(input_dir, output_dir=None, file_pattern='*.csv', unfiltered_suffix='_interpolated_unfiltered.csv'):
    """Process all files matching pattern in a directory. Attempts to find an unfiltered file
    for each input using the same basename + provided suffix if present."""
    if output_dir is None:
        output_dir = input_dir
    os.makedirs(output_dir, exist_ok=True)

    pattern = os.path.join(input_dir, file_pattern)
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"No files matching {pattern}")

    results = []
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0]
        # try to find unfiltered file next to it
        candidate_unfiltered = os.path.join(os.path.dirname(f), f"{base}_interpolated_unfiltered.csv")
        if os.path.exists(candidate_unfiltered):
            unfiltered = candidate_unfiltered
        else:
            unfiltered = None
        try:
            res = analyze_hand_reaches(f, unfiltered_file=unfiltered, output_dir=output_dir)
            results.append(res)
            print(f"Processed {f} -> {res[0]}")
        except Exception as e:
            print(f"Failed processing {f}: {e}")
    return results


def main():
    parser = argparse.ArgumentParser(description='Analyze hand reaches (single file or batch)')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--input', '-i', help='Single input CSV file')
    group.add_argument('--batch-dir', '-b', help='Directory with CSV files to process')
    parser.add_argument('--unfiltered', '-u', help='Optional unfiltered CSV to overlay in visualization')
    parser.add_argument('--output-dir', '-o', help='Output directory (default: same as input)')
    parser.add_argument('--file-pattern', help='Glob pattern for batch (default: *.csv)', default='*.csv')
    args = parser.parse_args()

    if args.input:
        if not os.path.exists(args.input):
            parser.error(f"Input file not found: {args.input}")
        try:
            out = analyze_hand_reaches(args.input, unfiltered_file=args.unfiltered, output_dir=args.output_dir)
            print('\nGenerated files:')
            for p in out:
                print('  -', p)
        except Exception as e:
            print('Error:', e)
    else:
        if not os.path.isdir(args.batch_dir):
            parser.error(f"Batch directory not found: {args.batch_dir}")
        try:
            results = process_batch_directory(args.batch_dir, output_dir=args.output_dir, file_pattern=args.file_pattern)
            print(f"\nBatch processed {len(results)} files")
        except Exception as e:
            print('Error during batch processing:', e)


if __name__ == '__main__':
    main()
