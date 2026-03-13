import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ============================================================================
# CONFIGURATION
# ============================================================================
INPUT_FILE = 'TA_OCULUS_PILOT_JUL4_2_OCULUS_interpolated.csv'
UNFILTERED_FILE = 'TA_OCULUS_PILOT_JUL4_2_OCULUS_interpolated_filtered.csv'
OUTPUT_FILE_FULL = 'hand_reaches_segmented.csv'
OUTPUT_FILE_REACH_SUMMARY = 'reach_summary.csv'
OUTPUT_FILE_TRIAL_SUMMARY = 'trial_summary.csv'
OUTPUT_HTML = 'reach_visualization_comparison.html'

# Analysis parameters
REACH_THRESHOLD = 0.93  # Only consider peaks above this HandZ value
TRIAL_BREAK_THRESHOLD = 10.0  # Gap > 15s between peaks indicates new trial
VELOCITY_THRESHOLD_PERCENTILE = 15  # Bottom 30% of velocities = "stopped"
LOW_POSITION_PERCENTILE = 20  # Bottom 20% above minimum = "at rest position"
DISTANCE_THRESHOLD_PERCENT = 10  # Start/end reach when X% of amplitude away from trough

# Filter parameters
FILTER_ORDER = 4
FILTER_CUTOFF_HZ = 12.0  # Low-pass cutoff frequency

print("="*70)
print("HAND REACH ANALYSIS (WITH RAW DATA OVERLAY)")
print("="*70)

# ============================================================================
# STEP 1: LOAD AND PREPARE DATA
# ============================================================================
print("\n[1/7] Loading data...")
df = pd.read_csv(INPUT_FILE, usecols=['Timestamp', 'HandZ'])
df_unfiltered = pd.read_csv(UNFILTERED_FILE, usecols=['Timestamp', 'HandZ'])

# Convert timestamp to elapsed seconds
df['Timestamp'] = pd.to_datetime(df['Timestamp'])
df['Timestamp'] = (df['Timestamp'] - df['Timestamp'].iloc[0]).dt.total_seconds()

df_unfiltered['Timestamp'] = pd.to_datetime(df_unfiltered['Timestamp'])
df_unfiltered['Timestamp'] = (df_unfiltered['Timestamp'] - df_unfiltered['Timestamp'].iloc[0]).dt.total_seconds()

# Ensure HandZ is numeric
df['HandZ'] = pd.to_numeric(df['HandZ'], errors='coerce')
df = df.dropna()

df_unfiltered['HandZ'] = pd.to_numeric(df_unfiltered['HandZ'], errors='coerce')
df_unfiltered = df_unfiltered.dropna()

print(f"   Loaded {len(df)} samples from interpolated file")
print(f"   Loaded {len(df_unfiltered)} samples from unfiltered file")
print(f"   Duration: {df['Timestamp'].max():.1f} seconds ({df['Timestamp'].max()/60:.1f} minutes)")

# Calculate sampling rate
timestamps = df['Timestamp'].values
dt = np.mean(np.diff(timestamps))
sampling_rate = 1.0 / dt
print(f"   Sampling rate: {sampling_rate:.1f} Hz")

# ============================================================================
# STEP 2: APPLY BUTTERWORTH FILTER
# ============================================================================
print(f"\n[2/7] Applying Butterworth low-pass filter (cutoff={FILTER_CUTOFF_HZ}Hz)...")

# Design filter
nyquist = sampling_rate / 2
cutoff_normalized = min(FILTER_CUTOFF_HZ, nyquist * 0.9) / nyquist
b, a = butter(FILTER_ORDER, cutoff_normalized, btype='low')

# Apply filter (filtfilt = zero-phase, forward-backward filtering)
handz_filtered = filtfilt(b, a, df['HandZ'].values)
df['HandZ_filtered'] = handz_filtered

print(f"   Raw HandZ range: [{df['HandZ'].min():.3f}, {df['HandZ'].max():.3f}]")
print(f"   Filtered HandZ range: [{handz_filtered.min():.3f}, {handz_filtered.max():.3f}]")

# ============================================================================
# STEP 3: CALCULATE VELOCITY
# ============================================================================
print(f"\n[3/7] Calculating velocity...")

velocity = np.gradient(handz_filtered, timestamps)
velocity_abs = np.abs(velocity)
df['Velocity'] = velocity

# Determine velocity threshold (what counts as "stopped")
velocity_threshold = np.percentile(velocity_abs, VELOCITY_THRESHOLD_PERCENTILE)
print(f"   Velocity threshold (stopped): {velocity_threshold:.4f} (bottom {VELOCITY_THRESHOLD_PERCENTILE}%)")
print(f"   Max velocity: {velocity_abs.max():.4f}")

# ============================================================================
# STEP 4: DETECT REACH PEAKS
# ============================================================================
print(f"\n[4/7] Detecting reach peaks (HandZ > {REACH_THRESHOLD})...")

# Find all peaks
handz_range = np.ptp(handz_filtered)
min_prominence = handz_range * 0.05  # Peaks must be at least 5% of range

all_peaks, _ = find_peaks(
    handz_filtered,
    prominence=min_prominence,
    distance=int(sampling_rate * 0.2)  # At least 0.2s between peaks
)

# Filter to only keep peaks above threshold
valid_peaks = all_peaks[handz_filtered[all_peaks] > REACH_THRESHOLD]

print(f"   Found {len(all_peaks)} total peaks")
print(f"   Filtered to {len(valid_peaks)} peaks above {REACH_THRESHOLD}")

if len(valid_peaks) == 0:
    print("\n⚠️ ERROR: No peaks found above threshold!")
    print("   Try lowering REACH_THRESHOLD or check your data.")
    exit(1)

# Mark peaks in dataframe
df['Is_Peak'] = False
df.loc[valid_peaks, 'Is_Peak'] = True

# ============================================================================
# STEP 5: DETECT TRIALS (based on gaps between peaks)
# ============================================================================
print(f"\n[5/7] Detecting trials (gaps > {TRIAL_BREAK_THRESHOLD}s between peaks)...")

peak_times = timestamps[valid_peaks]
peak_gaps = np.diff(peak_times)

# Find trial breaks
trial_break_indices = np.where(peak_gaps > TRIAL_BREAK_THRESHOLD)[0]
num_trials = len(trial_break_indices) + 1

print(f"   Found {len(trial_break_indices)} trial breaks")
print(f"   Total trials: {num_trials}")

if len(trial_break_indices) > 0:
    print(f"   Trial break locations:")
    for i, idx in enumerate(trial_break_indices):
        print(f"      Break {i+1}: between peak {idx} and {idx+1} (gap = {peak_gaps[idx]:.1f}s)")

# Assign trial numbers to peaks
peak_trial_numbers = np.ones(len(valid_peaks), dtype=int)
current_trial = 1
for break_idx in trial_break_indices:
    current_trial += 1
    peak_trial_numbers[break_idx + 1:] = current_trial

# ============================================================================
# STEP 6: SEGMENT REACHES (velocity-based boundaries)
# ============================================================================
print(f"\n[6/7] Segmenting individual reaches (velocity-based, Option 1)...")

reach_number = 0
df['Reach_Number'] = 0
df['Trial_Number'] = 0
df['Reach_In_Trial'] = 0

reach_info = []

for peak_idx_in_array, peak_sample_idx in enumerate(valid_peaks):
    reach_number += 1
    trial_num = peak_trial_numbers[peak_idx_in_array]
    
    # --- Find reach START (distance threshold from trough) ---
    start_idx = peak_sample_idx
    
    # Find the local minimum (trough) before the peak
    search_window_back = range(peak_sample_idx - 1, max(0, peak_sample_idx - int(sampling_rate * 5)), -1)
    trough_idx_before = peak_sample_idx
    min_handz_before_peak = handz_filtered[peak_sample_idx]
    
    for i in search_window_back:
        if handz_filtered[i] < min_handz_before_peak:
            min_handz_before_peak = handz_filtered[i]
            trough_idx_before = i
    
    # Calculate reach amplitude
    reach_amplitude = handz_filtered[peak_sample_idx] - min_handz_before_peak
    distance_threshold = reach_amplitude * (DISTANCE_THRESHOLD_PERCENT / 100.0)
    
    # Search forward from trough: start when hand has moved distance_threshold away from minimum
    for i in range(trough_idx_before, peak_sample_idx):
        if handz_filtered[i] - min_handz_before_peak >= distance_threshold:
            start_idx = i
            break
    
    # --- Find reach END (distance threshold from trough) ---
    end_idx = peak_sample_idx
    
    # Find the local minimum (trough) after the peak
    search_window_forward = range(peak_sample_idx + 1, min(len(df), peak_sample_idx + int(sampling_rate * 5)))
    trough_idx_after = peak_sample_idx
    min_handz_after_peak = handz_filtered[peak_sample_idx]
    
    for i in search_window_forward:
        if handz_filtered[i] < min_handz_after_peak:
            min_handz_after_peak = handz_filtered[i]
            trough_idx_after = i
    
    # Calculate reach amplitude for return
    reach_amplitude_after = handz_filtered[peak_sample_idx] - min_handz_after_peak
    distance_threshold_after = reach_amplitude_after * (DISTANCE_THRESHOLD_PERCENT / 100.0)
    
    # Search forward from peak: end when hand returns to within distance_threshold of minimum
    for i in search_window_forward:
        if handz_filtered[i] - min_handz_after_peak <= distance_threshold_after:
            end_idx = i
            break
    
    # Assign reach and trial numbers to this segment
    df.loc[start_idx:end_idx, 'Reach_Number'] = reach_number
    df.loc[start_idx:end_idx, 'Trial_Number'] = trial_num
    
    # Store reach info for summary
    reach_info.append({
        'reach_number': reach_number,
        'trial_number': trial_num,
        'start_idx': start_idx,
        'end_idx': end_idx,
        'peak_idx': peak_sample_idx
    })

# Assign reach-in-trial numbers
for trial_num in range(1, num_trials + 1):
    trial_reaches = [r for r in reach_info if r['trial_number'] == trial_num]
    for local_num, reach in enumerate(trial_reaches, start=1):
        mask = df['Reach_Number'] == reach['reach_number']
        df.loc[mask, 'Reach_In_Trial'] = local_num

print(f"   Segmented {reach_number} reaches")

# ============================================================================
# STEP 7: GENERATE OUTPUTS
# ============================================================================
print(f"\n[7/7] Generating outputs...")

# --- Save full CSV ---
print(f"   Saving {OUTPUT_FILE_FULL}...")
df.to_csv(OUTPUT_FILE_FULL, index=False)

# --- Generate reach summary ---
reach_stats = []
for reach in reach_info:
    reach_data = df[df['Reach_Number'] == reach['reach_number']]
    
    # Skip if no data for this reach (shouldn't happen, but safety check)
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
reach_summary.to_csv(OUTPUT_FILE_REACH_SUMMARY, index=False)
print(f"   Saved {OUTPUT_FILE_REACH_SUMMARY}")

# --- Generate trial summary ---
trial_stats = []
for trial_num in range(1, num_trials + 1):
    trial_reaches = reach_summary[reach_summary['Trial_Number'] == trial_num]
    trial_data = df[df['Trial_Number'] == trial_num]
    
    stats = {
        'Trial_Number': trial_num,
        'Num_Reaches': len(trial_reaches),
        'Start_Time': trial_data['Timestamp'].iloc[0] if len(trial_data) > 0 else np.nan,
        'End_Time': trial_data['Timestamp'].iloc[-1] if len(trial_data) > 0 else np.nan,
        'Duration': trial_data['Timestamp'].iloc[-1] - trial_data['Timestamp'].iloc[0] if len(trial_data) > 0 else np.nan,
        'Mean_Reach_Duration': trial_reaches['Duration'].mean(),
        'Mean_Peak_Value': trial_reaches['Peak_Value'].mean(),
        'Mean_Amplitude': trial_reaches['Amplitude'].mean(),
    }
    trial_stats.append(stats)

trial_summary = pd.DataFrame(trial_stats)
trial_summary.to_csv(OUTPUT_FILE_TRIAL_SUMMARY, index=False)
print(f"   Saved {OUTPUT_FILE_TRIAL_SUMMARY}")

# --- Create interactive visualization WITH RAW DATA OVERLAY ---
print(f"   Creating interactive visualization with raw data overlay...")

fig = make_subplots(
    rows=3, cols=1,
    subplot_titles=(
        'HandZ Position - Raw (gray) vs Filtered (colored) - Colored by Trial',
        'Reach Segmentation by Trial',
        'Velocity Profile'
    ),
    vertical_spacing=0.1,
    row_heights=[0.5, 0.25, 0.25]
)

# Define colors for trials
colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']

# Plot 1a: UNFILTERED DATA (bright orange) - plot first so it's in background
fig.add_trace(
    go.Scatter(
        x=df_unfiltered['Timestamp'],
        y=df_unfiltered['HandZ'],
        mode='lines',
        name='Unfiltered Data',
        line=dict(color='orange', width=2),
        opacity=0.7,
        hovertemplate='Time: %{x:.2f}s<br>HandZ (unfiltered): %{y:.3f}<extra></extra>'
    ),
    row=1, col=1
)

# Plot 1b: FILTERED DATA colored by trial - plot on top
for trial_num in range(1, num_trials + 1):
    trial_data = df[df['Trial_Number'] == trial_num]
    color = colors[(trial_num - 1) % len(colors)]
    
    fig.add_trace(
        go.Scatter(
            x=trial_data['Timestamp'],
            y=trial_data['HandZ_filtered'],
            mode='lines',
            name=f'Trial {trial_num} (filtered)',
            line=dict(color=color, width=2),
            hovertemplate='Time: %{x:.2f}s<br>HandZ (filtered): %{y:.3f}<extra></extra>'
        ),
        row=1, col=1
    )

# Add peaks
peak_data = df[df['Is_Peak']]
fig.add_trace(
    go.Scatter(
        x=peak_data['Timestamp'],
        y=peak_data['HandZ_filtered'],
        mode='markers',
        name='Peaks',
        marker=dict(color='black', size=8, symbol='star'),
        hovertemplate='Peak<br>Time: %{x:.2f}s<br>Value: %{y:.3f}<extra></extra>'
    ),
    row=1, col=1
)

# Add reach start and end markers
reach_starts_times = []
reach_starts_values = []
reach_ends_times = []
reach_ends_values = []

for reach in reach_info:
    reach_starts_times.append(timestamps[reach['start_idx']])
    reach_starts_values.append(handz_filtered[reach['start_idx']])
    reach_ends_times.append(timestamps[reach['end_idx']])
    reach_ends_values.append(handz_filtered[reach['end_idx']])

fig.add_trace(
    go.Scatter(
        x=reach_starts_times,
        y=reach_starts_values,
        mode='markers',
        name='Reach Start',
        marker=dict(color='green', size=6, symbol='triangle-up'),
        hovertemplate='Reach Start<br>Time: %{x:.2f}s<br>Value: %{y:.3f}<extra></extra>'
    ),
    row=1, col=1
)

fig.add_trace(
    go.Scatter(
        x=reach_ends_times,
        y=reach_ends_values,
        mode='markers',
        name='Reach End',
        marker=dict(color='red', size=6, symbol='triangle-down'),
        hovertemplate='Reach End<br>Time: %{x:.2f}s<br>Value: %{y:.3f}<extra></extra>'
    ),
    row=1, col=1
)

# Add threshold line
fig.add_hline(y=REACH_THRESHOLD, line_dash="dash", line_color="red",
              annotation_text=f"Threshold = {REACH_THRESHOLD}", row=1, col=1)

# Plot 2: Reach numbers
for trial_num in range(1, num_trials + 1):
    trial_data = df[df['Trial_Number'] == trial_num]
    color = colors[(trial_num - 1) % len(colors)]
    
    fig.add_trace(
        go.Scatter(
            x=trial_data['Timestamp'],
            y=trial_data['Reach_In_Trial'],
            mode='lines',
            name=f'Trial {trial_num} Reaches',
            line=dict(color=color, width=2),
            showlegend=False,
            hovertemplate='Trial %{text}<br>Reach: %{y}<extra></extra>',
            text=[trial_num] * len(trial_data)
        ),
        row=2, col=1
    )

# Plot 3: Velocity
fig.add_trace(
    go.Scatter(
        x=df['Timestamp'],
        y=df['Velocity'].abs(),
        mode='lines',
        name='|Velocity|',
        line=dict(color='purple', width=1),
        hovertemplate='Time: %{x:.2f}s<br>|Velocity|: %{y:.4f}<extra></extra>'
    ),
    row=3, col=1
)

fig.add_hline(y=velocity_threshold, line_dash="dash", line_color="red",
              annotation_text=f"Threshold = {velocity_threshold:.4f}", row=3, col=1)

# Update layout
fig.update_xaxes(title_text="Time (seconds)", row=3, col=1)
fig.update_yaxes(title_text="HandZ Position", row=1, col=1)
fig.update_yaxes(title_text="Reach Number", row=2, col=1)
fig.update_yaxes(title_text="|Velocity|", row=3, col=1)

fig.update_layout(
    height=1200,
    title_text="Comparison: Unfiltered (orange) vs Our Butterworth Filter (colored)",
    hovermode='closest'
)

fig.write_html(OUTPUT_HTML)
print(f"   Saved {OUTPUT_HTML}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*70)
print("ANALYSIS COMPLETE")
print("="*70)
print(f"\nDetected {len(reach_summary)} reaches across {num_trials} trials")
print(f"\nTrial Summary:")
print(trial_summary.to_string(index=False))

print(f"\n⚠️  Trials with unexpected reach counts:")
for _, trial in trial_summary.iterrows():
    if trial['Num_Reaches'] != 20:
        print(f"   Trial {trial['Trial_Number']}: {trial['Num_Reaches']} reaches (expected ~20)")

print(f"\n📁 Output files:")
print(f"   • {OUTPUT_FILE_FULL}")
print(f"   • {OUTPUT_FILE_REACH_SUMMARY}")
print(f"   • {OUTPUT_FILE_TRIAL_SUMMARY}")
print(f"   • {OUTPUT_HTML} ← Open this in your browser!")
print(f"\n💡 Orange line = Unfiltered interpolated data")
print(f"💡 Colored lines = Our Butterworth filtered data by trial")
print("="*70)
