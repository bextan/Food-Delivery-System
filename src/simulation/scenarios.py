from typing import Optional, Callable
from src.simulation.engine import SimulationEngine

def run_baseline_scenario(
    duration: float = 240.0,
    on_step: Optional[Callable[[SimulationEngine, str], None]] = None,
    render_interval: float = 2.0,
    step_sleep: float = 0.0
) -> SimulationEngine:
    """
    Standard operational dinner load:
    - Arrival rate: 1.2 orders/second (72 orders/minute)
    - Standard weather, normal courier response times
    - System operates comfortably below mediator concurrency limits
    """
    sim = SimulationEngine(
        duration=duration,
        mediator_capacity=35,
        arrival_rate_func=lambda t: 1.2,
        rain_surge_active=False
    )
    sim.run(on_step=on_step, render_interval=render_interval, step_sleep=step_sleep)
    return sim

def run_surge_scenario(
    duration: float = 240.0,
    on_step: Optional[Callable[[SimulationEngine, str], None]] = None,
    render_interval: float = 2.0,
    step_sleep: float = 0.0
) -> SimulationEngine:
    """
    High-volume dinner surge with unexpected rainstorm:
    - 0 to 40s: Normal load (1.5 orders/sec)
    - 40s onwards: Sudden dinner surge (8.5 orders/sec sustained)
    - 60s onwards: Rainstorm hits -> couriers reject pings, kitchen slows down
    - Causes Mediator active slot saturation, queue explosion, and order timeouts
    """
    def surge_rate(t: float) -> float:
        if t < 40.0:
            return 1.5
        else:
            return 8.5
            
    sim = SimulationEngine(
        duration=duration,
        mediator_capacity=35,
        arrival_rate_func=surge_rate,
        rain_surge_active=True
    )
    sim.run(on_step=on_step, render_interval=render_interval, step_sleep=step_sleep)
    return sim

def run_custom_scenario(
    duration: float = 200.0,
    mediator_capacity: int = 35,
    arrival_rate: float = 6.0,
    rain_surge: bool = True,
    timeout_threshold: float = 40.0,
    on_step: Optional[Callable[[SimulationEngine, str], None]] = None,
    render_interval: float = 2.0,
    step_sleep: float = 0.0
) -> SimulationEngine:
    """
    User-configured stress test scenario.
    """
    sim = SimulationEngine(
        duration=duration,
        mediator_capacity=mediator_capacity,
        arrival_rate_func=lambda t: arrival_rate,
        rain_surge_active=rain_surge,
        timeout_threshold=timeout_threshold
    )
    sim.run(on_step=on_step, render_interval=render_interval, step_sleep=step_sleep)
    return sim
