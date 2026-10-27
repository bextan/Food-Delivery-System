import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import List
from src.simulation.engine import MetricSnapshot, SimulationEngine

def generate_telemetry_dashboard(
    baseline_sim: SimulationEngine,
    surge_sim: SimulationEngine,
    output_path: str = "/workspace/scratch/food-delivery-mediator/telemetry_dashboard.png"
):
    """
    Renders a 4-panel high-resolution architectural telemetry dashboard
    illustrating the Event-Driven Mediator Bottleneck.
    """
    # Convert snapshots to DataFrames
    df_base = pd.DataFrame([s.__dict__ for s in baseline_sim.snapshots])
    df_surge = pd.DataFrame([s.__dict__ for s in surge_sim.snapshots])
    
    # Configure stylish dark-slate theme for modern observability UI
    plt.style.use('dark_background')
    fig, axes = plt.subplots(2, 2, figsize=(16, 11), dpi=160)
    fig.patch.set_facecolor('#0d1117')
    for ax in axes.flat:
        ax.set_facecolor('#161b22')
        ax.grid(True, linestyle='--', alpha=0.25, color='#8b949e')
        ax.tick_params(colors='#c9d1d9', labelsize=10)
        for spine in ax.spines.values():
            spine.set_color('#30363d')
            spine.set_linewidth(1.2)

    # ----------------------------------------------------
    # Panel 1: Initiating Event Queue Backlog (The Core Bottleneck)
    # ----------------------------------------------------
    ax1 = axes[0, 0]
    ax1.plot(df_base['time'], df_base['queue_depth'], label='Normal Load (λ=1.2 ord/s)', color='#3fb950', linewidth=2.0)
    ax1.plot(df_surge['time'], df_surge['queue_depth'], label='Dinner Surge (λ=8.5 ord/s + Rainstorm)', color='#f85149', linewidth=2.5)
    ax1.axvline(x=40, color='#d29922', linestyle='--', linewidth=1.5, label='Surge Rush (t=40s)')
    ax1.axvline(x=60, color='#db61a2', linestyle=':', linewidth=1.5, label='Rainstorm Delay (t=60s)')
    ax1.fill_between(df_surge['time'], df_surge['queue_depth'], color='#f85149', alpha=0.18)
    
    ax1.set_title("1. Initiating Event Queue Depth [Mediator Ingestion Backlog]", fontsize=12, fontweight='bold', color='#58a6ff', pad=12)
    ax1.set_xlabel("Simulation Timeline (seconds)", color='#8b949e', fontsize=10)
    ax1.set_ylabel("Queued Orders Waiting for Mediator Slot", color='#8b949e', fontsize=10)
    ax1.legend(loc='upper left', framealpha=0.85, facecolor='#21262d', edgecolor='#30363d', fontsize=8.5)
    
    max_q_time = df_surge.loc[df_surge['queue_depth'].idxmax(), 'time']
    max_q_val = df_surge['queue_depth'].max()
    ax1.annotate(
        f'Peak Backlog: {max_q_val} orders\nMediator slots 100% full',
        xy=(max_q_time, max_q_val),
        xytext=(max_q_time - 75, max_q_val * 0.75),
        arrowprops=dict(facecolor='#f85149', shrink=0.05, width=1.5, headwidth=6),
        bbox=dict(boxstyle="round,pad=0.4", fc="#21262d", ec="#f85149", lw=1.5),
        fontsize=9, color="#f85149", fontweight='bold'
    )

    # ----------------------------------------------------
    # Panel 2: End-to-End Latency & Degradation Breakdown
    # ----------------------------------------------------
    ax2 = axes[0, 1]
    completed_base = baseline_sim.mediator.completed_orders
    completed_surge = surge_sim.mediator.completed_orders
    
    base_wait = [o.queue_wait_time for o in completed_base] if completed_base else [0]
    base_orch = [o.orchestration_time for o in completed_base] if completed_base else [0]
    surge_wait = [o.queue_wait_time for o in completed_surge] if completed_surge else [0]
    surge_orch = [o.orchestration_time for o in completed_surge] if completed_surge else [0]
    
    categories = ['Normal Load\n(Completed)', 'Surge Load\n(Completed)']
    avg_wait = [float(np.mean(base_wait)), float(np.mean(surge_wait))]
    avg_orch = [float(np.mean(base_orch)), float(np.mean(surge_orch))]
    
    x = np.arange(len(categories))
    width = 0.42
    p1 = ax2.bar(x, avg_wait, width, label='Queue Ingestion Delay (Starvation Wait)', color='#f85149', alpha=0.88)
    p2 = ax2.bar(x, avg_orch, width, bottom=avg_wait, label='Active Orchestration Time (4 Processors)', color='#1f6feb', alpha=0.88)
    
    ax2.set_title("2. Latency Composition: Ingestion Wait vs Active Processing", fontsize=12, fontweight='bold', color='#58a6ff', pad=12)
    ax2.set_xticks(x)
    ax2.set_xticklabels(categories, color='#c9d1d9', fontsize=10)
    ax2.set_ylabel("Average Latency (seconds)", color='#8b949e', fontsize=10)
    
    max_height = max(avg_wait[1] + avg_orch[1], 10)
    ax2.set_ylim(0, max_height * 1.35)
    ax2.legend(loc='upper left', framealpha=0.85, facecolor='#21262d', edgecolor='#30363d', fontsize=8.5)
    
    for idx, (w, o) in enumerate(zip(avg_wait, avg_orch)):
        total = w + o
        ax2.text(idx, total + (max_height * 0.04), f"Total: {total:.1f}s\n(Wait: {w:.1f}s)", ha='center', va='bottom', color='#e6edf3', fontsize=9.5, fontweight='bold')

    # ----------------------------------------------------
    # Panel 3: Component Utilization & The Starvation Paradox
    # ----------------------------------------------------
    ax3 = axes[1, 0]
    surge_mediator_util = df_surge[df_surge['time'] > 100]['mediator_utilization'].mean()
    pay_util = (df_surge[df_surge['time'] > 100]['payment_busy_workers'].mean() / surge_sim.payment_proc.num_workers) * 100
    kit_util = (df_surge[df_surge['time'] > 100]['kitchen_busy_workers'].mean() / surge_sim.kitchen_proc.num_workers) * 100
    cou_util = (df_surge[df_surge['time'] > 100]['courier_busy_workers'].mean() / surge_sim.courier_proc.num_workers) * 100
    not_util = (df_surge[df_surge['time'] > 100]['notification_busy_workers'].mean() / surge_sim.notification_proc.num_workers) * 100
    
    components = ['Event Mediator\n(Orchestrator)', 'Courier\nProcessor', 'Kitchen\nProcessor', 'Payment\nProcessor', 'Notification\nProcessor']
    utilizations = [surge_mediator_util, cou_util, kit_util, pay_util, not_util]
    bar_colors = ['#f85149', '#d29922', '#db61a2', '#238636', '#388bfd']
    
    bars = ax3.bar(components, utilizations, color=bar_colors, width=0.55, edgecolor='#30363d', linewidth=1.2)
    ax3.axhline(y=100, color='#f85149', linestyle='--', alpha=0.5, label='100% Saturation Barrier')
    ax3.set_title("3. The Starvation Paradox: Orchestrator vs Worker Utilization", fontsize=12, fontweight='bold', color='#58a6ff', pad=12)
    ax3.set_ylabel("Capacity Utilization (%) during Peak Surge", color='#8b949e', fontsize=10)
    ax3.set_ylim(0, 118)
    
    for bar in bars:
        h = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width() / 2.0, h + 2.0, f"{h:.1f}%", ha='center', va='bottom', color='#e6edf3', fontsize=9, fontweight='bold')
    
    ax3.annotate(
        'Starved Workers!\nMediator cannot feed work fast enough',
        xy=(3, pay_util),
        xytext=(2.2, 52),
        arrowprops=dict(facecolor='#58a6ff', shrink=0.05, width=1.2, headwidth=5),
        bbox=dict(boxstyle="round,pad=0.3", fc="#21262d", ec="#58a6ff", lw=1.2),
        fontsize=8.5, color="#58a6ff"
    )

    # ----------------------------------------------------
    # Panel 4: Ingestion Rate vs Fulfilled vs Timed-Out (SLA Breach)
    # ----------------------------------------------------
    ax4 = axes[1, 1]
    ax4.plot(df_surge['time'], df_surge['completed_cumulative'], label='Completed Orders (SLA Met)', color='#3fb950', linewidth=2.2)
    ax4.plot(df_surge['time'], df_surge['timed_out_cumulative'], label=f'Timed-Out / Abandoned (> {surge_sim.timeout_threshold:.0f}s SLA)', color='#f85149', linewidth=2.2)
    ax4.set_title("4. Cumulative Order Outcomes under Surge", fontsize=12, fontweight='bold', color='#58a6ff', pad=12)
    ax4.set_xlabel("Simulation Timeline (seconds)", color='#8b949e', fontsize=10)
    ax4.set_ylabel("Cumulative Order Volume", color='#8b949e', fontsize=10)
    ax4.legend(loc='upper left', framealpha=0.85, facecolor='#21262d', edgecolor='#30363d', fontsize=8.5)
    
    # Subtitle / Super title
    fig.suptitle("EVENT-DRIVEN ARCHITECTURE (MEDIATOR TOPOLOGY) — BOTTLENECK TELEMETRY\nFood Delivery Order Dispatch Simulation (Richards & Ford Architecture Model)", fontsize=14, fontweight='bold', color='#f0f6fc', y=0.985)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    plt.savefig(output_path, dpi=160, bbox_inches='tight')
    plt.close()
    print(f"[Telemetry Plotter] Dashboard successfully saved to: {output_path}")
