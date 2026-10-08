import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

class OrderState(Enum):
    PENDING_INGESTION = "PENDING_INGESTION"
    SUBMITTED = "SUBMITTED"              # Waiting in initiating queue
    PAYMENT_AUTHORIZED = "PAYMENT_AUTHORIZED"
    KITCHEN_CONFIRMED = "KITCHEN_CONFIRMED"
    COURIER_ASSIGNED = "COURIER_ASSIGNED"   # Courier matched & in transit
    FULFILLMENT_NOTIFIED = "FULFILLMENT_NOTIFIED"
    COMPLETED = "COMPLETED"
    TIMED_OUT = "TIMED_OUT"
    REJECTED = "REJECTED"

class EventType(Enum):
    ORDER_PLACED = "ORDER_PLACED"
    AUTHORIZE_PAYMENT = "AUTHORIZE_PAYMENT"
    DISPATCH_KITCHEN_TICKET = "DISPATCH_KITCHEN_TICKET"
    MATCH_COURIER = "MATCH_COURIER"
    SEND_STATUS_NOTIFICATION = "SEND_STATUS_NOTIFICATION"
    PAYMENT_AUTHORIZED = "PAYMENT_AUTHORIZED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    KITCHEN_ACCEPTED = "KITCHEN_ACCEPTED"
    KITCHEN_BUSY = "KITCHEN_BUSY"
    COURIER_ACCEPTED = "COURIER_ACCEPTED"
    COURIER_UNAVAILABLE = "COURIER_UNAVAILABLE"
    NOTIFICATION_DELIVERED = "NOTIFICATION_DELIVERED"

@dataclass
class Event:
    event_id: str
    event_type: EventType
    order_id: str
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Order:
    order_id: str
    customer_id: str
    customer_name: str
    restaurant_id: str
    restaurant_name: str
    restaurant_x: float
    restaurant_y: float
    dest_x: float
    dest_y: float
    order_value: float
    items_count: int
    created_at: float
    state: OrderState = OrderState.PENDING_INGESTION
    
    # State tracking timestamps
    ingested_at: Optional[float] = None
    mediator_acquired_at: Optional[float] = None
    payment_done_at: Optional[float] = None
    kitchen_done_at: Optional[float] = None
    courier_done_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Live Physical/Courier tracking properties
    courier_start_time: Optional[float] = None
    courier_duration: float = 2.0
    courier_id: Optional[str] = None
    
    # Latency tracking
    queue_wait_time: float = 0.0
    orchestration_time: float = 0.0
    total_latency: float = 0.0
    timed_out: bool = False

    def get_courier_position(self, current_time: float) -> tuple[float, float, float]:
        """
        Returns (current_x, current_y, progress_fraction 0.0-1.0) for this actual order.
        """
        if self.state in [OrderState.PENDING_INGESTION, OrderState.SUBMITTED]:
            return self.restaurant_x, self.restaurant_y, 0.0
        
        if self.state in [OrderState.PAYMENT_AUTHORIZED, OrderState.KITCHEN_CONFIRMED]:
            return self.restaurant_x, self.restaurant_y, 0.15
        
        if self.state == OrderState.COURIER_ASSIGNED:
            if not self.courier_start_time or self.courier_duration <= 0:
                return self.restaurant_x, self.restaurant_y, 0.5
            elapsed = current_time - self.courier_start_time
            progress = min(0.95, max(0.15, 0.15 + 0.80 * (elapsed / self.courier_duration)))
            cur_x = self.restaurant_x + (self.dest_x - self.restaurant_x) * progress
            cur_y = self.restaurant_y + (self.dest_y - self.restaurant_y) * progress
            return cur_x, cur_y, progress
        
        if self.state == OrderState.COMPLETED:
            return self.dest_x, self.dest_y, 1.0
        
        return self.restaurant_x, self.restaurant_y, 0.0
