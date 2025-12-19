# GVS Analysis Tools

This folder contains the scripts and data for analyzing GVS reach data.

## Setup

1.  **Install Python**: Ensure you have Python installed.
2.  **Install Dependencies**: Open a terminal in this folder and run:
    ```bash
    pip install -r requirements.txt
    ```

## How to Run

Double-click `run_analysis.bat` to run the standard analysis pipeline.

## Scripts

-   `scripts/segmentation.py`: The main scientific segmentation algorithm. Reads from `data/` and saves segmented files back to `data/`.
-   `scripts/visualize_interactive.py`: Creates interactive Plotly graphs.
-   `scripts/visualize_peaks.py`: Visualizes peak detection.
-   `scripts/visualize_endpoints.py`: Visualizes reach endpoints.
-   `scripts/inspect_data.py`: Quick data inspection tool.

## Data

Place your new CSV files in the `data/` folder. The scripts are configured to look there.

## Methodology (For Researchers)

This analysis pipeline uses a standard kinematic segmentation approach to isolate reach movements from continuous data.

### 1. Signal Preprocessing
*   **Filtering**: Raw `HandZ` data is smoothed using a **4th-order Butterworth low-pass filter** with a **12 Hz cutoff frequency**. This removes high-frequency sensor noise while preserving human movement trajectories.
*   **Time Reconstruction**: If explicit timestamps are missing, the script reconstructs a linear time vector based on the recording start/end times.

### 2. Reach Segmentation Algorithm
The `segmentation.py` script identifies reaches using a geometric approach:
1.  **Peak Detection**: Identifies local maxima in the filtered Z-axis signal that exceed a height threshold (default: 0.93m).
2.  **Start Definition**: Searches backward from the peak to find the local minimum (trough). The "Start" is defined as the point where the hand rises **10%** of the way from the trough to the peak amplitude.
3.  **End Definition**: Searches forward from the peak to find the next local minimum. The "End" is defined as the point where the hand drops to within **10%** of the trough's amplitude.
4.  **Trial Splitting**: Continuous data is automatically split into "Trials" based on temporal gaps (default: >10 seconds of inactivity).

### 3. Endpoint Analysis
*   **Sub-frame Accuracy**: To determine exactly where the hand crossed a specific target height (e.g., Z=0.2m), the script uses **linear interpolation** between the two data points straddling the threshold. This provides a more accurate X/Y coordinate than simply taking the nearest sample.

