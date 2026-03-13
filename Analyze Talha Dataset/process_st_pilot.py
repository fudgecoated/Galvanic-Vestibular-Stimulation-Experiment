import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# Configuration
input_file = 'Segment_GVS_datasets/ST_PILOT_TEST_OCULUS_CLEAN.csv'
output_dir = 'Segment_GVS_datasets/results_new'
os.makedirs(output_dir, exist_ok=True)

output_file_full = os.path.join(output_dir, 'ST_PILOT_segmented_full.csv')
output_file_reach_summary = os.path.join(output_dir, 'ST_PILOT_reach_summary.csv')
output_file_trial_summary = os.path.join(output_dir, 'ST_PILOT_trial_summary.csv')
output_html = os.path.join(output_dir, 'ST_PILOT_visualization.html')

REACH_THRESHOLD = 0.8  # HandZ must be > this value to be considered a reach
TRIAL_BREAK_DURATION = 5.0  # seconds - if HandZ < threshold for this long, it's a new trial

print(f"Loading data from {input_file}...")
# Load specific columns: HandZ and seconds
df = pd.read_csv(input_file, usecols=['HandZ', 'seconds'])

# Handle the 'seconds' column
# The first value is usually NaN, replace it with 0.0
df['seconds'] = df['seconds'].fillna(0.0)
df.rename(columns={'seconds': 'Timestamp'}, inplace=True)

# Ensure HandZ is numeric
df['HandZ'] = pd.to_numeric(df['HandZ'], errors='coerce')
df = df.dropna()

print(f"Data shape: {df.shape}")
print(f"Data range: {df['Timestamp'].min():.3f} to {df['Timestamp'].max():.3f} seconds")
print(f"Total duration: {df['Timestamp'].max():.2f} seconds ({df['Timestamp'].max()/60:.2f} minutes)")

# Calculate sampling rate
timestamps = df['Timestamp'].values
time_diffs = np.diff(timestamps)
# Filter out large gaps or zeros for mean calculation
valid_diffs = time_diffs[(time_diffs > 0) & (time_diffs < 1.0)]
mean_dt = np.mean(valid_diffs) if len(valid_diffs) > 0 else 0.01
sampling_rate = 1.0 / mean_dt

print(f"\nSampling rate analysis:")
print(f"  Mean time between samples: {mean_dt:.4f} seconds")
print(f"  Sampling rate: {sampling_rate:.2f} Hz")

# Determine cutoff frequency for Butterworth filter
nyquist = sampling_rate / 2
suggested_cutoff = min(5.0, nyquist * 0.2)

print(f"\nFilter parameters:")
print(f"  Nyquist frequency: {nyquist:.2f} Hz")
print(f"  Cutoff frequency: {suggested_cutoff:.2f} Hz")
print(f"  Filter type: Low-pass Butterworth (order 4)")

# Design and apply Butterworth low-pass filter
filter_order = 4
b, a = butter(filter_order, suggested_cutoff, fs=sampling_rate, btype='low')
handz_filtered = filtfilt(b, a, df['HandZ'].values)

df['HandZ_filtered'] = handz_filtered

print(f"\nFiltering complete.")
print(f"  HandZ range (raw): [{df['HandZ'].min():.3f}, {df['HandZ'].max():.3f}]")
print(f"  HandZ range (filtered): [{handz_filtered.min():.3f}, {handz_filtered.max():.3f}]")

# Identify regions where HandZ > threshold (potential reaches)
print(f"\nIdentifying reach regions (HandZ > {REACH_THRESHOLD})...")
above_threshold = handz_filtered > REACH_THRESHOLD
df['Above_Threshold'] = above_threshold

# Calculate how much time is spent above threshold
time_above = np.sum(above_threshold) * mean_dt
print(f"  Time with HandZ > {REACH_THRESHOLD}: {time_above:.2f}s ({100*time_above/df['Timestamp'].max():.1f}%)")

# Detect peaks ONLY in regions where HandZ > threshold
print(f"\nDetecting reach peaks (only where HandZ > {REACH_THRESHOLD})...")

# Create a masked signal for peak detection
handz_masked = handz_filtered.copy()
handz_masked[~above_threshold] = -np.inf  # Set below-threshold values very low

handz_range = np.ptp(handz_filtered[above_threshold]) if np.any(above_threshold) else 1.0
min_prominence = handz_range * 0.1  # peaks must be at least 10% of range

peaks, peak_properties = find_peaks(
    handz_masked,
    prominence=min_prominence,
    distance=int(sampling_rate * 0.3)  # minimum 0.3 seconds between peaks
)

# Filter out any peaks that aren't actually above threshold (safety check)
peaks = peaks[handz_filtered[peaks] > REACH_THRESHOLD]

print(f"  Found {len(peaks)} reach peaks")

if len(peaks) > 0:
    peak_times = timestamps[peaks]
    peak_gaps = np.diff(peak_times)
    print(f"  Peak timing statistics:")
    print(f"    Mean gap between peaks: {np.mean(peak_gaps):.3f}s")
    print(f"    Median gap: {np.median(peak_gaps):.3f}s")
    print(f"    Max gap: {np.max(peak_gaps):.3f}s")

# Detect trial breaks - find continuous periods where HandZ < threshold
print(f"\nDetecting trial breaks (HandZ < {REACH_THRESHOLD} for > {TRIAL_BREAK_DURATION}s)...")

# Find transitions
threshold_crossings = np.diff(above_threshold.astype(int))
below_starts = np.where(threshold_crossings == -1)[0] + 1  # Going below threshold
below_ends = np.where(threshold_crossings == 1)[0]  # Going above threshold

# Handle edge cases
if not above_threshold[0]:
    below_starts = np.insert(below_starts, 0, 0)
if not above_threshold[-1]:
    below_ends = np.append(below_ends, len(df) - 1)

# Calculate duration of each below-threshold period
trial_breaks = []
for start_idx, end_idx in zip(below_starts, below_ends):
    if start_idx >= len(timestamps) or end_idx >= len(timestamps):
        continue
    duration = timestamps[end_idx] - timestamps[start_idx]
    if duration > TRIAL_BREAK_DURATION:
        trial_breaks.append({
            'start_idx': start_idx,
            'end_idx': end_idx,
            'start_time': timestamps[start_idx],
            'end_time': timestamps[end_idx],
            'duration': duration
        })

print(f"  Found {len(trial_breaks)} trial breaks")
for i, tb in enumerate(trial_breaks[:10], 1):  # Show first 10
    print(f"    {i}. t={tb['start_time']:.1f}s to {tb['end_time']:.1f}s (duration: {tb['duration']:.2f}s)")

# Assign trial numbers based on breaks
trial_numbers = np.zeros(len(df), dtype=int)
current_trial = 1

if len(trial_breaks) == 0:
    # No trial breaks found - everything is one trial
    trial_numbers[:] = 1
else:
    # Assign trial 1 from start to first break
    trial_numbers[:trial_breaks[0]['start_idx']] = 1
    
    # Assign trials between breaks
    for i in range(len(trial_breaks)):
        current_trial += 1
        if i < len(trial_breaks) - 1:
            # From end of this break to start of next break
            trial_numbers[trial_breaks[i]['end_idx']:trial_breaks[i+1]['start_idx']] = current_trial
        else:
            # From end of last break to end of data
            trial_numbers[trial_breaks[i]['end_idx']:] = current_trial
    
    # Mark the break periods themselves as trial 0 (no trial)
    for tb in trial_breaks:
        trial_numbers[tb['start_idx']:tb['end_idx']] = 0

num_trials = current_trial
print(f"  Total trials detected: {num_trials}")

df['Trial_Number'] = trial_numbers

# Assign reach numbers
print(f"\nAssigning reach numbers...")

reach_number_global = np.zeros(len(df), dtype=int)
reach_number_in_trial = np.zeros(len(df), dtype=int)

# Calculate velocity for reach boundary detection
velocity = np.gradient(handz_filtered, timestamps)
velocity_abs = np.abs(velocity)
velocity_threshold = np.percentile(velocity_abs[above_threshold], 20) if np.any(above_threshold) else 0

# For each peak, define its reach segment
for reach_num, peak_idx in enumerate(peaks, start=1):
    trial_num = trial_numbers[peak_idx]
    
    if trial_num == 0:  # Skip peaks in break periods
        continue
    
    # Search backward from peak for reach boundary
    start_idx = peak_idx
    search_limit_back = max(0, peak_idx - int(sampling_rate * 3))
    for i in range(peak_idx - 1, search_limit_back, -1):
        # Stop if we exit the reach region or hit a different trial
        if not above_threshold[i] or trial_numbers[i] != trial_num:
            start_idx = i + 1
            break
        # Stop if we hit a low-velocity region
        if velocity_abs[i] < velocity_threshold and handz_filtered[i] < handz_filtered[peak_idx] * 0.5:
            start_idx = i
            break
    
    # Search forward from peak for reach boundary
    end_idx = peak_idx
    search_limit_forward = min(len(df), peak_idx + int(sampling_rate * 3))
    for i in range(peak_idx + 1, search_limit_forward):
        # Stop if we exit the reach region or hit a different trial
        if not above_threshold[i] or trial_numbers[i] != trial_num:
            end_idx = i - 1
            break
        # Stop if we hit a low-velocity region
        if velocity_abs[i] < velocity_threshold and handz_filtered[i] < handz_filtered[peak_idx] * 0.5:
            end_idx = i
            break
    
    # Assign global reach number to this segment
    reach_number_global[start_idx:end_idx+1] = reach_num

# Calculate reach number within each trial
for trial_num in range(1, num_trials + 1):
    trial_mask = trial_numbers == trial_num
    trial_reaches = reach_number_global[trial_mask]
    unique_reaches = np.unique(trial_reaches[trial_reaches > 0])
    
    for local_reach_num, global_reach_num in enumerate(unique_reaches, start=1):
        reach_mask = (trial_numbers == trial_num) & (reach_number_global == global_reach_num)
        reach_number_in_trial[reach_mask] = local_reach_num

df['Reach_Number'] = reach_number_global
df['Reach_In_Trial'] = reach_number_in_trial
df['Velocity'] = velocity
df['Is_Peak'] = False
df.loc[peaks, 'Is_Peak'] = True

# Save full data
print(f"\nSaving full data to {output_file_full}...")
df.to_csv(output_file_full, index=False)

# Generate reach summary statistics
print(f"\nGenerating reach summary statistics...")
reach_stats = []
for reach_num in range(1, np.max(reach_number_global) + 1):
    reach_data = df[df['Reach_Number'] == reach_num]
    if len(reach_data) > 0 and reach_data['Trial_Number'].iloc[0] > 0:
        trial_num = reach_data['Trial_Number'].iloc[0]
        reach_in_trial = reach_data['Reach_In_Trial'].iloc[0]
        
        stats = {
            'Reach_Number': reach_num,
            'Trial_Number': trial_num,
            'Reach_In_Trial': reach_in_trial,
            'Start_Time': reach_data['Timestamp'].iloc[0],
            'End_Time': reach_data['Timestamp'].iloc[-1],
            'Duration': reach_data['Timestamp'].iloc[-1] - reach_data['Timestamp'].iloc[0],
            'Peak_Time': reach_data[reach_data['Is_Peak']]['Timestamp'].values[0] if any(reach_data['Is_Peak']) else np.nan,
            'Peak_Value': reach_data['HandZ_filtered'].max(),
            'Min_Value': reach_data['HandZ_filtered'].min(),
            'Amplitude': reach_data['HandZ_filtered'].max() - reach_data['HandZ_filtered'].min(),
            'Mean_Velocity': reach_data['Velocity'].abs().mean(),
            'Max_Velocity': reach_data['Velocity'].abs().max(),
            'Sample_Count': len(reach_data)
        }
        reach_stats.append(stats)

reach_summary = pd.DataFrame(reach_stats)
reach_summary.to_csv(output_file_reach_summary, index=False)

print(f"\nReach Summary Statistics (first 10 reaches):")
print(reach_summary.head(10))

# Generate trial summary statistics
print(f"\nGenerating trial summary statistics...")
trial_stats = []
for trial_num in range(1, num_trials + 1):
    trial_data = df[df['Trial_Number'] == trial_num]
    trial_reaches = reach_summary[reach_summary['Trial_Number'] == trial_num]
    
    if len(trial_data) == 0:
        continue

    stats = {
        'Trial_Number': trial_num,
        'Start_Time': trial_data['Timestamp'].iloc[0],
        'End_Time': trial_data['Timestamp'].iloc[-1],
        'Duration': trial_data['Timestamp'].iloc[-1] - trial_data['Timestamp'].iloc[0],
        'Num_Reaches': len(trial_reaches),
        'Mean_Reach_Duration': trial_reaches['Duration'].mean() if len(trial_reaches) > 0 else np.nan,
        'Mean_Amplitude': trial_reaches['Amplitude'].mean() if len(trial_reaches) > 0 else np.nan,
        'Mean_Peak_Value': trial_reaches['Peak_Value'].mean() if len(trial_reaches) > 0 else np.nan,
        'Sample_Count': len(trial_data)
    }
    trial_stats.append(stats)

trial_summary = pd.DataFrame(trial_stats)
trial_summary.to_csv(output_file_trial_summary, index=False)

print(f"\nTrial Summary Statistics:")
print(trial_summary)

# Create interactive Plotly visualization
print("\nGenerating interactive visualization...")

fig = make_subplots(
    rows=4, cols=1,
    subplot_titles=(
        'HandZ Position Over Time (Filtered)',
        'Reach Detection (HandZ > 0.8 threshold)',
        'Trial Segmentation',
        'First Trial Detail'
    ),
    vertical_spacing=0.08,
    row_heights=[0.3, 0.2, 0.2, 0.3]
)

# Plot 1: Full time series with peaks
fig.add_trace(
    go.Scatter(x=df['Timestamp'], y=df['HandZ_filtered'],
               mode='lines', name='HandZ (filtered)',
               line=dict(color='blue', width=1),
               hovertemplate='Time: %{x:.2f}s<br>HandZ: %{y:.3f}<extra></extra>'),
    row=1, col=1
)

# Add threshold line
fig.add_hline(y=REACH_THRESHOLD, line_dash="dash", line_color="red",
              annotation_text=f"Threshold = {REACH_THRESHOLD}",
              row=1, col=1)

# Add peaks
peak_data = df[df['Is_Peak']]
fig.add_trace(
    go.Scatter(x=peak_data['Timestamp'], y=peak_data['HandZ_filtered'],
               mode='markers', name='Reach Peaks',
               marker=dict(color='red', size=6, symbol='star'),
               hovertemplate='Peak at %{x:.2f}s<br>Value: %{y:.3f}<extra></extra>'),
    row=1, col=1
)

# Plot 2: Above/below threshold
fig.add_trace(
    go.Scatter(x=df['Timestamp'], y=df['Above_Threshold'].astype(int),
               mode='lines', name='Above Threshold',
               line=dict(color='green', width=1),
               fill='tozeroy',
               hovertemplate='Time: %{x:.2f}s<extra></extra>'),
    row=2, col=1
)

# Plot 3: Trial numbers
fig.add_trace(
    go.Scatter(x=df['Timestamp'], y=df['Trial_Number'],
               mode='lines', name='Trial Number',
               line=dict(color='purple', width=2),
               hovertemplate='Time: %{x:.2f}s<br>Trial: %{y}<extra></extra>'),
    row=3, col=1
)

# Plot 4: First trial detail
if num_trials > 0:
    trial_1_data = df[df['Trial_Number'] == 1]
    fig.add_trace(
        go.Scatter(x=trial_1_data['Timestamp'], y=trial_1_data['HandZ_filtered'],
                   mode='lines', name='Trial 1 - HandZ',
                   line=dict(color='blue', width=1.5),
                   hovertemplate='Time: %{x:.2f}s<br>HandZ: %{y:.3f}<extra></extra>'),
        row=4, col=1
    )
    
    trial_1_peaks = trial_1_data[trial_1_data['Is_Peak']]
    fig.add_trace(
        go.Scatter(x=trial_1_peaks['Timestamp'], y=trial_1_peaks['HandZ_filtered'],
                   mode='markers', name='Trial 1 - Peaks',
                   marker=dict(color='red', size=8, symbol='star'),
                   hovertemplate='Peak %{pointNumber}<br>Time: %{x:.2f}s<br>Value: %{y:.3f}<extra></extra>'),
        row=4, col=1
    )
    
    fig.add_hline(y=REACH_THRESHOLD, line_dash="dash", line_color="red", row=4, col=1)

# Update axes
fig.update_xaxes(title_text="Time (seconds)", row=4, col=1)
fig.update_yaxes(title_text="HandZ", row=1, col=1)
fig.update_yaxes(title_text="0=Below, 1=Above", row=2, col=1)
fig.update_yaxes(title_text="Trial Number", row=3, col=1)
fig.update_yaxes(title_text="HandZ", row=4, col=1)

fig.update_layout(
    height=1400,
    title_text="Hand Reach Analysis - ST_PILOT",
    showlegend=True,
    hovermode='closest'
)

fig.write_html(output_html)
print(f"Saved interactive plot to: {output_html}")

print("\n" + "="*60)
print("=== PROCESSING COMPLETE ===")
print("="*60)
print(f"\nTotal reaches detected: {len(reach_summary)}")
print(f"Total trials detected: {num_trials}")
if num_trials > 0:
    print(f"Average reaches per trial: {len(reach_summary)/num_trials:.1f}")
