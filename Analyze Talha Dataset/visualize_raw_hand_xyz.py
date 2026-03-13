import argparse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


DEFAULT_INPUT = "TA_OCULUS_PILOT_JUL4_2_OCULUS.csv"
DEFAULT_OUTPUT = "TA_OCULUS_PILOT_JUL4_2_OCULUS_raw_handxyz_timeseries.html"


def load_raw_hand_xyz(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    required = ["HandX", "HandY", "HandZ"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    use_seconds = False
    if "seconds" in df.columns:
        seconds = pd.to_numeric(df["seconds"], errors="coerce")
        # This raw TA file has a 'seconds' column, but it is not reliable if it is flat or nearly flat.
        if seconds.notna().any() and seconds.nunique(dropna=True) > 100 and seconds.max() > seconds.min():
            df["TimeSeconds"] = seconds
            use_seconds = True

    if not use_seconds and "timestamp" in df.columns:
        clean = (
            df["timestamp"]
            .astype(str)
            .str.replace("Day: ", "", regex=False)
            .str.replace(" Time: ", " ", regex=False)
        )
        ts = pd.to_datetime(clean, errors="coerce")
        df["TimeSeconds"] = (ts - ts.iloc[0]).dt.total_seconds()
    elif not use_seconds:
        df["TimeSeconds"] = range(len(df))

    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["TimeSeconds", "HandX", "HandY", "HandZ"]).reset_index(drop=True)
    return df


def build_figure(df: pd.DataFrame, title: str) -> go.Figure:
    fig = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=("HandX vs Time", "HandY vs Time", "HandZ vs Time"),
        vertical_spacing=0.07,
        row_heights=[0.33, 0.33, 0.34],
    )

    traces = [
        ("HandX", "#1f77b4", 1),
        ("HandY", "#ff7f0e", 2),
        ("HandZ", "#2ca02c", 3),
    ]
    for col, color, row in traces:
        fig.add_trace(
            go.Scatter(
                x=df["TimeSeconds"],
                y=df[col],
                mode="lines",
                name=col,
                line=dict(color=color, width=1.4),
                hovertemplate=f"Time: %{{x:.2f}} s<br>{col}: %{{y:.4f}}<extra></extra>",
        ),
        row=row,
        col=1,
    )

    fig.update_xaxes(title_text="Time (s)", row=3, col=1)
    fig.update_yaxes(title_text="HandX (m)", row=1, col=1)
    fig.update_yaxes(title_text="HandY (m)", row=2, col=1)
    fig.update_yaxes(title_text="HandZ (m)", row=3, col=1)

    fig.update_layout(
        title=title,
        template="plotly_white",
        hovermode="closest",
        height=950,
    )
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize raw TA HandX, HandY, and HandZ data.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    df = load_raw_hand_xyz(input_path)
    title = f"Raw TA HandX / HandY / HandZ: {input_path.name}"
    fig = build_figure(df, title)
    fig.write_html(output_path)

    print(f"Input file: {input_path.resolve()}")
    print(f"Columns used: HandX, HandY, HandZ")
    print(f"Rows plotted: {len(df)}")
    print(f"Saved Plotly visualization to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
