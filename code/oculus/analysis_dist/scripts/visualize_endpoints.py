import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import argparse
import os
import numpy as np
import math
from scipy.signal import butter, filtfilt

def _butter_lowpass_filter(data, cutoff_hz=12.0, fs=72.0, order=4):
    nyquist = 0.5 * fs
    normal_cutoff = min(cutoff_hz, nyquist * 0.9) / nyquist
    b, a = butter(order, normal_cutoff, btype='low')
    return filtfilt(b, a, data)

def load_data(base_path):
    segments_file = f"{base_path}_reach_summary.csv"
    data_file = f"{base_path}_scientific_segmented.csv"
    
    if not os.path.exists(segments_file) or not os.path.exists(data_file):
        print(f"Error: Could not find input files for {base_path}")
        return None, None

    print(f"Loading {data_file}...")
    df = pd.read_csv(data_file)
    
    if 'HandX' not in df.columns and '6' in df.columns:
        df.rename(columns={'6': 'HandX'}, inplace=True)
    if 'HandY' not in df.columns and '7' in df.columns:
        df.rename(columns={'7': 'HandY'}, inplace=True)
    if '8' in df.columns:
        df['HandZ'] = df['8']
        
    print(f"Loading {segments_file}...")
    reaches = pd.read_csv(segments_file)
    
    return df, reaches

def calculate_endpoints(df, reaches, z_threshold, target_pos=(0,0)):
    print(f"Calculating endpoints at Z = {z_threshold}...")
    endpoints = []
    
    # Define Target Center
    tx, ty = target_pos
    
    for _, reach in reaches.iterrows():
        reach_num = int(reach['Reach_Number'])
        trial_num = int(reach['Trial_Number'])
        reach_in_trial = int(reach['Reach_In_Trial'])
        
        start_time = reach['Start_Time']
        peak_time = reach['Peak_Time']
        
        reach_data = df[(df['seconds'] >= start_time) & (df['seconds'] <= peak_time)].copy()
        
        if reach_data.empty:
            continue
            
        if reach_data['HandZ_filtered'].max() < z_threshold:
            continue
            
        crossing_indices = reach_data.index[reach_data['HandZ_filtered'] >= z_threshold]
        
        if len(crossing_indices) == 0:
            continue
            
        idx_after = crossing_indices[0]
        
        if idx_after == reach_data.index[0]:
            x = reach_data.loc[idx_after, 'HandX']
            y = reach_data.loc[idx_after, 'HandY']
            time = reach_data.loc[idx_after, 'seconds']
        else:
            row_after = df.loc[idx_after]
            row_before = df.loc[idx_after - 1]
            
            z1 = row_before['HandZ_filtered']
            z2 = row_after['HandZ_filtered']
            
            if z2 == z1:
                frac = 0
            else:
                frac = (z_threshold - z1) / (z2 - z1)
            
            x = row_before['HandX'] + frac * (row_after['HandX'] - row_before['HandX'])
            y = row_before['HandY'] + frac * (row_after['HandY'] - row_before['HandY'])
            z = z_threshold
            time = row_before['seconds'] + frac * (row_after['seconds'] - row_before['seconds'])
            
        # --- Error Metrics ---
        # Cartesian Error
        error_x = x - tx
        error_y = y - ty
        
        # Euclidean Error
        euclidean_error = math.sqrt(error_x**2 + error_y**2)
        
        # Bullseye Hit (2cm diameter circle around target)
        # Radius = 1.0cm = 0.01m
        hit_bullseye = bool(euclidean_error <= 0.01)
            
        endpoints.append({
            'Reach_Number': reach_num,
            'Trial_Number': trial_num,
            'Reach_In_Trial': reach_in_trial,
            'HandX': x,
            'HandY': y,
            'HandZ': z,
            'Time': time,
            'Error_X': error_x,
            'Error_Y': error_y,
            'Euclidean_Error': euclidean_error,
            'Hit_Bullseye': hit_bullseye
        })
        
    df_out = pd.DataFrame(endpoints)
    if not df_out.empty:
        df_out['Global_Success_Index'] = range(1, len(df_out) + 1)
    return df_out

def create_interactive_visualization(endpoints, full_df, reaches, z_threshold, output_path, target_pos=None):
    print("Creating interactive visualization (Spatial Endpoints + Time Series Segments + Learning Rate)...")
    
    unique_trials = sorted(endpoints['Trial_Number'].unique())
    num_trials = len(unique_trials)
    
    fig = make_subplots(
        rows=4, cols=2,
        column_widths=[0.6, 0.4],
        specs=[[{"rowspan": 3}, {}],
               [None, {}],
               [None, {}],
               [{"colspan": 2}, None]],
        subplot_titles=("Spatial Endpoints (X-Y)", "Hand Z vs Time", "Hand X vs Time", "Hand Y vs Time", "Learning Rate (Euclidean Error vs Reach Number)"),
        horizontal_spacing=0.08,
        vertical_spacing=0.08
    )
    
    x_min, x_max = endpoints['HandX'].min(), endpoints['HandX'].max()
    y_min, y_max = endpoints['HandY'].min(), endpoints['HandY'].max()
    
    if target_pos:
        tx, ty, tz = target_pos
        x_min = min(x_min, tx)
        x_max = max(x_max, tx)
        y_min = min(y_min, ty)
        y_max = max(y_max, ty)
        
    pad_factor = 0.1
    x_pad = (x_max - x_min) * pad_factor if x_max != x_min else 0.1
    y_pad = (y_max - y_min) * pad_factor if y_max != y_min else 0.1
    
    x_range = [x_min - x_pad, x_max + x_pad]
    y_range = [y_min - y_pad, y_max + y_pad]
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    all_times = []
    hit_pct_dict = {}

    for i, trial_num in enumerate(unique_trials):
        color = colors[i % len(colors)]
        
        # 1. Spatial Endpoints (DOTS)
        trial_endpoints = endpoints[endpoints['Trial_Number'] == trial_num]
        
        # Calculate Hit Percentage
        hits = trial_endpoints['Hit_Bullseye'].sum()
        total = len(trial_endpoints)
        hit_pct = (hits / total) * 100 if total > 0 else 0
        hit_pct_dict[trial_num] = hit_pct
        
        fig.add_trace(
            go.Scatter(
                x=trial_endpoints['HandX'],
                y=trial_endpoints['HandY'],
                mode='markers',
                marker=dict(size=8, color=color, opacity=0.8),
                text=trial_endpoints['Reach_In_Trial'],
                name=f"Trial {trial_num} (Endpoints | {hit_pct:.1f}% Hit)",
                hovertemplate="Trial: %{customdata[0]}<br>Reach: %{text}<br>X: %{x:.3f}<br>Y: %{y:.3f}<br>Hit: %{customdata[1]}<extra></extra>",
                customdata=np.stack((trial_endpoints['Trial_Number'], trial_endpoints['Hit_Bullseye']), axis=-1),
                visible=True,
                legendgroup=f"group_{trial_num}"
            ),
            row=1, col=1
        )
        
        # 2. Time Series (LINES)
        trial_reaches = reaches[reaches['Trial_Number'] == trial_num]
        
        t_seq, x_seq, y_seq, z_seq = [], [], [], []
        
        for _, reach in trial_reaches.iterrows():
            start_time = reach['Start_Time']
            peak_time = reach['Peak_Time']
            
            segment = full_df[(full_df['seconds'] >= start_time) & (full_df['seconds'] <= peak_time)].copy()
            
            if segment.empty:
                continue
                
            # Filter the raw X, Y, Z for smooth plotting
            if len(segment) > 15: # Need enough points to filter
                try:
                    seg_x_smooth = _butter_lowpass_filter(segment['HandX'].values)
                    seg_y_smooth = _butter_lowpass_filter(segment['HandY'].values)
                    seg_z_smooth = _butter_lowpass_filter(segment['HandZ'].values)
                except:
                    seg_x_smooth = segment['HandX'].tolist()
                    seg_y_smooth = segment['HandY'].tolist()
                    seg_z_smooth = segment['HandZ'].tolist()
            else:
                seg_x_smooth = segment['HandX'].tolist()
                seg_y_smooth = segment['HandY'].tolist()
                seg_z_smooth = segment['HandZ'].tolist()
                
            t_seq.extend(segment['seconds'].tolist() + [None])
            x_seq.extend(list(seg_x_smooth) + [None])
            y_seq.extend(list(seg_y_smooth) + [None])
            z_seq.extend(list(seg_z_smooth) + [None])
            
            all_times.extend(segment['seconds'].tolist())

        fig.add_trace(
            go.Scatter(
                x=t_seq, y=z_seq,
                mode='lines', line=dict(color=color, width=1.5),
                name=f"Trial {trial_num} (Z)",
                visible=True, showlegend=False, legendgroup=f"group_{trial_num}",
                hovertemplate="T: %{x:.2f}<br>Z: %{y:.3f}<extra></extra>"
            ), row=1, col=2
        )
        
        fig.add_trace(
            go.Scatter(
                x=t_seq, y=x_seq,
                mode='lines', line=dict(color=color, width=1.5),
                name=f"Trial {trial_num} (X)",
                visible=True, showlegend=False, legendgroup=f"group_{trial_num}",
                hovertemplate="T: %{x:.2f}<br>X: %{y:.3f}<extra></extra>"
            ), row=2, col=2
        )
        
        fig.add_trace(
            go.Scatter(
                x=t_seq, y=y_seq,
                mode='lines', line=dict(color=color, width=1.5),
                name=f"Trial {trial_num} (Y)",
                visible=True, showlegend=False, legendgroup=f"group_{trial_num}",
                hovertemplate="T: %{x:.2f}<br>Y: %{y:.3f}<extra></extra>"
            ), row=3, col=2
        )
        
        # 3. Learning Rate (Euclidean Error vs Reach Number)
        # We plot Euclidean Error sequentially for this trial
        # We need the global reach number to string them together across trials
        fig.add_trace(
            go.Scatter(
                x=trial_endpoints['Global_Success_Index'],
                y=trial_endpoints['Euclidean_Error'],
                mode='lines+markers',
                marker=dict(size=6, color=color),
                line=dict(color=color, width=2),
                name=f"Trial {trial_num} (Learning)",
                visible=True, showlegend=False, legendgroup=f"group_{trial_num}",
                hovertemplate="Global Success #: %{x}<br>Error (m): %{y:.4f}<extra></extra>"
            ), row=4, col=1
        )

    if all_times:
        t_min, t_max = min(all_times), max(all_times)
        t_pad = (t_max - t_min) * 0.05
        t_range = [t_min - t_pad, t_max + t_pad]
    else:
        t_range = None

    if target_pos is not None:
        tx, ty, tz = target_pos
        
        # Draw 2cm Diameter Bullseye Circle
        radius = 0.01 # 1cm radius
        fig.add_shape(
            type="circle",
            x0=tx - radius, y0=ty - radius,
            x1=tx + radius, y1=ty + radius,
            line=dict(color="red", width=1),
            fillcolor="red", opacity=0.3,
            row=1, col=1
        )
        
        fig.add_trace(go.Scatter(
            x=[tx], y=[ty],
            mode='markers',
            marker=dict(size=10, color='gold', symbol='cross', line=dict(width=1, color='black')),
            name='Target Center',
        ), row=1, col=1)
        
        fig.add_hline(y=tz, line_dash="dash", line_color="gold", row=1, col=2, annotation_text="Target Z")
        fig.add_hline(y=tx, line_dash="dash", line_color="gold", row=2, col=2, annotation_text="Target X")
        fig.add_hline(y=ty, line_dash="dash", line_color="gold", row=3, col=2, annotation_text="Target Y")

    buttons = []
    total_traces = len(fig.data)
    
    # Button: All
    vis_all = [True] * total_traces
    buttons.append(dict(label="All Trials", method="update", args=[{"visible": vis_all}]))

    # Button: Hide All (for manual legend selection)
    vis_none = [False] * total_traces
    if target_pos:
        vis_none[-1] = True # Keep target visible
    buttons.append(dict(label="Hide All", method="update", args=[{"visible": vis_none}]))
    
    # 5 traces per trial now: Endpoints, Z-time, X-time, Y-time, Learning Rate
    traces_per_group = 5 
    for i, trial_num in enumerate(unique_trials):
        vis = [False] * total_traces
        
        start_idx = i * traces_per_group
        for offset in range(traces_per_group):
            if start_idx + offset < total_traces:
                vis[start_idx + offset] = True
        
        if target_pos:
            vis[-1] = True
            
        buttons.append(dict(label=f"Trial {trial_num} ({hit_pct_dict[trial_num]:.1f}% Hit)", method="update", args=[{"visible": vis}]))

    fig.update_layout(
        title='Reach Analysis: Spatial Endpoints, Time-Series & Learning Rate',
        template='plotly_white',
        width=1600,
        height=1200,
        updatemenus=[dict(active=0, buttons=buttons, x=1.0, y=1.05, xanchor='right', yanchor='top')],
    )
    
    fig.update_xaxes(title_text="Hand X (m)", range=x_range, row=1, col=1)
    fig.update_yaxes(title_text="Hand Y (m)", range=y_range, scaleanchor="x", scaleratio=1, row=1, col=1)
    
    fig.update_yaxes(title_text="Hand Z (m)", row=1, col=2)
    fig.update_yaxes(title_text="Hand X (m)", row=2, col=2)
    fig.update_yaxes(title_text="Hand Y (m)", row=3, col=2)
    
    if t_range:
        for r in [1, 2, 3]:
            fig.update_xaxes(range=t_range, row=r, col=2)
            
    fig.update_xaxes(title_text="Time (s)", row=3, col=2)
    
    # Learning Rate Axes
    fig.update_xaxes(title_text="Global Success Number (1-N)", row=4, col=1)
    fig.update_yaxes(title_text="Euclidean Error (m)", row=4, col=1, rangemode='tozero')
    
    fig.write_html(output_path)
    print(f"Saved visualization to {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Visualize reach endpoints at specific Z threshold.')
    parser.add_argument('--file', type=str, required=True, help='Base path to the dataset')
    parser.add_argument('--z-value', type=float, default=0.2, help='Z threshold for endpoint (default: 0.2)')
    parser.add_argument('--target-x', type=float, help='X coordinate of the target (optional)')
    parser.add_argument('--target-y', type=float, help='Y coordinate of the target (optional)')
    parser.add_argument('--target-z', type=float, help='Z coordinate of the target (optional)')
    parser.add_argument('--shift-x', type=float, default=0.0, help='Shift value for Hand X (m) (default: 0.0)')
    parser.add_argument('--shift-y', type=float, default=0.0, help='Shift value for Hand Y (m) (default: 0.0)')
    
    args = parser.parse_args()

    base_path = args.file
    if base_path.endswith('.csv'):
        base_path = base_path[:-4]
        
    df, reaches = load_data(base_path)

    if df is not None:
        if args.shift_x != 0:
            print(f"Shifting HandX by {args.shift_x}")
            df['HandX'] += args.shift_x
        if args.shift_y != 0:
            print(f"Shifting HandY by {args.shift_y}")
            df['HandY'] += args.shift_y
            
        target_pos = None
        if args.target_x is not None or args.target_y is not None:
            tx = args.target_x if args.target_x is not None else 0.0
            ty = args.target_y if args.target_y is not None else 0.0
            target_pos = (tx, ty)
        else:
            target_pos = (0.0, 0.0) # Default target
            
    if df is not None:
        endpoints = calculate_endpoints(df, reaches, args.z_value, target_pos=target_pos)
        
        if endpoints.empty:
            print(f"No reaches found crossing Z={args.z_value}")
            return
            
        csv_output = f"{base_path}_endpoints_z{args.z_value}.csv"
        endpoints.to_csv(csv_output, index=False)
        print(f"Saved endpoints data to {csv_output}")
        
        # Include Z for backwards compatibility in args to create_interactive 
        # but calculation only uses X,Y
        tz = args.target_z if args.target_z is not None else args.z_value
        vis_target_pos = (target_pos[0], target_pos[1], tz)

        html_output = f"{base_path}_endpoints_z{args.z_value}_interactive.html"
        
        create_interactive_visualization(endpoints, df, reaches, args.z_value, html_output, target_pos=vis_target_pos)

if __name__ == "__main__":
    main()
