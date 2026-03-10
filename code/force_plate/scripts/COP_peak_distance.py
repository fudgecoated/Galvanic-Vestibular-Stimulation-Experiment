from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from scipy.io import loadmat
from scipy.signal import find_peaks, savgol_filter


# =========================
# PATHS (portable)
# =========================
REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_MAT_DIR = REPO_ROOT / "data" / "raw" / "force_plate"
OUT_DATA_DIR = REPO_ROOT / "results" / "force_plate"


# =========================
# DATA MAPPING
# =========================
COPX_COL = 0
COPY_COL = 1


# =========================
# DISTANCE DEFINITION
# =========================
# Reference centre (x0,y0) defined from mean COP over initial baseline window.
BASELINE_SEC_FOR_CENTER = 30.0


# =========================
# PEAK DETECTION (distance)
# =========================
MIN_PEAK_DISTANCE_SEC = 25.0   # allow ~1 peak per 30s block (tune)
MIN_PEAK_PROMINENCE = 0.005    # metres (tune)
N_PEAKS = 10                   # keep strongest N by prominence


# =========================
# SMOOTHING (helps distance peaks a lot)
# =========================
SMOOTH_WINDOW_SEC = 1.5
SAVGOL_POLYORDER = 3


# =========================
# STABILOGRAM WINDOWS (UPDATED)
# =========================
CONTEXT_HALF_SEC = 5.0     # ±5s in black
HIGHLIGHT_HALF_SEC = 2.0   # ±2s in red


# =========================
# 30s BLOCK SHADING
# =========================
BLOCK_SEC = 30.0


# =========================
# PLOT STYLE
# =========================
LW_CONTEXT = 1.1
LW_HIGHLIGHT = 2.6
ELLIPSE_LW = 2.8
PEAK_MARKER_SIZE = 120

# Ellipse colours
CONTEXT_ELLIPSE_COLOR = "#00E5FF"   # bright cyan / turquoise
HIGHLIGHT_ELLIPSE_COLOR = "#39FF14" # neon green


def find_input_files() -> list[Path]:
    if not RAW_MAT_DIR.exists():
        raise FileNotFoundError(f"Raw MAT folder not found:\n  {RAW_MAT_DIR}")
    mats = sorted(RAW_MAT_DIR.glob("*.mat"))
    if not mats:
        raise FileNotFoundError(f"No .mat files found in:\n  {RAW_MAT_DIR}")
    return mats


def out_dir_for(mat_path: Path) -> Path:
    stem = mat_path.stem
    out_dir = OUT_DATA_DIR / stem / "figures" / "distance"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def load_cop(mat_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    m = loadmat(mat_path)
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

    n = min(len(t), len(rx), len(ry))
    t, rx, ry = t[:n], rx[:n], ry[:n]

    t = t - t[0]  # reset time to 0
    return t, rx, ry


def estimate_fs(t: np.ndarray) -> float:
    dt = np.diff(t)
    dt = dt[np.isfinite(dt)]
    dt = dt[dt > 0]
    if len(dt) == 0:
        return 1.0
    return float(1.0 / np.median(dt))


def baseline_center(t: np.ndarray, rx: np.ndarray, ry: np.ndarray) -> tuple[float, float]:
    """
    Compute (x0,y0) as mean COP position during first BASELINE_SEC_FOR_CENTER seconds.
    """
    if len(t) == 0:
        return 0.0, 0.0

    mask = t <= BASELINE_SEC_FOR_CENTER
    if np.sum(mask) < 10:
        return float(np.mean(rx)), float(np.mean(ry))
    return float(np.mean(rx[mask])), float(np.mean(ry[mask]))


def sway_distance_vector_magnitude(rx: np.ndarray, ry: np.ndarray, x0: float, y0: float) -> np.ndarray:
    """
    Distance of COP from (x0,y0) using vector magnitude (Pythagoras):
      r(t) = || [rx(t)-x0, ry(t)-y0] ||_2
    """
    dx = rx - x0
    dy = ry - y0
    return np.sqrt(dx * dx + dy * dy)


def smooth_signal_savgol(s: np.ndarray, fs: float) -> np.ndarray:
    win = int(round(SMOOTH_WINDOW_SEC * fs))
    if win < (SAVGOL_POLYORDER + 2):
        win = SAVGOL_POLYORDER + 2
    if win % 2 == 0:
        win += 1
    if win >= len(s):
        return s.copy()
    return savgol_filter(s, window_length=win, polyorder=SAVGOL_POLYORDER)


def detect_distance_peaks(r_smooth: np.ndarray, fs: float) -> np.ndarray:
    min_dist_samples = max(1, int(MIN_PEAK_DISTANCE_SEC * fs))
    peaks, props = find_peaks(
        r_smooth,
        distance=min_dist_samples,
        prominence=MIN_PEAK_PROMINENCE,
    )
    if len(peaks) == 0:
        return peaks

    prom = props.get("prominences", r_smooth[peaks])
    if len(peaks) > N_PEAKS:
        order = np.argsort(prom)[::-1][:N_PEAKS]
        peaks = peaks[order]

    return np.sort(peaks)


def window_idx(t: np.ndarray, centre_time: float, half_window_sec: float) -> tuple[int, int]:
    left = centre_time - half_window_sec
    right = centre_time + half_window_sec
    i0 = int(np.searchsorted(t, left, side="left"))
    i1 = int(np.searchsorted(t, right, side="right"))
    return max(0, i0), min(len(t), i1)


def covariance_ellipse_points(x: np.ndarray, y: np.ndarray, n_std: float = 1.0, n_points: int = 220):
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


def add_30s_blocks(ax: plt.Axes, t_start: float, t_end: float):
    i = 0
    x = t_start
    while x < t_end:
        x2 = min(x + BLOCK_SEC, t_end)
        if i % 2 == 0:
            ax.axvspan(x, x2, alpha=0.10)
        i += 1
        x = x2


def plot_three_panel_timeseries_distance(
    stem: str,
    t: np.ndarray,
    rx: np.ndarray,
    ry: np.ndarray,
    r_smooth: np.ndarray,
    peak_times: np.ndarray,
    out_path: Path,
):
    fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(14, 10), sharex=True)

    t_start = 0.0
    t_end = float(t[-1]) if len(t) else 0.0

    peak_handle = plt.Line2D(
        [], [], marker="*", linestyle="None",
        markersize=12, markerfacecolor="red", markeredgecolor="black",
        label="Distance peak"
    )
    block_handle = Patch(alpha=0.10, label="30 s blocks")

    # COPx
    ax = axes[0]
    add_30s_blocks(ax, t_start, t_end)
    ax.plot(t, rx, linewidth=LW_CONTEXT)
    if len(peak_times) > 0:
        ax.scatter(
            peak_times, np.interp(peak_times, t, rx),
            marker="*", s=PEAK_MARKER_SIZE,
            color="red", edgecolors="black", linewidths=0.8, zorder=5,
        )
    ax.set_ylabel("COPx (m)")
    ax.set_title(f"{stem} | COPx, COPy, sway distance (30 s blocks shaded)")

    # COPy
    ax = axes[1]
    add_30s_blocks(ax, t_start, t_end)
    ax.plot(t, ry, linewidth=LW_CONTEXT)
    if len(peak_times) > 0:
        ax.scatter(
            peak_times, np.interp(peak_times, t, ry),
            marker="*", s=PEAK_MARKER_SIZE,
            color="red", edgecolors="black", linewidths=0.8, zorder=5,
        )
    ax.set_ylabel("COPy (m)")

    # Distance
    ax = axes[2]
    add_30s_blocks(ax, t_start, t_end)
    ax.plot(t, r_smooth, linewidth=LW_CONTEXT)
    if len(peak_times) > 0:
        ax.scatter(
            peak_times, np.interp(peak_times, t, r_smooth),
            marker="*", s=PEAK_MARKER_SIZE,
            color="red", edgecolors="black", linewidths=0.8, zorder=5,
        )
    ax.set_ylabel("Sway distance (m)")
    ax.set_xlabel("Time (s)")

    for ax in axes:
        ax.grid(True, alpha=0.35)

    axes[0].legend(handles=[peak_handle, block_handle], loc="upper right")

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
    if len(x) < 2:
        return

    fig, ax = plt.subplots(figsize=(8, 8))

    # Context (black)
    ax.plot(x, y, color="black", linewidth=LW_CONTEXT, label=f"Context ±{CONTEXT_HALF_SEC:.0f}s")

    # Highlight (red)
    if np.any(highlight_mask):
        ax.plot(x[highlight_mask], y[highlight_mask], color="red",
                linewidth=LW_HIGHLIGHT, label=f"Highlight ±{HIGHLIGHT_HALF_SEC:.0f}s")

    # Ellipses
    xe, ye = covariance_ellipse_points(x, y)
    if xe.size:
        ax.plot(xe, ye, linestyle="--", linewidth=ELLIPSE_LW,
                color=CONTEXT_ELLIPSE_COLOR, label="Context cov ellipse (1σ)")

    xh = x[highlight_mask]
    yh = y[highlight_mask]
    xe2, ye2 = covariance_ellipse_points(xh, yh)
    if xe2.size:
        ax.plot(xe2, ye2, linestyle="--", linewidth=ELLIPSE_LW,
                color=HIGHLIGHT_ELLIPSE_COLOR, label="Highlight cov ellipse (1σ)")

    ax.set_title(title)
    ax.set_xlabel("COPx (m)")
    ax.set_ylabel("COPy (m)")
    ax.grid(True, alpha=0.4)
    ax.axis("equal")
    ax.legend(loc="lower left")

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def run_one_file(mat_path: Path):
    stem = mat_path.stem
    out_dir = out_dir_for(mat_path)

    t, rx, ry = load_cop(mat_path)
    fs = estimate_fs(t)

    # Vector magnitude distance from baseline centre
    x0, y0 = baseline_center(t, rx, ry)
    r = sway_distance_vector_magnitude(rx, ry, x0, y0)
    r_smooth = smooth_signal_savgol(r, fs)

    peaks_r = detect_distance_peaks(r_smooth, fs)
    peak_times = t[peaks_r] if len(peaks_r) else np.array([])

    # 3-panel plot
    plot_three_panel_timeseries_distance(
        stem=stem,
        t=t,
        rx=rx,
        ry=ry,
        r_smooth=r_smooth,
        peak_times=peak_times,
        out_path=out_dir / "COPx_COPy_Distance_3panel_30s_blocks.png",
    )

    # Stabilograms per peak (±5s black, ±2s red)
    for i_peak, pk in enumerate(peaks_r, start=1):
        pk_time = float(t[pk])

        i0, i1 = window_idx(t, pk_time, CONTEXT_HALF_SEC)
        h0, h1 = window_idx(t, pk_time, HIGHLIGHT_HALF_SEC)

        rx_win = rx[i0:i1]
        ry_win = ry[i0:i1]

        highlight_mask = np.zeros(i1 - i0, dtype=bool)
        a = max(0, h0 - i0)
        b = max(0, h1 - i0)
        highlight_mask[a:b] = True

        plot_peak_stabilogram_black_red(
            x=rx_win,
            y=ry_win,
            highlight_mask=highlight_mask,
            title=f"Distance peak {i_peak} stabilogram ±{CONTEXT_HALF_SEC:.0f}s (black)\nHighlight ±{HIGHLIGHT_HALF_SEC:.0f}s (red)",
            out_path=out_dir / f"Peak_{i_peak:02d}_stabilogram_black_red_ellipses.png",
        )


def main():
    mats = find_input_files()
    print(f"Input MAT folder: {RAW_MAT_DIR}")
    print(f"Output root:      {OUT_DATA_DIR}")
    print(f"Found {len(mats)} MAT file(s).")

    for p in mats:
        print(f"\nProcessing {p.name}")
        run_one_file(p)
        print(f"  Saved to: {out_dir_for(p)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
