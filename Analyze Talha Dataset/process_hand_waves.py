import pandas as pd
import numpy as np
from scipy import signal
from scipy.signal import butter, filtfilt, find_peaks
import matplotlib.pyplot as plt

# Configuration
input_file = 'TA_OCULUS_PILOT_JUL4_2_OCULUS_interpolated.csv'
output_file_full = 'hand_waves_segmented_full.csv'
output_file_wave_summary = 'wave_summary.csv'
output_file_trial_summary = 'trial_summary.csv'

TRIAL_BREAK_THRESHOLD = 15.0  # seconds - breaks longer than this indicate new trial
PEAK_GAP_THRESHOLD = 0.8  # seconds - gap between peaks longer than this indicates new trial

print("Loading data...")
# Read only the columns we need to save memory
df = pd.read_csv(input_file, usecols=['Timestamp', 'HandZ'])

# Convert Timestamp from datetime string to elapsed seconds
df['Timestamp'] = pd.to_datetime(df['Timestamp'])
# Calculate elapsed time in seconds from the first timestamp
df['Timestamp'] = (df['Timestamp'] - df['Timestamp'].iloc[0]).dt.total_seconds()

# Ensure HandZ is numeric
df['HandZ'] = pd.to_numeric(df['HandZ'], errors='coerce')

# Drop any rows with NaN values
df = df.dropna()

print(f"Data shape: {df.shape}")
print(f"Data range: {df['Timestamp'].min():.3f} to {df['Timestamp'].max():.3f} seconds")
print(f"Total duration: {df['Timestamp'].max() - df['Timestamp'].min():.2f} seconds")

# Calculate sampling rate
timestamps = df['Timestamp'].values
time_diffs = np.diff(timestamps)
mean_dt = np.mean(time_diffs)
sampling_rate = 1.0 / mean_dt

print(f"\nSampling rate analysis:")
print(f"  Mean time between samples: {mean_dt:.4f} seconds")
print(f"  Sampling rate: {sampling_rate:.2f} Hz")
print(f"  Min dt: {np.min(time_diffs):.4f}, Max dt: {np.max(time_diffs):.4f}")

# Determine cutoff frequency
# For hand movements, typical frequencies are 0.5-5 Hz
# Set cutoff at ~20% of Nyquist frequency or 5 Hz (whichever is lower)
nyquist = sampling_rate / 2
suggested_cutoff = min(5.0, nyquist * 0.2)

print(f"\nFilter parameters:")
print(f"  Nyquist frequency: {nyquist:.2f} Hz")
print(f"  Suggested cutoff: {suggested_cutoff:.2f} Hz")
print(f"  Filter type: Low-pass Butterworth (removes high-frequency noise)")

# Design and apply Butterworth low-pass filter
filter_order = 4
b, a = butter(filter_order, suggested_cutoff, fs=sampling_rate, btype='low')

# Apply filter (forward-backward to avoid phase shift)
handz_filtered = filtfilt(b, a, df['HandZ'].values)

print(f"\nFiltering complete.")




















# Detect peaks and troughs FIRST (before trial detection)
print(f"\nDetecting peaks and troughs...")

# Use prominence to avoid detecting tiny fluctuations
handz_range = np.ptp(handz_filtered)
min_prominence = handz_range * 0.1  # peaks must be at least 10% of range

peaks, peak_properties = find_peaks(
    handz_filtered, 
    prominence=min_prominence,
    distance=int(sampling_rate * 0.3)  # minimum 0.3 seconds between peaks
)

# Detect troughs (local minima) - invert signal
troughs, trough_properties = find_peaks(
    -handz_filtered,
    prominence=min_prominence,
    distance=int(sampling_rate * 0.3)
)

print(f"  Found {len(peaks)} peaks")
print(f"  Found {len(troughs)} troughs")

# Detect trial boundaries based on gaps between PEAKS
print(f"\nDetecting trial boundaries (peak gaps > {PEAK_GAP_THRESHOLD}s)...")
peak_times = timestamps[peaks]
peak_gaps = np.diff(peak_times)

# Find where peak gaps exceed threshold (indicates trial break)
trial_break_peaks = np.where(peak_gaps > PEAK_GAP_THRESHOLD)[0]
print(f"  Found {len(trial_break_peaks)} trial breaks between peaks")

if len(trial_break_peaks) > 0:
    print(f"  Peak gap durations at trial breaks:")
    for idx in trial_break_peaks[:10]:  # Show first 10
        print(f"    - Gap between peak {idx} and {idx+1}: {peak_gaps[idx]:.2f}s")

# Assign trial numbers based on peak gaps
trial_numbers = np.ones(len(df), dtype=int)
peak_trial_numbers = np.ones(len(peaks), dtype=int)

current_trial = 1
for break_idx in trial_break_peaks:
    current_trial += 1
    # All peaks after this break belong to the next trial
    peak_trial_numbers[break_idx + 1:] = current_trial

num_trials = current_trial
print(f"  Total trials detected: {num_trials}")

# Assign trial numbers to all data points based on nearest peak
for i, peak_idx in enumerate(peaks):
    trial_num = peak_trial_numbers[i]
    # Find the boundaries of this peak's wave (roughly)
    if i == 0:
        start_bound = 0
    else:
        start_bound = (peaks[i-1] + peak_idx) // 2
    
    if i == len(peaks) - 1:
        end_bound = len(df)
    else:
        end_bound = (peak_idx + peaks[i+1]) // 2
    
    trial_numbers[start_bound:end_bound] = trial_num

# Add trial number to dataframe
df['Trial_Number'] = trial_numbers

# Segment waves using peaks as centers
print(f"\nSegmenting individual waves...")

# Calculate velocity (rate of change)
velocity = np.gradient(handz_filtered, timestamps)
velocity_abs = np.abs(velocity)

# Find low-velocity regions (pauses between waves, not trial breaks)
velocity_threshold = np.percentile(velocity_abs, 20)  # bottom 20% of velocities

# Initialize wave segments
wave_number_global = np.zeros(len(df), dtype=int)  # Global wave number across all trials
wave_number_in_trial = np.zeros(len(df), dtype=int)  # Wave number within current trial

# For each peak, define its wave segment
for wave_num, peak_idx in enumerate(peaks, start=1):
    # Get trial number for this peak
    trial_num = trial_numbers[peak_idx]
    
    # Search backward from peak for wave boundary
    start_idx = peak_idx
    search_limit_back = max(0, peak_idx - int(sampling_rate * 3))
    for i in range(peak_idx - 1, search_limit_back, -1):
        # Stop if we hit a different trial
        if trial_numbers[i] != trial_num:
            start_idx = i + 1
            break
        # Stop if we hit a low-velocity region
        if velocity_abs[i] < velocity_threshold:
            start_idx = i
            break
    
    # Search forward from peak for wave boundary
    end_idx = peak_idx
    search_limit_forward = min(len(df), peak_idx + int(sampling_rate * 3))
    for i in range(peak_idx + 1, search_limit_forward):
        # Stop if we hit a different trial
        if trial_numbers[i] != trial_num:
            end_idx = i - 1
            break
        # Stop if we hit a low-velocity region
        if velocity_abs[i] < velocity_threshold:
            end_idx = i
            break
    
    # Assign global wave number to this segment
    wave_number_global[start_idx:end_idx+1] = wave_num

# Calculate wave number within each trial
for trial_num in range(1, num_trials + 1):
    trial_mask = trial_numbers == trial_num
    trial_waves = wave_number_global[trial_mask]
    unique_waves = np.unique(trial_waves[trial_waves > 0])
    
    for local_wave_num, global_wave_num in enumerate(unique_waves, start=1):
        wave_mask = (trial_numbers == trial_num) & (wave_number_global == global_wave_num)
        wave_number_in_trial[wave_mask] = local_wave_num

# Add all results to dataframe
df['HandZ_filtered'] = handz_filtered
df['Velocity'] = velocity
df['Wave_Number'] = wave_number_global  # Global wave number
df['Wave_In_Trial'] = wave_number_in_trial  # Wave number within trial (1-20)
df['Is_Peak'] = False
df.loc[peaks, 'Is_Peak'] = True
df['Is_Trough'] = False
df.loc[troughs, 'Is_Trough'] = True

# Save full data (Option A)
print(f"\nSaving full data to {output_file_full}...")
df.to_csv(output_file_full, index=False)

# Generate wave summary statistics (Option C - Part 1)
print(f"\nGenerating wave summary statistics...")
wave_stats = []
for wave_num in range(1, len(peaks) + 1):
    wave_data = df[df['Wave_Number'] == wave_num]
    if len(wave_data) > 0:
        trial_num = wave_data['Trial_Number'].iloc[0]
        wave_in_trial = wave_data['Wave_In_Trial'].iloc[0]
        
        stats = {
            'Wave_Number': wave_num,
            'Trial_Number': trial_num,
            'Wave_In_Trial': wave_in_trial,
            'Start_Time': wave_data['Timestamp'].iloc[0],
            'End_Time': wave_data['Timestamp'].iloc[-1],
            'Duration': wave_data['Timestamp'].iloc[-1] - wave_data['Timestamp'].iloc[0],
            'Peak_Time': wave_data[wave_data['Is_Peak']]['Timestamp'].values[0] if any(wave_data['Is_Peak']) else np.nan,
            'Peak_Value': wave_data['HandZ_filtered'].max(),
            'Trough_Value': wave_data['HandZ_filtered'].min(),
            'Amplitude': wave_data['HandZ_filtered'].max() - wave_data['HandZ_filtered'].min(),
            'Mean_Velocity': wave_data['Velocity'].abs().mean(),
            'Max_Velocity': wave_data['Velocity'].abs().max(),
            'Sample_Count': len(wave_data)
        }
        wave_stats.append(stats)

wave_summary = pd.DataFrame(wave_stats)
wave_summary.to_csv(output_file_wave_summary, index=False)

print(f"\nWave Summary Statistics (first 10 waves):")
print(wave_summary.head(10))

# Generate trial summary statistics (Option C - Part 2)
print(f"\nGenerating trial summary statistics...")
trial_stats = []
for trial_num in range(1, num_trials + 1):
    trial_data = df[df['Trial_Number'] == trial_num]
    trial_waves = wave_summary[wave_summary['Trial_Number'] == trial_num]
    
    stats = {
        'Trial_Number': trial_num,
        'Start_Time': trial_data['Timestamp'].iloc[0],
        'End_Time': trial_data['Timestamp'].iloc[-1],
        'Duration': trial_data['Timestamp'].iloc[-1] - trial_data['Timestamp'].iloc[0],
        'Num_Waves': len(trial_waves),
        'Mean_Wave_Duration': trial_waves['Duration'].mean() if len(trial_waves) > 0 else np.nan,
        'Mean_Amplitude': trial_waves['Amplitude'].mean() if len(trial_waves) > 0 else np.nan,
        'Mean_Wave_Velocity': trial_waves['Mean_Velocity'].mean() if len(trial_waves) > 0 else np.nan,
        'Sample_Count': len(trial_data)
    }
    trial_stats.append(stats)

trial_summary = pd.DataFrame(trial_stats)
trial_summary.to_csv(output_file_trial_summary, index=False)

print(f"\nTrial Summary Statistics:")
print(trial_summary)

# Validation: Check for trials with unusual wave counts
print(f"\n=== VALIDATION ===")
for _, trial in trial_summary.iterrows():
    if trial['Num_Waves'] != 20:
        print(f"⚠️  Trial {trial['Trial_Number']} has {trial['Num_Waves']} waves (expected ~20)")

# Create visualization
print("\nGenerating visualization...")
fig, axes = plt.subplots(3, 1, figsize=(16, 12))

# Plot 1: First trial in detail
trial_1_data = df[df['Trial_Number'] == 1]
ax1 = axes[0]
ax1.plot(trial_1_data['Timestamp'], trial_1_data['HandZ'], 'b-', alpha=0.3, label='Raw', linewidth=1)
ax1.plot(trial_1_data['Timestamp'], trial_1_data['HandZ_filtered'], 'r-', linewidth=2, label='Filtered')

# Mark peaks and troughs for trial 1
trial_1_peaks = trial_1_data[trial_1_data['Is_Peak']]
trial_1_troughs = trial_1_data[trial_1_data['Is_Trough']]
ax1.plot(trial_1_peaks['Timestamp'], trial_1_peaks['HandZ_filtered'], 'go', markersize=8, label='Peaks')
ax1.plot(trial_1_troughs['Timestamp'], trial_1_troughs['HandZ_filtered'], 'mo', markersize=6, label='Troughs')

ax1.set_xlabel('Time (s)')
ax1.set_ylabel('HandZ Position')
ax1.set_title('Trial 1: Hand Movement with Detected Peaks and Troughs')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Plot 2: Wave segmentation for trial 1
ax2 = axes[1]
ax2.plot(trial_1_data['Timestamp'], trial_1_data['Wave_In_Trial'], 'b-', linewidth=2)
ax2.set_xlabel('Time (s)')
ax2.set_ylabel('Wave Number (within trial)')
ax2.set_title('Trial 1: Wave Segmentation')
ax2.grid(True, alpha=0.3)
ax2.set_ylim(0, 22)

# Plot 3: All trials overview
ax3 = axes[2]
# Color each trial differently
colors = plt.cm.tab10(np.linspace(0, 1, min(10, num_trials)))
for trial_num in range(1, min(num_trials + 1, 6)):  # Plot first 5 trials max
    trial_data = df[df['Trial_Number'] == trial_num]
    color_idx = (trial_num - 1) % 10
    ax3.plot(trial_data['Timestamp'], trial_data['HandZ_filtered'], 
             linewidth=1.5, label=f'Trial {trial_num}', color=colors[color_idx])

ax3.set_xlabel('Time (s)')
ax3.set_ylabel('HandZ Position (filtered)')
ax3.set_title(f'Overview: First {min(num_trials, 5)} Trials')
ax3.legend()
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('wave_analysis_with_trials.png', dpi=150, bbox_inches='tight')
print("Saved visualization to 'wave_analysis_with_trials.png'")

# Print summary
print("\n" + "="*60)
print("=== PROCESSING COMPLETE ===")
print("="*60)
print(f"\nTotal waves detected: {len(wave_summary)}")
print(f"Total trials detected: {num_trials}")
print(f"Average waves per trial: {len(wave_summary)/num_trials:.1f}")
print(f"Mean wave duration: {wave_summary['Duration'].mean():.3f} seconds")
print(f"Mean wave amplitude: {wave_summary['Amplitude'].mean():.4f}")

print(f"\n📁 Output files created:")
print(f"  1. {output_file_full}")
print(f"     - Full time series with Trial_Number, Wave_Number, Wave_In_Trial")
print(f"     - Use for: Detailed analysis, plotting individual waves")
print(f"  2. {output_file_wave_summary}")
print(f"     - Statistics for each wave (duration, amplitude, velocity, etc.)")
print(f"     - Use for: Statistical analysis, comparing waves")
print(f"  3. {output_file_trial_summary}")
print(f"     - Statistics for each trial (wave count, mean metrics)")
print(f"     - Use for: Trial-level analysis, quality checks")
print(f"  4. wave_analysis_with_trials.png")
print(f"     - Visualization of segmentation results")

print(f"\n💡 Example queries:")
print(f"  - Get all data from trial 3:")
print(f"    df[df['Trial_Number'] == 3]")
print(f"  - Get wave 5 from trial 3:")
print(f"    df[(df['Trial_Number'] == 3) & (df['Wave_In_Trial'] == 5)]")
print(f"  - Get all peaks from trial 2:")
print(f"    df[(df['Trial_Number'] == 2) & (df['Is_Peak'] == True)]")
