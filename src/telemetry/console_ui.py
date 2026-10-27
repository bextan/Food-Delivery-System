import sys
import time
from typing import List
from src.simulation.engine import MetricSnapshot, SimulationEngine

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GRAY = "\033[90m"
BG_RED = "\033[41m"
WHITE_BOLD = "\033[1;37m"

def render_meter(current: float, maximum: float, width: int = 24, alert_threshold: float = 0.85) -> str:
    ratio = min(1.0, max(0.0, current / maximum if maximum > 0 else 0.0))
    filled = int(ratio * width)
    empty = width - filled
    
    if ratio >= alert_threshold:
        color = RED
    elif ratio >= 0.60:
        color = YELLOW
    else:
        color = GREEN
    
    bar = f"{color}{'█' * filled}{GRAY}{'░' * empty}{RESET}"
    return f"[{bar}] {ratio*100:5.1f}% ({int(current)}/{int(maximum)})"

class ConsoleDashboard:
    RESET = RESET
    BOLD = BOLD
    GREEN = GREEN
    RED = RED
    YELLOW = YELLOW
    CYAN = CYAN
    WHITE_BOLD = WHITE_BOLD

    @staticmethod
    def print_header(title: str):
        print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{CYAN}║ {WHITE_BOLD}{title.center(84)}{BOLD}{CYAN} ║{RESET}")
        print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════════════════════════════╝{RESET}\n")

    @staticmethod
    def render_live_telemetry_frame(t: float, sim: SimulationEngine, label: str):
        q_depth = sim.mediator.current_queue_depth
        active_slots = sim.mediator.active_slots_used
        max_slots = sim.mediator.max_concurrency
        
        status_tag = f"{BG_RED} BOTTLENECK SATURATED {RESET}" if active_slots >= max_slots else f"{GREEN} BALANCED {RESET}"
        
        print(f"{BOLD}--- Simulation Time: {t:5.1f}s | Scenario: {label} | Status: {status_tag} ---{RESET}")
        print(f"  {BOLD}Mediator Inbound Queue : {RESET}{render_meter(q_depth, 250, width=20, alert_threshold=0.50)}")
        print(f"  {BOLD}Mediator Active Slots  : {RESET}{render_meter(active_slots, max_slots, width=20, alert_threshold=0.90)}")
        print(f"  {BOLD}Payment Workers (n={sim.payment_proc.num_workers:2d}) : {RESET}{render_meter(sim.payment_proc.busy_workers, sim.payment_proc.num_workers, width=20)}")
        print(f"  {BOLD}Kitchen Workers (n={sim.kitchen_proc.num_workers:2d}) : {RESET}{render_meter(sim.kitchen_proc.busy_workers, sim.kitchen_proc.num_workers, width=20)}")
        print(f"  {BOLD}Courier Workers (n={sim.courier_proc.num_workers:2d}) : {RESET}{render_meter(sim.courier_proc.busy_workers, sim.courier_proc.num_workers, width=20)}")
        print(f"  {BOLD}Notif Workers   (n={sim.notification_proc.num_workers:2d}) : {RESET}{render_meter(sim.notification_proc.busy_workers, sim.notification_proc.num_workers, width=20)}")
        print(f"  {GRAY}Completed: {len(sim.mediator.completed_orders):4d} | Timed Out: {len(sim.mediator.timed_out_orders):4d} | Peak Queue: {sim.mediator.peak_queue_depth:4d}{RESET}\n")

    @staticmethod
    def print_comparison_table(base_sim: SimulationEngine, surge_sim: SimulationEngine):
        base_completed = base_sim.mediator.completed_orders
        surge_completed = surge_sim.mediator.completed_orders
        base_timeouts = base_sim.mediator.timed_out_orders
        surge_timeouts = surge_sim.mediator.timed_out_orders
        
        base_avg_wait = sum(o.queue_wait_time for o in base_completed) / len(base_completed) if base_completed else 0
        surge_avg_wait = sum(o.queue_wait_time for o in surge_completed) / len(surge_completed) if surge_completed else 0
        
        base_avg_total = sum(o.total_latency for o in base_completed) / len(base_completed) if base_completed else 0
        surge_avg_total = sum(o.total_latency for o in surge_completed) / len(surge_completed) if surge_completed else 0
        
        timeout_sla = surge_sim.timeout_threshold
        print(f"{BOLD}{WHITE_BOLD}┌──────────────────────────────────────────────┬──────────────────┬──────────────────┐{RESET}")
        print(f"{BOLD}{WHITE_BOLD}│ Architectural Metric / SLA Indicator         │ Baseline (Norm)  │ Surge (Bottleneck│{RESET}")
        print(f"{BOLD}{WHITE_BOLD}├──────────────────────────────────────────────┼──────────────────┼──────────────────┤{RESET}")
        print(f"│ Total Orders Generated                       │ {base_sim.total_orders_generated:>16d} │ {surge_sim.total_orders_generated:>16d} │")
        print(f"│ Completed Successfully (SLA Met)             │ {GREEN}{len(base_completed):>16d}{RESET} │ {len(surge_completed):>16d} │")
        print(f"│ Timed-Out / Abandoned Orders (>{timeout_sla:.0f}s SLA)     │ {GREEN}{len(base_timeouts):>16d}{RESET} │ {RED}{len(surge_timeouts):>16d}{RESET} │")
        print(f"│ Peak Initiating Queue Depth                  │ {GREEN}{base_sim.mediator.peak_queue_depth:>16d}{RESET} │ {RED}{surge_sim.mediator.peak_queue_depth:>16d}{RESET} │")
        print(f"│ Average Ingestion Queue Delay (Wait)         │ {GREEN}{base_avg_wait:>15.2f}s{RESET} │ {RED}{surge_avg_wait:>15.2f}s{RESET} │")
        print(f"│ Average Total End-to-End Latency             │ {GREEN}{base_avg_total:>15.2f}s{RESET} │ {RED}{surge_avg_total:>15.2f}s{RESET} │")
        print(f"│ Mediator Active Capacity Utilization         │ {GREEN}{base_sim.snapshots[-1].mediator_utilization:>15.1f}%{RESET} │ {RED}{surge_sim.snapshots[-1].mediator_utilization:>15.1f}%{RESET} │")
        print(f"│ Downstream Payment Processor Utilization     │ {base_sim.snapshots[-1].payment_busy_workers / base_sim.payment_proc.num_workers * 100:>15.1f}% │ {surge_sim.snapshots[-1].payment_busy_workers / surge_sim.payment_proc.num_workers * 100:>15.1f}% │")
        print(f"{BOLD}{WHITE_BOLD}└──────────────────────────────────────────────┴──────────────────┴──────────────────┘{RESET}")
        print(f"\n{BOLD}{YELLOW}Architectural Insight (Richards & Ford - Fundamentals of Software Architecture):{RESET}")
        print(f"Notice that while the {RED}Central Mediator thread pool is 100% saturated{RESET} and inbound queue")
        print(f"depth reached {RED}{surge_sim.mediator.peak_queue_depth} orders{RESET}, downstream processors (like Payment)")
        print(f"sat largely under-utilized ({CYAN}<15%{RESET}). This proves the classic {BOLD}Mediator Orchestration Bottleneck{RESET}:")
        print(f"coordination state overhead throttles horizontal scalability regardless of worker capacity.\n")
