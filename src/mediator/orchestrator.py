from typing import Dict, List, Optional
from collections import deque
from src.domain.models import Order, OrderState, Event, EventType

class OrderFulfillmentMediator:
    """
    Central Event Mediator for Order Fulfillment.
    Orchestrates the multi-step saga workflow across decoupled event processors:
      Payment -> Kitchen -> Courier -> Notification
    
    Architectural Bottleneck Characteristics:
    - Maintains in-memory session/state for all in-flight orders.
    - Bound by max_concurrency (thread pool / active orchestration context limits).
    - Blocks new incoming events when active slots are exhausted.
    - Inbound queue grows unbounded under arrival bursts or downstream processor delays.
    """
    def __init__(self, max_concurrency: int = 35, timeout_threshold: float = 60.0):
        self.max_concurrency = max_concurrency
        self.timeout_threshold = timeout_threshold
        
        # Initiating Queue (The Primary Bottleneck Queue)
        self.initiating_queue: deque[Order] = deque()
        
        # Active Orchestrations held in memory by the Mediator
        self.active_workflows: Dict[str, Order] = {}
        
        # Historical tracking
        self.completed_orders: List[Order] = []
        self.timed_out_orders: List[Order] = []
        
        # Real-time state metrics
        self.peak_queue_depth: int = 0

    @property
    def current_queue_depth(self) -> int:
        return len(self.initiating_queue)

    @property
    def active_slots_used(self) -> int:
        return len(self.active_workflows)

    @property
    def utilization_percentage(self) -> float:
        return (self.active_slots_used / self.max_concurrency) * 100.0

    def enqueue_order(self, order: Order, current_time: float):
        order.ingested_at = current_time
        order.state = OrderState.SUBMITTED
        self.initiating_queue.append(order)
        if len(self.initiating_queue) > self.peak_queue_depth:
            self.peak_queue_depth = len(self.initiating_queue)

    def can_admit_order(self) -> bool:
        return len(self.active_workflows) < self.max_concurrency and len(self.initiating_queue) > 0

    def admit_next_order(self, current_time: float) -> Optional[Order]:
        if not self.can_admit_order():
            return None
        
        order = self.initiating_queue.popleft()
        order.mediator_acquired_at = current_time
        order.queue_wait_time = current_time - (order.ingested_at or current_time)
        
        # Check SLA timeout inside queue
        if order.queue_wait_time > self.timeout_threshold:
            order.state = OrderState.TIMED_OUT
            order.timed_out = True
            order.total_latency = order.queue_wait_time
            self.timed_out_orders.append(order)
            return None
        
        self.active_workflows[order.order_id] = order
        return order

    def complete_order(self, order_id: str, current_time: float) -> Optional[Order]:
        if order_id not in self.active_workflows:
            return None
        
        order = self.active_workflows.pop(order_id)
        order.completed_at = current_time
        order.orchestration_time = current_time - (order.mediator_acquired_at or current_time)
        order.total_latency = current_time - (order.ingested_at or current_time)
        order.state = OrderState.COMPLETED
        self.completed_orders.append(order)
        return order
