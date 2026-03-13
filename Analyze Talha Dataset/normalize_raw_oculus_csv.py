import argparse
from pathlib import Path

import numpy as np
import pandas as pd


RAW_COLUMNS = [
    "HeadQX",
    "HeadQY",
    "HeadQZ",
    "HeadQW",
    "HeadX",
    "HeadY",
    "HeadZ",
    "HandX",
    "HandY",
    "HandZ",
    "TF",
    "truetime",
    "seconds",
    "timestamp",
]


def normalize_headerless_oculus_csv(input_path: Path, output_path: Path) -> None:
    df = pd.read_csv(input_path, header=None, names=RAW_COLUMNS)

    clean_timestamps = (
        df["timestamp"]
        .astype(str)
        .str.replace("Day: ", "", regex=False)
        .str.replace(" Time: ", " ", regex=False)
    )
    parsed = pd.to_datetime(clean_timestamps, errors="coerce")
    if parsed.isna().all():
        raise ValueError("Could not parse timestamp column from raw Oculus file.")

    valid = parsed.dropna()
    start = valid.iloc[0]
    end = valid.iloc[-1]

    # These raw files often have repeated/coarse timestamps. Reconstruct a monotonic timeline
    # spanning the observed recording interval while preserving row count.
    reconstructed = pd.date_range(start=start, end=end, periods=len(df))

    for col in RAW_COLUMNS[:-1]:
        df[col] = pd.to_numeric(df[col], errors="ignore")

    df["Timestamp"] = reconstructed.strftime("%Y-%m-%d %H:%M:%S.%f")
    df.to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize a headerless Oculus CSV by applying standard headers and reconstructing Timestamp.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    normalize_headerless_oculus_csv(input_path, output_path)
    print(f"Saved normalized file to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
