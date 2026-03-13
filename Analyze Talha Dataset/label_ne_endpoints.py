from pathlib import Path

import pandas as pd

from visualize_endpoints_plotly import create_interactive_visualization, _load_segmented, calculate_endpoints


BASE = "NE_JAN0626_OCULUS_REACH_FINAL_OCULUS_CLEAN"
SOURCE_DIR = Path(r"..\results\oculus\analysis_dist\tables")
RAW_DIR = Path(r"..\data\raw\oculus")

RAW_FILE = RAW_DIR / f"{BASE}.csv"
SEGMENTED_FILE = SOURCE_DIR / f"{BASE}_scientific_segmented.csv"
REACH_SUMMARY_FILE = SOURCE_DIR / f"{BASE}_reach_summary.csv"
ENDPOINTS_FILE = SOURCE_DIR / f"{BASE}_endpoints_z0.98.csv"

TARGET_X = 0.0
TARGET_Y = 1.06
TARGET_Z = 0.98

OUT_CSV = Path(f"{BASE}_endpoints_z0.98_y1.06_labeled.csv")
OUT_HTML = Path(f"{BASE}_endpoints_z0.98_y1.06_labeled_interactive.html")

TRIAL_LABELS = {
    2: "ctrl",
    3: "vngvswa",
    4: "ctrl",
    5: "nvgvswb",
    6: "ctrl",
    7: "vgvsnw",
    8: "ctrl",
    9: "nvgvsnw",
    10: "ctrl",
    11: "vgvswa",
    12: "ctrl",
    13: "vgvsnw",
    14: "ctrl",
    15: "nvgvswa",
    16: "ctrl",
    17: "nvgvsnw",
    18: "ctrl",
    19: "vgvswa",
    20: "ctrl",
    21: "nvngvsnw",
    22: "ctrl",
    23: "vgvswa",
    24: "ctrl",
    25: "nvgvswb",
    26: "ctrl",
    27: "nvngvsnw",
    28: "ctrl",
    29: "nvgvswa",
    30: "ctrl",
}


def main() -> None:
    reaches = pd.read_csv(REACH_SUMMARY_FILE)
    full_df = _load_segmented(SEGMENTED_FILE)
    endpoints = calculate_endpoints(full_df, reaches, TARGET_Z, (TARGET_X, TARGET_Y))

    endpoints = endpoints[endpoints["Trial_Number"] != 1].copy()
    reaches = reaches[reaches["Trial_Number"] != 1].copy()
    full_df = full_df[full_df["Trial_Number"] != 1].copy()

    endpoints["Condition"] = endpoints["Trial_Number"].map(TRIAL_LABELS)
    reaches["Condition"] = reaches["Trial_Number"].map(TRIAL_LABELS)

    missing = sorted(endpoints.loc[endpoints["Condition"].isna(), "Trial_Number"].unique().tolist())
    if missing:
        raise ValueError(f"Missing labels for trials: {missing}")

    endpoints["Trial_Label"] = endpoints["Trial_Number"].astype(str) + "_" + endpoints["Condition"]
    reaches["Trial_Label"] = reaches["Trial_Number"].astype(str) + "_" + reaches["Condition"]

    endpoints.to_csv(OUT_CSV, index=False)

    # Reuse the existing visual generator, but temporarily relabel trials to annotated strings
    trial_order = sorted(endpoints["Trial_Number"].unique())
    label_map = {trial: f"{trial}_{TRIAL_LABELS[trial]}" for trial in trial_order}

    endpoints_vis = endpoints.copy()
    reaches_vis = reaches.copy()
    full_df_vis = full_df.copy()

    # Preserve original numeric trial order for grouping while exposing text labels in hover output.
    endpoints_vis["Condition"] = endpoints_vis["Trial_Number"].map(TRIAL_LABELS)

    create_interactive_visualization(
        endpoints_vis,
        full_df_vis,
        reaches_vis,
        TARGET_Z,
        OUT_HTML,
        (TARGET_X, TARGET_Y, TARGET_Z),
    )

    print(f"Saved labeled CSV to: {OUT_CSV.resolve()}")
    print(f"Saved labeled HTML to: {OUT_HTML.resolve()}")
    print("Trial labels:")
    for trial in trial_order:
        print(f"  {trial}: {label_map[trial]}")


if __name__ == "__main__":
    main()
