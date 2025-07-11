# Performance Analysis

Command-line tool for **quantifying the overhead introduced by the Simulation Bridge**.

It scans the raw CSV logs emitted by the _sim-bridge_ Performance Monitor and produces a compact report (CSV) with key statistics per:

1. **Client Protocol** (e.g. REST, MQTT)
2. **Simulation Type** (batch, streaming, interactive)

The output helps you spot latency outliers, compare protocols, and track performance trends over time.

> ⚠️ Before running this analysis, make sure the Performance Monitor is enabled in the Simulation Bridge configuration file.

## What is "Total Overhead"?

The **Total Overhead** is a performance metric that quantifies the internal time spent within the Simulation Bridge, excluding the actual simulation time and protocol transmission delays.

It consists of two components:

- **Input Overhead:** Time taken from when a request is received by the bridge to when it is handed off to the simulation core (i.e., routing, decoding, and buffering).

- **Output Overhead:** For each result (including partial results), the time between when the bridge receives it from the simulator and when it sends it out to the client.

## Requirements

- Python 3.8+
- pandas 2.0+
- numpy 1.23+

```bash
pip install -r requirements.txt
```

## Usage

**Default execution:**

```bash
python performance_analysis.py
```

- Input: `../performance_log/performance_metrics.csv`
- Output: `total_overhead_summary.csv`

**Custom paths:**

```bash
python performance_analysis.py \
    --input ../performance_log/performance_metrics_v4.csv \
    --output results/overhead_summary.csv
```

## Output Format

The script produces a CSV file where each row summarizes the performance of a specific (Client Protocol, Simulation Type) combination.

**Example output:**

| Client Protocol | Simulation Type | Median_ms | StdDev_ms | Pct5_ms | Pct95_ms |
| --------------- | --------------- | --------- | --------- | ------- | -------- |
| MQTT            | batch           | 2.47      | 10.49     | 1.69    | 11.98    |
| AMQP            | batch           | 1.95      | 0.99      | 1.12    | 3.69     |
| REST            | batch           | 4.63      | 4.72      | 2.92    | 11.42    |

Each column provides insight into the average overhead time introduced by the Simulation Bridge per simulation operation, measured in milliseconds.

### Column Definitions

- **Client Protocol**: The communication protocol used by the client (e.g., REST, MQTT)
- **Simulation Type**: The type of simulation executed (batch, streaming, or interactive)
- **Median_ms**: The median of the average total overhead across all operations of this type. This is the central (typical) value and a good measure of consistent performance
- **StdDev_ms**: The standard deviation of the overhead values. Higher values indicate greater variability or inconsistency in performance
- **Pct5_ms and Pct95_ms**: The 5th and 95th percentiles. These define the typical range of performance:
  - **Pct5_ms**: 5% of operations performed faster than this threshold
  - **Pct95_ms**: 95% of operations performed faster than this threshold
  - Together, they help detect outliers and define performance bounds
