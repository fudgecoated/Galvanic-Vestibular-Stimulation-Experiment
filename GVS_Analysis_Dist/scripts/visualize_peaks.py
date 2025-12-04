import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, Slider
import numpy as np
import os
import argparse
from matplotlib.patches import Rectangle
import matplotlib.gridspec as gridspec

# Function to load data files
def load_data(segments_file, handy_file=None, peaks_file=None):
    # Load segments data
    segments_df = pd.read_csv(segments_file)
    
    # Load HandY data if file exists
    handy_df = None
    if handy_file and os.path.exists(handy_file):
        handy_df = pd.read_csv(handy_file)
    
    # Load peaks data if file exists
    peaks_df = None
    if peaks_file and os.path.exists(peaks_file):
        peaks_df = pd.read_csv(peaks_file)
        
    return segments_df, handy_df, peaks_df

class InteractiveVisualizer:
    def __init__(self, segments_df, handy_df=None, peaks_df=None):
        self.segments_df = segments_df
        self.handy_df = handy_df
        self.peaks_df = peaks_df
        
        # Determine time range
        self.min_time = 0
        self.max_time = segments_df['End_Time'].max()
        
        if handy_df is not None and 'seconds' in handy_df.columns:
            self.min_time = min(self.min_time, handy_df['seconds'].min())
            self.max_time = max(self.max_time, handy_df['seconds'].max())
        
        if peaks_df is not None and 'time' in peaks_df.columns:
            self.min_time = min(self.min_time, peaks_df['time'].min())
            self.max_time = max(self.max_time, peaks_df['time'].max())
        
        self.current_time = self.min_time
        self.animation_running = False
        self.setup_plot()
    
    def setup_plot(self):
        # Create figure and layout
        self.fig = plt.figure(figsize=(15, 10))
        gs = gridspec.GridSpec(2, 1, height_ratios=[9, 1])
        
        # Main plot area
        self.ax = plt.subplot(gs[0])
        
        # Controls area
        self.controls_ax = plt.subplot(gs[1])
        self.controls_ax.set_facecolor('#f0f0f0')
        self.controls_ax.set_xticks([])
        self.controls_ax.set_yticks([])
        
        # Plot HandY data if available
        self.max_y_value = 1.0
        if self.handy_df is not None and 'HandZ_filtered' in self.handy_df.columns:
            self.handy_line, = self.ax.plot(self.handy_df['seconds'], self.handy_df['HandZ_filtered'], 
                                            label='HandZ Filtered', linewidth=1)
            self.max_y_value = self.handy_df['HandZ_filtered'].max() * 1.1
        
        # Plot segments as shaded regions
        self.segment_patches = []
        for _, segment in self.segments_df.iterrows():
            start_time = segment['Start_Time']
            end_time = segment['End_Time']
            patch = self.ax.axvspan(start_time, end_time, alpha=0.2, color='blue')
            self.segment_patches.append(patch)
            
            # Label segments
            segment_mid = (start_time + end_time) / 2
            self.ax.text(segment_mid, self.max_y_value * 0.95, str(int(segment['Reach_Number'])), 
                     horizontalalignment='center', fontsize=8)
        
        # Plot peaks if available
        if self.peaks_df is not None and 'time' in self.peaks_df.columns and 'height' in self.peaks_df.columns:
            self.ax.scatter(self.peaks_df['time'], self.peaks_df['height'], color='red', 
                        marker='^', label='Peaks', s=50, zorder=5)
        
        # Add time cursor line
        self.time_line = self.ax.axvline(x=self.current_time, color='r', linestyle='-', linewidth=2)
        
        # Add current segment indicator
        self.current_segment_text = self.ax.text(0.02, 0.95, '', transform=self.ax.transAxes,
                                            bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))
        
        # Configure plot
        self.ax.set_title('Scientific Segments and HandZ Data Visualization')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('HandZ Position')
        self.ax.grid(True, linestyle='--', alpha=0.7)
        
        # Add legend if we have multiple data series
        if self.handy_df is not None or self.peaks_df is not None:
            self.ax.legend(loc='upper right')
        
        # Set time limits with padding
        padding = (self.max_time - self.min_time) * 0.05
        self.ax.set_xlim(self.min_time - padding, self.max_time + padding)
        
        # Add controls
        play_ax = plt.axes([0.1, 0.05, 0.1, 0.04])
        self.play_button = Button(play_ax, 'Play')
        self.play_button.on_clicked(self.toggle_animation)
        
        pause_ax = plt.axes([0.21, 0.05, 0.1, 0.04])
        self.pause_button = Button(pause_ax, 'Pause')
        self.pause_button.on_clicked(self.toggle_animation)
        
        reset_ax = plt.axes([0.32, 0.05, 0.1, 0.04])
        self.reset_button = Button(reset_ax, 'Reset')
        self.reset_button.on_clicked(self.reset_animation)
        
        save_ax = plt.axes([0.43, 0.05, 0.1, 0.04])
        self.save_button = Button(save_ax, 'Save Video')
        self.save_button.on_clicked(self.save_animation)
        
        slider_ax = plt.axes([0.1, 0.15, 0.8, 0.03])
        self.time_slider = Slider(slider_ax, 'Time', self.min_time, self.max_time, 
                                 valinit=self.min_time, valstep=0.1)
        self.time_slider.on_changed(self.update_time_from_slider)
        
        self.fig.tight_layout()
    
    def update_plot(self, frame):
        # Update the current time (if animation is running)
        if self.animation_running:
            self.current_time += 0.1  # Adjust speed as needed
            if self.current_time > self.max_time:
                self.current_time = self.min_time
            
            # Update the slider position
            self.time_slider.set_val(self.current_time)
        
        # Update time line position
        self.time_line.set_xdata([self.current_time, self.current_time])
        
        # Find current segment
        current_segment = None
        for _, segment in self.segments_df.iterrows():
            if segment['Start_Time'] <= self.current_time <= segment['End_Time']:
                current_segment = segment
                break
        
        # Update current segment text
        if current_segment is not None:
            segment_info = f"Reach: {int(current_segment['Reach_Number'])} " + \
                          f"(Duration: {current_segment['Duration']:.2f}s)"
            self.current_segment_text.set_text(segment_info)
        else:
            self.current_segment_text.set_text("No reach")
        
        # Return all artists that need to be redrawn
        return [self.time_line, self.current_segment_text]
    
    def toggle_animation(self, event):
        self.animation_running = not self.animation_running
    
    def reset_animation(self, event):
        self.current_time = self.min_time
        self.time_slider.set_val(self.min_time)
    
    def update_time_from_slider(self, val):
        self.current_time = val
    
    def save_animation(self, event):
        # Pause animation while saving
        was_running = self.animation_running
        self.animation_running = False
        
        print("Saving video... This may take a while.")
        
        # Create new animation instance for saving
        save_anim = animation.FuncAnimation(self.fig, self.update_plot, 
                                           frames=int((self.max_time - self.min_time) * 10),
                                           interval=100, blit=True)
        
        # Save as mp4
        save_anim.save('visualization.mp4', writer='ffmpeg', fps=10, 
                      dpi=300, extra_args=['-vcodec', 'libx264'])
        
        print("Video saved to visualization.mp4")
        
        # Restore animation state
        self.animation_running = was_running
    
    def start(self):
        # Create animation
        self.anim = animation.FuncAnimation(
            self.fig, self.update_plot, interval=100, blit=True)
        plt.show()

# Main function
def main():
    parser = argparse.ArgumentParser(description='Visualize scientific segmentation results.')
    parser.add_argument('--file', type=str, help='Base path to the dataset (e.g., combined_data/ST_PILOT_OCULUS_CLEAN)')
    args = parser.parse_args()

    if args.file:
        base_path = args.file
        # Remove extension if provided
        if base_path.endswith('.csv'):
            base_path = base_path[:-4]
            
        segments_file = f"{base_path}_reach_summary.csv"
        handy_file = f"{base_path}_scientific_segmented.csv"
        print(f"Loading files:\n  Segments: {segments_file}\n  Data: {handy_file}")
    else:
        # Default fallback
        print("No file specified. Using default.")
        segments_file = "TA_OCULUS_PILOT_JUL4_2_OCULUS_reach_summary.csv"
        handy_file = "TA_OCULUS_PILOT_JUL4_2_OCULUS_scientific_segmented.csv"
    
    peaks_file = None  # We don't have a separate peaks file for this run
    
    if not os.path.exists(segments_file) or not os.path.exists(handy_file):
        print(f"Error: Could not find input files.\nChecked:\n  {segments_file}\n  {handy_file}")
        return

    # Load data
    segments_df, handy_df, peaks_df = load_data(segments_file, handy_file, peaks_file)
    
    # Create and start the interactive visualizer
    visualizer = InteractiveVisualizer(segments_df, handy_df, peaks_df)
    visualizer.start()
    
    # Print summary statistics (once visualization is closed)
    print("\nSegment Summary Statistics:")
    print(f"Total number of reaches: {len(segments_df)}")
    print(f"Average reach duration: {segments_df['Duration'].mean():.2f} seconds")
    print(f"Min reach duration: {segments_df['Duration'].min():.2f} seconds")
    print(f"Max reach duration: {segments_df['Duration'].max():.2f} seconds")
    
    # Identify unusually short or long segments (outside 1.5 IQR)
    Q1 = segments_df['Duration'].quantile(0.25)
    Q3 = segments_df['Duration'].quantile(0.75)
    IQR = Q3 - Q1
    
    outliers = segments_df[(segments_df['Duration'] < (Q1 - 1.5 * IQR)) | 
                           (segments_df['Duration'] > (Q3 + 1.5 * IQR))]
    
    if not outliers.empty:
        print("\nPotential outlier reaches:")
        print(outliers[['Reach_Number', 'Duration']])

if __name__ == "__main__":
    main()