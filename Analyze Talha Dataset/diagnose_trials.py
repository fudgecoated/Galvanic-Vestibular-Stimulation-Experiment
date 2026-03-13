import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Load data
print("Loading data...")
df = pd.read_csv('TA_OCULUS_PILOT_JUL4_2_OCULUS_interpolated.csv', usecols=['Timestamp', 'HandZ'])

# Convert Timestamp from datetime string to elapsed seconds
df['Timestamp'] = pd.to_datetime(df['Timestamp'])
df['Timestamp'] = (df['Timestamp'] - df['Timestamp'].iloc[0]).dt.total_seconds()

# Ensure HandZ is numeric
df['HandZ'] = pd.to_numeric(df['HandZ'], errors='coerce')
df = df.dropna()

print(f"Data shape: {df.shape}")
print(f"Duration: {df['Timestamp'].max():.2f} seconds ({df['Timestamp'].max()/60:.2f} minutes)")

# Analyze time gaps
timestamps = df['Timestamp'].values
time_diffs = np.diff(timestamps)

print(f"\nTime gap statistics:")
print(f"  Mean gap: {np.mean(time_diffs):.4f} seconds")
print(f"  Median gap: {np.median(time_diffs):.4f} seconds")
print(f"  Min gap: {np.min(time_diffs):.4f} seconds")
print(f"  Max gap: {np.max(time_diffs):.4f} seconds")
print(f"  Std dev: {np.std(time_diffs):.4f} seconds")

# Find all gaps of different thresholds
thresholds = [1.0, 5.0, 10.0, 15.0, 20.0, 30.0]
print(f"\nGap analysis at different thresholds:")
for threshold in thresholds:
    gaps = np.where(time_diffs > threshold)[0]
    print(f"  Gaps > {threshold:4.1f}s: {len(gaps):3d} gaps")
    if len(gaps) > 0 and len(gaps) <= 10:
        for idx in gaps:
            print(f"    - Gap at t={timestamps[idx]:.2f}s, duration={time_diffs[idx]:.2f}s")

# Find the largest gaps
print(f"\n10 Largest time gaps:")
largest_gap_indices = np.argsort(time_diffs)[-10:][::-1]
for i, idx in enumerate(largest_gap_indices, 1):
    print(f"  {i:2d}. Gap at t={timestamps[idx]:8.2f}s, duration={time_diffs[idx]:6.2f}s")

# Create interactive visualization using Plotly
print("\nCreating interactive visualization...")

# Create subplots
fig = make_subplots(
    rows=3, cols=1,
    subplot_titles=('HandZ Position Over Time', 
                    'Time Gaps Between Samples (log scale)',
                    'Zoomed: First 120 seconds'),
    vertical_spacing=0.12,
    row_heights=[0.4, 0.3, 0.3]
)

# Plot 1: Full HandZ time series
fig.add_trace(
    go.Scatter(
        x=df['Timestamp'], 
        y=df['HandZ'],
        mode='lines',
        name='HandZ',
        line=dict(color='blue', width=1),
        hovertemplate='Time: %{x:.2f}s<br>HandZ: %{y:.4f}<extra></extra>'
    ),
    row=1, col=1
)

# Plot 2: Time gaps (log scale to see structure)
# Add small offset to avoid log(0)
time_diffs_plot = time_diffs + 1e-6
fig.add_trace(
    go.Scatter(
        x=timestamps[:-1],
        y=time_diffs_plot,
        mode='markers',
        name='Time Gaps',
        marker=dict(
            color=time_diffs_plot,
            colorscale='Viridis',
            size=4,
            colorbar=dict(title="Gap (s)", y=0.35, len=0.25)
        ),
        hovertemplate='Time: %{x:.2f}s<br>Gap: %{y:.4f}s<extra></extra>'
    ),
    row=2, col=1
)

# Add threshold line at 15 seconds
fig.add_hline(y=15.0, line_dash="dash", line_color="red", 
              annotation_text="15s threshold", row=2, col=1)

# Plot 3: Zoomed view of first 120 seconds
zoom_mask = df['Timestamp'] <= 120
zoom_data = df[zoom_mask]
fig.add_trace(
    go.Scatter(
        x=zoom_data['Timestamp'], 
        y=zoom_data['HandZ'],
        mode='lines',
        name='HandZ (zoomed)',
        line=dict(color='green', width=1),
        hovertemplate='Time: %{x:.2f}s<br>HandZ: %{y:.4f}<extra></extra>'
    ),
    row=3, col=1
)

# Update axes
fig.update_xaxes(title_text="Time (seconds)", row=1, col=1)
fig.update_xaxes(title_text="Time (seconds)", row=2, col=1)
fig.update_xaxes(title_text="Time (seconds)", row=3, col=1)

fig.update_yaxes(title_text="HandZ Position", row=1, col=1)
fig.update_yaxes(title_text="Gap Duration (s)", type="log", row=2, col=1)
fig.update_yaxes(title_text="HandZ Position", row=3, col=1)

# Update layout
fig.update_layout(
    height=1200,
    title_text="Trial Detection Diagnostics - Interactive",
    showlegend=True,
    hovermode='closest'
)

# Save interactive HTML
output_file = 'trial_diagnostics_interactive.html'
fig.write_html(output_file)
print(f"\nSaved interactive plot to: {output_file}")
print("Open this file in your web browser to interact with the data!")

# Suggest optimal threshold
print("\n" + "="*60)
print("RECOMMENDATIONS:")
print("="*60)

# Look for a natural gap in the distribution
gaps_sorted = np.sort(time_diffs)
# Find the largest jump in gap sizes (potential natural threshold)
gap_increases = np.diff(gaps_sorted)
large_jump_idx = np.argmax(gap_increases)
suggested_threshold = (gaps_sorted[large_jump_idx] + gaps_sorted[large_jump_idx + 1]) / 2

print(f"\nBased on the gap distribution:")
print(f"  - Suggested threshold: {suggested_threshold:.2f} seconds")
print(f"  - This would detect {np.sum(time_diffs > suggested_threshold)} trials")

# Check if interpolation might have removed the breaks
if np.max(time_diffs) < 15.0:
    print(f"\n⚠️  WARNING: Maximum gap ({np.max(time_diffs):.2f}s) is less than 15s threshold!")
    print(f"  The 'interpolated' file may have filled in the trial breaks.")
    print(f"  Try using the NON-interpolated file: TA_OCULUS_PILOT_JUL4_2_OCULUS.csv")
