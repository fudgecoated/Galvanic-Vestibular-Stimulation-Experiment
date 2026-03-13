import pandas as pd
import numpy as np

file_path = 'Segment_GVS_datasets/ST_PILOT_TEST_OCULUS_CLEAN.csv'

print(f"Loading {file_path}...")
try:
    df = pd.read_csv(file_path)
    print("Columns:", df.columns.tolist())
    print("\nFirst 5 rows:")
    print(df.head())
    
    print("\nChecking 'seconds' column:")
    print(df['seconds'].head(10))
    
    print("\nChecking 'truetime' column:")
    print(df['truetime'].head(10))
    
    # Check for NaNs in seconds
    print(f"\nNaNs in 'seconds': {df['seconds'].isna().sum()}")
    
except Exception as e:
    print(f"Error: {e}")
