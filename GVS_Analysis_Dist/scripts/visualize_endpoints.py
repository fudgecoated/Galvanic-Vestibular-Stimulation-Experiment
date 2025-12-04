import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import argparse
import os
import numpy as np
import math

def load_data(base_path):
    segments_file = f"{base_path}_reach_summary.csv"
    data_file = f"{base_path}_scientific_segmented.csv"
    
    if not os.path.exists(segments_file) or not os.path.exists(data_file):
        print(f"Error: Could not find input files for {base_path}")
        return None, None

    print(f"Loading {data_file}...")
    df = pd.read_csv(data_file)
    print(f"Loading {segments_file}...")
    reaches = pd.read_csv(segments_file)
    
    return df, reaches

def calculate_endpoints(df, reaches, z_threshold):
    print(f"Calculating endpoints at Z = {z_threshold}...")
    endpoints = []
    
    for _, reach in reaches.iterrows():
        reach_num = int(reach['Reach_Number'])
        trial_num = int(reach['Trial_Number'])
        reach_in_trial = int(reach['Reach_In_Trial'])
        
        # Get data for this reach
        # We only want the OUTWARD phase: Start to Peak
        start_time = reach['Start_Time']
        peak_time = reach['Peak_Time']
        
        # Filter dataframe for this reach's outward phase
        reach_data = df[(df['seconds'] >= start_time) & (df['seconds'] <= peak_time)].copy()
        
        if reach_data.empty:
            continue
            
        # Check if peak reached the threshold
        if reach_data['HandZ_filtered'].max() < z_threshold:
            # print(f"Reach {reach_num} (Trial {trial_num}) did not reach Z={z_threshold}")
            continue
            
        # Find crossing point
        # We want the first point where HandZ >= threshold
        crossing_indices = reach_data.index[reach_data['HandZ_filtered'] >= z_threshold]
        
        if len(crossing_indices) == 0:
            continue
            
        idx_after = crossing_indices[0]
        
        # If it's the very first point, we can't interpolate with previous
        if idx_after == reach_data.index[0]:
            x = reach_data.loc[idx_after, 'HandX']
            y = reach_data.loc[idx_after, 'HandY']
            time = reach_data.loc[idx_after, 'seconds']
        else:
            # Interpolate
            idx_before = idx_after - 1
            # Note: idx_before might not be in reach_data if we sliced by time, 
            # but since we sliced a contiguous block from the main df, we should check the main df indices
            # Actually, let's just use iloc on the sliced frame for safety if indices are reset, 
            # but here we preserved original indices.
            
            # Let's get the rows from the main df to be safe about continuity
            row_after = df.loc[idx_after]
            row_before = df.loc[idx_after - 1] # Assuming standard integer index
            
            z1 = row_before['HandZ_filtered']
            z2 = row_after['HandZ_filtered']
            
            # Fraction of distance covered
            if z2 == z1:
                frac = 0
            else:
                frac = (z_threshold - z1) / (z2 - z1)
            
            x = row_before['HandX'] + frac * (row_after['HandX'] - row_before['HandX'])
            y = row_before['HandY'] + frac * (row_after['HandY'] - row_before['HandY'])
            time = row_before['seconds'] + frac * (row_after['seconds'] - row_before['seconds'])
            
        endpoints.append({
            'Reach_Number': reach_num,
            'Trial_Number': trial_num,
            'Reach_In_Trial': reach_in_trial,
            'HandX': x,
            'HandY': y,
            'Time': time
        })
        
    return pd.DataFrame(endpoints)

def create_faceted_visualization(endpoints, z_threshold, output_path):
    print("Creating visualization...")
    
    unique_trials = sorted(endpoints['Trial_Number'].unique())
    num_trials = len(unique_trials)
    
    # Calculate grid dimensions
    cols = 4
    rows = math.ceil(num_trials / cols)
    
    titles = [f"Trial {t}" for t in unique_trials]
    
    fig = make_subplots(
        rows=rows, cols=cols,
        subplot_titles=titles,
        horizontal_spacing=0.05,
        vertical_spacing=0.08
    )
    
    # Determine global range for consistent axes
    x_min, x_max = endpoints['HandX'].min(), endpoints['HandX'].max()
    y_min, y_max = endpoints['HandY'].min(), endpoints['HandY'].max()
    
    # Add padding
    x_pad = (x_max - x_min) * 0.1
    y_pad = (y_max - y_min) * 0.1
    x_range = [x_min - x_pad, x_max + x_pad]
    y_range = [y_min - y_pad, y_max + y_pad]
    
    for i, trial_num in enumerate(unique_trials):
        row = (i // cols) + 1
        col = (i % cols) + 1
        
        trial_data = endpoints[endpoints['Trial_Number'] == trial_num]
        
        # Add scatter points
        fig.add_trace(
            go.Scatter(
                x=trial_data['HandX'],
                y=trial_data['HandY'],
                mode='markers+text',
                marker=dict(size=10, color='blue'),
                text=trial_data['Reach_In_Trial'],
                textposition="top center",
                name=f"Trial {trial_num}",
                hovertemplate="Reach: %{text}<br>X: %{x:.3f}<br>Y: %{y:.3f}<extra></extra>",
                showlegend=False
            ),
            row=row, col=col
        )
        
        # Update axes for this subplot
        fig.update_xaxes(range=x_range, row=row, col=col, title_text="HandX" if row == rows else None)
        fig.update_yaxes(range=y_range, row=row, col=col, title_text="HandY" if col == 1 else None)

    fig.update_layout(
        title=f'Reach Endpoints at Z = {z_threshold}m (Outward Trajectory)',
        height=300 * rows,
        width=1200,
        template='plotly_white'
    )
    
    fig.write_html(output_path)
    print(f"Saved visualization to {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Visualize reach endpoints at specific Z threshold.')
    parser.add_argument('--file', type=str, required=True, help='Base path to the dataset')
    parser.add_argument('--z-value', type=float, default=0.2, help='Z threshold for endpoint (default: 0.2)')
    
    args = parser.parse_args()

    base_path = args.file
    if base_path.endswith('.csv'):
        base_path = base_path[:-4]
        
    df, reaches = load_data(base_path)
    
    if df is not None:
        endpoints = calculate_endpoints(df, reaches, args.z_value)
        
        if endpoints.empty:
            print(f"No reaches found crossing Z={args.z_value}")
            return
            
        # Save endpoints data
        csv_output = f"{base_path}_endpoints_z{args.z_value}.csv"
        endpoints.to_csv(csv_output, index=False)
        print(f"Saved endpoints data to {csv_output}")
        
        # Create visualization
        html_output = f"{base_path}_endpoints_z{args.z_value}_trials.html"
        create_faceted_visualization(endpoints, args.z_value, html_output)

if __name__ == "__main__":
    main()
