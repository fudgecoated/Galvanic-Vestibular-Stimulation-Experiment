#!/usr/bin/env python3
"""
visualize_st_pilot.py

Simple visualization script for ST_PILOT data to inspect HandZ over time
and identify natural trial/reach structure.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Load ST_PILOT data
input_file = 'ST_PILOT_TEST_OCULUS_CLEAN.csv'
df = pd.read_csv(input_file)

# Drop NaN in seconds column and reset
df = df.dropna(subset=['seconds']).reset_index(drop=True)

# Extract time and HandZ
time = df['seconds'].values
handz = df['HandZ'].values

# Compute some basic stats
print("="*70)
print("ST_PILOT DATA OVERVIEW")
print("="*70)
print(f"Total samples: {len(df)}")
print(f"Duration: {time[-1]:.1f} seconds ({time[-1]/60:.1f} minutes)")
print(f"Sampling rate (approx): {1.0/np.mean(np.diff(time)):.1f} Hz")
print(f"\nHandZ statistics:")
print(f"  Min: {handz.min():.3f}")
print(f"  Max: {handz.max():.3f}")
print(f"  Mean: {handz.mean():.3f}")
print(f"  Median: {np.median(handz):.3f}")
print(f"  25th percentile: {np.percentile(handz, 25):.3f}")
print(f"  75th percentile: {np.percentile(handz, 75):.3f}")
print(f"  90th percentile: {np.percentile(handz, 90):.3f}")
print(f"  95th percentile: {np.percentile(handz, 95):.3f}")

# Count how many samples are above various thresholds
print(f"\nSamples above thresholds:")
for thresh in [0.5, 0.7, 0.8, 0.9, 1.0, 1.1]:
    count = (handz > thresh).sum()
    pct = 100 * count / len(handz)
    print(f"  > {thresh}: {count} ({pct:.1f}%)")

# Create visualization
fig = make_subplots(
    rows=3, cols=1,
    subplot_titles=(
        'HandZ Position Over Time',
        'HandZ Distribution (Histogram)',
        'HandZ Velocity Over Time'
    ),
    vertical_spacing=0.12,
    row_heights=[0.5, 0.25, 0.25]
)

# Plot 1: HandZ over time
fig.add_trace(
    go.Scatter(
        x=time,
        y=handz,
        mode='lines',
        name='HandZ',
        line=dict(color='blue', width=1),
        hovertemplate='Time: %{x:.2f}s<br>HandZ: %{y:.3f}<extra></extra>'
    ),
    row=1, col=1
)

# Add horizontal reference lines for common thresholds
for thresh, color, label in [
    (0.8, 'orange', '0.8'),
    (0.9, 'red', '0.9'),
    (0.93, 'darkred', '0.93 (current)')
]:
    fig.add_hline(
        y=thresh,
        line_dash='dash',
        line_color=color,
        annotation_text=label,
        row=1, col=1
    )

# Plot 2: Histogram of HandZ values
fig.add_trace(
    go.Histogram(
        x=handz,
        nbinsx=100,
        name='HandZ Distribution',
        marker=dict(color='green'),
        hovertemplate='HandZ: %{x:.3f}<br>Count: %{y}<extra></extra>'
    ),
    row=2, col=1
)

# Plot 3: Velocity (gradient of HandZ)
velocity = np.gradient(handz, time)
fig.add_trace(
    go.Scatter(
        x=time,
        y=np.abs(velocity),
        mode='lines',
        name='|Velocity|',
        line=dict(color='purple', width=1),
        hovertemplate='Time: %{x:.2f}s<br>|Velocity|: %{y:.4f}<extra></extra>'
    ),
    row=3, col=1
)

# Add threshold for "movement" vs "stopped"
velocity_threshold = np.percentile(np.abs(velocity), 30)
fig.add_hline(
    y=velocity_threshold,
    line_dash='dash',
    line_color='red',
    annotation_text=f'30th percentile = {velocity_threshold:.4f}',
    row=3, col=1
)

# Update axes labels
fig.update_xaxes(title_text='Time (seconds)', row=1, col=1)
fig.update_xaxes(title_text='HandZ Value', row=2, col=1)
fig.update_xaxes(title_text='Time (seconds)', row=3, col=1)

fig.update_yaxes(title_text='HandZ Position', row=1, col=1)
fig.update_yaxes(title_text='Count', row=2, col=1)
fig.update_yaxes(title_text='|Velocity|', row=3, col=1)

# Update layout
fig.update_layout(
    height=1200,
    title_text='ST_PILOT HandZ Analysis - Raw Data Exploration',
    hovermode='closest',
    showlegend=True
)

# Save to HTML
output_file = 'ST_PILOT_exploration.html'
fig.write_html(output_file)

print(f"\n{'='*70}")
print(f"Visualization saved to: {output_file}")
print(f"Open this file in your browser to explore the data interactively.")
print(f"{'='*70}")

# Find periods of high activity (HandZ > 0.8)
active_mask = handz > 0.8
active_periods = []
in_active = False
start_idx = 0

for i in range(len(active_mask)):
    if active_mask[i] and not in_active:
        # Start of active period
        start_idx = i
        in_active = True
    elif not active_mask[i] and in_active:
        # End of active period
        active_periods.append((time[start_idx], time[i-1], time[i-1] - time[start_idx]))
        in_active = False

# Handle case where data ends during active period
if in_active:
    active_periods.append((time[start_idx], time[-1], time[-1] - time[start_idx]))

print(f"\nFound {len(active_periods)} periods with HandZ > 0.8:")
print(f"{'Period':<8} {'Start (s)':<12} {'End (s)':<12} {'Duration (s)':<15}")
print("-" * 50)
for i, (start, end, duration) in enumerate(active_periods[:20], 1):  # Show first 20
    print(f"{i:<8} {start:<12.2f} {end:<12.2f} {duration:<15.2f}")

if len(active_periods) > 20:
    print(f"... and {len(active_periods) - 20} more periods")

print("\n" + "="*70)
