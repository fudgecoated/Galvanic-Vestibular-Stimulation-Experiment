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
