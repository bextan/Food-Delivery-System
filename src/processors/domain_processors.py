import random
from typing import Tuple
from src.domain.models import Event, EventType

class PaymentProcessor:
    """
    Decoupled event processor responsible for payment authorization.
    Fast execution, external gateway interaction (simulated).
    """
    def __init__(self, num_workers: int = 10, mean_latency: float = 0.15, std_latency: float = 0.04):
        self.name = "PaymentProcessor"
        self.num_workers = num_workers
        self.mean_latency = mean_latency
        self.std_latency = std_latency
        self.busy_workers = 0
        self.total_processed = 0

    def compute_service_time(self) -> float:
        val = random.gauss(self.mean_latency, self.std_latency)
        return max(0.05, val)

    def process(self, event: Event) -> Tuple[EventType, float]:
        service_time = self.compute_service_time()
        self.total_processed += 1
        return EventType.PAYMENT_AUTHORIZED, service_time

class KitchenNotifierProcessor:
    """
    Decoupled event processor responsible for restaurant POS integration,
    order ticket validation, and kitchen prep time estimation.
    """
    def __init__(self, num_workers: int = 15, mean_latency: float = 0.80, std_latency: float = 0.20):
        self.name = "KitchenNotifierProcessor"
        self.num_workers = num_workers
        self.mean_latency = mean_latency
        self.std_latency = std_latency
        self.busy_workers = 0
        self.total_processed = 0

    def compute_service_time(self, surge_factor: float = 1.0) -> float:
        val = random.gauss(self.mean_latency * surge_factor, self.std_latency * surge_factor)
        return max(0.2, val)

    def process(self, event: Event, surge_factor: float = 1.0) -> Tuple[EventType, float]:
        service_time = self.compute_service_time(surge_factor)
        self.total_processed += 1
        return EventType.KITCHEN_ACCEPTED, service_time

class CourierMatcherProcessor:
    """
    Decoupled event processor responsible for geospatial courier search,
    routing optimization, and sending dispatch offers to courier mobile apps.
    High latency variance, sensitive to weather / courier availability.
    """
    def __init__(self, num_workers: int = 20, mean_latency: float = 1.50, std_latency: float = 0.40):
        self.name = "CourierMatcherProcessor"
        self.num_workers = num_workers
        self.mean_latency = mean_latency
        self.std_latency = std_latency
        self.busy_workers = 0
        self.total_processed = 0

    def compute_service_time(self, rain_surge: bool = False) -> float:
        # In bad weather / dinner rush, couriers reject initial pings, causing re-dispatch latency
        mean = self.mean_latency * (2.5 if rain_surge else 1.0)
        std = self.std_latency * (2.0 if rain_surge else 1.0)
        val = random.gauss(mean, std)
        return max(0.5, val)

    def process(self, event: Event, rain_surge: bool = False) -> Tuple[EventType, float]:
        service_time = self.compute_service_time(rain_surge)
        self.total_processed += 1
        return EventType.COURIER_ACCEPTED, service_time

class NotificationProcessor:
    """
    Decoupled event processor for sending APNS/FCM push notifications
    and live WebSocket tracking updates to the consumer client.
    Very fast, lightweight.
    """
    def __init__(self, num_workers: int = 15, mean_latency: float = 0.05, std_latency: float = 0.01):
        self.name = "NotificationProcessor"
        self.num_workers = num_workers
        self.mean_latency = mean_latency
        self.std_latency = std_latency
        self.busy_workers = 0
        self.total_processed = 0

    def compute_service_time(self) -> float:
        val = random.gauss(self.mean_latency, self.std_latency)
        return max(0.01, val)

    def process(self, event: Event) -> Tuple[EventType, float]:
        service_time = self.compute_service_time()
        self.total_processed += 1
        return EventType.NOTIFICATION_DELIVERED, service_time
