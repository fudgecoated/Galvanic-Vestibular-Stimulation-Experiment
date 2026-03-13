import pandas as pd

# Read the CSV file
input_file = 'TA_OCULUS_PILOT_JUL4_2_OCULUS_interpolated.csv'
output_file = 'TA_OCULUS_PILOT_JUL4_2_OCULUS_interpolated_filtered.csv'

# Read the CSV (may take a moment due to file size)
print(f"Reading {input_file}...")
df = pd.read_csv(input_file)

print(f"Original shape: {df.shape}")
print(f"Original columns: {list(df.columns)}")

# Keep only the last 7 columns
df_filtered = df.iloc[:, -7:]

print(f"Filtered shape: {df_filtered.shape}")
print(f"Filtered columns: {list(df_filtered.columns)}")

# Save to new CSV
print(f"Saving to {output_file}...")
df_filtered.to_csv(output_file, index=False)

print("Done!")