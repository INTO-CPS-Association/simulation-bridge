# Performance Metrics

This guide explains how to enable performance logging in the Simulation Bridge and how to interpret each column in the generated CSV file.

## Enable Monitoring

Add or modify the following section in your `config.yaml`:

```yaml
performance:
  enabled: true # Enable performance logging
  file: performance_log/performance_metrics_v3.csv # CSV output path
```

The parent directory will be created automatically if it doesn't exist.

A new row is appended to the CSV each time the bridge processes a client request.

## CSV Schema - Column Descriptions

| Column                                | Type                  | Description                                                                                                                                                                                                                                      |
| ------------------------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Operation ID**                      | String (UUID)         | Unique identifier for each request. Used for cross-referencing logs and traces.                                                                                                                                                                  |
| **Timestamp**                         | Float (epoch seconds) | Time when `start_operation()` is called. Serves as the reference point for all time deltas.                                                                                                                                                      |
| **Request Received Time**             | Float (seconds)       | When the bridge's event loop first registers the incoming API call.                                                                                                                                                                              |
| **Core Received Input Time**          | Float (seconds)       | The moment when the simulation core acknowledged and buffered the input payload (i.e., when it consumed the data from the bridge). The difference between `Core Received Input Time` and `Request Received Time` quantifies the signal overhead. |
| **Core Sent Input Time**              | Float (seconds)       | The point when the bridge finished delivering the prepared input to the simulation core.                                                                                                                                                         |
| **Number of Results**                 | Integer               | Count of partial results produced by the core (`len(Result Times)`).                                                                                                                                                                             |
| **Result Times**                      | List                  | Semicolon-separated timestamps when each partial result arrives at the bridge.                                                                                                                                                                   |
| **Result Sent Times**                 | List                  | Timestamps when results are sent from the bridge to the client. Same length as Result Times.                                                                                                                                                     |
| **Simulation Request Completed Time** | Float (seconds)       | When the final byte of the last response is sent. Represents the true end-to-end completion.                                                                                                                                                     |
| **CPU Percent**                       | Float (%)             | Instantaneous CPU usage of the bridge process when the row is written. Useful for identifying performance spikes.                                                                                                                                |
| **Memory RSS (MB)**                   | Float (MiB)           | Resident memory usage of the bridge process at the time of measurement.                                                                                                                                                                          |
| **Total Duration**                    | Float (seconds)       | `Simulation Request Completed Time - Request Received Time`. The total latency perceived by the client.                                                                                                                                          |
| **Average Result Interval**           | Float (seconds)       | Average time between successive results in Result Times (0 if fewer than 2 results). Indicates streaming frequency.                                                                                                                              |
| **Input Overhead**                    | Float (seconds)       | `Core Sent Input Time - Request Received Time`. Time spent in the bridge before core processing begins.                                                                                                                                          |
| **Output Overheads**                  | List                  | For each result i: `Result Sent Times[i] - Result Times[i]`. Serialization and transport delay per result chunk.                                                                                                                                 |
| **Total Overheads**                   | List                  | `Input Overhead + Output Overheads[i]`. Complete bridge processing time contribution per result chunk.                                                                                                                                           |

> **Note:**
>
> - **Output Overheads** and **Total Overheads** are stored as lists to maintain consistency across batch, streaming, and interactive modes
