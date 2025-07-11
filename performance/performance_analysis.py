from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


DEFAULT_INPUT  = Path("../performance_log/performance_metrics.csv")
DEFAULT_OUTPUT = Path("total_overhead_summary.csv")


def parse_and_average(cell: str | float | int | pd.NA) -> float | np.float64:
    """
    Convert a semicolon-separated list of numbers (seconds) to the mean
    in **milliseconds**.
    """
    if pd.isna(cell):
        return np.nan
    values = [float(x) for x in str(cell).split(";") if x.strip()]
    if not values:
        return np.nan
    # Seconds → milliseconds
    return np.mean(values) * 1_000.0


def build_parser() -> argparse.ArgumentParser:
    """ Builds the command-line argument parser for the script."""
    parser = argparse.ArgumentParser(
        description="Analyse PerformanceMonitor CSV and create a summary.")
    parser.add_argument(
        "-i", "--input", type=Path, default=DEFAULT_INPUT,
        help=f"Path to the raw PerformanceMonitor CSV (default: {DEFAULT_INPUT})")
    parser.add_argument(
        "-o", "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Path for the summary CSV (default: {DEFAULT_OUTPUT})")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    df = pd.read_csv(args.input)
    df.columns = df.columns.str.strip()  # remove any whitespace in headers

    required_cols = {"Client Protocol", "Simulation Type", "Total Overheads"}
    missing = required_cols - set(df.columns)
    if missing:
        raise KeyError(f"Missing columns in CSV: {', '.join(missing)}")

    # Compute mean Total Overhead per operation
    df["Avg Total Overhead"] = df["Total Overheads"].apply(parse_and_average)

    # Group and aggregate statistics
    groups = df.groupby(["Client Protocol", "Simulation Type"])
    summary = groups["Avg Total Overhead"].agg(
        Median="median",
        StdDev="std",
        Pct5=lambda x: np.percentile(x.dropna(), 5),
        Pct95=lambda x: np.percentile(x.dropna(), 95),
    ).reset_index()

    summary.to_csv(args.output, index=False)
    print(f"Summary saved to {args.output}")


if __name__ == "__main__":
    main()
