from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from scipy.io import loadmat
from scipy.signal import savgol_filter


# =========================
# PATHS (portable)
# =========================
REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_MAT_DIR = REPO_ROOT / "data" / "raw" / "force_plate"
OUT_DATA_DIR = REPO_ROOT / "results" / "force_plate"


# =========================
# DATA MAPPING (adjust if needed)
# =========================
COPX_COL = 0
COPY_COL = 1


# =========================
# PROTOCOL PRIOR
# =========================
BLOCK_SEC = 30.0
FIRST_EVENT_SEARCH = (15.0, 50.0)   # first switch ~30s
NEXT_EVENT_TOL_SEC = 7.0            # drift tolerance
MAX_EVENTS = 12


# =========================
# CHANGE SCORE WINDOWS
# =========================
PRE_SEC = 3.0
POST_SEC = 3.0
CANDIDATE_STEP_SEC = 0.15           # evaluate candidates every 150 ms (fast + accurate enough)


# =========================
# SIGNAL PROCESSING
# =========================
COP_SMOOTH_SEC = 0.20
V_SMOOTH_SEC = 0.30
R_SMOOTH_SEC = 0.50


# =========================
# STABILOGRAM WINDOWS
# =========================
STAB_CONTEXT_SEC = 5.0      # ±5s black
STAB_HIGHLIGHT_SEC = 2.0    # ±2s red


# =========================
# COMPOSITE SCORE WEIGHTS
# =========================
W_PATH = 0.45
W_AREA = 0.30
W_R    = 0.15
W_V    = 0.10


# =========================
# PLOT STYLE
# =========================
LW_BLACK = 1.1
LW_RED = 2.4

ELLIPSE_LW = 2.8
CONTEXT_ELLIPSE_COLOR = "#00E5FF"    # bright cyan/turquoise
HIGHLIGHT_ELLIPSE_COLOR = "#39FF14"  # neon green

PEAK_MARKER_SIZE = 140


# -------------------------
# IO helpers
# -------------------------
def find_input_files() -> list[Path]:
    if not RAW_MAT_DIR.exists():
        raise FileNotFoundError(f"Raw MAT folder not found:\n  {RAW_MAT_DIR}")
    mats = sorted(RAW_MAT_DIR.glob("*.mat"))
    if not mats:
        raise FileNotFoundError(f"No .mat files found in:\n  {RAW_MAT_DIR}")
    return mats


def out_dir_for(mat_path: Path) -> Path:
    # You asked: call it guided
    stem = mat_path.stem
    out_dir = OUT_DATA_DIR / stem / "figures" / "guided"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def load_cop(mat_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    m = loadmat(mat_path)
    t = np.asarray(m["time"]).squeeze().astype(float)
    samples = np.asarray(m["samples"]).astype(float)

    rx = samples[:, COPX_COL].astype(float)
    ry = samples[:, COPY_COL].astype(float)

    n = min(len(t), len(rx), len(ry))
    t, rx, ry = t[:n], rx[:n], ry[:n]
    t = t - t[0]
    return t, rx, ry


# -------------------------
# Signal helpers
# -------------------------
def estimate_fs(t: np.ndarray) -> float:
    dt = np.diff(t)
    dt = dt[np.isfinite(dt)]
    dt = dt[dt > 0]
    if len(dt) == 0:
        return 1.0
    return float(1.0 / np.median(dt))


def smooth_savgol(x: np.ndarray, fs: float, win_sec: float, poly: int = 3) -> np.ndarray:
    win = int(round(win_sec * fs))
    win = max(win, poly + 2)
    if win % 2 == 0:
        win += 1
    if win >= len(x):
        return x.copy()
    return savgol_filter(x, window_length=win, polyorder=poly)


def baseline_center(t: np.ndarray, rx: np.ndarray, ry: np.ndarray, baseline_sec: float = 30.0) -> tuple[float, float]:
    mask = t <= baseline_sec
    if np.sum(mask) < 10:
        return float(np.mean(rx)), float(np.mean(ry))
    return float(np.mean(rx[mask])), float(np.mean(ry[mask]))


def idx_range(t: np.ndarray, t0: float, t1: float) -> tuple[int, int]:
    i0 = int(np.searchsorted(t, t0, side="left"))
    i1 = int(np.searchsorted(t, t1, side="right"))
    return max(0, i0), min(len(t), i1)


def add_30s_blocks(ax: plt.Axes, t_start: float, t_end: float, block_sec: float = 30.0):
    i = 0
    x = t_start
    while x < t_end:
        x2 = min(x + block_sec, t_end)
        if i % 2 == 0:
            ax.axvspan(x, x2, alpha=0.10)
        i += 1
        x = x2


# -------------------------
# Fast rolling metrics using cumulative sums
# -------------------------
def cumsum0(x: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(x.astype(float))])


def window_mean_from_cumsum(cs: np.ndarray, i0: int, i1: int) -> float:
    n = i1 - i0
    if n <= 0:
        return 0.0
    return float((cs[i1] - cs[i0]) / n)


def window_second_moment_from_cumsum(cs2: np.ndarray, i0: int, i1: int) -> float:
    n = i1 - i0
    if n <= 0:
        return 0.0
    return float((cs2[i1] - cs2[i0]) / n)


def window_cov_det(x: np.ndarray, y: np.ndarray, csx, csy, csx2, csy2, csxy, i0: int, i1: int) -> float:
    """
    det(Cov) computed from window sums (fast).
    Cov = [[varx, covxy], [covxy, vary]]
    det = varx*vary - covxy^2
    """
    n = i1 - i0
    if n < 8:
        return 0.0

    mx = window_mean_from_cumsum(csx, i0, i1)
    my = window_mean_from_cumsum(csy, i0, i1)

    ex2 = window_second_moment_from_cumsum(csx2, i0, i1)
    ey2 = window_second_moment_from_cumsum(csy2, i0, i1)
    exy = window_second_moment_from_cumsum(csxy, i0, i1)

    varx = max(0.0, ex2 - mx * mx)
    vary = max(0.0, ey2 - my * my)
    covxy = exy - mx * my

    det = varx * vary - covxy * covxy
    return float(max(det, 0.0))


def robust_z(val: float, base: np.ndarray) -> float:
    if base.size < 20:
        return 0.0
    med = float(np.median(base))
    mad = float(np.median(np.abs(base - med))) + 1e-9
    return (val - med) / (1.4826 * mad)


# -------------------------
# Event detection (change-based, fast)
# -------------------------
def detect_events_change_guided_fast(t: np.ndarray, rx: np.ndarray, ry: np.ndarray) -> np.ndarray:
    fs = estimate_fs(t)

    # Smooth COP slightly (helps path/area stability)
    rx_s = smooth_savgol(rx, fs, COP_SMOOTH_SEC)
    ry_s = smooth_savgol(ry, fs, COP_SMOOTH_SEC)

    # Radial distance from baseline centre (pythagoras)
    x0, y0 = baseline_center(t, rx_s, ry_s, baseline_sec=30.0)
    r = np.sqrt((rx_s - x0) ** 2 + (ry_s - y0) ** 2)
    r_s = smooth_savgol(r, fs, R_SMOOTH_SEC)

    # Velocity magnitude on t_v = t[1:]
    dx = np.diff(rx_s) * fs
    dy = np.diff(ry_s) * fs
    v = np.sqrt(dx**2 + dy**2)
    t_v = t[1:]
    v_s = smooth_savgol(v, fs, V_SMOOTH_SEC)

    # Precompute cumulative sums for fast window stats
    csx = cumsum0(rx_s)
    csy = cumsum0(ry_s)
    csx2 = cumsum0(rx_s * rx_s)
    csy2 = cumsum0(ry_s * ry_s)
    csxy = cumsum0(rx_s * ry_s)

    csr = cumsum0(r_s)

    # Path length cumulative from step lengths (aligned to samples)
    step = np.sqrt(np.diff(rx_s) ** 2 + np.diff(ry_s) ** 2)
    cspath = cumsum0(step)  # length N

    # For velocity (t_v), cumulative sums too
    csv = cumsum0(v_s)

    n = len(t)
    trial_end = float(t[-1])

    preN = int(round(PRE_SEC * fs))
    postN = int(round(POST_SEC * fs))
    if preN < 5 or postN < 5:
        return np.array([])

    # Baseline candidate indices (first 30 s) for robust z normalisation
    b0, b1 = idx_range(t, 0.0, 30.0)
    baseline_idxs = np.arange(b0 + preN + 5, max(b0 + preN + 5, b1 - postN - 5), int(round(0.50 * fs)))
    if baseline_idxs.size < 30:
        baseline_idxs = np.arange(max(0, preN + 10), min(n - postN - 10, b1), max(1, int(round(0.50 * fs))))

    base_d_path = []
    base_d_area = []
    base_d_r = []
    base_d_v = []

    def win_path(i0: int, i1: int) -> float:
        # path length = sum step lengths over [i0, i1)
        # step indices correspond to transitions; cspath is aligned with step length list
        # cspath length is len(step)+1 = n
        return float(cspath[i1 - 1] - cspath[i0]) if i1 - i0 > 2 else 0.0

    def win_mean_r(i0: int, i1: int) -> float:
        return window_mean_from_cumsum(csr, i0, i1)

    def win_mean_v(t0: float, t1: float) -> float:
        j0, j1 = idx_range(t_v, t0, t1)
        return window_mean_from_cumsum(csv, j0, j1)

    for idx in baseline_idxs:
        pre0, pre1 = idx - preN, idx
        post0, post1 = idx, idx + postN

        dp = win_path(post0, post1) - win_path(pre0, pre1)

        det_pre = window_cov_det(rx_s, ry_s, csx, csy, csx2, csy2, csxy, pre0, pre1)
        det_post = window_cov_det(rx_s, ry_s, csx, csy, csx2, csy2, csxy, post0, post1)

        # area proxy: pi * sqrt(det)
        da = (np.pi * np.sqrt(det_post)) - (np.pi * np.sqrt(det_pre))

        dr = win_mean_r(post0, post1) - win_mean_r(pre0, pre1)

        tc = float(t[idx])
        dv = win_mean_v(tc, tc + POST_SEC) - win_mean_v(tc - PRE_SEC, tc)

        base_d_path.append(dp)
        base_d_area.append(da)
        base_d_r.append(dr)
        base_d_v.append(dv)

    base_d_path = np.asarray(base_d_path, dtype=float)
    base_d_area = np.asarray(base_d_area, dtype=float)
    base_d_r = np.asarray(base_d_r, dtype=float)
    base_d_v = np.asarray(base_d_v, dtype=float)

    def score_at_index(idx: int, expected_t: float | None) -> float:
        pre0, pre1 = idx - preN, idx
        post0, post1 = idx, idx + postN
        if pre0 < 0 or post1 >= n:
            return -1e18

        dp = win_path(post0, post1) - win_path(pre0, pre1)

        det_pre = window_cov_det(rx_s, ry_s, csx, csy, csx2, csy2, csxy, pre0, pre1)
        det_post = window_cov_det(rx_s, ry_s, csx, csy, csx2, csy2, csxy, post0, post1)
        da = (np.pi * np.sqrt(det_post)) - (np.pi * np.sqrt(det_pre))

        dr = win_mean_r(post0, post1) - win_mean_r(pre0, pre1)

        tc = float(t[idx])
        dv = win_mean_v(tc, tc + POST_SEC) - win_mean_v(tc - PRE_SEC, tc)

        z_path = robust_z(dp, base_d_path)
        z_area = robust_z(da, base_d_area)
        z_r = robust_z(dr, base_d_r)
        z_v = robust_z(dv, base_d_v)

        score = W_PATH * z_path + W_AREA * z_area + W_R * z_r + W_V * z_v

        if expected_t is not None:
            dt = abs(tc - expected_t)
            timing = float(np.exp(-(dt**2) / (2 * (NEXT_EVENT_TOL_SEC**2))))
            score *= timing

        return float(score)

    def best_event_in_time_window(t0: float, t1: float, expected_t: float | None) -> float | None:
        # Candidate indices sampled every CANDIDATE_STEP_SEC
        i0, i1 = idx_range(t, t0, t1)
        if i1 <= i0:
            return None

        step = max(1, int(round(CANDIDATE_STEP_SEC * fs)))
        candidates = np.arange(i0, i1, step, dtype=int)

        best_idx = None
        best_score = -1e18
        for idx in candidates:
            sc = score_at_index(idx, expected_t)
            if sc > best_score:
                best_score = sc
                best_idx = idx
        if best_idx is None:
            return None
        return float(t[best_idx])

    # ---- Anchor first event near ~30 s ----
    first = best_event_in_time_window(FIRST_EVENT_SEARCH[0], FIRST_EVENT_SEARCH[1], expected_t=30.0)
    if first is None:
        return np.array([])

    events = [first]

    # ---- Step forward by protocol ----
    for k in range(2, MAX_EVENTS + 1):
        expected = events[0] + (k - 1) * BLOCK_SEC
        if expected > trial_end - POST_SEC - 1.0:
            break
        tc = best_event_in_time_window(expected - NEXT_EVENT_TOL_SEC, expected + NEXT_EVENT_TOL_SEC, expected_t=expected)
        if tc is not None:
            events.append(tc)

    return np.array(events, dtype=float)


# -------------------------
# Plotting
# -------------------------
def covariance_ellipse_points(x: np.ndarray, y: np.ndarray, n_std: float = 1.0, n_points: int = 240):
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

    a, b = np.sqrt(eigvals[0]), np.sqrt(eigvals[1])
    theta = np.linspace(0, 2 * np.pi, n_points)
    circle = np.vstack([np.cos(theta), np.sin(theta)])
    ellipse = (eigvecs @ np.diag([a, b]) @ circle).T + mean
    return ellipse[:, 0], ellipse[:, 1]


def plot_three_panel(t: np.ndarray, rx: np.ndarray, ry: np.ndarray, fs: float, events: np.ndarray, out_path: Path, title: str):
    dx = np.diff(rx) * fs
    dy = np.diff(ry) * fs
    v = np.sqrt(dx**2 + dy**2)
    t_v = t[1:]

    fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(14, 10), sharex=True)

    peak_handle = plt.Line2D(
        [], [], marker="*", linestyle="None",
        markersize=12, markerfacecolor="red", markeredgecolor="black",
        label="Detected switch event"
    )
    block_handle = Patch(alpha=0.10, label="30 s blocks")

    ax = axes[0]
    add_30s_blocks(ax, 0.0, float(t[-1]), BLOCK_SEC)
    ax.plot(t, rx, linewidth=1.0)
    if len(events):
        ax.scatter(events, np.interp(events, t, rx),
                   marker="*", s=PEAK_MARKER_SIZE, color="red",
                   edgecolors="black", linewidths=0.8, zorder=5)
    ax.set_ylabel("COPx (m)")
    ax.set_title(title)

    ax = axes[1]
    add_30s_blocks(ax, 0.0, float(t[-1]), BLOCK_SEC)
    ax.plot(t, ry, linewidth=1.0)
    if len(events):
        ax.scatter(events, np.interp(events, t, ry),
                   marker="*", s=PEAK_MARKER_SIZE, color="red",
                   edgecolors="black", linewidths=0.8, zorder=5)
    ax.set_ylabel("COPy (m)")

    ax = axes[2]
    add_30s_blocks(ax, 0.0, float(t[-1]), BLOCK_SEC)
    ax.plot(t_v, v, linewidth=1.0)
    if len(events):
        ax.scatter(events, np.interp(events, t_v, v),
                   marker="*", s=PEAK_MARKER_SIZE, color="red",
                   edgecolors="black", linewidths=0.8, zorder=5)
    ax.set_ylabel("COPv (m/s)")
    ax.set_xlabel("Time (s)")

    for ax in axes:
        ax.grid(True, alpha=0.35)

    axes[0].legend(handles=[peak_handle, block_handle], loc="upper right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def plot_stabilogram(rx: np.ndarray, ry: np.ndarray, t: np.ndarray, tc: float, out_path: Path, title: str):
    c0, c1 = idx_range(t, tc - STAB_CONTEXT_SEC, tc + STAB_CONTEXT_SEC)
    h0, h1 = idx_range(t, tc - STAB_HIGHLIGHT_SEC, tc + STAB_HIGHLIGHT_SEC)

    x = rx[c0:c1]
    y = ry[c0:c1]
    h0r = max(0, h0 - c0)
    h1r = max(0, h1 - c0)

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot(x, y, color="black", linewidth=LW_BLACK, label=f"Context ±{STAB_CONTEXT_SEC:.0f}s")
    if h1r > h0r + 2:
        ax.plot(x[h0r:h1r], y[h0r:h1r], color="red", linewidth=LW_RED, label=f"Highlight ±{STAB_HIGHLIGHT_SEC:.0f}s")

    xe, ye = covariance_ellipse_points(x, y)
    if xe.size:
        ax.plot(xe, ye, linestyle="--", linewidth=ELLIPSE_LW,
                color=CONTEXT_ELLIPSE_COLOR, label="Context cov ellipse (1σ)")

    xh = x[h0r:h1r]
    yh = y[h0r:h1r]
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
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


# -------------------------
# Run per file
# -------------------------
def run_one_file(mat_path: Path):
    stem = mat_path.stem
    out_dir = out_dir_for(mat_path)

    t, rx, ry = load_cop(mat_path)
    fs = estimate_fs(t)

    events = detect_events_change_guided_fast(t, rx, ry)

    plot_three_panel(
        t=t, rx=rx, ry=ry, fs=fs, events=events,
        out_path=out_dir / "COPx_COPy_COPv_3panel_guided_events.png",
        title=f"{stem} | Guided robust change-based detection (fast)",
    )

    for i, tc in enumerate(events, start=1):
        plot_stabilogram(
            rx=rx, ry=ry, t=t, tc=float(tc),
            out_path=out_dir / f"Event_{i:02d}_stabilogram_black_red_ellipses.png",
            title=f"Event {i} stabilogram | ±{STAB_CONTEXT_SEC:.0f}s black, ±{STAB_HIGHLIGHT_SEC:.0f}s red",
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
