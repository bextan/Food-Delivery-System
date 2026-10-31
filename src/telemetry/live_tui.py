"""
Live Terminal User Interface for Event-Driven Architecture Simulator
Renders real-time ASCII/Unicode Mediator Topology Diagram, dynamic telemetry gauges,
and rolling event stream using rich.live.Live.
"""

from typing import List, Optional
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress_bar import ProgressBar
from src.simulation.engine import SimulationEngine

def make_gauge_table(label: str, current: float, maximum: float, alert_threshold: float = 0.85) -> Table:
    ratio = min(1.0, max(0.0, current / maximum if maximum > 0 else 0.0))
    if ratio >= alert_threshold:
        bar_style = "bold red"
        pct_style = "bold red"
    elif ratio >= 0.60:
        bar_style = "bold yellow"
        pct_style = "bold yellow"
    else:
        bar_style = "bold green"
        pct_style = "green"

    t = Table.grid(expand=True)
    t.add_column(justify="left", ratio=3)
    t.add_column(justify="center", ratio=4)
    t.add_column(justify="right", ratio=2)

    bar = ProgressBar(total=maximum, completed=current, width=18, complete_style=bar_style, finished_style=bar_style)
    pct_text = Text(f"{ratio*100:4.1f}% ({int(current)}/{int(maximum)})", style=pct_style)
    t.add_row(Text(label, style="bold white"), bar, pct_text)
    return t

class LiveTerminalUI:
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.layout = Layout()
        self.event_log: List[str] = [
            "[dim]Simulation initialized. Ready for order stream ingestion.[/dim]",
            "[dim]Awaiting initiating events...[/dim]"
        ]
        self._setup_layout()

    def _setup_layout(self):
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=7)
        )
        self.layout["body"].split_row(
            Layout(name="diagram", ratio=12),
            Layout(name="telemetry", ratio=11)
        )

    def log_event(self, message: str):
        self.event_log.append(message)
        if len(self.event_log) > 6:
            self.event_log.pop(0)

    def render_frame(self, sim: SimulationEngine, scenario_name: str, status_msg: str = "") -> Layout:
        t = sim.current_time
        q_depth = sim.mediator.current_queue_depth
        max_q = 250
        active_slots = sim.mediator.active_slots_used
        max_slots = sim.mediator.max_concurrency

        pay_busy = sim.payment_proc.busy_workers
        kit_busy = sim.kitchen_proc.busy_workers
        cou_busy = sim.courier_proc.busy_workers
        not_busy = sim.notification_proc.busy_workers

        is_saturated = active_slots >= max_slots
        is_backlog = q_depth > 50

        # --- 1. HEADER ---
        if is_saturated:
            status_badge = "[bold white on red] ⚠️ BOTTLENECK ACTIVE: MEDIATOR THREADS SATURATED [/bold white on red]"
        else:
            status_badge = "[bold black on green] BALANCED ARCHITECTURAL FLOW [/bold black on green]"

        header_text = Text.from_markup(
            f" [bold cyan]EVENT-DRIVEN ARCHITECTURE: MEDIATOR TOPOLOGY[/bold cyan] | "
            f"Scenario: [bold yellow]{scenario_name}[/bold yellow] | "
            f"Sim Time: [bold white]{t:5.1f}s / {sim.duration:.0f}s[/bold white] | {status_badge}"
        )
        self.layout["header"].update(Panel(header_text, style="cyan", border_style="cyan"))

        # --- 2. LEFT PANE: DYNAMIC TOPOLOGY DIAGRAM ---
        # Component status styles
        if q_depth > 100:
            q_box_style = "bold red"
            q_status_str = f"[bold red]CRITICAL BACKLOG ({q_depth})[/bold red]"
        elif q_depth > 20:
            q_box_style = "bold yellow"
            q_status_str = f"[yellow]BACKLOG FORMING ({q_depth})[/yellow]"
        else:
            q_box_style = "green"
            q_status_str = f"[green]EMPTY / CLEAR ({q_depth})[/green]"

        if is_saturated:
            med_box_style = "bold white on red"
            med_status_str = f"[bold red]⚠️ 100% EXHAUSTED ({active_slots}/{max_slots})[/bold red]"
        elif active_slots > max_slots * 0.7:
            med_box_style = "yellow"
            med_status_str = f"[yellow]HEAVY LOAD ({active_slots}/{max_slots})[/yellow]"
        else:
            med_box_style = "green"
            med_status_str = f"[green]NORMAL ({active_slots}/{max_slots})[/green]"

        # Workers status
        pay_tag = "[red bold]STARVED[/red bold]" if (is_saturated and pay_busy <= 3) else "[green]ACTIVE[/green]"
        kit_tag = "[red bold]STARVED[/red bold]" if (is_saturated and kit_busy <= 6) else "[green]ACTIVE[/green]"
        cou_tag = "[bold red]WEATHER DELAY[/bold red]" if (sim.rain_surge_active and t > 60 and cou_busy >= 24) else "[green]ACTIVE[/green]"
        not_tag = "[red bold]STARVED[/red bold]" if (is_saturated and not_busy <= 2) else "[green]ACTIVE[/green]"

        diagram_markup = f"""[bold yellow]Incoming Stream[/bold yellow]  │ λ = {sim.arrival_rate_func(t):.1f} orders/sec (Poisson Ingestion)
                ▼
┌────────────────────────────────────────────────────────┐
│ [bold white]INITIATING EVENT QUEUE[/bold white] (order-fulfillment-inbound)     │
│ Depth: [bold]{q_depth:3d} / {max_q}[/bold] orders   Status: {q_status_str}
└───────────────────────────┬────────────────────────────┘
                            │ [dim]Mediator Worker Thread Allocation[/dim]
                            ▼
┌────────────────────────────────────────────────────────┐
│ [bold white]ORDER FULFILLMENT CENTRAL MEDIATOR (SAGA ENGINE)[/bold white]       │
│ Active Slots: [{med_status_str}]  Barrier Synchronization│
│ State Table: Tracks In-Flight Multi-Step Compensations │
└──────┬────────────────────┬────────────────────┬───────┘
       │ [dim]Async Command[/dim]      │ [dim]Async Command[/dim]      │ [dim]Async Command[/dim]       │ [dim]Async Command[/dim]
       ▼                    ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ [bold white]Payment[/bold white]     │      │ [bold white]Kitchen[/bold white]     │      │ [bold white]Courier[/bold white]     │      │ [bold white]Notification[/bold white]│
│ Processor   │      │ Notifier    │      │ Matcher     │      │ Service     │
│ [{pay_busy:2d}/20 busy] │      │ [{kit_busy:2d}/25 busy] │      │ [{cou_busy:2d}/30 busy] │      │ [{not_busy:2d}/20 busy] │
│ {pay_tag:11s} │      │ {kit_tag:11s} │      │ {cou_tag:11s} │      │ {not_tag:11s} │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
  (Hold/Settle)        (Prep Est.)          (Geosearch)          (Push / SMS)"""

        diagram_panel = Panel(
            Text.from_markup(diagram_markup),
            title="[bold yellow]Architecture Topology & Live Orchestration State[/bold yellow]",
            border_style=q_box_style if is_saturated else "blue"
        )
        self.layout["diagram"].update(diagram_panel)

        # --- 3. RIGHT PANE: TELEMETRY GAUGES & METRICS ---
        metrics_table = Table.grid(expand=True, padding=(0, 1))
        metrics_table.add_column()
        
        # Add Gauges
        metrics_table.add_row(make_gauge_table("Mediator Inbound Q", q_depth, max_q, alert_threshold=0.50))
        metrics_table.add_row(make_gauge_table("Mediator Slots", active_slots, max_slots, alert_threshold=0.90))
        metrics_table.add_row(make_gauge_table("Payment Workers", pay_busy, 20, alert_threshold=0.85))
        metrics_table.add_row(make_gauge_table("Kitchen Workers", kit_busy, 25, alert_threshold=0.85))
        metrics_table.add_row(make_gauge_table("Courier Matchers", cou_busy, 30, alert_threshold=0.85))
        metrics_table.add_row(make_gauge_table("Notification Svc", not_busy, 20, alert_threshold=0.85))

        # KPI Summary Table
        completed_count = len(sim.mediator.completed_orders)
        timeout_count = len(sim.mediator.timed_out_orders)
        
        avg_wait = sum(o.queue_wait_time for o in sim.mediator.completed_orders[-50:]) / max(1, len(sim.mediator.completed_orders[-50:]))
        avg_lat = sum(o.total_latency for o in sim.mediator.completed_orders[-50:]) / max(1, len(sim.mediator.completed_orders[-50:]))

        kpi_table = Table(title="[bold cyan]Real-Time Performance Indicators[/bold cyan]", expand=True, show_header=True, header_style="bold magenta")
        kpi_table.add_column("Metric", style="white")
        kpi_table.add_column("Value", justify="right")
        kpi_table.add_column("Architecture SLA", justify="center")

        kpi_table.add_row("Orders Ingested", f"{sim.total_orders_generated:,}", "N/A")
        kpi_table.add_row("Orders Completed", f"[green]{completed_count:,}[/green]", "Throughput")
        timeout_color = "red bold" if timeout_count > 0 else "green"
        kpi_table.add_row(f"SLA Violations (>{sim.timeout_threshold:.0f}s)", f"[{timeout_color}]{timeout_count:,}[/{timeout_color}]", "< 1% Target")
        kpi_table.add_row("Queue Ingestion Delay", f"[{'red' if avg_wait > 5.0 else 'green'}]{avg_wait:5.2f}s[/{'red' if avg_wait > 5.0 else 'green'}]", "< 2.0s Target")
        kpi_table.add_row("End-to-End Latency", f"[{'red' if avg_lat > 15.0 else 'green'}]{avg_lat:5.2f}s[/{'red' if avg_lat > 15.0 else 'green'}]", "< 10.0s Target")
        
        starvation_str = "[bold red]HIGH (STARVED)[/bold red]" if (is_saturated and pay_busy < 4) else "[green]LOW (BALANCED)[/green]"
        kpi_table.add_row("Downstream Starvation", starvation_str, "Orchestration Bottleneck")

        telemetry_content = Group(metrics_table, Text(""), kpi_table)
        telemetry_panel = Panel(
            telemetry_content,
            title="[bold cyan]Live Telemetry & Workload Gauges[/bold cyan]",
            border_style="cyan"
        )
        self.layout["telemetry"].update(telemetry_panel)

        # --- 4. FOOTER: LIVE EVENT STREAM ---
        footer_lines = "\n".join(self.event_log)
        footer_panel = Panel(
            Text.from_markup(footer_lines),
            title="[bold white]Live Orchestration Event Log & System Observability Feed[/bold white]",
            border_style="magenta"
        )
        self.layout["footer"].update(footer_panel)

        return self.layout
