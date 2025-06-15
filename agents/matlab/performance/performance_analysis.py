"""
Performance analysis module for MATLAB simulation bridge.

This module analyzes performance metrics collected during MATLAB simulations,
calculates overheads, and generates visualizations and reports.
"""

import pandas as pd
import matplotlib.pyplot as plt


def plot_agent_overhead(df, mean_overhead):
    """Plot agent overhead metrics and save to file."""
    plt.figure(figsize=(12, 8))
    plt.plot(df["Operation ID"], df["Agent Overhead (s)"],
             'b-o', label="Agent Overhead")
    plt.axhline(mean_overhead, color='r', linestyle='--',
                label=f"Mean Overhead ({mean_overhead:.4f}s)")

    plt.title("Agents Overhead", fontsize=16)
    plt.xlabel("Request ID")
    plt.ylabel("Agent Overhead (seconds)")
    plt.xticks(rotation=45, ha='right')
    plt.legend(loc="best", fontsize=12)
    plt.grid(True)

    note_agent = (
        "Note:\n"
        "Agent Overhead is the time spent excluding MATLAB startup and simulation durations.\n"
        "It represents overhead in processing the request."
    )
    plt.text(
        0.5, -0.4,
        note_agent,
        ha='center', va='top', fontsize=10, color='black', transform=plt.gca().transAxes,
        bbox={"facecolor": 'white', "alpha": 0.8, "boxstyle": 'round,pad=0.5'}
    )
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    plt.savefig("agents_overhead.png")
    plt.close()


def plot_startup_ratio(mean_startup_ratio):
    """Plot startup/total ratio as pie chart and save to file."""
    # Pie chart values: startup ratio vs other duration
    labels = ["Startup Duration", "Other Duration"]
    sizes = [mean_startup_ratio, 1 - mean_startup_ratio]
    colors = ['#66b3ff', '#ff9999']

    plt.figure(figsize=(8, 8))
    plt.pie(
        sizes,
        labels=labels,
        autopct='%1.1f%%',
        startangle=90,
        colors=colors,
        wedgeprops={'edgecolor': 'black'},
        textprops={'fontsize': 12}
    )
    plt.title("Average Startup / Total Duration Ratio", fontsize=14)
    explanation_text = (
        "Note:\n"
        "Simulation Duration is excluded.\n"
        "This ratio shows the average time spent\n"
        "starting MATLAB relative to total processing time\n"
        "(excluding simulation), i.e., message handling and response."
    )
    plt.text(
        0, -1.4, explanation_text,
        ha='center', va='top', fontsize=10,
        bbox={"facecolor": 'white', "alpha": 0.8, "boxstyle": 'round,pad=0.5'}
    )
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    plt.savefig("startup_total_ratio_pie.png")
    plt.close()


def plot_resource_usage(df_sorted):
    """Plot CPU and memory usage and save to file."""
    _, ax1 = plt.subplots(figsize=(14, 7))

    color_cpu = 'tab:green'
    ax1.set_xlabel("Request ID")
    ax1.set_ylabel("CPU Usage (%)", color=color_cpu)
    ax1.plot(df_sorted["Operation ID"],
             df_sorted["CPU Usage (%)"], 'g-o', label="CPU Usage (%)")
    ax1.tick_params(axis='y', labelcolor=color_cpu)
    ax1.tick_params(axis='x', rotation=45)
    ax1.grid(True)

    ax2 = ax1.twinx()
    color_mem = 'tab:blue'
    ax2.set_ylabel("Memory RSS (MB)", color=color_mem)
    ax2.plot(df_sorted["Operation ID"],
             df_sorted["Memory RSS (MB)"], 'b-s', label="Memory RSS (MB)")
    ax2.tick_params(axis='y', labelcolor=color_mem)

    plt.title("CPU and Memory Usage", fontsize=16)

    note_resource = (
        "Note:\n"
        "CPU Usage (%) and Memory RSS (MB) are shown for each request.\n"
        "Helps monitor resource consumption during performance tests."
    )
    plt.text(
        0.5, -0.5, note_resource,
        ha='center', va='top', fontsize=10, color='black', transform=plt.gca().transAxes,
        bbox={"facecolor": 'white', "alpha": 0.8, "boxstyle": 'round,pad=0.5'}
    )

    plt.tight_layout(rect=[0, 0, 1, 1])
    plt.savefig("resource_usage.png")
    plt.close()


def main():
    """Main function to run performance analysis and generate report."""
    # --- Load data ---
    df = pd.read_csv("../performance_log/performance_metrics.csv")

    # --- Calculate Agent Overhead ---
    df["Agent Overhead (s)"] = (
        df["Total Duration (s)"]
        - df["MATLAB Startup Duration (s)"]
        - df["Simulation Duration (s)"]
    )

    # --- Calculate mean overhead ---
    mean_overhead = df["Agent Overhead (s)"].mean()

    # --- Plot Agent Overhead ---
    plot_agent_overhead(df, mean_overhead)

    # --- Calculate Startup / Total Duration Ratio ---
    df["Startup/Total Ratio"] = (
        df["MATLAB Startup Duration (s)"]
        / (df["Total Duration (s)"] - df["Simulation Duration (s)"])
    )
    mean_startup_ratio = df["Startup/Total Ratio"].mean()

    # --- Plot Startup Ratio ---
    plot_startup_ratio(mean_startup_ratio)

    # --- Plot CPU and Memory Usage ---
    df_sorted = df.sort_values("Operation ID")
    plot_resource_usage(df_sorted)

    # --- Generate Markdown report ---
    generate_markdown_report(df, mean_overhead, mean_startup_ratio)


def generate_markdown_report(dataframe, mean_agent_overhead, mean_startup_ratio):
    """
    Generate a Markdown report file with analysis results.

    Args:
        dataframe (pd.DataFrame): Full dataframe with overhead calculated.
        mean_agent_overhead (float): Mean of agent overhead.
        mean_startup_ratio (float): Mean startup/total duration ratio.
    """
    lines = []

    # Title
    lines.append("# Performance Analysis Report\n")

    # --- Overview / Summary ---
    mean_cpu = dataframe["CPU Usage (%)"].mean()
    mean_mem = dataframe["Memory RSS (MB)"].mean()

    lines.append("## 🔍 Summary Overview\n")
    lines.append(
        "Here is a concise summary of the key performance metrics "
        "averaged over all requests:\n"
    )
    # Using blockquote and bold for clear metric display
    lines.append("> **Mean Agent Overhead:** "
                 f"`{mean_agent_overhead:.4f} seconds`\n")
    lines.append("> **Mean Startup / Total Duration Ratio:** "
                 f"`{mean_startup_ratio:.4f}`\n")
    lines.append("> **Mean CPU Usage:** "
                 f"`{mean_cpu:.2f}%`\n")
    lines.append("> **Mean Memory RSS:** "
                 f"`{mean_mem:.2f} MB`\n")

    lines.append("---\n")

    # --- Agent Overhead Section ---
    lines.append("## 📊 Agent Overhead by Operation ID\n")
    lines.append(
        "Agent Overhead is the time spent processing a request *excluding* "
        "MATLAB startup and simulation durations. "
        "This metric helps identify the processing overhead for each operation.\n"
    )
    lines.append("| Operation ID | Agent Overhead (s) |")
    lines.append("|--------------|--------------------|")
    for _, row in dataframe.iterrows():
        lines.append(f"| {row['Operation ID']} | {row['Agent Overhead (s)']:.4f} |")

    lines.append(f"\n**Mean Agent Overhead:** {mean_agent_overhead:.4f} seconds\n")

    lines.append("![Agents Overhead](agents_overhead.png)\n")
    lines.append("---\n")

    # --- Startup / Total Duration Ratio Section ---
    lines.append("## ⏳ Startup / Total Duration Ratio (Batch Requests)\n")
    lines.append(
        "This ratio represents the proportion of time spent starting MATLAB "
        "relative to total processing time (excluding simulation). "
        "A higher ratio indicates more startup overhead per request.\n"
    )
    lines.append("| Operation ID | Startup / Total Ratio |")
    lines.append("|--------------|----------------------|")
    for _, row in dataframe.iterrows():
        lines.append(f"| {row['Operation ID']} | {row['Startup/Total Ratio']:.4f} |")

    lines.append(f"\n**Average Startup / Total Duration Ratio:** {mean_startup_ratio:.4f}\n")

    lines.append("![Startup / Total Duration Ratio Pie Chart](startup_total_ratio_pie.png)\n")
    lines.append("---\n")

    # --- Resource Usage Summary Section ---
    lines.append("## 🖥️ Resource Usage Summary\n")
    lines.append(
        "This section summarizes the average CPU and memory consumption "
        "across all requests. Monitoring these metrics helps identify resource "
        "usage patterns and potential bottlenecks.\n"
    )
    lines.append(f"- **Mean CPU Usage (%):** `{mean_cpu:.2f}`")
    lines.append(f"- **Mean Memory RSS (MB):** `{mean_mem:.2f}`\n")

    lines.append("![CPU and Memory Usage](resource_usage.png)\n")

    # Write to file
    with open("report_performance.md", "w", encoding="utf-8") as file:
        file.write("\n".join(lines))

    print("Markdown report 'report_performance.md' generated successfully.")

if __name__ == "__main__":
    main()
