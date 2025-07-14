from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


DEFAULT_INPUT  = Path("../performance_log/performance_metrics.csv")
DEFAULT_OUTPUT = Path("overhead_summary.csv")


def parse_and_average(cell: str | float | int | pd.NA) -> float | np.float64:
    """
    Convert a semicolon-separated list of numbers (seconds) to the mean
    in **milliseconds**. If the cell is empty or NaN → np.nan.
    """
    if pd.isna(cell):
        return np.nan
    values = [float(x) for x in str(cell).split(";") if x.strip()]
    if not values:
        return np.nan
    # Seconds → milliseconds
    return np.mean(values) * 1_000.0


def build_parser() -> argparse.ArgumentParser:
    """Builds the command-line argument parser for the script."""
    parser = argparse.ArgumentParser(
        description="Analyse PerformanceMonitor CSV and create an overhead summary.")
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
    df.columns = df.columns.str.strip()          # Remove spaces in column names

    # Check that required columns exist
    required_cols = {
        "Client Protocol",
        "Simulation Type",
        "Input Overhead",
        "Output Overheads",
        "Total Overheads",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise KeyError(f"Missing columns in CSV: {', '.join(sorted(missing))}")

    # Convert the three overhead columns to milliseconds (average per row)
    df["Avg Input Overhead"]   = df["Input Overhead"].apply(parse_and_average)
    df["Avg Output Overhead"]  = df["Output Overheads"].apply(parse_and_average)
    df["Avg Total Overhead"]   = df["Total Overheads"].apply(parse_and_average)

    # Group by Client Protocol + Simulation Type and calculate statistics
    groups = df.groupby(["Client Protocol", "Simulation Type"])

    summary = groups.agg(
        # Input Overhead
        Input_Median = pd.NamedAgg(
            column="Avg Input Overhead", aggfunc="median"),
        Input_StdDev = pd.NamedAgg(
            column="Avg Input Overhead", aggfunc="std"),
        Input_Pct5  = pd.NamedAgg(
            column="Avg Input Overhead", aggfunc=lambda x: np.percentile(x.dropna(), 5)),
        Input_Pct95 = pd.NamedAgg(
            column="Avg Input Overhead", aggfunc=lambda x: np.percentile(x.dropna(), 95)),
        # Output Overhead
        Output_Median = pd.NamedAgg(
            column="Avg Output Overhead", aggfunc="median"),
        Output_StdDev = pd.NamedAgg(
            column="Avg Output Overhead", aggfunc="std"),
        Output_Pct5  = pd.NamedAgg(
            column="Avg Output Overhead", aggfunc=lambda x: np.percentile(x.dropna(), 5)),
        Output_Pct95 = pd.NamedAgg(
            column="Avg Output Overhead", aggfunc=lambda x: np.percentile(x.dropna(), 95)),
        # Total Overhead
        Total_Median = pd.NamedAgg(
            column="Avg Total Overhead", aggfunc="median"),
        Total_StdDev = pd.NamedAgg(
            column="Avg Total Overhead", aggfunc="std"),
        Total_Pct5  = pd.NamedAgg(
            column="Avg Total Overhead", aggfunc=lambda x: np.percentile(x.dropna(), 5)),
        Total_Pct95 = pd.NamedAgg(
            column="Avg Total Overhead", aggfunc=lambda x: np.percentile(x.dropna(), 95)),
    ).reset_index()

    summary.to_csv(args.output, index=False)
    print(f"Summary saved to {args.output}")


if __name__ == "__main__":
    main()
