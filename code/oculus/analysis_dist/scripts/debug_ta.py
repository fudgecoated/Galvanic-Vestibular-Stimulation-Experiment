import pandas as pd
import numpy as np
from scipy.signal import find_peaks, butter, filtfilt
import sys

file_path = sys.argv[1] if len(sys.argv) > 1 else 'data/raw/oculus/TEST_ACCURACY_GRID_TRIAL_JUN_24_1_OCULUS_CLEAN.csv'
df = pd.read_csv(file_path)
z = df['HandZ'].values
t = df['seconds'].values

mask = ~(np.isnan(z) | np.isnan(t))
z = z[mask]
t = t[mask]
t_diff = np.diff(t)
t_diff[t_diff == 0] = 1e-6

fs_est = 1.0 / np.nanmean(t_diff)
print(f"Estimated fs: {fs_est:.2f} Hz")

nyq = 0.5 * fs_est
cutoff = min(12.0, nyq * 0.9) / nyq
b, a = butter(4, cutoff, btype='low')
zf = filtfilt(b, a, z)

zrange = np.ptp(zf)
dist_samples = max(1, int(fs_est * 0.2))

for prom in [0.005, 0.01, 0.02, zrange * 0.02, zrange * 0.05]:
    peaks, _ = find_peaks(zf, prominence=prom, distance=dist_samples)
    valid = peaks[zf[peaks] > 0.93]
    print(f"prominence={prom:.4f}: {len(peaks)} peaks total, {len(valid)} above 0.93")
    for p in valid[:5]:
        print(f"   t={t[p]:.2f}s, Z={zf[p]:.3f}")
