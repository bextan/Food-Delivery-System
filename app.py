import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import time
import os
import sys

# Ensure root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.simulation.engine import SimulationEngine
from src.domain.models import OrderState
from src.ui.models import RESTAURANTS

st.set_page_config(
    page_title="Food Delivery Dispatch: Real-Time Mediator Simulation",
    page_icon="🛵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .stMetric {
        background-color: #1e293b;
        border-radius: 8px;
        padding: 12px;
        border-left: 4px solid #3b82f6;
    }
    .alert-card-red {
        background-color: #450a0a;
        border-left: 5px solid #ef4444;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 16px;
        color: #fca5a5;
    }
    .alert-card-green {
        background-color: #064e3b;
        border-left: 5px solid #10b981;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 16px;
        color: #6ee7b7;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SESSION STATE MANAGEMENT -----------------
if "sim_engine" not in st.session_state:
    st.session_state.sim_engine = None
if "sim_running" not in st.session_state:
    st.session_state.sim_running = False

# ----------------- SIDEBAR CONTROLS -----------------
st.sidebar.title("🛵 Dispatch Control Center")
st.sidebar.markdown("**Event-Driven Mediator Topology Simulator**")
st.sidebar.caption("Mark Richards & Neal Ford (Fundamentals of Software Architecture)")

st.sidebar.subheader("Live Execution Controls")
col_btn1, col_btn2, col_btn3 = st.sidebar.columns(3)
start_clicked = col_btn1.button("▶ Start", use_container_width=True)
pause_clicked = col_btn2.button("⏸ Pause", use_container_width=True)
reset_clicked = col_btn3.button("⏹ Reset", use_container_width=True)

st.sidebar.divider()
st.sidebar.subheader("Architecture Parameters (Tune Live)")

arrival_rate = st.sidebar.slider(
    "Order Arrival Rate (λ orders/sec)",
    min_value=0.5, max_value=12.0, value=7.5, step=0.5,
    help="Poisson arrival frequency of customer orders"
)

mediator_capacity = st.sidebar.slider(
    "Mediator Concurrency Slots (C max)",
    min_value=10, max_value=150, value=35, step=5,
    help="Active in-flight workflows the central mediator can hold simultaneously"
)

courier_base_delay = st.sidebar.slider(
    "Courier Base Transit Latency (sec)",
    min_value=0.5, max_value=6.0, value=2.4, step=0.2,
    help="Time required for courier matching and transit to customer"
)

rain_active = st.sidebar.toggle(
    "🌧️ Rainstorm Weather Shock", value=True,
    help="Severe weather causes couriers to slow down, increasing barrier-wait duration"
)

sla_timeout = st.sidebar.slider(
    "Customer SLA Abandonment Timeout (sec)",
    min_value=15.0, max_value=60.0, value=35.0, step=5.0,
    help="Orders waiting in initiating queue longer than this are abandoned"
)

sim_speed = st.sidebar.select_slider(
    "Clock Tick Speed",
    options=["0.25x Slow", "1.0x Normal", "2.5x Fast"],
    value="1.0x Normal"
)
tick_sleep = 0.12 if "Normal" in sim_speed else (0.25 if "Slow" in sim_speed else 0.05)

# Handle Control Buttons
if reset_clicked:
    st.session_state.sim_engine = None
    st.session_state.sim_running = False

if start_clicked:
    if st.session_state.sim_engine is None or not st.session_state.sim_engine.is_running():
        st.session_state.sim_engine = SimulationEngine(
            duration=300.0,
            mediator_capacity=mediator_capacity,
            arrival_rate=arrival_rate,
            rain_surge_active=rain_active,
            timeout_threshold=sla_timeout,
            courier_base_delay=courier_base_delay
        )
    st.session_state.sim_running = True

if pause_clicked:
    st.session_state.sim_running = False

# ----------------- TABS -----------------
tab_sim, tab_arch, tab_adr, tab_srs = st.tabs([
    "Live Streaming Dispatcher & Map",
    "Mediator Topology Architecture",
    "ADR-001 (Mediator vs Broker)",
    "Requirements Spec (SRS)"
])

def render_actual_simulation_frame(sim: SimulationEngine, placeholder_kpi, placeholder_map, placeholder_table, placeholder_alert):
    # Dynamic capacity calculation
    effective_courier_delay = sim.courier_proc.mean_latency * (1.6 if sim.rain_surge_active else 1.0)
    service_capacity = sim.mediator.max_concurrency / (effective_courier_delay + 1.08)
    is_bottleneck = sim.arrival_rate > service_capacity

    with placeholder_alert.container():
        if is_bottleneck:
            st.markdown(f"""
            <div class="alert-card-red">
                <strong>⚠️ BOTTLENECK ACTIVE:</strong> Arrival rate <strong>λ = {sim.arrival_rate:.1f} ord/s</strong> exceeds Central Mediator capacity <strong>μ = {service_capacity:.1f} ord/s</strong>.<br>
                The orchestrator thread pool is saturated! Inbound queue is accumulating while downstream payment workers starve.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="alert-card-green">
                <strong>✔ BALANCED OPERATION:</strong> Central Mediator capacity <strong>μ = {service_capacity:.1f} ord/s</strong> accommodates Arrival rate <strong>λ = {sim.arrival_rate:.1f} ord/s</strong>.
            </div>
            """, unsafe_allow_html=True)

    # 1. Update KPI Row
    q_depth = sim.mediator.current_queue_depth
    active_slots = sim.mediator.active_slots_used
    max_slots = sim.mediator.max_concurrency
    completed = len(sim.mediator.completed_orders)
    timed_out = len(sim.mediator.timed_out_orders)
    total = sim.total_orders_generated

    with placeholder_kpi.container():
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Virtual Clock", f"{sim.current_time:.1f}s")
        c2.metric("Inbound Queue (Backlog)", f"{q_depth}", f"{q_depth} waiting", delta_color="inverse" if q_depth > 15 else "normal")
        c3.metric("Mediator Active Slots", f"{active_slots} / {max_slots}", f"{(active_slots/max_slots)*100:.0f}% Saturated", delta_color="inverse" if active_slots >= max_slots else "normal")
        c4.metric("Completed (SLA Met)", f"{completed}", f"{completed/(total or 1)*100:.0f}% rate")
        c5.metric("SLA Timeouts (> {sim.timeout_threshold:.0f}s)", f"{timed_out}", f"-{timed_out} abandoned", delta_color="inverse")

    # 2. Render Real Map with Actual Simulation Objects
    fig, (ax_map, ax_gauge) = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw={'width_ratios': [2, 1]})
    fig.patch.set_facecolor('#0f172a')
    ax_map.set_facecolor('#1e293b')
    ax_gauge.set_facecolor('#1e293b')

    # Grid roads
    for coord in range(10, 100, 15):
        ax_map.axhline(coord, color='#334155', linestyle='--', linewidth=0.8, alpha=0.5)
        ax_map.axvline(coord, color='#334155', linestyle='--', linewidth=0.8, alpha=0.5)

    # Plot restaurant hubs
    for r in RESTAURANTS:
        ax_map.plot(r['x'], r['y'], marker='s', markersize=14, color='#f59e0b', markeredgecolor='#fbbf24', markeredgewidth=2)
        ax_map.text(r['x'], r['y'] + 4.5, f"{r['icon']} {r['name'].split()[0]}", color='#f8fafc', fontsize=9, fontweight='bold', ha='center')

    # Iterate over ACTUAL orders currently in the simulation
    active_in_flight = list(sim.mediator.active_workflows.values())
    orders_table_data = []

    # Draw couriers currently in transit
    courier_count = 0
    for order in active_in_flight:
        cx, cy, progress = order.get_courier_position(sim.current_time)
        
        # Plot real customer drop-off pin
        ax_map.plot(order.dest_x, order.dest_y, marker='o', markersize=7, color='#38bdf8', markeredgecolor='#0284c7', markeredgewidth=1.2)
        
        if order.state == OrderState.COURIER_ASSIGNED:
            courier_count += 1
            # Trail from restaurant to current courier position
            ax_map.plot([order.restaurant_x, cx], [order.restaurant_y, cy], color='#10b981', linestyle='-', linewidth=2.0, alpha=0.8)
            # Planned remaining trail
            ax_map.plot([cx, order.dest_x], [cy, order.dest_y], color='#64748b', linestyle=':', linewidth=1.2, alpha=0.5)
            # Courier moving vehicle marker
            ax_map.plot(cx, cy, marker='^', markersize=12, color='#22c55e', markeredgecolor='#ffffff', markeredgewidth=1.5)
            ax_map.text(cx, cy + 3.0, f"{order.courier_id or 'Courier'}", color='#4ade80', fontsize=8, fontweight='bold', ha='center')

    # If initiating queue has waiting orders, show blocked warning on restaurants
    if q_depth > 0:
        waiting_orders = list(sim.mediator.initiating_queue)
        for order in waiting_orders[:6]:
            ax_map.plot(order.restaurant_x + np.random.uniform(-3, 3), order.restaurant_y + np.random.uniform(-3, 3),
                        marker='x', markersize=9, color='#ef4444', markeredgewidth=2.0)

    ax_map.set_xlim(0, 100)
    ax_map.set_ylim(0, 100)
    ax_map.set_title(f"Real City Map: {courier_count} Live Couriers Moving ({q_depth} Blocked in Queue)", color='#f8fafc', fontsize=12, fontweight='bold', pad=12)
    ax_map.axis('off')

    # 3. Component Utilization Bar Chart (The Starvation Paradox)
    med_util = sim.mediator.utilization_percentage
    comp_names = ['Mediator\n(Orchestrator)', 'Courier\nWorkers', 'Kitchen\nWorkers', 'Payment\nWorkers', 'Push\nWorkers']
    comp_utils = [
        med_util,
        (sim.courier_proc.busy_workers / sim.courier_proc.num_workers) * 100.0,
        (sim.kitchen_proc.busy_workers / sim.kitchen_proc.num_workers) * 100.0,
        (sim.payment_proc.busy_workers / sim.payment_proc.num_workers) * 100.0,
        (sim.notification_proc.busy_workers / sim.notification_proc.num_workers) * 100.0,
    ]
    colors = ['#ef4444' if u >= 90 else ('#f59e0b' if u >= 60 else '#10b981') for u in comp_utils]

    bars = ax_gauge.barh(comp_names, comp_utils, color=colors, height=0.52, edgecolor='#334155')
    ax_gauge.set_xlim(0, 100)
    ax_gauge.set_xlabel("Worker Busy %", color='#94a3b8', fontsize=10, fontweight='bold')
    ax_gauge.set_title("Component Saturation vs. Starvation", color='#f8fafc', fontsize=12, fontweight='bold', pad=12)
    ax_gauge.tick_params(colors='#94a3b8', labelsize=9)
    ax_gauge.grid(axis='x', color='#334155', linestyle='--', alpha=0.5)

    for bar, val in zip(bars, comp_utils):
        ax_gauge.text(val + 2, bar.get_y() + bar.get_height()/2, f"{val:.1f}%", va='center', color='#f8fafc', fontsize=9, fontweight='bold')

    plt.tight_layout()
    with placeholder_map.container():
        st.pyplot(fig)
    plt.close(fig)

    # 4. Pipeline Table of ACTUAL Orders
    # Combine some waiting orders and in-flight orders
    table_orders = []
    # 3 from initiating queue
    for o in list(sim.mediator.initiating_queue)[:4]:
        table_orders.append({
            "Order ID": o.order_id,
            "Customer": o.customer_name,
            "Restaurant": o.restaurant_name,
            "Pipeline Stage": "🔴 QUEUED (BLOCKED BY MEDIATOR)",
            "Wait in Queue": f"{sim.current_time - (o.ingested_at or 0):.1f}s",
            "Courier ID": "None (Starved)"
        })
    # Active orders
    for o in active_in_flight[-8:]:
        _, _, prog = o.get_courier_position(sim.current_time)
        table_orders.append({
            "Order ID": o.order_id,
            "Customer": o.customer_name,
            "Restaurant": o.restaurant_name,
            "Pipeline Stage": f"🛵 {o.state.value} ({int(prog*100)}% route)",
            "Wait in Queue": f"{o.queue_wait_time:.1f}s",
            "Courier ID": o.courier_id or "Assigned"
        })

    with placeholder_table.container():
        st.markdown("##### Live In-Flight Order Pipeline (Real Simulation Objects)")
        if table_orders:
            st.dataframe(pd.DataFrame(table_orders), use_container_width=True)
        else:
            st.info("No in-flight orders. Ingestion pipeline is waiting for customer arrivals.")


with tab_sim:
    st.header("Live Streaming Dispatch Engine: Mediator Bottleneck Simulator")
    st.caption("True continuous simulation loop: orders advance incrementally, couriers navigate actual coordinates, and sliders take effect on the fly.")

    placeholder_alert = st.empty()
    placeholder_kpi = st.empty()
    placeholder_map = st.empty()
    placeholder_table = st.empty()

    if st.session_state.sim_engine is None:
        st.info("Click **▶ Start** in the sidebar to launch the real-time simulation engine.")
    else:
        sim = st.session_state.sim_engine
        
        # If currently running, execute the incremental generator loop
        if st.session_state.sim_running and sim.is_running():
            while st.session_state.sim_running and sim.is_running():
                # 1. Dynamically synchronize user sliders with live running engine
                sim.arrival_rate = arrival_rate
                sim.mediator.max_concurrency = mediator_capacity
                sim.courier_proc.mean_latency = courier_base_delay
                sim.rain_surge_active = rain_active
                sim.timeout_threshold = sla_timeout

                # 2. Advance discrete event clock incrementally by 0.5 virtual second
                sim.step_until(sim.current_time + 0.5)

                # 3. Render real frame
                render_actual_simulation_frame(sim, placeholder_kpi, placeholder_map, placeholder_table, placeholder_alert)

                # 4. Yield UI thread briefly so browser renders smoothly and registers button clicks
                time.sleep(tick_sleep)
                
                # Check for pause condition
                if not st.session_state.sim_running:
                    break
        else:
            # Paused or finished: render static state
            render_actual_simulation_frame(sim, placeholder_kpi, placeholder_map, placeholder_table, placeholder_alert)


# ----------------- ARCHITECTURE TAB -----------------
with tab_arch:
    st.header("Event-Driven Architecture: Mediator Topology")
    st.markdown("Reference: *Mark Richards & Neal Ford, Fundamentals of Software Architecture (Chapter 14)*")
    st.code("""
                         [ Incoming Order Stream ]
                                     │
                                     ▼
                       ┌───────────────────────────┐
                       │   INITIATING EVENT QUEUE  │  <─── [PRIMARY BOTTLENECK]
                       │ (order-fulfillment-inbound│       (Queue explodes from 0 to 300+ orders)
                       └─────────────┬─────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │  ORDER FULFILLMENT        │  <─── Active Workflow Concurrency Limit
                       │  CENTRAL MEDIATOR         │       (100% thread pool & state saturation)
                       └──────┬──────┬──────┬──────┘
                              │      │      │      │
         ┌────────────────────┘      │      │      └────────────────────┐
         ▼                           ▼      ▼                           ▼
   ┌───────────┐               ┌───────────┐  ┌───────────┐       ┌───────────┐
   │  Payment  │               │  Kitchen  │  │  Courier  │       │   Push    │
   │ Processor │               │ Processor │  │  Matcher  │       │ Notifier  │
   └───────────┘               └───────────┘  └───────────┘       └───────────┘
   (Hold/Capture)              (POS Ticket)   (Geosearch)         (Live Track)
    """)

# ----------------- ADR TAB -----------------
with tab_adr:
    st.header("Architecture Decision Record (ADR-001)")
    adr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "ADR-001-event-driven-mediator-topology.md")
    if os.path.exists(adr_path):
        with open(adr_path, "r", encoding="utf-8") as f:
            st.markdown(f.read())

# ----------------- SRS TAB -----------------
with tab_srs:
    st.header("Software Requirements Specification (SRS)")
    srs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "SRS-order-dispatch-system.md")
    if os.path.exists(srs_path):
        with open(srs_path, "r", encoding="utf-8") as f:
            st.markdown(f.read())
