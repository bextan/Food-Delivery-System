import heapq
import random
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional
from src.domain.models import Order, OrderState
from src.mediator.orchestrator import OrderFulfillmentMediator
from src.processors.domain_processors import (
    PaymentProcessor,
    KitchenNotifierProcessor,
    CourierMatcherProcessor,
    NotificationProcessor
)
from src.ui.models import RESTAURANTS, CUSTOMERS

@dataclass(order=True)
class SimEvent:
    time: float
    priority: int
    event_type: str = field(compare=False)
    data: Dict[str, Any] = field(compare=False)

@dataclass
class MetricSnapshot:
    time: float
    queue_depth: int
    active_mediator_slots: int
    mediator_utilization: float
    payment_busy_workers: int
    kitchen_busy_workers: int
    courier_busy_workers: int
    notification_busy_workers: int
    completed_cumulative: int
    timed_out_cumulative: int

class SimulationEngine:
    def __init__(
        self,
        duration: float = 240.0,
        mediator_capacity: int = 35,
        arrival_rate: float = 1.2,
        rain_surge_active: bool = False,
        timeout_threshold: float = 40.0,
        courier_base_delay: float = 1.6
    ):
        self.duration = duration
        self.arrival_rate = arrival_rate
        self.rain_surge_active = rain_surge_active
        self.timeout_threshold = timeout_threshold
        
        self.event_queue: List[SimEvent] = []
        self.current_time: float = 0.0
        
        self.mediator = OrderFulfillmentMediator(max_concurrency=mediator_capacity, timeout_threshold=timeout_threshold)
        self.payment_proc = PaymentProcessor(num_workers=20, mean_latency=0.18, std_latency=0.04)
        self.kitchen_proc = KitchenNotifierProcessor(num_workers=25, mean_latency=0.85, std_latency=0.20)
        self.courier_proc = CourierMatcherProcessor(num_workers=30, mean_latency=courier_base_delay, std_latency=0.45)
        self.notification_proc = NotificationProcessor(num_workers=20, mean_latency=0.05, std_latency=0.01)
        
        self.snapshots: List[MetricSnapshot] = []
        self.total_orders_generated: int = 0
        self.recent_logs: List[str] = []
        
        self.all_active_orders_map: Dict[str, Order] = {}
        
        self.schedule(0.0, 'ORDER_ARRIVAL', {})
        self.schedule(1.0, 'SAMPLE_METRICS', {}, priority=1)

    def is_running(self) -> bool:
        return bool(self.event_queue) and (self.current_time < self.duration)

    def schedule(self, delay: float, event_type: str, data: Dict[str, Any], priority: int = 10):
        heapq.heappush(self.event_queue, SimEvent(self.current_time + delay, priority, event_type, data))

    def step_until(self, target_time: float):
        while self.event_queue and self.event_queue[0].time <= target_time and self.current_time < self.duration:
            event = heapq.heappop(self.event_queue)
            self.current_time = event.time
            self._dispatch_event(event)
        self.current_time = min(target_time, self.duration)

    def _dispatch_event(self, event: SimEvent):
        if event.event_type == 'ORDER_ARRIVAL':
            self._handle_order_arrival()
        elif event.event_type == 'STEP_PAYMENT_DONE':
            self._handle_payment_done(event.data)
        elif event.event_type == 'STEP_KITCHEN_DONE':
            self._handle_kitchen_done(event.data)
        elif event.event_type == 'STEP_COURIER_DONE':
            self._handle_courier_done(event.data)
        elif event.event_type == 'STEP_NOTIFICATION_DONE':
            self._handle_notification_done(event.data)
        elif event.event_type == 'SAMPLE_METRICS':
            self._handle_sample_metrics()

    def _handle_order_arrival(self):
        self.total_orders_generated += 1
        rest = random.choice(RESTAURANTS)
        cust_name = random.choice(CUSTOMERS)
        dest_x = random.uniform(10.0, 90.0)
        dest_y = random.uniform(10.0, 90.0)
        
        order = Order(
            order_id=f'ORD-{self.total_orders_generated:04d}',
            customer_id=f'CUST-{random.randint(100, 999)}',
            customer_name=cust_name,
            restaurant_id=f'REST-{rest["name"][:4]}',
            restaurant_name=rest["name"],
            restaurant_x=rest["x"],
            restaurant_y=rest["y"],
            dest_x=dest_x,
            dest_y=dest_y,
            order_value=round(random.uniform(18.0, 85.0), 2),
            items_count=random.randint(1, 5),
            created_at=self.current_time
        )
        self.all_active_orders_map[order.order_id] = order
        self.mediator.enqueue_order(order, self.current_time)
        self._try_admit_orders()
        
        if self.arrival_rate > 0:
            inter_arrival = random.expovariate(self.arrival_rate)
            self.schedule(inter_arrival, 'ORDER_ARRIVAL', {})

    def _try_admit_orders(self):
        while self.mediator.can_admit_order():
            order = self.mediator.admit_next_order(self.current_time)
            if order is None:
                continue
            self.payment_proc.busy_workers += 1
            _, duration = self.payment_proc.process(None)
            self.schedule(duration, 'STEP_PAYMENT_DONE', {'order_id': order.order_id})

    def _handle_payment_done(self, data: Dict[str, Any]):
        self.payment_proc.busy_workers = max(0, self.payment_proc.busy_workers - 1)
        order_id = data['order_id']
        if order_id not in self.mediator.active_workflows:
            return
        order = self.mediator.active_workflows[order_id]
        order.state = OrderState.PAYMENT_AUTHORIZED
        order.payment_done_at = self.current_time
        
        self.kitchen_proc.busy_workers += 1
        surge_mult = 1.6 if (self.rain_surge_active and self.current_time > 30.0) else 1.0
        _, duration = self.kitchen_proc.process(None, surge_factor=surge_mult)
        self.schedule(duration, 'STEP_KITCHEN_DONE', {'order_id': order_id})

    def _handle_kitchen_done(self, data: Dict[str, Any]):
        self.kitchen_proc.busy_workers = max(0, self.kitchen_proc.busy_workers - 1)
        order_id = data['order_id']
        if order_id not in self.mediator.active_workflows:
            return
        order = self.mediator.active_workflows[order_id]
        order.state = OrderState.KITCHEN_CONFIRMED
        order.kitchen_done_at = self.current_time
        
        self.courier_proc.busy_workers += 1
        is_surge = self.rain_surge_active and (self.current_time > 30.0)
        _, duration = self.courier_proc.process(None, rain_surge=is_surge)
        
        order.state = OrderState.COURIER_ASSIGNED
        order.courier_start_time = self.current_time
        order.courier_duration = duration
        order.courier_id = f'C-{random.randint(10, 99)}'
        self.schedule(duration, 'STEP_COURIER_DONE', {'order_id': order_id})

    def _handle_courier_done(self, data: Dict[str, Any]):
        self.courier_proc.busy_workers = max(0, self.courier_proc.busy_workers - 1)
        order_id = data['order_id']
        if order_id not in self.mediator.active_workflows:
            return
        order = self.mediator.active_workflows[order_id]
        order.courier_done_at = self.current_time
        
        self.notification_proc.busy_workers += 1
        _, duration = self.notification_proc.process(None)
        self.schedule(duration, 'STEP_NOTIFICATION_DONE', {'order_id': order_id})

    def _handle_notification_done(self, data: Dict[str, Any]):
        self.notification_proc.busy_workers = max(0, self.notification_proc.busy_workers - 1)
        order_id = data['order_id']
        completed_order = self.mediator.complete_order(order_id, self.current_time)
        if completed_order and order_id in self.all_active_orders_map:
            del self.all_active_orders_map[order_id]
        self._try_admit_orders()

    def _handle_sample_metrics(self):
        while self.mediator.initiating_queue:
            head_order = self.mediator.initiating_queue[0]
            if self.current_time - (head_order.ingested_at or self.current_time) > self.timeout_threshold:
                abandoned = self.mediator.initiating_queue.popleft()
                abandoned.state = OrderState.TIMED_OUT
                abandoned.timed_out = True
                abandoned.queue_wait_time = self.timeout_threshold
                abandoned.total_latency = self.timeout_threshold
                self.mediator.timed_out_orders.append(abandoned)
                if abandoned.order_id in self.all_active_orders_map:
                    del self.all_active_orders_map[abandoned.order_id]
            else:
                break

        snapshot = MetricSnapshot(
            time=round(self.current_time, 1),
            queue_depth=self.mediator.current_queue_depth,
            active_mediator_slots=self.mediator.active_slots_used,
            mediator_utilization=self.mediator.utilization_percentage,
            payment_busy_workers=self.payment_proc.busy_workers,
            kitchen_busy_workers=self.kitchen_proc.busy_workers,
            courier_busy_workers=self.courier_proc.busy_workers,
            notification_busy_workers=self.notification_proc.busy_workers,
            completed_cumulative=len(self.mediator.completed_orders),
            timed_out_cumulative=len(self.mediator.timed_out_orders)
        )
        self.snapshots.append(snapshot)
        if self.current_time + 1.0 <= self.duration:
            self.schedule(1.0, 'SAMPLE_METRICS', {}, priority=1)

    def run(self, on_step=None, render_interval=2.0, step_sleep=0.0):
        last_t = -render_interval
        while self.is_running():
            self.step_until(self.current_time + 1.0)
            if on_step and (self.current_time - last_t >= render_interval):
                last_t = self.current_time
                on_step(self, self.recent_logs[-1] if self.recent_logs else '')
                if step_sleep > 0:
                    time.sleep(step_sleep)
