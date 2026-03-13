import pandas as pd
import numpy as np 
import matplotlib.pyplot as plt
from scipy.signal import butter, sosfiltfilt,  find_peaks


file_path = 'TA_OCULUS_PILOT_JUL4_2_OCULUS_interpolated.csv'
data = pd.read_csv(file_path)

COL_TIME = 'Timestamp'
COL_HANDZ = 'HandZ'

# Convert columns to numeric, coercing errors
data[COL_TIME] = pd.to_numeric(data[COL_TIME], errors='coerce')
data[COL_HANDZ] = pd.to_numeric(data[COL_HANDZ], errors='coerce')

# Drop rows where conversion resulted in NaT/NaN
data.dropna(subset=[COL_TIME, COL_HANDZ], inplace=True)

CUTOFF_HZ_FALLBACK =  8.0
BUTTER_ORDER = 4

MIN_PERIOD_SEC = 0.25
PROMINENCE_K_MAD = 2.0



# Check if there is enough data to proceed
if len(data) < 2:
    print("Not enough data to perform filtering after cleaning. Exiting.")
else:
    # Calculate sampling frequency
    time_diffs = np.diff(data[COL_TIME])
    sampling_hz = 1.0 / np.median(time_diffs)

    # Design the Butterworth filter
    sos = butter(BUTTER_ORDER, CUTOFF_HZ_FALLBACK, 'low', fs=sampling_hz, output='sos')

    # Apply the filter to the HandZ column
    data['HandZ_filtered'] = sosfiltfilt(sos, data[COL_HANDZ])

    # Plot the original and filtered data
    plt.figure(figsize=(15, 7))
    plt.plot(data[COL_TIME], data[COL_HANDZ], label='Original HandZ', alpha=0.6)
    plt.plot(data[COL_TIME], data['HandZ_filtered'], label='Filtered HandZ', linewidth=2)
    plt.title('HandZ Data: Original vs. Butterworth Filtered')
    plt.xlabel('Timestamp')
    plt.ylabel('HandZ Position')
    plt.legend()
    plt.grid(True)
    plt.show()

