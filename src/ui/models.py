import time
import math
import random
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class VisualOrder:
    order_id: str
    customer_name: str
    restaurant_name: str
    items_count: int
    order_value: float
    state: str # QUEUED, PAYMENT, KITCHEN, COURIER_TRANSIT, DELIVERED, TIMED_OUT
    created_at: float
    progress: float # 0.0 to 1.0
    courier_x: float
    courier_y: float
    dest_x: float
    dest_y: float
    restaurant_x: float
    restaurant_y: float
    wait_time: float = 0.0
    total_time: float = 0.0

RESTAURANTS = [
    {"name": "Luigi's Neapolitan Pizza", "x": 25.0, "y": 30.0, "icon": "🍕"},
    {"name": "Tokyo Express Ramen", "x": 75.0, "y": 25.0, "icon": "🍜"},
    {"name": "El Fuego Burrito Bar", "x": 30.0, "y": 75.0, "icon": "🌯"},
    {"name": "Green Garden Bowls", "x": 70.0, "y": 80.0, "icon": "🥗"},
]

CUSTOMERS = [
    "Alex Mercer", "Sarah Chen", "Elena Rostova", "Marcus Vance",
    "David Kim", "Maya Lin", "James O'Connor", "Fatima Al-Mansoor"
]
