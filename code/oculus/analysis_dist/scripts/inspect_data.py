import pandas as pd
import numpy as np

import argparse
import os

def main():
    parser = argparse.ArgumentParser(description='Inspect GVS data timestamps.')
    parser.add_argument('--file', type=str, default=os.path.join(os.path.dirname(__file__), '../data/sample_data.csv'),
                        help='Path to the CSV file to inspect')
    args = parser.parse_args()

    file_path = args.file
    print(f"Inspecting: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return

    df = pd.read_csv(file_path)

    if 'timestamp' in df.columns:
        print("Unique timestamps (first 10):")
        print(df['timestamp'].unique()[:10])
        print(f"\nTotal unique timestamps: {df['timestamp'].nunique()}")

        try:
            df['parsed_time'] = pd.to_datetime(
                df['timestamp'].astype(str).str.replace('Day: ', '').str.replace(' Time: ', ' ')
            )

            print("\nParsed time range:")
            print(f"Start: {df['parsed_time'].min()}")
            print(f"End: {df['parsed_time'].max()}")

            duration = (df['parsed_time'].max() - df['parsed_time'].min()).total_seconds()
            print(f"Total duration (s): {duration}")

            estimated_fs = len(df) / duration if duration > 0 else 0
            print(f"Estimated sampling rate: {estimated_fs:.2f} Hz")
        except Exception as e:
            print(f"Error parsing timestamps: {e}")
    elif 'seconds' in df.columns:
        seconds = pd.to_numeric(df['seconds'], errors='coerce')
        valid = seconds.dropna()

        print("Detected cleaned schema with 'seconds' column.")
        print(f"Non-null seconds rows: {len(valid)} / {len(df)}")

        if not valid.empty:
            print(f"Seconds range: {valid.min()} to {valid.max()}")
            dt = valid.diff().dropna()
            dt = dt[dt > 0]
            estimated_fs = (1.0 / dt.median()) if not dt.empty else 0
            print(f"Estimated sampling rate: {estimated_fs:.2f} Hz")
        else:
            print("No valid numeric values found in 'seconds'.")
    else:
        print("No 'timestamp' or 'seconds' column found.")

if __name__ == "__main__":
    main()
