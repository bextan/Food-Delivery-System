#!/usr/bin/env python3
"""
Food Delivery Order Dispatch Engine (Event-Driven Architecture - Mediator Topology)
Interactive Simulation & Architectural Bottleneck Demonstrator
Reference: Software Architecture Patterns & Fundamentals of Software Architecture (Mark Richards & Neal Ford)
"""

import sys
import os
import argparse
import time
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, FloatPrompt, Confirm
from rich.table import Table
from rich.text import Text
from rich.live import Live

from src.simulation.scenarios import run_baseline_scenario, run_surge_scenario, run_custom_scenario
from src.simulation.engine import SimulationEngine
from src.telemetry.console_ui import ConsoleDashboard
from src.telemetry.live_tui import LiveTerminalUI
from src.telemetry.dashboard_plotter import generate_telemetry_dashboard

console = Console()

def run_simulation_with_live_tui(sim_func, scenario_name: str, duration: float = 240.0, step_sleep: float = 0.02) -> SimulationEngine:
    tui = LiveTerminalUI(console=console)
    tui.log_event(f"[bold cyan]▶ Starting scenario: {scenario_name}[/bold cyan]")
    tui.log_event("[dim]Mediator state table initialized. Tracking initiating events.[/dim]")
    
    def on_step(sim: SimulationEngine, log_msg: str):
        if log_msg:
            tui.log_event(log_msg)
        tui.render_frame(sim, scenario_name=scenario_name)

    with Live(tui.layout, console=console, screen=False, refresh_per_second=15) as live:
        sim = sim_func(duration=duration, on_step=on_step, render_interval=2.0, step_sleep=step_sleep)
        tui.log_event(f"[bold green]✔ Simulation completed: {len(sim.mediator.completed_orders)} orders processed.[/bold green]")
        tui.render_frame(sim, scenario_name=scenario_name)
        time.sleep(0.5)

    return sim

def launch_gui_window():
    console.print("\n[bold cyan]🚀 Launching Interactive GUI Window (Streamlit)...[/bold cyan]")
    console.print("[dim]Starting web server at http://localhost:8501 (Ctrl+C to return to CLI)...[/dim]\n")
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    os.system(f"streamlit run {app_path}")

def show_static_diagram():
    diagram = """
                     [ Incoming Customer Order Stream ]
                                     │ (Poisson Ingestion λ)
                                     ▼
                   ┌───────────────────────────────────┐
                   │       INITIATING EVENT QUEUE      │
                   │    (order-fulfillment-inbound)    │ <── [PRIMARY BOTTLENECK]
                   └─────────────────┬─────────────────┘     (Queue Backlog Explosion)
                                     │
                   ┌─────────────────▼─────────────────┐
                   │    ORDER FULFILLMENT MEDIATOR     │ <── Central Thread Pool &
                   │       (Orchestration Engine)      │     Active Workflow State Table
                   └────────┬────────┬────────┬────────┘
                            │        │        │        │
         ┌──────────────────┘        │        │        └──────────────────┐
         ▼                           ▼        ▼                           ▼
   ┌───────────┐               ┌───────────┐ ┌───────────┐          ┌───────────┐
   │  Payment  │               │  Kitchen  │ │  Courier  │          │   Push    │
   │ Processor │               │ Notifier  │ │  Matcher  │          │ Notifier  │
   └───────────┘               └───────────┘ └───────────┘          └───────────┘
   (Hold/Capture)              (POS Prep)    (Geosearch)            (Live Track)
   
   [THE STARVATION PARADOX]: Under severe courier delays, the central mediator holds
   active workflow state across barrier joins. Once mediator slots saturate, the
   initiating queue explodes while fast downstream services (Payment, Notif) sit starved!
"""
    console.print(Panel(Text(diagram, style="bold cyan"), title="[bold yellow]Event-Driven Mediator Topology Architecture[/bold yellow]", border_style="yellow"))

def show_doc_preview(filepath: str, title: str):
    if not os.path.exists(filepath):
        console.print(f"[red]Document not found: {filepath}[/red]")
        return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read(2500)
    console.print(Panel(content + "\n\n[dim]... [Open file in editor for full text] ...[/dim]", title=f"[bold green]{title}[/bold green]", border_style="green"))

def interactive_menu():
    base_sim = None
    surge_sim = None

    while True:
        console.clear()
        banner = """
[bold cyan]╔══════════════════════════════════════════════════════════════════════════════════════╗
║        [bold white]FOOD DELIVERY ORDER DISPATCH ENGINE: ARCHITECTURE BENCHMARK (CLI UI)[/bold white]         ║
║          [dim]Event-Driven Architecture: Mediator Topology Bottleneck Demonstration[/dim]       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝[/bold cyan]
"""
        console.print(banner)
        menu_table = Table.grid(padding=(0, 2))
        menu_table.add_column(style="bold yellow", justify="right")
        menu_table.add_column(style="bold white")
        menu_table.add_column(style="dim")

        menu_table.add_row("[1]", "▶  Run Baseline Load Simulation", "(Normal dinner flow, balanced throughput)")
        menu_table.add_row("[2]", "⚡  Run Surge Shock Simulation", "(Dinner rush + rainstorm -> Mediator Bottleneck!)")
        menu_table.add_row("[3]", "🔬  Run Custom Stress Test", "(Tune arrival rate, mediator slots, courier delays)")
        menu_table.add_row("[4]", "📊  Generate Visual Telemetry Dashboard", "(Saves high-res 4-panel telemetry_dashboard.png)")
        menu_table.add_row("[5]", "🌐  Launch Interactive Web GUI Window", "(Streamlit app: visual map, sliders & animations)")
        menu_table.add_row("[6]", "📐  View Architecture Diagram & Theory", "(Mark Richards Mediator Topology review)")
        menu_table.add_row("[7]", "📖  Inspect Architecture Decision Record", "(ADR-001: Mediator vs. Broker trade-offs)")
        menu_table.add_row("[8]", "📋  Inspect Software Requirements Spec", "(IEEE-830 SRS, queuing math & fitness functions)")
        menu_table.add_row("[0]", "🚪  Exit", "")

        console.print(Panel(menu_table, title="[bold green]Control Center Options[/bold green]", border_style="green"))

        choice = Prompt.ask("\n[bold cyan]Select an option[/bold cyan]", choices=["1", "2", "3", "4", "5", "6", "7", "8", "0"], default="5")

        if choice == "1":
            console.print("\n[bold yellow]Launching Baseline Normal Load Simulation with Live Telemetry...[/bold yellow]")
            base_sim = run_simulation_with_live_tui(run_baseline_scenario, "Baseline Normal Load", duration=240.0, step_sleep=0.015)
            console.print("\n[bold green]✔ Baseline Simulation Complete![/bold green]")
            ConsoleDashboard.render_live_telemetry_frame(240.0, base_sim, "Baseline Normal Load")
            Prompt.ask("\n[dim]Press Enter to return to menu...[/dim]")

        elif choice == "2":
            console.print("\n[bold red]Launching Surge Shock Bottleneck Simulation with Live Telemetry...[/bold red]")
            surge_sim = run_simulation_with_live_tui(run_surge_scenario, "Surge Peak Bottleneck", duration=240.0, step_sleep=0.015)
            console.print("\n[bold red]✔ Surge Bottleneck Simulation Complete![/bold red]")
            ConsoleDashboard.render_live_telemetry_frame(240.0, surge_sim, "Surge Peak Bottleneck")
            
            if base_sim:
                console.print(f"\n{ConsoleDashboard.BOLD}=== ARCHITECTURAL METRIC COMPARISON ==={ConsoleDashboard.RESET}")
                ConsoleDashboard.print_comparison_table(base_sim, surge_sim)
                
            Prompt.ask("\n[dim]Press Enter to return to menu...[/dim]")

        elif choice == "3":
            console.print("\n[bold yellow]Configure Custom Simulation Parameters:[/bold yellow]")
            rate = FloatPrompt.ask("  Incoming Order Arrival Rate (λ orders/sec)", default=7.5)
            slots = IntPrompt.ask("  Mediator Worker Concurrency Slots", default=35)
            rain = Confirm.ask("  Activate Rainstorm Courier Delay Shock?", default=True)
            duration = FloatPrompt.ask("  Virtual Duration (seconds)", default=200.0)

            def custom_runner(duration, on_step, render_interval, step_sleep):
                return run_custom_scenario(
                    duration=duration,
                    mediator_capacity=slots,
                    arrival_rate=rate,
                    rain_surge=rain,
                    on_step=on_step,
                    render_interval=render_interval,
                    step_sleep=step_sleep
                )

            custom_sim = run_simulation_with_live_tui(custom_runner, f"Custom Test (λ={rate}, Slots={slots})", duration=duration, step_sleep=0.015)
            ConsoleDashboard.render_live_telemetry_frame(duration, custom_sim, "Custom Stress Test")
            Prompt.ask("\n[dim]Press Enter to return to menu...[/dim]")

        elif choice == "4":
            if not base_sim or not surge_sim:
                console.print("[yellow]Running both baseline and surge scenarios to generate complete comparison dashboard...[/yellow]")
                if not base_sim:
                    base_sim = run_baseline_scenario(duration=240.0)
                if not surge_sim:
                    surge_sim = run_surge_scenario(duration=240.0)
            
            out_path = os.path.abspath("telemetry_dashboard.png")
            console.print(f"[*] Rendering dashboard to: {out_path}")
            generate_telemetry_dashboard(base_sim, surge_sim, output_path=out_path)
            console.print(f"[bold green]✔ High-resolution visual dashboard saved to: {out_path}[/bold green]")
            Prompt.ask("\n[dim]Press Enter to return to menu...[/dim]")

        elif choice == "5":
            launch_gui_window()
            Prompt.ask("\n[dim]Press Enter to return to menu...[/dim]")

        elif choice == "6":
            show_static_diagram()
            Prompt.ask("\n[dim]Press Enter to return to menu...[/dim]")

        elif choice == "7":
            show_doc_preview("docs/ADR-001-event-driven-mediator-topology.md", "ADR-001: Event-Driven Architecture Mediator Topology")
            Prompt.ask("\n[dim]Press Enter to return to menu...[/dim]")

        elif choice == "8":
            show_doc_preview("docs/SRS-order-dispatch-system.md", "Software Requirements Specification (SRS)")
            Prompt.ask("\n[dim]Press Enter to return to menu...[/dim]")

        elif choice == "0":
            console.print("[bold cyan]Exiting Food Delivery Architecture Simulator. Goodbye![/bold cyan]")
            break

def main():
    parser = argparse.ArgumentParser(description="Food Delivery Event-Driven Mediator Architecture Simulator")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive terminal UI control center (default)")
    parser.add_argument("--gui", "--web", action="store_true", help="Launch interactive GUI window (Streamlit app)")
    parser.add_argument("--baseline", action="store_true", help="Run only baseline scenario with live UI")
    parser.add_argument("--surge", action="store_true", help="Run only surge scenario with live UI")
    parser.add_argument("--batch", action="store_true", help="Run headless batch simulation and generate PNG dashboard")
    parser.add_argument("--duration", type=float, default=240.0, help="Simulation duration in virtual seconds")
    parser.add_argument("--speed", type=float, default=0.015, help="Step sleep delay for live animation")
    parser.add_argument("--output", type=str, default="telemetry_dashboard.png", help="Path for telemetry dashboard PNG")
    args = parser.parse_args()

    if args.gui or getattr(args, "web", False):
        launch_gui_window()
        return

    if args.baseline:
        console.print("[bold cyan]Running Baseline Simulation with Live UI...[/bold cyan]")
        base_sim = run_simulation_with_live_tui(run_baseline_scenario, "Baseline Normal Load", duration=args.duration, step_sleep=args.speed)
        ConsoleDashboard.render_live_telemetry_frame(args.duration, base_sim, "Baseline Normal Load")
        return

    if args.surge:
        console.print("[bold red]Running Surge Shock Simulation with Live UI...[/bold red]")
        surge_sim = run_simulation_with_live_tui(run_surge_scenario, "Surge Peak Bottleneck", duration=args.duration, step_sleep=args.speed)
        ConsoleDashboard.render_live_telemetry_frame(args.duration, surge_sim, "Surge Peak Bottleneck")
        return

    if args.batch:
        ConsoleDashboard.print_header("EVENT-DRIVEN ARCHITECTURE: MEDIATOR TOPOLOGY (BATCH MODE)")
        print(f"[*] Executing Scenario 1: Baseline Normal Dinner Load (duration={args.duration:.0f}s)...")
        base_sim = run_baseline_scenario(duration=args.duration)
        ConsoleDashboard.render_live_telemetry_frame(args.duration, base_sim, "Baseline Normal Load")

        print(f"[*] Executing Scenario 2: Dinner Surge + Rainstorm Bottleneck (duration={args.duration:.0f}s)...")
        surge_sim = run_surge_scenario(duration=args.duration)
        ConsoleDashboard.render_live_telemetry_frame(args.duration, surge_sim, "Surge Peak Bottleneck")

        ConsoleDashboard.print_comparison_table(base_sim, surge_sim)
        generate_telemetry_dashboard(base_sim, surge_sim, output_path=args.output)
        print(f"[+] Visual dashboard written to: {args.output}\n")
        return

    # Default: Full Interactive UI Control Center
    interactive_menu()

if __name__ == "__main__":
    main()
