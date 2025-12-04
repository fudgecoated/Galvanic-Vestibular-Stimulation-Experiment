import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import argparse
import os
import numpy as np

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

def create_visualization(df, reaches, output_path):
    print("Creating visualization...")
    
    fig = go.Figure()

    # 1. Plot the continuous HandZ signal (background, faint)
    fig.add_trace(go.Scatter(
        x=df['seconds'], 
        y=df['HandZ_filtered'],
        mode='lines',
        name='HandZ Signal',
        line=dict(color='lightgray', width=1),
        opacity=0.5,
        hoverinfo='skip'
    ))

    # 2. Plot Trials with Color Coding
    # We'll iterate through trials to assign colors
    unique_trials = df['Trial_Number'].unique()
    # Remove 0 if it exists (non-trial data)
    unique_trials = [t for t in unique_trials if t != 0]
    
    colors = px.colors.qualitative.Plotly
    
    for i, trial_num in enumerate(unique_trials):
        trial_data = df[df['Trial_Number'] == trial_num]
        color = colors[i % len(colors)]
        
        fig.add_trace(go.Scatter(
            x=trial_data['seconds'],
            y=trial_data['HandZ_filtered'],
            mode='lines',
            name=f'Trial {trial_num}',
            line=dict(color=color, width=2),
            legendgroup=f'Trial {trial_num}'
        ))

    # 3. Mark Reach Start, Peak, End
    # We can do this efficiently by creating lists for all reaches
    starts_x, starts_y = [], []
    peaks_x, peaks_y = [], []
    ends_x, ends_y = [], []
    
    text_labels = []
    
    for _, reach in reaches.iterrows():
        starts_x.append(reach['Start_Time'])
        starts_y.append(reach['Start_Value'])
        
        peaks_x.append(reach['Peak_Time'])
        peaks_y.append(reach['Peak_Value'])
        
        ends_x.append(reach['End_Time'])
        ends_y.append(reach['End_Value'])
        
        text_labels.append(f"Reach {int(reach['Reach_Number'])}<br>Trial {int(reach['Trial_Number'])}")

    # Add Markers
    fig.add_trace(go.Scatter(
        x=starts_x, y=starts_y,
        mode='markers',
        name='Reach Start',
        marker=dict(symbol='triangle-up', size=10, color='green'),
        text=text_labels,
        hovertemplate='%{text}<br>Start<br>Time: %{x:.2f}s<br>Value: %{y:.2f}<extra></extra>'
    ))

    fig.add_trace(go.Scatter(
        x=peaks_x, y=peaks_y,
        mode='markers',
        name='Reach Peak',
        marker=dict(symbol='star', size=12, color='red'),
        text=text_labels,
        hovertemplate='%{text}<br>Peak<br>Time: %{x:.2f}s<br>Value: %{y:.2f}<extra></extra>'
    ))

    fig.add_trace(go.Scatter(
        x=ends_x, y=ends_y,
        mode='markers',
        name='Reach End',
        marker=dict(symbol='triangle-down', size=10, color='blue'),
        text=text_labels,
        hovertemplate='%{text}<br>End<br>Time: %{x:.2f}s<br>Value: %{y:.2f}<extra></extra>'
    ))

    # Layout updates
    fig.update_layout(
        title='Reach Segmentation Analysis',
        xaxis_title='Time (seconds)',
        yaxis_title='HandZ Position',
        hovermode='closest',
        template='plotly_white',
        height=800
    )
    
    # Save
    fig.write_html(output_path)
    print(f"Saved visualization to {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Create Plotly visualization for segmented data.')
    parser.add_argument('--file', type=str, help='Base path to the dataset (e.g., combined_data/ST_PILOT_OCULUS_CLEAN)')
    parser.add_argument('--batch-dir', type=str, help='Directory to batch process all datasets')
    
    args = parser.parse_args()

    if args.batch_dir:
        # Process all datasets in directory
        if not os.path.exists(args.batch_dir):
            print(f"Error: Directory {args.batch_dir} not found.")
            return
            
        # Find all _scientific_segmented.csv files to identify datasets
        files = [f for f in os.listdir(args.batch_dir) if f.endswith('_scientific_segmented.csv')]
        
        for f in files:
            # Reconstruct base path
            base_name = f.replace('_scientific_segmented.csv', '')
            base_path = os.path.join(args.batch_dir, base_name)
            
            df, reaches = load_data(base_path)
            if df is not None:
                output_path = f"{base_path}_plotly_visualization.html"
                create_visualization(df, reaches, output_path)
                
    elif args.file:
        base_path = args.file
        if base_path.endswith('.csv'):
            base_path = base_path[:-4]
            
        df, reaches = load_data(base_path)
        if df is not None:
            output_path = f"{base_path}_plotly_visualization.html"
            create_visualization(df, reaches, output_path)
    else:
        print("Please specify --file or --batch-dir")

if __name__ == "__main__":
    main()
