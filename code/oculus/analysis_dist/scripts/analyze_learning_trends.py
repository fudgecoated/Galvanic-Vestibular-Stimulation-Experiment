import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import linregress
import argparse
import os

def analyze_learning_trends(endpoints_file):
    print(f"Reading {endpoints_file}...")
    df = pd.read_csv(endpoints_file)
    
    if df.empty:
        print("Dataset is empty.")
        return
        
    trials = sorted(df['Trial_Number'].unique())
    num_trials = len(trials)
    
    trial_data = []
    
    for i, trial_num in enumerate(trials):
        trial_df = df[df['Trial_Number'] == trial_num].sort_values(by='Reach_In_Trial')
        
        if len(trial_df) == 0:
            continue
            
        # Overall trial metrics
        total_reaches = len(trial_df)
        hits = trial_df['Hit_Bullseye'].sum()
        hit_pct = (hits / total_reaches) * 100 if total_reaches > 0 else 0
        mean_trial_error = trial_df['Euclidean_Error'].mean()
        
        # Metric 2: Initial vs Final End Target Error
        # Mean of first 3 reaches
        initial_reaches = trial_df.head(3)
        initial_error = initial_reaches['Euclidean_Error'].mean() if len(initial_reaches) > 0 else np.nan
        
        # Mean of last 3 reaches
        final_reaches = trial_df.tail(3)
        final_error = final_reaches['Euclidean_Error'].mean() if len(final_reaches) > 0 else np.nan
        
        # Metric 3: Within-Trial Learning Rate (Slope)
        if len(trial_df) > 1:
            slope, intercept, r_value, p_value, std_err = linregress(trial_df['Reach_In_Trial'], trial_df['Euclidean_Error'])
        else:
            slope, intercept, r_value, p_value, std_err = np.nan, np.nan, np.nan, np.nan, np.nan

        trial_data.append({
            'Trial_Number': trial_num,
            'Hit_Percentage': hit_pct,
            'Total_Reaches': total_reaches,
            'Mean_Trial_Error': mean_trial_error,
            'Initial_Error': initial_error,
            'Final_Error': final_error,
            'Learning_Slope': slope
        })

    results_df = pd.DataFrame(trial_data)
    
    # Metric 4: Between-Trial Retention
    # Difference between Initial Error of Trial N and Final Error of Trial N-1
    results_df['Retention_Error_Diff'] = np.nan
    for i in range(1, len(results_df)):
        initial_n = results_df.loc[i, 'Initial_Error']
        final_prev = results_df.loc[i-1, 'Final_Error']
        
        # Positive diff = forgot/worsened. Negative diff = retained/improved.
        results_df.loc[i, 'Retention_Error_Diff'] = initial_n - final_prev

    # Save summary data
    base_name = endpoints_file.replace('.csv', '')
    csv_out = f"{base_name}_learning_trends.csv"
    results_df.to_csv(csv_out, index=False)
    print(f"Saved learning trends data to: {csv_out}")
    
    # Visualization
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        subplot_titles=(
            "Initial vs. Final End Target Error (per Trial)",
            "Within-Trial Learning Slope (Euclidean Error vs Reach)",
            "Between-Trial Retention (Initial Error T(n) - Final Error T(n-1))"
        ),
        vertical_spacing=0.1
    )
    
    trial_labels = [f"Trial {t}" for t in results_df['Trial_Number']]
    
    # --- Plot 1: Initial vs Final Error ---
    fig.add_trace(go.Bar(
        x=trial_labels, 
        y=results_df['Initial_Error'],
        name='Initial Error (First 3 reaches)',
        marker_color='indianred',
        hovertemplate="Initial Error: %{y:.4f}m<extra></extra>"
    ), row=1, col=1)
    
    fig.add_trace(go.Bar(
        x=trial_labels, 
        y=results_df['Final_Error'],
        name='Final Error (Last 3 reaches)',
        marker_color='lightsalmon',
        hovertemplate="Final Error: %{y:.4f}m<extra></extra>"
    ), row=1, col=1)

    # --- Plot 2: Learning Slope ---
    # Assign green to negative (improving) and red to positive (worsening)
    slope_colors = ['green' if s < 0 else 'red' for s in results_df['Learning_Slope']]
    
    fig.add_trace(go.Bar(
        x=trial_labels,
        y=results_df['Learning_Slope'],
        name='Learning Slope',
        marker_color=slope_colors,
        hovertemplate="Slope: %{y:.5f} m/reach<extra></extra>"
    ), row=2, col=1)
    
    # --- Plot 3: Between Trial Retention ---
    # Retention available from Trial 2 onwards
    retention_trials = trial_labels[1:]
    retention_vals = results_df['Retention_Error_Diff'].values[1:]
    ret_colors = ['green' if r <= 0 else 'red' for r in retention_vals]
    
    fig.add_trace(go.Bar(
        x=retention_trials,
        y=retention_vals,
        name='Retention Diff',
        marker_color=ret_colors,
        hovertemplate="Diff from Prev Trial: %{y:.4f}m<extra></extra>"
    ), row=3, col=1)

    fig.update_layout(
        title='Trial-Level Learning Trends & Retention Metrics',
        barmode='group',
        height=1000,
        template='plotly_white',
        showlegend=True
    )
    
    # Axis titles
    fig.update_yaxes(title_text="Mean Error (m)", row=1, col=1)
    fig.update_yaxes(title_text="Slope (m/reach)", row=2, col=1)
    fig.update_yaxes(title_text="Error Difference (m)", row=3, col=1)
    fig.update_xaxes(title_text="Trial Number", row=3, col=1)

    html_out = f"{base_name}_learning_trends_interactive.html"
    fig.write_html(html_out)
    print(f"Saved learning trends visualization to: {html_out}")


def main():
    parser = argparse.ArgumentParser(description='Analyze and visualize trial-to-trial learning metrics.')
    parser.add_argument('--file', type=str, required=True, help='Path to the ends_points_z<Z>.csv dataset')
    args = parser.parse_args()
    
    analyze_learning_trends(args.file)

if __name__ == "__main__":
    main()
