from __future__ import annotations

from pathlib import Path
import csv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
# Windows may require: python -m pip install tzdata
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from scipy.io import loadmat
from scipy.signal import butter, filtfilt, find_peaks, savgol_filter


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]

RAW_MAT_DIR = REPO_ROOT / "data" / "raw" / "force_plate"
OUT_RESULTS_ROOT = REPO_ROOT / "analysis" / "results"


# Arduino/force-plate synchronization settings
FORCE_PLATE_TIMEZONE = "America/Edmonton"
# Add to Arduino UTC timestamps only if an independently measured clock correction exists.
ARDUINO_CLOCK_CORRECTION_SEC = 0.0
ARDUINO_ON_THRESHOLD_V = 0.01
ACTIVE_BLOCKS = []


def choose_arduino_file():
    folder = REPO_ROOT / "data" / "raw" / "arduino"
    files = sorted(folder.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No Arduino CSV files in {folder}")
    for i, path in enumerate(files, 1):
        print(f"{i}. {path.name}")
    while True:
        try:
            i = int(input("Select matching Arduino CSV for this MAT recording: "))
            if 1 <= i <= len(files):
                return files[i - 1]
        except ValueError:
            pass
        print("Enter a listed file number.")


def aligned_arduino_blocks(mat_path, csv_path, trim_origin, duration):
    """Half-open ON/OFF intervals, relative to the actual retained first MAT sample.

    pc_time_utc is serial receipt time: clock agreement does not establish
    hardware synchronization. Uncovered recording sections remain UNKNOWN.
    """
    m = loadmat(mat_path, variable_names=["realtime"])
    fields = np.asarray(m["realtime"]).ravel()
    if fields.size != 6:
        raise ValueError("Expected six-component MAT realtime recording-start field")
    sec = float(fields[5])
    local = datetime(*map(int, fields[:5]), int(sec),
                     int(round((sec % 1) * 1e6)), tzinfo=ZoneInfo(FORCE_PLATE_TIMEZONE))
    start_utc = local.astimezone(timezone.utc).timestamp()
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if len(rows) < 2:
        raise ValueError("Arduino CSV needs at least two samples")
    stamps = np.array([datetime.fromisoformat(r["pc_time_utc"].replace("Z", "+00:00")).timestamp()
                       for r in rows])
    if np.any(np.diff(stamps) < 0):
        raise ValueError("Arduino PC timestamps run backwards; inspect clock/logging")
    device = np.array([float(r["device_ms"]) for r in rows])
    if np.any(np.diff(device) <= 0):
        raise ValueError("Arduino device clock reset or duplicate samples; split recording first")
    volts = np.array([float(r["output_v"]) for r in rows])
    if not np.all(np.isfinite(volts)):
        raise ValueError("Nonfinite Arduino voltage")
    times = stamps - start_utc - trim_origin + ARDUINO_CLOCK_CORRECTION_SEC
    states = np.abs(volts) > ARDUINO_ON_THRESHOLD_V
    edges = np.r_[0, np.flatnonzero(states[1:] != states[:-1]) + 1, len(rows)]
    blocks = []
    for a, b in zip(edges[:-1], edges[1:]):
        raw_start = float(times[a])
        raw_end = float(times[b]) if b < len(rows) else float(times[-1])
        left, right = max(0., raw_start), min(duration, raw_end)
        if right <= left:
            continue
        blocks.append(dict(block_index=len(blocks), state="ON" if states[a] else "OFF",
                           start=left, end=right, voltage=float(np.median(volts[a:b])),
                           onset_observed=bool(a > 0 and raw_start >= 0),
                           end_observed=bool(b < len(rows) and raw_end <= duration)))
    if not blocks:
        raise ValueError("No timestamp overlap: check matching files and timezone")
    print(f"Force plate start UTC: {local.astimezone(timezone.utc).isoformat()}")
    print(f"Arduino coverage on trimmed MAT timeline: {times[0]:.3f} to {times[-1]:.3f} s")
    return blocks


def save_block_table(out_dir):
    with open(out_dir / "arduino_aligned_blocks.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(ACTIVE_BLOCKS[0]))
        writer.writeheader()
        writer.writerows(ACTIVE_BLOCKS)


# ============================================================
# left forces   = samples[:, [0, 1, 2]]
# left moments  = samples[:, [3, 4, 5]]
# ============================================================
LEFT_FORCE_COLS = [0, 1, 2]    # Fx, Fy, Fz
LEFT_MOMENT_COLS = [3, 4, 5]   # Mx, My, Mz


# ============================================================
# CALIBRATION
# ============================================================
FORCE_CALIBRATION = np.diag([500.0, 500.0, 1000.0])
MOMENT_CALIBRATION = np.diag([800.0, 250.0, 400.0])


# ============================================================
# CORE PROCESSING SETTINGS
# ============================================================
# If True, sample rate will be estimated from the time vector.
# If False, FORCE_FREQUENCY_HZ below will be used.
USE_TIME_VECTOR_FOR_FS = True
FORCE_FREQUENCY_HZ = 960.0

# Optional trimming before any baseline/COP/velocity analysis
TRIM_START_SEC = 55.0
TRIM_END_SEC = 0.0

# Force/moment filtering before COP calculation
APPLY_FORCE_MOMENT_FILTER = True
FILTER_ORDER = 3
FILTER_CUTOFF_HZ = 25.0

# Small COP smoothing before differentiation to reduce noisy velocity
APPLY_COP_SMOOTHING_BEFORE_VELOCITY = True
COP_SMOOTH_WINDOW_SEC = 0.05
COP_SMOOTH_POLYORDER = 2

# Optional smoothing of resultant velocity before peak detection
APPLY_VELOCITY_SMOOTHING = True
VELOCITY_SMOOTH_WINDOW_SEC = 0.10
VELOCITY_SMOOTH_POLYORDER = 2


# ============================================================
# BASELINE / PEAK DETECTION SETTINGS
# ============================================================
# Adjustable baseline window
BASELINE_WINDOW_SEC = 10.0

# Threshold based on baseline distribution of resultant velocity
BASELINE_PERCENTILE = 95

# Peak detection settings
MIN_PEAK_DISTANCE_SEC = 2.0
MIN_PEAK_WIDTH_SEC = 0.03
MIN_PEAK_PROMINENCE = 0.02   # in Vr units after true COP velocity calculation

# Optional cap on number of peaks kept overall (None = keep all)
MAX_SELECTED_PEAKS = None

# Optional block-based selection
USE_BLOCK_SELECTION = True
BLOCK_SEC = 30.0
TOP_N_PER_BLOCK = 3


# ============================================================
# COP SAFETY SETTINGS
# ============================================================
# Avoid division instability when Fz is too small
MIN_ABS_FZ = 1e-6  # makes sure we are not dividing by 0 / near-0 Fz

# Neutral point for descriptive reporting only (not required for velocity detection)
NEUTRAL_WINDOW_SEC = 10.0
NEUTRAL_METHOD = "median"   # switch to "mean" if needed


# ============================================================
# STABILOGRAM WINDOWS
# ============================================================
CONTEXT_HALF_SEC = 5.0
HIGHLIGHT_HALF_SEC = 2.0


# ============================================================
# STABILOGRAM DISPLAY SETTINGS
# ============================================================
STAB_PLOT_SMOOTH_WINDOW = 9
STAB_PLOT_SMOOTH_POLYORDER = 2
STAB_INTERP_FACTOR = 6

LW_CONTEXT = 1.4
LW_HIGHLIGHT = 2.6
ELLIPSE_LW = 2.8
PEAK_MARKER_SIZE = 120

CONTEXT_ELLIPSE_COLOR = "black"
HIGHLIGHT_ELLIPSE_COLOR = "red"

CONTEXT_GRADIENT_START = "#163D99"   # deep blue
CONTEXT_GRADIENT_END = "#B9E3FF"     # pale blue

HIGHLIGHT_GRADIENT_START = "#C96A1B" # warm orange
HIGHLIGHT_GRADIENT_END = "#FFF2A8"   # soft yellow


# ============================================================
# GENERAL HELPERS
# ============================================================
def find_input_files() -> list[Path]:
    """Find all .mat files in the repo's interim force plate folder."""
    if not RAW_MAT_DIR.exists():
        raise FileNotFoundError(
            f"Input folder not found:\n  {RAW_MAT_DIR}\n\n"
            f"Expected repo structure:\n"
            f"  repo_root/data/interim/force_plate/"
        )

    mats = sorted(RAW_MAT_DIR.glob("*.mat"))
    if not mats:
        raise FileNotFoundError(f"No .mat files found in:\n  {RAW_MAT_DIR}")
    return mats


def choose_input_files() -> list[Path]:
    """
    Show all .mat files and ask whether to process:
    1. All files
    2+. One specific file
    """
    mats = find_input_files()

    print("=" * 70)
    print("AVAILABLE .MAT FILES")
    print("=" * 70)
    print(" 1. ALL FILES")
    for i, p in enumerate(mats, start=2):
        print(f"{i:>2}. {p.name}")
    print("=" * 70)

    while True:
        user_input = input("Select file to analyse: ").strip()
        try:
            idx = int(user_input)
            if idx == 1:
                return mats
            if 2 <= idx <= len(mats) + 1:
                return [mats[idx - 2]]
            print(f"Please enter a number from 1 to {len(mats) + 1}.")
        except ValueError:
            print("Invalid input. Please enter a number.")


def out_dir_for(mat_path: Path) -> Path:
    """
    Make an output folder for one .mat file:

    analysis/results/<file_stem>/figures/velocity/
    """
    stem = mat_path.stem
    out_dir = OUT_RESULTS_ROOT / stem / "figures" / "velocity"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def estimate_fs(t: np.ndarray) -> float:
    """Estimate sampling frequency from the time vector."""
    dt = np.diff(t)
    dt = dt[np.isfinite(dt)]
    dt = dt[dt > 0]
    if len(dt) == 0:
        return 1.0
    return float(1.0 / np.median(dt))


def trim_time_series(
    t: np.ndarray,
    arrays: list[np.ndarray],
    trim_start_sec: float,
    trim_end_sec: float,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Trim the beginning and/or end of a time series and aligned arrays."""
    if len(t) == 0:
        return t, arrays

    t_start = float(t[0]) + max(0.0, trim_start_sec)
    t_end = float(t[-1]) - max(0.0, trim_end_sec)

    if t_end <= t_start:
        raise ValueError(
            f"Invalid trimming: start trim {trim_start_sec}s and end trim {trim_end_sec}s "
            f"remove all data."
        )

    mask = (t >= t_start) & (t <= t_end)
    t_trim = t[mask]
    out_arrays = [arr[mask] for arr in arrays]

    # reset time to start at 0
    t_trim = t_trim - t_trim[0]
    return t_trim, out_arrays


def smooth_signal_time_based(
    x: np.ndarray,
    fs: float,
    window_sec: float,
    polyorder: int,
) -> np.ndarray:
    """Savitzky-Golay smoothing with a time-based window."""
    n = len(x)
    if n < 7:
        return x.copy()

    window = max(5, int(round(window_sec * fs)))
    if window % 2 == 0:
        window += 1
    if window >= n:
        window = n - 1 if n % 2 == 0 else n
    if window < 5:
        return x.copy()
    if window % 2 == 0:
        window -= 1

    polyorder = min(polyorder, window - 2)
    if polyorder < 1:
        return x.copy()

    return savgol_filter(x, window_length=window, polyorder=polyorder, mode="interp")


def robust_baseline_and_spread(x: np.ndarray) -> tuple[float, float]:
    """Robust centre/spread summary."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]

    if len(x) == 0:
        return 0.0, 1.0

    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    sigma = 1.4826 * mad
    if sigma <= 1e-12:
        sigma = max(float(np.std(x)), 1e-9)
    return med, sigma


def window_idx(t: np.ndarray, centre_time: float, half_window_sec: float) -> tuple[int, int]:
    """Get index bounds for a time window around a centre time."""
    left = centre_time - half_window_sec
    right = centre_time + half_window_sec
    i0 = int(np.searchsorted(t, left, side="left"))
    i1 = int(np.searchsorted(t, right, side="right"))
    return max(0, i0), min(len(t), i1)


# ============================================================
# LOAD RAW FORCE/MOMENT DATA
# ============================================================
def load_raw_mat(mat_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load samples and time from the MATLAB file."""
    m = loadmat(mat_path)

    if "samples" not in m:
        raise KeyError(f"'samples' not found in {mat_path.name}")
    if "time" not in m:
        raise KeyError(f"'time' not found in {mat_path.name}")

    samples = np.asarray(m["samples"], dtype=float)
    t = np.asarray(m["time"]).squeeze().astype(float)

    if samples.ndim != 2:
        raise ValueError(f"'samples' is not 2D in {mat_path.name}. Got shape {samples.shape}")
    if samples.shape[1] < 6:
        raise ValueError(f"'samples' has too few columns in {mat_path.name}: {samples.shape[1]}")

    n = min(len(t), samples.shape[0])
    t = t[:n]
    samples = samples[:n, :]

    # start time at 0
    t = t - t[0]
    return t, samples


def calibrate_left_force_moment(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Extract left-side force/moment channels and apply calibration.
    """
    left_forces_raw = samples[:, LEFT_FORCE_COLS]
    left_moments_raw = samples[:, LEFT_MOMENT_COLS]

    left_forces = left_forces_raw @ FORCE_CALIBRATION
    left_moments = left_moments_raw @ MOMENT_CALIBRATION

    return left_forces, left_moments


def butterworth_lowpass(data: np.ndarray, fs: float, cutoff_hz: float, order: int) -> np.ndarray:
    """Apply zero-phase Butterworth low-pass filtering column-wise."""
    if cutoff_hz <= 0:
        return data.copy()

    nyq = 0.5 * fs
    wn = cutoff_hz / nyq
    if wn >= 1.0:
        return data.copy()

    b, a = butter(order, wn, btype="low")
    return filtfilt(b, a, data, axis=0)


def compute_true_cop_from_left_plate(
    left_forces: np.ndarray,
    left_moments: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute true COP from left force plate:

        COPy = Mx / Fz
        COPx = -My / Fz

    Returns:
        rx = COPx
        ry = COPy
        fz = Fz
    """
    fx, fy, fz = left_forces[:, 0], left_forces[:, 1], left_forces[:, 2]
    mx, my, mz = left_moments[:, 0], left_moments[:, 1], left_moments[:, 2]

    safe_fz = np.where(np.abs(fz) < MIN_ABS_FZ, np.nan, fz)

    ry = mx / safe_fz
    rx = -my / safe_fz

    #Temporarily swap plate x and y
    rx, ry = ry, rx

    # Reverse the new x direction — only if confirmed
    rx = -rx
    
    return rx, ry, fz


def compute_neutral_point(rx: np.ndarray, ry: np.ndarray, t: np.ndarray) -> tuple[float, float]:
    """
    Compute neutral point (adjustable window).
    """
    mask = t <= NEUTRAL_WINDOW_SEC
    if not np.any(mask):
        mask = np.ones_like(t, dtype=bool)

    if NEUTRAL_METHOD.lower() == "mean":
        return float(np.mean(rx[mask])), float(np.mean(ry[mask]))
    else:
        return float(np.median(rx[mask])), float(np.median(ry[mask]))


# ============================================================
# VELOCITY CALCULATION
# ============================================================
def compute_cop_velocity(rx: np.ndarray, ry: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute COP velocity from true COP.

        vx = diff(rx) * fs
        vy = diff(ry) * fs
        vr = sqrt(vx^2 + vy^2)
    """
    rx_use = rx.copy()
    ry_use = ry.copy()

    if APPLY_COP_SMOOTHING_BEFORE_VELOCITY:
        rx_use = smooth_signal_time_based(rx_use, fs, COP_SMOOTH_WINDOW_SEC, COP_SMOOTH_POLYORDER)
        ry_use = smooth_signal_time_based(ry_use, fs, COP_SMOOTH_WINDOW_SEC, COP_SMOOTH_POLYORDER)

    vx = np.diff(rx_use) * fs
    vy = np.diff(ry_use) * fs
    vr = np.sqrt(vx ** 2 + vy ** 2)

    return vx, vy, vr


# ============================================================
# BASELINE + PEAK DETECTION
# ============================================================
def baseline_threshold_from_percentile(signal: np.ndarray, t_signal: np.ndarray) -> tuple[float, dict]:
    """
    Compute an absolute peak threshold from the baseline window using a percentile.
    """
    mask = t_signal <= BASELINE_WINDOW_SEC
    if not np.any(mask):
        mask = np.ones_like(t_signal, dtype=bool)

    baseline_vals = signal[mask]
    baseline_vals = baseline_vals[np.isfinite(baseline_vals)]

    if len(baseline_vals) == 0:
        threshold = np.nan
        info = {
            "baseline_n": 0,
            "baseline_percentile": BASELINE_PERCENTILE,
            "threshold": threshold,
            "baseline_median": np.nan,
            "baseline_sigma_robust": np.nan,
        }
        return threshold, info

    baseline_median, baseline_sigma = robust_baseline_and_spread(baseline_vals)
    threshold = float(np.percentile(baseline_vals, BASELINE_PERCENTILE))

    info = {
        "baseline_n": int(len(baseline_vals)),
        "baseline_percentile": BASELINE_PERCENTILE,
        "threshold": threshold,
        "baseline_median": baseline_median,
        "baseline_sigma_robust": baseline_sigma,
    }
    return threshold, info


def detect_velocity_peaks(vr_raw: np.ndarray, tv: np.ndarray, fs: float):
    """
    Detect peaks on resultant COP velocity using:
    - baseline percentile threshold
    - minimum prominence
    - minimum distance
    - optional minimum width
    """
    vr_use = vr_raw.copy()
    if APPLY_VELOCITY_SMOOTHING:
        vr_use = smooth_signal_time_based(vr_use, fs, VELOCITY_SMOOTH_WINDOW_SEC, VELOCITY_SMOOTH_POLYORDER)

    absolute_threshold, baseline_info = baseline_threshold_from_percentile(vr_use, tv)

    min_distance_samples = max(1, int(round(MIN_PEAK_DISTANCE_SEC * fs)))
    min_width_samples = max(1, int(round(MIN_PEAK_WIDTH_SEC * fs)))

    peaks, props = find_peaks(
        vr_use,
        height=absolute_threshold,
        prominence=MIN_PEAK_PROMINENCE,
        distance=min_distance_samples,
        width=min_width_samples,
    )

    peak_heights = vr_use[peaks] if len(peaks) else np.array([], dtype=float)
    peak_proms = np.asarray(props.get("prominences", np.zeros(len(peaks))), dtype=float)

    info = {
        "absolute_threshold": absolute_threshold,
        "baseline_info": baseline_info,
        "n_candidates": int(len(peaks)),
    }

    return peaks.astype(int), peak_heights, peak_proms, vr_use, info


def select_top_n_per_block(
    candidate_peaks: np.ndarray,
    peak_times: np.ndarray,
    peak_heights: np.ndarray,
    block_sec: float = BLOCK_SEC,
    top_n: int = TOP_N_PER_BLOCK,
) -> list[dict]:
    """In each block, keep the top N tallest peaks."""
    selected = []
    for block in ACTIVE_BLOCKS:
        mask = (peak_times >= block["start"]) & (peak_times < block["end"])
        indices = np.flatnonzero(mask)
        keep = indices[np.argsort(peak_heights[indices])[::-1][:top_n]]
        for rank, k in enumerate(keep, 1):
            selected.append(dict(block_index=block["block_index"], rank_in_block=rank,
                                 peak_idx=int(candidate_peaks[k]), peak_time=float(peak_times[k]),
                                 peak_height=float(peak_heights[k])))
    return sorted(selected, key=lambda p: p["peak_time"])


def select_final_peaks(candidate_peaks: np.ndarray, peak_times: np.ndarray, peak_heights: np.ndarray) -> list[dict]:
    """
    Final peak selection logic:
    - optionally top N per block
    - otherwise keep all
    - optionally cap total number kept
    """
    if len(candidate_peaks) == 0:
        return []

    if USE_BLOCK_SELECTION:
        selected = select_top_n_per_block(
            candidate_peaks=candidate_peaks,
            peak_times=peak_times,
            peak_heights=peak_heights,
            block_sec=BLOCK_SEC,
            top_n=TOP_N_PER_BLOCK,
        )
    else:
        selected = [
            {
                "block_index": 0,
                "rank_in_block": i + 1,
                "peak_idx": int(pk),
                "peak_time": float(pt),
                "peak_height": float(ph),
            }
            for i, (pk, pt, ph) in enumerate(zip(candidate_peaks, peak_times, peak_heights))
        ]

    if MAX_SELECTED_PEAKS is not None and len(selected) > MAX_SELECTED_PEAKS:
        selected = sorted(selected, key=lambda d: d["peak_height"], reverse=True)[:MAX_SELECTED_PEAKS]
        selected = sorted(selected, key=lambda d: d["peak_time"])

    return selected


# ============================================================
# STABILOGRAM DISPLAY HELPERS
# ============================================================
def covariance_ellipse_points(
    x: np.ndarray,
    y: np.ndarray,
    n_std: float = 1.0,
    n_points: int = 220,
):
    """Build a covariance ellipse for the stabilogram."""
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]

    if len(x) < 8:
        return np.array([]), np.array([])

    C = np.cov(np.column_stack([x, y]), rowvar=False)
    mean = np.array([np.mean(x), np.mean(y)])

    eigvals, eigvecs = np.linalg.eigh(C)
    order = np.argsort(eigvals)[::-1]
    eigvals = np.maximum(eigvals[order], 0.0)
    eigvecs = eigvecs[:, order]

    a, b = n_std * np.sqrt(eigvals)
    theta = np.linspace(0, 2 * np.pi, n_points)
    circle = np.vstack([np.cos(theta), np.sin(theta)])
    ellipse = (eigvecs @ np.diag([a, b]) @ circle).T + mean
    return ellipse[:, 0], ellipse[:, 1]


def make_segments(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Convert x/y points into line segments for gradient plotting."""
    points = np.column_stack((x, y)).reshape(-1, 1, 2)
    return np.concatenate([points[:-1], points[1:]], axis=1)


def make_custom_cmap(color_start: str, color_end: str) -> LinearSegmentedColormap:
    """Create a custom 2-colour gradient map."""
    return LinearSegmentedColormap.from_list(
        "custom_time_gradient",
        [color_start, color_end]
    )


def smooth_for_plot(x: np.ndarray, window: int = STAB_PLOT_SMOOTH_WINDOW, polyorder: int = STAB_PLOT_SMOOTH_POLYORDER) -> np.ndarray:
    """Light smoothing for stabilogram display only."""
    x = np.asarray(x, dtype=float)
    n = len(x)

    if n < 7:
        return x.copy()

    window = min(window, n if n % 2 == 1 else n - 1)
    if window < 5:
        return x.copy()
    if window % 2 == 0:
        window -= 1

    polyorder = min(polyorder, window - 2)
    if polyorder < 1:
        return x.copy()

    return savgol_filter(x, window_length=window, polyorder=polyorder, mode="interp")


def upsample_path(x: np.ndarray, y: np.ndarray, t: np.ndarray, factor: int = STAB_INTERP_FACTOR):
    """Increase point density so the stabilogram gradient looks smoother."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    t = np.asarray(t, dtype=float)

    if len(x) < 2 or factor <= 1:
        return x, y, t

    idx = np.arange(len(x), dtype=float)
    idx_new = np.linspace(0, len(x) - 1, len(x) * factor)

    x_new = np.interp(idx_new, idx, x)
    y_new = np.interp(idx_new, idx, y)
    t_new = np.interp(idx_new, idx, t)

    return x_new, y_new, t_new


def prepare_stabilogram_path(x: np.ndarray, y: np.ndarray, t: np.ndarray):
    """Smooth and densify path for cleaner plotting only."""
    x_s = smooth_for_plot(x)
    y_s = smooth_for_plot(y)
    x_u, y_u, t_u = upsample_path(x_s, y_s, t, factor=STAB_INTERP_FACTOR)
    return x_u, y_u, t_u


def plot_gradient_line_by_time(
    ax: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    t: np.ndarray,
    color_start: str,
    color_end: str,
    linewidth: float,
    alpha: float = 1.0,
    zorder: int = 2,
    show_start_end: bool = False,
):
    """
    Plot a trajectory with segment colour representing time progression.

    Start = start colour
    Finish = end colour
    """
    if len(x) < 2 or len(y) < 2 or len(t) < 2:
        return None

    segments = make_segments(x, y)
    seg_t = 0.5 * (t[:-1] + t[1:])

    t0 = float(seg_t.min())
    t1 = float(seg_t.max())
    if abs(t1 - t0) < 1e-12:
        values = np.zeros_like(seg_t)
    else:
        values = (seg_t - t0) / (t1 - t0)

    cmap = make_custom_cmap(color_start, color_end)

    lc = LineCollection(
        segments,
        cmap=cmap,
        linewidths=linewidth,
        alpha=alpha,
        zorder=zorder,
        capstyle="round",
        joinstyle="round",
    )
    lc.set_array(values)
    ax.add_collection(lc)

    if show_start_end:
        ax.scatter(
            x[0], y[0],
            s=70, marker="o",
            color=color_start, edgecolors="black", linewidths=0.8,
            zorder=zorder + 2,
        )
        ax.scatter(
            x[-1], y[-1],
            s=90, marker="X",
            color=color_end, edgecolors="black", linewidths=0.8,
            zorder=zorder + 2,
        )

    return cmap


def add_bottom_right_legend_block(
    ax: plt.Axes,
    context_cmap: LinearSegmentedColormap,
    highlight_cmap: LinearSegmentedColormap,
):
    """Legend block."""
    grad = np.linspace(0, 1, 256)[None, :]

    ellipse_handles = [
        Line2D([0], [0], color=CONTEXT_ELLIPSE_COLOR, lw=ELLIPSE_LW, linestyle="--",
               label="Context ellipse (1σ)"),
        Line2D([0], [0], color=HIGHLIGHT_ELLIPSE_COLOR, lw=ELLIPSE_LW, linestyle="--",
               label="Highlight ellipse (1σ)"),
    ]
    leg = ax.legend(
        handles=ellipse_handles,
        loc="lower right",
        bbox_to_anchor=(0.995, 0.005),
        framealpha=0.9,
        borderpad=0.35,
        labelspacing=0.35,
        handlelength=2.0,
        handletextpad=0.5,
    )
    ax.add_artist(leg)

    ax_c = inset_axes(
        ax,
        width="24%",
        height="2.9%",
        loc="lower right",
        bbox_to_anchor=(0.0, 0.115, 1.0, 1.0),
        bbox_transform=ax.transAxes,
        borderpad=0.8,
    )
    ax_c.imshow(grad, aspect="auto", cmap=context_cmap, origin="lower")
    ax_c.set_xticks([0, 255])
    ax_c.set_xticklabels(["start", "finish"], fontsize=8)
    ax_c.set_yticks([])
    ax_c.set_title("Context", fontsize=9, pad=2)
    for spine in ax_c.spines.values():
        spine.set_linewidth(0.8)

    ax_h = inset_axes(
        ax,
        width="24%",
        height="2.9%",
        loc="lower right",
        bbox_to_anchor=(0.0, 0.185, 1.0, 1.0),
        bbox_transform=ax.transAxes,
        borderpad=0.8,
    )
    ax_h.imshow(grad, aspect="auto", cmap=highlight_cmap, origin="lower")
    ax_h.set_xticks([0, 255])
    ax_h.set_xticklabels(["start", "finish"], fontsize=8)
    ax_h.set_yticks([])
    ax_h.set_title("Highlight", fontsize=9, pad=2)
    for spine in ax_h.spines.values():
        spine.set_linewidth(0.8)


# ============================================================
# MAIN PLOTTING
# ============================================================
def add_30s_blocks(ax: plt.Axes, t_start: float, t_end: float):
    """Shade actual Arduino ON intervals; OFF intervals are unshaded."""
    for block in ACTIVE_BLOCKS:
        if block["state"] == "ON":
            ax.axvspan(block["start"], block["end"], color="orange", alpha=0.15)
            ax.text((block["start"] + block["end"]) / 2, .98,
                    f'{block["voltage"]:g} V', transform=ax.get_xaxis_transform(),
                    ha="center", va="top", fontsize=7)
        if block["onset_observed"]:
            ax.axvline(block["start"], color="darkorange" if block["state"] == "ON" else "gray",
                       linestyle="--", linewidth=.7)


def plot_three_panel_velocity(
    stem: str,
    tv: np.ndarray,
    vx: np.ndarray,
    vy: np.ndarray,
    vr: np.ndarray,
    selected_peak_indices: np.ndarray,
    out_path: Path,
):
    """Plot Vx, Vy, and resultant velocity."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    t_end = float(tv[-1])

    ax = axes[0]
    add_30s_blocks(ax, 0.0, t_end)
    ax.plot(tv, vx, linewidth=LW_CONTEXT)
    if len(selected_peak_indices):
        ax.scatter(
            tv[selected_peak_indices], vx[selected_peak_indices],
            marker="*", s=PEAK_MARKER_SIZE, color="red",
            edgecolors="black", linewidths=0.8, zorder=5
        )
    ax.set_ylabel("Vx")
    ax.set_title(f"{stem} | True COP velocity (left plate)")

    ax = axes[1]
    add_30s_blocks(ax, 0.0, t_end)
    ax.plot(tv, vy, linewidth=LW_CONTEXT)
    if len(selected_peak_indices):
        ax.scatter(
            tv[selected_peak_indices], vy[selected_peak_indices],
            marker="*", s=PEAK_MARKER_SIZE, color="red",
            edgecolors="black", linewidths=0.8, zorder=5
        )
    ax.set_ylabel("Vy")

    ax = axes[2]
    add_30s_blocks(ax, 0.0, t_end)
    ax.plot(tv, vr, linewidth=LW_CONTEXT)
    if len(selected_peak_indices):
        ax.scatter(
            tv[selected_peak_indices], vr[selected_peak_indices],
            marker="*", s=PEAK_MARKER_SIZE, color="red",
            edgecolors="black", linewidths=0.8, zorder=5
        )
    ax.set_ylabel("Vr")
    ax.set_xlabel("Time (s)")

    for ax in axes:
        ax.grid(True, alpha=0.35)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_velocity_diagnostic(
    stem: str,
    tv: np.ndarray,
    vr_raw: np.ndarray,
    vr_smooth: np.ndarray,
    absolute_threshold: float,
    candidate_peaks: np.ndarray,
    selected_peak_indices: np.ndarray,
    out_path: Path,
):
    """Plot raw and smoothed resultant velocity with threshold and peaks."""
    fig, ax = plt.subplots(figsize=(14, 5))
    add_30s_blocks(ax, 0.0, float(tv[-1]))

    ax.plot(tv, vr_raw, linewidth=1.0, alpha=0.45, label="Raw Vr")
    ax.plot(tv, vr_smooth, linewidth=1.4, label="Smoothed Vr")

    if np.isfinite(absolute_threshold):
        ax.axhline(absolute_threshold, linestyle="--", linewidth=1.2, alpha=0.8, label="Baseline percentile threshold")

    if len(candidate_peaks):
        ax.scatter(
            tv[candidate_peaks], vr_smooth[candidate_peaks],
            s=24, color="grey", alpha=0.7,
            label=f"Candidate peaks (n={len(candidate_peaks)})"
        )

    if len(selected_peak_indices):
        ax.scatter(
            tv[selected_peak_indices], vr_smooth[selected_peak_indices],
            marker="*", s=PEAK_MARKER_SIZE,
            color="red", edgecolors="black", linewidths=0.8, zorder=6,
            label=f"Selected peaks (n={len(selected_peak_indices)})"
        )

    ax.set_title(f"{stem} | Resultant velocity peak detection")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Vr")
    ax.grid(True, alpha=0.35)
    ax.legend(loc="upper right")

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_peak_stabilogram_gradient(
    x: np.ndarray,
    y: np.ndarray,
    t_win: np.ndarray,
    highlight_mask: np.ndarray,
    title: str,
    out_path: Path,
):
    """Plot stabilogram around one selected peak."""
    if len(x) < 2:
        return

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_axes([0.11, 0.10, 0.82, 0.82])

    context_cmap = make_custom_cmap(CONTEXT_GRADIENT_START, CONTEXT_GRADIENT_END)
    highlight_cmap = make_custom_cmap(HIGHLIGHT_GRADIENT_START, HIGHLIGHT_GRADIENT_END)

    x_plot, y_plot, t_plot = prepare_stabilogram_path(x, y, t_win)

    plot_gradient_line_by_time(
        ax=ax,
        x=x_plot,
        y=y_plot,
        t=t_plot,
        color_start=CONTEXT_GRADIENT_START,
        color_end=CONTEXT_GRADIENT_END,
        linewidth=LW_CONTEXT,
        alpha=0.65,
        zorder=2,
        show_start_end=True,
    )

    xh = x[highlight_mask]
    yh = y[highlight_mask]
    if np.any(highlight_mask) and len(xh) >= 2:
        th = t_win[highlight_mask]
        xh_plot, yh_plot, th_plot = prepare_stabilogram_path(xh, yh, th)

        plot_gradient_line_by_time(
            ax=ax,
            x=xh_plot,
            y=yh_plot,
            t=th_plot,
            color_start=HIGHLIGHT_GRADIENT_START,
            color_end=HIGHLIGHT_GRADIENT_END,
            linewidth=LW_HIGHLIGHT,
            alpha=0.90,
            zorder=4,
            show_start_end=True,
        )

    xe, ye = covariance_ellipse_points(x, y)
    if xe.size:
        ax.plot(
            xe, ye,
            linestyle="--",
            linewidth=ELLIPSE_LW,
            color=CONTEXT_ELLIPSE_COLOR,
            zorder=5,
        )

    xe2, ye2 = covariance_ellipse_points(xh, yh)
    if xe2.size:
        ax.plot(
            xe2, ye2,
            linestyle="--",
            linewidth=ELLIPSE_LW,
            color=HIGHLIGHT_ELLIPSE_COLOR,
            zorder=6,
        )

    ax.set_title(title, fontsize=16, pad=14)
    ax.set_xlabel("COPx (m)")
    ax.set_ylabel("COPy (m)")
    ax.grid(True, alpha=0.35)
    # Equal physical scale, with symmetric limits around baseline
    limit = max(
        float(np.max(np.abs(x))),
        float(np.max(np.abs(y))),
        0.01,
    ) * 1.10

    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.set_aspect("equal", adjustable="box")

    ax.axhline(0, color="gray", linewidth=0.8)
    ax.axvline(0, color="gray", linewidth=0.8)

    add_bottom_right_legend_block(ax, context_cmap, highlight_cmap)

    fig.savefig(out_path, dpi=200)
    plt.close(fig)


# ============================================================
# RUN ONE FILE
# ============================================================
def run_one_file(mat_path: Path, arduino_path: Path | None = None) -> Path:
    """Run the full true-COP velocity analysis on one file."""
    global ACTIVE_BLOCKS
    ACTIVE_BLOCKS = []
    stem = mat_path.stem
    out_dir = out_dir_for(mat_path)

    # --------------------------------------------------------
    # Load raw data
    # --------------------------------------------------------
    t, samples = load_raw_mat(mat_path)

    # Preserve actual retained sample origin, not merely the requested trim duration.
    trim_origin = float(t[np.flatnonzero(t >= t[0] + max(0., TRIM_START_SEC))[0]])
    if arduino_path is None:
        arduino_path = choose_arduino_file()

    # Sampling frequency
    fs = estimate_fs(t) if USE_TIME_VECTOR_FOR_FS else FORCE_FREQUENCY_HZ

    # --------------------------------------------------------
    # Extract + calibrate left force/moment channels
    # --------------------------------------------------------
    left_forces, left_moments = calibrate_left_force_moment(samples)

    # Optional filtering before COP calculation
    if APPLY_FORCE_MOMENT_FILTER:
        left_forces = butterworth_lowpass(left_forces, fs, FILTER_CUTOFF_HZ, FILTER_ORDER)
        left_moments = butterworth_lowpass(left_moments, fs, FILTER_CUTOFF_HZ, FILTER_ORDER)

    # --------------------------------------------------------
    # Trim start/end before baseline and COP analysis
    # --------------------------------------------------------
    t, [left_forces, left_moments] = trim_time_series(
        t,
        [left_forces, left_moments],
        trim_start_sec=TRIM_START_SEC,
        trim_end_sec=TRIM_END_SEC,
    )

    ACTIVE_BLOCKS = aligned_arduino_blocks(mat_path, arduino_path, trim_origin, float(t[-1]))
    save_block_table(out_dir)

    # --------------------------------------------------------
    # Compute true COP from left plate
    # --------------------------------------------------------
    rx, ry, fz = compute_true_cop_from_left_plate(left_forces, left_moments)

    # Remove samples where Fz is unusable
    valid = np.isfinite(rx) & np.isfinite(ry) & np.isfinite(fz)
    t = t[valid]
    rx = rx[valid]
    ry = ry[valid]
    fz = fz[valid]

    if len(t) < 10:
        raise ValueError(f"Too few valid COP samples after processing in {mat_path.name}")

    # Neutral point for descriptive reporting
    neutral_x, neutral_y = compute_neutral_point(rx, ry, t)

    # Express COP relative to the first 10 seconds of standing (can delete if we odont want to start at 0,0)
    rx = rx - neutral_x
    ry = ry - neutral_y

    # --------------------------------------------------------
    # Compute velocity from true COP
    # --------------------------------------------------------
    vx, vy, vr = compute_cop_velocity(rx, ry, fs)
    tv = t[1:]

    # --------------------------------------------------------
    # Peak detection on resultant velocity
    # --------------------------------------------------------
    candidate_peaks, peak_heights, peak_proms, vr_use, info = detect_velocity_peaks(vr, tv, fs)
    peak_times = tv[candidate_peaks] if len(candidate_peaks) else np.array([])

    selected = select_final_peaks(candidate_peaks, peak_times, peak_heights)
    selected_peak_indices = np.array([item["peak_idx"] for item in selected], dtype=int) if selected else np.array([], dtype=int)

    # --------------------------------------------------------
    # Console reporting
    # --------------------------------------------------------
    print(f"  File: {mat_path.name}")
    print(f"  fs:                         {fs:.3f} Hz")
    print(f"  Trim start / end:           {TRIM_START_SEC:.2f}s / {TRIM_END_SEC:.2f}s")
    print(f"  Neutral point ({NEUTRAL_METHOD}): ({neutral_x:.6f}, {neutral_y:.6f})")
    print(f"  Baseline window:            first {BASELINE_WINDOW_SEC:.2f}s")
    print(f"  Baseline percentile:        {BASELINE_PERCENTILE}")
    print(f"  Threshold (Vr):             {info['absolute_threshold']:.6f}")
    print(f"  Candidate peaks:            {len(candidate_peaks)}")
    print(f"  Selected peaks:             {len(selected_peak_indices)}")
    for item in selected:
        print(
            f"    block={item['block_index']:02d} "
            f"rank={item['rank_in_block']} "
            f"time={item['peak_time']:.2f}s "
            f"height={item['peak_height']:.6f}"
        )

    # --------------------------------------------------------
    # Save plots
    # --------------------------------------------------------
    plot_three_panel_velocity(
        stem=stem,
        tv=tv,
        vx=vx,
        vy=vy,
        vr=vr_use,
        selected_peak_indices=selected_peak_indices,
        out_path=out_dir / "Vx_Vy_Vr_trueCOP_3panel.png",
    )

    plot_velocity_diagnostic(
        stem=stem,
        tv=tv,
        vr_raw=vr,
        vr_smooth=vr_use,
        absolute_threshold=info["absolute_threshold"],
        candidate_peaks=candidate_peaks,
        selected_peak_indices=selected_peak_indices,
        out_path=out_dir / "Vr_trueCOP_peak_detection.png",
    )

    # One stabilogram per selected peak
    for global_num, item in enumerate(selected, start=1):
        pk_time = item["peak_time"]
        block_idx = item["block_index"]
        rank_in_block = item["rank_in_block"]

        i0, i1 = window_idx(t, pk_time, CONTEXT_HALF_SEC)
        h0, h1 = window_idx(t, pk_time, HIGHLIGHT_HALF_SEC)

        rx_win = rx[i0:i1]
        ry_win = ry[i0:i1]
        t_win = t[i0:i1]

        # highlight indices must be relative to the context window start i0,
        # not the full signal.
        highlight_mask = np.zeros(i1 - i0, dtype=bool)
        a = max(0, h0 - i0)
        b = min(i1 - i0, h1 - i0)
        highlight_mask[a:b] = True

        plot_peak_stabilogram_gradient(
            x=rx_win,
            y=ry_win,
            t_win=t_win,
            highlight_mask=highlight_mask,
            title=(
                f"Block {block_idx:02d} {ACTIVE_BLOCKS[block_idx]['state']} ({ACTIVE_BLOCKS[block_idx]['voltage']:g} V) | Peak rank {rank_in_block} | t = {pk_time:.2f} s\n"
                f"Context ±{CONTEXT_HALF_SEC:.0f}s, Highlight ±{HIGHLIGHT_HALF_SEC:.0f}s"
            ),
            out_path=out_dir / (
                f"Block_{block_idx:02d}_Rank_{rank_in_block}_"
                f"Peak_{global_num:02d}_stabilogram_trueCOP_velocity.png"
            ),
        )

    return out_dir


# ============================================================
# MAIN
# ============================================================
def main():
    """Run the analysis on selected file(s)."""
    print("=" * 70)
    print("TRUE COP VELOCITY ANALYSIS (LEFT PLATE)")
    print("=" * 70)
    print(f"Repo root:        {REPO_ROOT}")
    print(f"Input MAT folder: {RAW_MAT_DIR}")
    print(f"Output root:      {OUT_RESULTS_ROOT}")
    print("-" * 70)

    selected_paths = choose_input_files()

    print(f"Files selected:   {len(selected_paths)}")
    print("-" * 70)

    for i, mat_path in enumerate(selected_paths, start=1):
        print(f"[{i}/{len(selected_paths)}] Processing: {mat_path.name}")
        out_dir = run_one_file(mat_path)
        print(f"Saved to: {out_dir}")
        print("-" * 70)

    print("=" * 70)
    print("Done.")
    print("=" * 70)


if __name__ == "__main__":
    main()