from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy.io import loadmat
from scipy.signal import find_peaks, savgol_filter


# ============================================================
# PATHS (portable for GitHub repo)
# ============================================================
# Script location:
#   code/force_plate/scripts/COP_peak_distance.py
#
# Repo root is 3 levels up:
#   scripts -> force_plate -> code -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

# Read raw .mat files from here
RAW_MAT_DIR = REPO_ROOT / "data" / "raw" / "force_plate"

# Save outputs here
OUT_DATA_DIR = REPO_ROOT / "results" / "force_plate"


# ============================================================
# DATA COLUMNS
# ============================================================
# These tell the script which columns contain COP x and y
COPX_COL = 0
COPY_COL = 1


# ============================================================
# DISTANCE-BASED SETTINGS
# ============================================================
# Use first 10 seconds to define the participant's neutral position
BASELINE_SEC = 10.0

# Light smoothing of total sway signal before peak detection
SMOOTH_WINDOW_SEC = 0.35
SMOOTH_POLYORDER = 3

# Peak detection settings for total sway distance
MIN_PEAK_DISTANCE_SEC = 0.75
MIN_PEAK_WIDTH_SEC = 0.05
HEIGHT_MAD_MULT = 1.0
PROM_MAD_MULT = 0.9
REFINE_WINDOW_SEC = 0.25

# Split the trial into 30-second blocks and keep top 2 peaks in each block
BLOCK_SEC = 30.0
TOP_N_PER_BLOCK = 2

# Stabilogram windows around each selected peak
CONTEXT_HALF_SEC = 5.0
HIGHLIGHT_HALF_SEC = 2.0


# ============================================================
# PLOT STYLE
# ============================================================
LW_CONTEXT = 1.1
LW_HIGHLIGHT = 2.6
ELLIPSE_LW = 2.8
PEAK_MARKER_SIZE = 120

CONTEXT_ELLIPSE_COLOR = "#00E5FF"
HIGHLIGHT_ELLIPSE_COLOR = "#39FF14"


# ============================================================
# FILE HELPERS
# ============================================================
def find_input_files() -> list[Path]:
    """Find all .mat files in the raw force_plate folder."""
    if not RAW_MAT_DIR.exists():
        raise FileNotFoundError(f"Working folder not found:\n  {RAW_MAT_DIR}")

    mats = sorted(RAW_MAT_DIR.glob("*.mat"))
    if not mats:
        raise FileNotFoundError(f"No .mat files found in:\n  {RAW_MAT_DIR}")

    return mats


def out_dir_for(mat_path: Path) -> Path:
    """Make an output folder for each .mat file."""
    stem = mat_path.stem
    out_dir = OUT_DATA_DIR / stem / "figures" / "distance"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


# ============================================================
# LOAD DATA
# ============================================================
def load_cop(mat_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load time, COPx, and COPy from the MATLAB file."""
    m = loadmat(mat_path)

    if "time" not in m:
        raise KeyError(f"'time' not found in {mat_path.name}")
    if "samples" not in m:
        raise KeyError(f"'samples' not found in {mat_path.name}")

    t = np.asarray(m["time"]).squeeze().astype(float)
    samples = np.asarray(m["samples"]).astype(float)

    if samples.ndim != 2:
        raise ValueError(f"'samples' is not 2D in {mat_path.name}. Got shape {samples.shape}")

    if COPX_COL >= samples.shape[1] or COPY_COL >= samples.shape[1]:
        raise IndexError(
            f"COPX_COL/COPY_COL out of range for {mat_path.name}. "
            f"samples has {samples.shape[1]} columns."
        )

    rx = samples[:, COPX_COL].astype(float)
    ry = samples[:, COPY_COL].astype(float)

    # Make all arrays the same length
    n = min(len(t), len(rx), len(ry))
    t = t[:n]
    rx = rx[:n]
    ry = ry[:n]

    # Reset time so the run starts at 0 s
    t = t - t[0]
    return t, rx, ry


def estimate_fs(t: np.ndarray) -> float:
    """Estimate the sampling frequency from the time vector."""
    dt = np.diff(t)
    dt = dt[np.isfinite(dt)]
    dt = dt[dt > 0]

    if len(dt) == 0:
        return 1.0

    return float(1.0 / np.median(dt))


# ============================================================
# NEUTRAL POINT STANDARDIZATION
# ============================================================
def compute_neutral_point(
    t: np.ndarray,
    rx: np.ndarray,
    ry: np.ndarray,
    baseline_sec: float = BASELINE_SEC,
) -> tuple[float, float]:
    """Use the first 10 seconds to set the neutral reference point."""
    mask = t <= baseline_sec
    if not np.any(mask):
        raise ValueError("No samples found in the baseline window.")

    x0 = float(np.mean(rx[mask]))
    y0 = float(np.mean(ry[mask]))
    return x0, y0


def recenter_to_neutral(
    rx: np.ndarray,
    ry: np.ndarray,
    x0: float,
    y0: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Shift COP so the neutral point becomes (0, 0)."""
    x_rel = rx - x0
    y_rel = ry - y0
    return x_rel, y_rel


def compute_total_sway_distance(x_rel: np.ndarray, y_rel: np.ndarray) -> np.ndarray:
    """Calculate total distance from neutral at each time point."""
    return np.sqrt(x_rel**2 + y_rel**2)


# ============================================================
# SIGNAL PROCESSING
# ============================================================
def smooth_signal(x: np.ndarray, fs: float) -> np.ndarray:
    """Smooth the signal slightly to reduce noise before peak detection."""
    n = len(x)
    if n < 7:
        return x.copy()

    window = max(5, int(round(SMOOTH_WINDOW_SEC * fs)))
    if window % 2 == 0:
        window += 1

    if window >= n:
        window = n - 1 if n % 2 == 0 else n

    if window < 5:
        return x.copy()

    if window % 2 == 0:
        window -= 1

    polyorder = min(SMOOTH_POLYORDER, window - 2)
    if polyorder < 1:
        return x.copy()

    return savgol_filter(x, window_length=window, polyorder=polyorder, mode="interp")


def robust_baseline_and_spread(x: np.ndarray) -> tuple[float, float]:
    """Get a robust baseline and spread for adaptive thresholds."""
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


def refine_peaks_to_raw(raw_signal: np.ndarray, coarse_peaks: np.ndarray, fs: float) -> np.ndarray:
    """After detecting peaks on the smoothed signal, snap them to the true raw maximum nearby."""
    if len(coarse_peaks) == 0:
        return np.array([], dtype=int)

    half_width = max(1, int(round(REFINE_WINDOW_SEC * fs)))
    refined = []

    for pk in coarse_peaks:
        left = max(0, pk - half_width)
        right = min(len(raw_signal), pk + half_width + 1)

        local = raw_signal[left:right]
        if len(local) == 0:
            continue

        refined.append(left + int(np.argmax(local)))

    return np.array(sorted(set(refined)), dtype=int)


def detect_candidate_distance_peaks(distance_raw: np.ndarray, fs: float):
    """Find candidate peaks on the total sway distance signal."""
    distance_smooth = smooth_signal(distance_raw, fs)

    baseline, spread = robust_baseline_and_spread(distance_smooth)
    height_threshold = baseline + HEIGHT_MAD_MULT * spread
    prominence_threshold = PROM_MAD_MULT * spread

    min_distance_samples = max(1, int(round(MIN_PEAK_DISTANCE_SEC * fs)))
    min_width_samples = max(1, int(round(MIN_PEAK_WIDTH_SEC * fs)))

    coarse_peaks, props = find_peaks(
        distance_smooth,
        height=height_threshold,
        prominence=prominence_threshold,
        distance=min_distance_samples,
        width=min_width_samples,
    )

    # If detection is too strict, relax it slightly
    if len(coarse_peaks) == 0:
        coarse_peaks, props = find_peaks(
            distance_smooth,
            height=baseline + 0.6 * spread,
            prominence=0.5 * spread,
            distance=min_distance_samples,
        )

    refined_peaks = refine_peaks_to_raw(distance_raw, coarse_peaks, fs)

    coarse_peaks = np.asarray(coarse_peaks, dtype=int)
    coarse_proms = np.asarray(props.get("prominences", np.zeros(len(coarse_peaks))), dtype=float)

    peak_heights = []
    peak_proms = []

    for rpk in refined_peaks:
        if len(coarse_peaks) == 0:
            continue
        j = int(np.argmin(np.abs(coarse_peaks - rpk)))
        peak_heights.append(float(distance_raw[rpk]))
        peak_proms.append(float(coarse_proms[j]))

    peak_heights = np.asarray(peak_heights, dtype=float)
    peak_proms = np.asarray(peak_proms, dtype=float)

    info = {
        "baseline": baseline,
        "spread": spread,
        "height_threshold": height_threshold,
        "prominence_threshold": prominence_threshold,
        "n_candidates": int(len(refined_peaks)),
    }

    return refined_peaks, peak_heights, peak_proms, distance_smooth, info


# ============================================================
# TOP N PEAKS PER 30-SECOND BLOCK
# ============================================================
def select_top_n_per_block(
    candidate_peaks: np.ndarray,
    peak_times: np.ndarray,
    peak_heights: np.ndarray,
    block_sec: float = BLOCK_SEC,
    top_n: int = TOP_N_PER_BLOCK,
) -> list[dict]:
    """In each 30-second block, keep the top N tallest peaks."""
    selected: list[dict] = []

    if len(candidate_peaks) == 0:
        return selected

    t_end = float(np.max(peak_times))
    n_blocks = int(np.ceil((t_end + 1e-9) / block_sec))

    for block_idx in range(n_blocks):
        t0 = block_idx * block_sec
        t1 = t0 + block_sec

        mask = (peak_times >= t0) & (peak_times < t1)
        block_peak_idx = candidate_peaks[mask]
        block_peak_times = peak_times[mask]
        block_peak_heights = peak_heights[mask]

        if len(block_peak_idx) == 0:
            continue

        order = np.argsort(block_peak_heights)[::-1]
        keep = order[:top_n]

        keep_sorted_by_time = keep[np.argsort(block_peak_times[keep])]

        for rank_num, local_k in enumerate(keep_sorted_by_time, start=1):
            selected.append(
                {
                    "block_index": block_idx,
                    "rank_in_block": rank_num,
                    "peak_idx": int(block_peak_idx[local_k]),
                    "peak_time": float(block_peak_times[local_k]),
                    "peak_height": float(block_peak_heights[local_k]),
                }
            )

    return selected


# ============================================================
# STABILOGRAM HELPERS
# ============================================================
def window_idx(t: np.ndarray, centre_time: float, half_window_sec: float) -> tuple[int, int]:
    """Get index bounds for a time window around a selected peak."""
    left = centre_time - half_window_sec
    right = centre_time + half_window_sec

    i0 = int(np.searchsorted(t, left, side="left"))
    i1 = int(np.searchsorted(t, right, side="right"))

    return max(0, i0), min(len(t), i1)


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


# ============================================================
# PLOTTING
# ============================================================
def add_30s_blocks(ax: plt.Axes, t_start: float, t_end: float):
    """Add alternating 30-second shading to the plot."""
    i = 0
    x = t_start
    while x < t_end:
        x2 = min(x + BLOCK_SEC, t_end)
        if i % 2 == 0:
            ax.axvspan(x, x2, alpha=0.10)
        i += 1
        x = x2


def plot_three_panel_distance(
    stem: str,
    t: np.ndarray,
    x_rel: np.ndarray,
    y_rel: np.ndarray,
    distance_raw: np.ndarray,
    selected_peak_indices: np.ndarray,
    out_path: Path,
):
    """Plot x sway, y sway, and total sway distance."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    t_end = float(t[-1])

    ax = axes[0]
    add_30s_blocks(ax, 0.0, t_end)
    ax.plot(t, x_rel, linewidth=LW_CONTEXT)
    if len(selected_peak_indices):
        ax.scatter(
            t[selected_peak_indices], x_rel[selected_peak_indices],
            marker="*", s=PEAK_MARKER_SIZE,
            color="red", edgecolors="black", linewidths=0.8, zorder=5
        )
    ax.set_ylabel("X sway (m)")
    ax.set_title(f"{stem} | X sway, Y sway, total sway distance")

    ax = axes[1]
    add_30s_blocks(ax, 0.0, t_end)
    ax.plot(t, y_rel, linewidth=LW_CONTEXT)
    if len(selected_peak_indices):
        ax.scatter(
            t[selected_peak_indices], y_rel[selected_peak_indices],
            marker="*", s=PEAK_MARKER_SIZE,
            color="red", edgecolors="black", linewidths=0.8, zorder=5
        )
    ax.set_ylabel("Y sway (m)")

    ax = axes[2]
    add_30s_blocks(ax, 0.0, t_end)
    ax.plot(t, distance_raw, linewidth=LW_CONTEXT)
    if len(selected_peak_indices):
        ax.scatter(
            t[selected_peak_indices], distance_raw[selected_peak_indices],
            marker="*", s=PEAK_MARKER_SIZE,
            color="red", edgecolors="black", linewidths=0.8, zorder=5
        )
    ax.set_ylabel("Total sway (m)")
    ax.set_xlabel("Time (s)")

    for ax in axes:
        ax.grid(True, alpha=0.35)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_distance_diagnostic(
    stem: str,
    t: np.ndarray,
    distance_raw: np.ndarray,
    distance_smooth: np.ndarray,
    candidate_peaks: np.ndarray,
    selected_peak_indices: np.ndarray,
    out_path: Path,
):
    """Plot raw and smoothed total sway with candidate and selected peaks."""
    fig, ax = plt.subplots(figsize=(14, 5))
    add_30s_blocks(ax, 0.0, float(t[-1]))

    ax.plot(t, distance_raw, linewidth=1.0, alpha=0.45, label="Raw total sway")
    ax.plot(t, distance_smooth, linewidth=1.4, label="Smoothed total sway")

    if len(candidate_peaks):
        ax.scatter(
            t[candidate_peaks], distance_raw[candidate_peaks],
            s=24, color="grey", alpha=0.7,
            label=f"Candidate peaks (n={len(candidate_peaks)})"
        )

    if len(selected_peak_indices):
        ax.scatter(
            t[selected_peak_indices], distance_raw[selected_peak_indices],
            marker="*", s=PEAK_MARKER_SIZE,
            color="red", edgecolors="black", linewidths=0.8, zorder=6,
            label=f"Selected peaks (n={len(selected_peak_indices)})"
        )

    ax.set_title(f"{stem} | Total sway distance peak selection")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Total sway (m)")
    ax.grid(True, alpha=0.35)
    ax.legend(loc="upper right")

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_peak_stabilogram_black_red(
    x: np.ndarray,
    y: np.ndarray,
    highlight_mask: np.ndarray,
    title: str,
    out_path: Path,
):
    """Plot the stabilogram around one selected peak."""
    if len(x) < 2:
        return

    fig, ax = plt.subplots(figsize=(8, 8))

    ax.plot(
        x, y,
        color="black", linewidth=LW_CONTEXT,
        label=f"Context ±{CONTEXT_HALF_SEC:.0f}s"
    )

    if np.any(highlight_mask):
        ax.plot(
            x[highlight_mask], y[highlight_mask],
            color="red", linewidth=LW_HIGHLIGHT,
            label=f"Highlight ±{HIGHLIGHT_HALF_SEC:.0f}s"
        )

    xe, ye = covariance_ellipse_points(x, y)
    if xe.size:
        ax.plot(
            xe, ye,
            linestyle="--", linewidth=ELLIPSE_LW,
            color=CONTEXT_ELLIPSE_COLOR,
            label="Context cov ellipse (1σ)"
        )

    xh = x[highlight_mask]
    yh = y[highlight_mask]
    xe2, ye2 = covariance_ellipse_points(xh, yh)
    if xe2.size:
        ax.plot(
            xe2, ye2,
            linestyle="--", linewidth=ELLIPSE_LW,
            color=HIGHLIGHT_ELLIPSE_COLOR,
            label="Highlight cov ellipse (1σ)"
        )

    ax.set_title(title)
    ax.set_xlabel("X sway from neutral (m)")
    ax.set_ylabel("Y sway from neutral (m)")
    ax.grid(True, alpha=0.4)
    ax.axis("equal")
    ax.legend(loc="lower left")

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


# ============================================================
# MAIN PER FILE
# ============================================================
def run_one_file(mat_path: Path):
    """Run the full neutral-standardized sway analysis on one file."""
    stem = mat_path.stem
    out_dir = out_dir_for(mat_path)

    t, rx, ry = load_cop(mat_path)
    fs = estimate_fs(t)

    # Set neutral reference point from first 10 seconds
    x0, y0 = compute_neutral_point(t, rx, ry, baseline_sec=BASELINE_SEC)

    # Convert raw COP into sway relative to neutral
    x_rel, y_rel = recenter_to_neutral(rx, ry, x0, y0)

    # Calculate total sway distance from neutral
    distance_raw = compute_total_sway_distance(x_rel, y_rel)

    # Detect candidate peaks on total sway distance
    candidate_peaks, peak_heights, peak_proms, distance_smooth, info = detect_candidate_distance_peaks(distance_raw, fs)
    peak_times = t[candidate_peaks] if len(candidate_peaks) else np.array([])

    # Keep top 2 peaks in each 30-second block
    selected = select_top_n_per_block(
        candidate_peaks=candidate_peaks,
        peak_times=peak_times,
        peak_heights=peak_heights,
        block_sec=BLOCK_SEC,
        top_n=TOP_N_PER_BLOCK,
    )

    selected_peak_indices = np.array([item["peak_idx"] for item in selected], dtype=int) if selected else np.array([], dtype=int)

    print(f"  File: {mat_path.name}")
    print(f"  fs:                    {fs:.3f} Hz")
    print(f"  Neutral point x0:      {x0:.6f} m")
    print(f"  Neutral point y0:      {y0:.6f} m")
    print(f"  Candidate peaks:       {len(candidate_peaks)}")
    print(f"  Selected peaks:        {len(selected_peak_indices)}")
    for item in selected:
        print(
            f"    block={item['block_index']:02d} "
            f"rank={item['rank_in_block']} "
            f"time={item['peak_time']:.2f}s "
            f"distance={item['peak_height']:.4f}m"
        )

    # Save the main 3-panel sway figure
    plot_three_panel_distance(
        stem=stem,
        t=t,
        x_rel=x_rel,
        y_rel=y_rel,
        distance_raw=distance_raw,
        selected_peak_indices=selected_peak_indices,
        out_path=out_dir / "Xsway_Ysway_TotalSway_3panel.png",
    )

    # Save the diagnostic peak-detection figure
    plot_distance_diagnostic(
        stem=stem,
        t=t,
        distance_raw=distance_raw,
        distance_smooth=distance_smooth,
        candidate_peaks=candidate_peaks,
        selected_peak_indices=selected_peak_indices,
        out_path=out_dir / "TotalSway_peak_detection.png",
    )

    # Save a stabilogram for each selected peak
    for global_num, item in enumerate(selected, start=1):
        pk_idx = item["peak_idx"]
        pk_time = item["peak_time"]
        block_idx = item["block_index"]
        rank_in_block = item["rank_in_block"]

        i0, i1 = window_idx(t, pk_time, CONTEXT_HALF_SEC)
        h0, h1 = window_idx(t, pk_time, HIGHLIGHT_HALF_SEC)

        x_win = x_rel[i0:i1]
        y_win = y_rel[i0:i1]

        highlight_mask = np.zeros(i1 - i0, dtype=bool)
        a = max(0, h0 - i0)
        b = max(0, h1 - i0)
        highlight_mask[a:b] = True

        plot_peak_stabilogram_black_red(
            x=x_win,
            y=y_win,
            highlight_mask=highlight_mask,
            title=(
                f"Block {block_idx:02d} | Peak rank {rank_in_block} | t = {pk_time:.2f} s\n"
                f"Context ±{CONTEXT_HALF_SEC:.0f}s (black), "
                f"Highlight ±{HIGHLIGHT_HALF_SEC:.0f}s (red)"
            ),
            out_path=out_dir / (
                f"Block_{block_idx:02d}_Rank_{rank_in_block}_"
                f"Peak_{global_num:02d}_stabilogram_black_red_ellipses.png"
            ),
        )


# ============================================================
# MAIN
# ============================================================
def main():
    """Run the analysis on all .mat files in the folder."""
    mats = find_input_files()

    print("=" * 70)
    print("COP DISTANCE ANALYSIS - NEUTRAL STANDARDIZED")
    print("=" * 70)
    print(f"Input MAT folder: {RAW_MAT_DIR}")
    print(f"Output root:      {OUT_DATA_DIR}")
    print(f"Found {len(mats)} MAT file(s).")
    print()

    for p in mats:
        print("-" * 70)
        print(f"Processing: {p.name}")
        run_one_file(p)
        print(f"  Saved to: {out_dir_for(p)}")
        print()

    print("=" * 70)
    print("Done.")
    print("=" * 70)


if __name__ == "__main__":
    main()