import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


DEFAULT_RAW_FILE = "TA_OCULUS_PILOT_JUL4_2_OCULUS_interpolated.csv"
DEFAULT_SEGMENTED_FILE = "hand_reaches_segmented_full.csv"
DEFAULT_REACH_SUMMARY_FILE = "reach_summary.csv"
DEFAULT_Z_THRESHOLD = 0.2
DEFAULT_TARGET_X = 0.0
DEFAULT_TARGET_Y = 0.96
BULLSEYE_DIAMETER_M = 0.02


def _load_raw_xyz(raw_file: Path) -> pd.DataFrame:
    raw_df = pd.read_csv(raw_file)
    required = {"HandX", "HandY", "HandZ"}
    missing = required - set(raw_df.columns)
    if missing:
        raise ValueError(f"Raw file is missing columns: {sorted(missing)}")

    if "Timestamp" in raw_df.columns:
        timestamp = pd.to_datetime(raw_df["Timestamp"], errors="coerce")
        raw_df["Timestamp"] = (timestamp - timestamp.iloc[0]).dt.total_seconds()
    elif "timestamp" in raw_df.columns:
        clean = (
            raw_df["timestamp"]
            .astype(str)
            .str.replace("Day: ", "", regex=False)
            .str.replace(" Time: ", " ", regex=False)
        )
        timestamp = pd.to_datetime(clean, errors="coerce")
        raw_df["Timestamp"] = (timestamp - timestamp.iloc[0]).dt.total_seconds()
    elif "seconds" in raw_df.columns:
        raw_df["Timestamp"] = pd.to_numeric(raw_df["seconds"], errors="coerce")
    else:
        raise ValueError("Raw file must contain one of: Timestamp, timestamp, or seconds.")

    for col in ["HandX", "HandY", "HandZ"]:
        raw_df[col] = pd.to_numeric(raw_df[col], errors="coerce")

    raw_df = raw_df.dropna(subset=["Timestamp", "HandX", "HandY", "HandZ"]).reset_index(drop=True)
    return raw_df[["Timestamp", "HandX", "HandY", "HandZ"]]


def _load_segmented(segmented_file: Path) -> pd.DataFrame:
    segmented_df = pd.read_csv(segmented_file)
    if "Timestamp" not in segmented_df.columns and "seconds" in segmented_df.columns:
        segmented_df["Timestamp"] = pd.to_numeric(segmented_df["seconds"], errors="coerce")

    required_segmented = {"Timestamp", "HandZ_filtered", "Trial_Number", "Reach_Number", "Reach_In_Trial", "Is_Peak"}
    missing_segmented = required_segmented - set(segmented_df.columns)
    if missing_segmented:
        raise ValueError(f"Segmented file is missing columns: {sorted(missing_segmented)}")

    segmented_df["Timestamp"] = pd.to_numeric(segmented_df["Timestamp"], errors="coerce")
    segmented_df = segmented_df.dropna(subset=["Timestamp"]).reset_index(drop=True)
    return segmented_df


def load_inputs(raw_file: Path, segmented_file: Path, reach_summary_file: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_df = _load_raw_xyz(raw_file)
    segmented_df = _load_segmented(segmented_file)

    if len(segmented_df) == len(raw_df) and np.allclose(
        segmented_df["Timestamp"].to_numpy(),
        raw_df["Timestamp"].to_numpy(),
        atol=1e-6,
        rtol=0.0,
    ):
        merged = segmented_df.copy()
        merged[["HandX", "HandY"]] = raw_df[["HandX", "HandY"]].to_numpy()
    else:
        raw_for_merge = raw_df.copy()
        raw_for_merge["TimestampKey"] = raw_for_merge["Timestamp"].round(6)
        segmented_for_merge = segmented_df.copy()
        segmented_for_merge["TimestampKey"] = segmented_for_merge["Timestamp"].round(6)
        merged = segmented_for_merge.merge(
            raw_for_merge[["TimestampKey", "HandX", "HandY"]],
            on="TimestampKey",
            how="left",
        ).drop(columns=["TimestampKey"])

        # Fallback for raw vs interpolated copies of the same recording:
        # keep the segmented timing/reach structure and map raw X/Y by row order.
        if merged[["HandX", "HandY"]].isna().any().any() and len(segmented_df) == len(raw_df):
            merged = segmented_df.copy()
            merged[["HandX", "HandY"]] = raw_df[["HandX", "HandY"]].to_numpy()

    if merged[["HandX", "HandY"]].isna().any().any():
        raise ValueError("Failed to align HandX/HandY with segmented data.")

    reaches = pd.read_csv(reach_summary_file)
    required_reaches = {"Reach_Number", "Trial_Number", "Reach_In_Trial", "Start_Time", "Peak_Time"}
    missing_reaches = required_reaches - set(reaches.columns)
    if missing_reaches:
        raise ValueError(f"Reach summary is missing columns: {sorted(missing_reaches)}")

    return merged, reaches


def calculate_endpoints(df: pd.DataFrame, reaches: pd.DataFrame, z_threshold: float, target_xy: tuple[float, float]) -> pd.DataFrame:
    endpoints = []
    target_x, target_y = target_xy

    for _, reach in reaches.iterrows():
        reach_number = int(reach["Reach_Number"])
        trial_number = int(reach["Trial_Number"])
        reach_in_trial = int(reach["Reach_In_Trial"])
        start_time = float(reach["Start_Time"])
        peak_time = float(reach["Peak_Time"])

        reach_data = df[(df["Timestamp"] >= start_time) & (df["Timestamp"] <= peak_time)].copy()
        if reach_data.empty or reach_data["HandZ_filtered"].max() < z_threshold:
            continue

        crossing_indices = reach_data.index[reach_data["HandZ_filtered"] >= z_threshold]
        if len(crossing_indices) == 0:
            continue

        idx_after = crossing_indices[0]
        if idx_after == reach_data.index[0]:
            row = df.loc[idx_after]
            x = float(row["HandX"])
            y = float(row["HandY"])
            t = float(row["Timestamp"])
        else:
            row_before = df.loc[idx_after - 1]
            row_after = df.loc[idx_after]
            z1 = float(row_before["HandZ_filtered"])
            z2 = float(row_after["HandZ_filtered"])
            frac = 0.0 if z2 == z1 else (z_threshold - z1) / (z2 - z1)
            x = float(row_before["HandX"] + frac * (row_after["HandX"] - row_before["HandX"]))
            y = float(row_before["HandY"] + frac * (row_after["HandY"] - row_before["HandY"]))
            t = float(row_before["Timestamp"] + frac * (row_after["Timestamp"] - row_before["Timestamp"]))

        error_x = x - target_x
        error_y = y - target_y
        euclidean_error = math.sqrt(error_x ** 2 + error_y ** 2)

        endpoints.append(
            {
                "Reach_Number": reach_number,
                "Trial_Number": trial_number,
                "Reach_In_Trial": reach_in_trial,
                "HandX": x,
                "HandY": y,
                "HandZ": z_threshold,
                "Time": t,
                "Error_X": error_x,
                "Error_Y": error_y,
                "Euclidean_Error": euclidean_error,
                "Hit_Bullseye": bool(euclidean_error <= (BULLSEYE_DIAMETER_M / 2.0)),
            }
        )

    endpoints_df = pd.DataFrame(endpoints)
    if not endpoints_df.empty:
        endpoints_df["Global_Success_Index"] = np.arange(1, len(endpoints_df) + 1)
    return endpoints_df


def create_interactive_visualization(
    endpoints: pd.DataFrame,
    full_df: pd.DataFrame,
    reaches: pd.DataFrame,
    z_threshold: float,
    output_path: Path,
    target_pos: tuple[float, float, float],
) -> None:
    unique_trials = sorted(endpoints["Trial_Number"].unique())
    fig = make_subplots(
        rows=4,
        cols=2,
        column_widths=[0.6, 0.4],
        specs=[
            [{"rowspan": 3}, {}],
            [None, {}],
            [None, {}],
            [{"colspan": 2}, None],
        ],
        subplot_titles=(
            "Spatial Endpoints (X-Y)",
            "Hand Z vs Time",
            "Hand X vs Time",
            "Hand Y vs Time",
            "Learning Rate (Euclidean Error)",
        ),
        horizontal_spacing=0.08,
        vertical_spacing=0.08,
    )

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]
    hit_pct_by_trial = {}
    label_by_trial = {}
    all_times = []

    for i, trial_num in enumerate(unique_trials):
        color = colors[i % len(colors)]
        trial_endpoints = endpoints[endpoints["Trial_Number"] == trial_num]
        trial_reaches = reaches[reaches["Trial_Number"] == trial_num]
        trial_label = (
            trial_endpoints["Trial_Label"].iloc[0]
            if "Trial_Label" in trial_endpoints.columns and not trial_endpoints.empty
            else f"Trial {trial_num}"
        )
        label_by_trial[trial_num] = trial_label

        hit_pct = 100.0 * trial_endpoints["Hit_Bullseye"].mean() if not trial_endpoints.empty else 0.0
        hit_pct_by_trial[trial_num] = hit_pct

        fig.add_trace(
            go.Scatter(
                x=trial_endpoints["HandX"],
                y=trial_endpoints["HandY"],
                mode="markers+text",
                text=trial_endpoints["Reach_In_Trial"],
                textposition="top center",
                marker=dict(size=8, color=color, opacity=0.85),
                name=f"{trial_label} ({hit_pct:.1f}% hit)",
                customdata=np.stack(
                    (
                        trial_endpoints["Trial_Number"],
                        trial_endpoints["Euclidean_Error"],
                        trial_endpoints["Hit_Bullseye"],
                    ),
                    axis=-1,
                ),
                hovertemplate=f"{trial_label}<br>Reach %{{text}}<br>X %{{x:.3f}}<br>Y %{{y:.3f}}<br>Error %{{customdata[1]:.4f}} m<br>Hit %{{customdata[2]}}<extra></extra>",
                legendgroup=f"trial_{trial_num}",
            ),
            row=1,
            col=1,
        )

        t_seq, x_seq, y_seq, z_seq = [], [], [], []
        for _, reach in trial_reaches.iterrows():
            segment = full_df[(full_df["Timestamp"] >= reach["Start_Time"]) & (full_df["Timestamp"] <= reach["Peak_Time"])]
            if segment.empty:
                continue
            t_seq.extend(segment["Timestamp"].tolist() + [None])
            x_seq.extend(segment["HandX"].tolist() + [None])
            y_seq.extend(segment["HandY"].tolist() + [None])
            z_seq.extend(segment["HandZ_filtered"].tolist() + [None])
            all_times.extend(segment["Timestamp"].tolist())

        for row, values, axis_name in [(1, z_seq, "Z"), (2, x_seq, "X"), (3, y_seq, "Y")]:
            fig.add_trace(
                go.Scatter(
                    x=t_seq,
                    y=values,
                    mode="lines",
                    line=dict(color=color, width=1.5),
                    name=f"{trial_label} ({axis_name})",
                    showlegend=False,
                    legendgroup=f"trial_{trial_num}",
                    hovertemplate=f"T: %{{x:.2f}}<br>{axis_name}: %{{y:.3f}}<extra></extra>",
                ),
                row=row,
                col=2,
            )

        fig.add_trace(
            go.Scatter(
                x=trial_endpoints["Global_Success_Index"],
                y=trial_endpoints["Euclidean_Error"],
                mode="lines+markers",
                marker=dict(size=6, color=color),
                line=dict(color=color, width=2),
                name=f"{trial_label} learning",
                showlegend=False,
                legendgroup=f"trial_{trial_num}",
                hovertemplate="Global Success %{x}<br>Error %{y:.4f} m<extra></extra>",
            ),
            row=4,
            col=1,
        )

    target_x, target_y, target_z = target_pos
    radius = BULLSEYE_DIAMETER_M / 2.0
    fig.add_shape(
        type="circle",
        x0=target_x - radius,
        y0=target_y - radius,
        x1=target_x + radius,
        y1=target_y + radius,
        line=dict(color="red", width=1),
        fillcolor="red",
        opacity=0.25,
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=[target_x],
            y=[target_y],
            mode="markers",
            marker=dict(size=10, color="gold", symbol="cross", line=dict(color="black", width=1)),
            name="Target Center",
            hovertemplate="Target<br>X %{x:.3f}<br>Y %{y:.3f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_hline(y=target_z, line_dash="dash", line_color="gold", annotation_text="Target Z", row=1, col=2)
    fig.add_hline(y=target_x, line_dash="dash", line_color="gold", annotation_text="Target X", row=2, col=2)
    fig.add_hline(y=target_y, line_dash="dash", line_color="gold", annotation_text="Target Y", row=3, col=2)
    fig.add_hline(y=z_threshold, line_dash="dot", line_color="red", annotation_text=f"Endpoint Z={z_threshold}", row=1, col=2)

    x_min = min(endpoints["HandX"].min(), target_x)
    x_max = max(endpoints["HandX"].max(), target_x)
    y_min = min(endpoints["HandY"].min(), target_y)
    y_max = max(endpoints["HandY"].max(), target_y)
    x_pad = (x_max - x_min) * 0.1 if x_max != x_min else 0.05
    y_pad = (y_max - y_min) * 0.1 if y_max != y_min else 0.05

    fig.update_xaxes(title_text="Hand X (m)", range=[x_min - x_pad, x_max + x_pad], row=1, col=1)
    fig.update_yaxes(title_text="Hand Y (m)", range=[y_min - y_pad, y_max + y_pad], scaleanchor="x", scaleratio=1, row=1, col=1)
    fig.update_yaxes(title_text="Hand Z (m)", row=1, col=2)
    fig.update_yaxes(title_text="Hand X (m)", row=2, col=2)
    fig.update_yaxes(title_text="Hand Y (m)", row=3, col=2)
    fig.update_xaxes(title_text="Time (s)", row=3, col=2)
    fig.update_xaxes(title_text="Global Success Number", row=4, col=1)
    fig.update_yaxes(title_text="Euclidean Error (m)", rangemode="tozero", row=4, col=1)

    if all_times:
        t_min = min(all_times)
        t_max = max(all_times)
        t_pad = (t_max - t_min) * 0.05 if t_max != t_min else 1.0
        for row in (1, 2, 3):
            fig.update_xaxes(range=[t_min - t_pad, t_max + t_pad], row=row, col=2)

    total_traces = len(fig.data)
    buttons = [dict(label="All Trials", method="update", args=[{"visible": [True] * total_traces}])]

    hide_all = [False] * total_traces
    hide_all[-1] = True
    buttons.append(dict(label="Hide All", method="update", args=[{"visible": hide_all}]))

    traces_per_trial = 5
    for i, trial_num in enumerate(unique_trials):
        visible = [False] * total_traces
        start = i * traces_per_trial
        for offset in range(traces_per_trial):
            visible[start + offset] = True
        visible[-1] = True
        buttons.append(
            dict(
                label=f"{label_by_trial[trial_num]} ({hit_pct_by_trial[trial_num]:.1f}% hit)",
                method="update",
                args=[{"visible": visible}],
            )
        )

    fig.update_layout(
        title="Talha Dataset Endpoint Analysis",
        template="plotly_white",
        width=1600,
        height=1200,
        hovermode="closest",
        updatemenus=[dict(active=0, buttons=buttons, x=1.0, y=1.05, xanchor="right", yanchor="top")],
    )
    fig.write_html(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Plotly endpoint visualization from the Talha reach outputs.")
    parser.add_argument("--raw-file", default=DEFAULT_RAW_FILE)
    parser.add_argument("--segmented-file", default=DEFAULT_SEGMENTED_FILE)
    parser.add_argument("--reach-summary", default=DEFAULT_REACH_SUMMARY_FILE)
    parser.add_argument("--z-value", type=float, default=DEFAULT_Z_THRESHOLD)
    parser.add_argument("--target-x", type=float, default=DEFAULT_TARGET_X)
    parser.add_argument("--target-y", type=float, default=DEFAULT_TARGET_Y)
    parser.add_argument("--target-z", type=float)
    args = parser.parse_args()

    raw_file = Path(args.raw_file)
    segmented_file = Path(args.segmented_file)
    reach_summary_file = Path(args.reach_summary)

    df, reaches = load_inputs(raw_file, segmented_file, reach_summary_file)
    endpoints = calculate_endpoints(df, reaches, args.z_value, (args.target_x, args.target_y))
    if endpoints.empty:
        raise RuntimeError(f"No reaches crossed Z={args.z_value}")

    stem = raw_file.stem
    csv_output = Path(f"{stem}_endpoints_z{args.z_value}.csv")
    html_output = Path(f"{stem}_endpoints_z{args.z_value}_interactive.html")

    endpoints.to_csv(csv_output, index=False)
    create_interactive_visualization(
        endpoints,
        df,
        reaches,
        args.z_value,
        html_output,
        (args.target_x, args.target_y, args.target_z if args.target_z is not None else args.z_value),
    )

    print(f"Saved endpoints data to: {csv_output}")
    print(f"Saved Plotly visualization to: {html_output}")


if __name__ == "__main__":
    main()
