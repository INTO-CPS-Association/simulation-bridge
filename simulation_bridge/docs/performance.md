# Performance Metrics

To track the performance of the simulation bridge, you need to enable performance monitoring in the configuration file `config.yaml`:

```yaml
# config.yaml
performance:
  enabled: true
  file: performance_log/performance_metrics_streaming.csv
```

This file and folder will be automatically generated and updated with the bridge's performance metrics.

## Column-by-Column Guide

### Operation ID

**Type:** string (UUID)  
**Description:** Unique identifier for the simulation request being tracked.

---

### Timestamp

**Type:** float (UNIX epoch seconds)  
**Description:** Wall-clock time when the `PerformanceMonitor.start_operation()` call was executed. This provides the absolute start time of monitoring but is **not** used in calculations.

---

### Request Received Time

**Type:** float (seconds)  
**Description:** The moment when the bridge's event loop recorded the arrival of the API request from the client (first signal in the pipeline).

---

### Core Received Input Time

**Type:** float (seconds)  
**Description:** The moment when the simulation core acknowledged and buffered the input payload (i.e., when it consumed the data from the bridge).

**Signal overhead:** The difference between `Core Received Input Time` and `Request Received Time` quantifies the signal overhead.

---

### Core Sent Input Time

**Type:** float (seconds)  
**Description:** The point when the bridge finished delivering the prepared input to the simulation core.

---

### Number of Results

**Type:** integer  
**Description:** The number of partial results that were observed (`len(result_times)`).

---

### Result Sent Time

**Type:** float (seconds)  
**Description:** Wall-clock time when the bridge began sending the final reply to the client.

---

### Simulation Request Completed Time

**Type:** float (seconds)  
**Description:** The moment when the bridge finished transmitting the final response and closed the request.

---

### CPU Percent

**Type:** float (%)  
**Description:** CPU load of the bridge process at the moment the event is logged. This is a snapshot value, not an average over time.

---

### Memory RSS (MB)

**Type:** float (MiB)  
**Description:** Amount of RAM the bridge process is using at the same moment.

---

### Total Duration

**Equation:**

```text
Total Duration = Simulation Request Completed Time − Request Received Time
```

**Unit:** seconds  
**Description:** End-to-end latency as perceived by the client.

---

### Average Result Interval

**Equation:**

```python
# result_times is a chronologically-sorted list of partial-result timestamps
intervals = [t2 - t1 for t1, t2 in zip(result_times, result_times[1:])]
Average Result Interval = sum(intervals) / len(intervals)  # only if len(result_times) > 1
```

**Unit:** seconds  
**Description:** Mean spacing between consecutive partial results. In streaming mode, this approximates the output cadence.

---

### Input Overhead

**Equation:**

```text
Input Overhead = Core Sent Input Time − Request Received Time
```

**Unit:** seconds  
**Description:** Time taken by the bridge to receive the request, convert it into an event, forward it to the simulation core, and deliver it to the simulation agent, excluding communication protocol overhead.

---

### Output Overhead

**Equation (batch):**

```text
Output Overhead = Result Sent Time − last_result_time
```

**Unit:** seconds  
**Description:** Time spent after the simulation core produces its **last** result, but before the result is actually sent out.

> **Batch mode** – In a batch simulation, agents produce 3 results: 2 partial and 1 final. In this case, `last_result_time` refers to the timestamp of the third result, which is the only "real" outcome of the simulation. The output overhead therefore represents the time taken to serialize and send the final result.

> **Streaming/Interactive mode** – In a streaming/interactive setup, this equation only measures how long the final result takes to be sent (also called tail latency). To characterize steady-state latency, you may compute the average of `(next_send_time − result_time)` for every emitted chunk.  
> **This enhancement is not yet implemented in the current monitor.**

---

### Total Overhead

**Equation:**

```text
Total Overhead = Input Overhead + Output Overhead
```

**Unit:** seconds  
**Description:** Aggregate latency introduced by the bridge itself.

## Example Timeline (Batch)

```
|<-- Input Overhead -->|<---- Core Compute ---->|<- Output Overhead ->|
0s                 1.4s                   12.6s                  14.1s
Request→Core in  Core executes     Last result      Reply leaves bridge
```
