# Food Delivery Order Dispatch Engine: Architectural Bottleneck Simulation

> **Architectural Pattern:** Event-Driven Architecture (Mediator Topology)  
> **Reference Text:** Mark Richards & Neal Ford, *Fundamentals of Software Architecture: An Engineering Approach* (Ch. 14) / Mark Richards, *Software Architecture Patterns* (Ch. 2)  
> **System Context:** Real-World On-Demand Food Delivery Fulfillment (DoorDash / Deliveroo style)  
> **Core Focus:** Empirical Demonstration of the **Central Mediator Schedulability Bottleneck** and the **Downstream Worker Starvation Paradox**

---

## 1. System Overview

This repository implements a production-grade discrete-event simulation and architectural analysis of an **On-Demand Food Delivery Order Dispatch Engine**. 

When a customer submits an order, it enters an asynchronous, multi-step fulfillment pipeline:
1. **Payment Authorization:** Pre-authorizes customer card / fraud check.
2. **Kitchen Notification:** Transmits order ticket to restaurant POS and negotiates food prep duration.
3. **Courier Matching:** Performs geospatial proximity search, routing optimization, and sends offers to courier mobile apps.
4. **Customer Telemetry:** Dispatches APNs/FCM push notifications and live tracking coordinates.

### The Architectural Choice: Mediator Topology
Rather than using a choreographed **Broker Topology** (where services react to events without centralized coordination), this system adopts the **Mediator Topology**:
* A central **`OrderFulfillmentMediator`** orchestrates the sequence, enforces barrier conditions (e.g., *do not dispatch a courier until the kitchen confirms prep time*), and manages transactional rollbacks (compensating transactions if no courier is available).
* **Decoupled Event Processors** (`PaymentProcessor`, `KitchenNotifierProcessor`, `CourierMatcherProcessor`, `NotificationProcessor`) execute domain logic as autonomous competing consumers.

```
                         [ Incoming Order Stream ]
                                     │
                                     ▼
                       ┌───────────────────────────┐
                       │   INITIATING EVENT QUEUE  │  <─── [PRIMARY BOTTLENECK]
                       │ (order-fulfillment-inbound│       (Queue explodes under surge)
                       └─────────────┬─────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │  ORDER FULFILLMENT        │  <─── Active Workflow Concurrency Limit
                       │  CENTRAL MEDIATOR         │       (Thread pool & state table saturation)
                       └──────┬──────┬──────┬──────┘
                              │      │      │      │
         ┌────────────────────┘      │      │      └────────────────────┐
         ▼                           ▼      ▼                           ▼
   ┌───────────┐               ┌───────────┐  ┌───────────┐       ┌───────────┐
   │  Payment  │               │  Kitchen  │  │  Courier  │       │   Push    │
   │ Processor │               │ Processor │  │  Matcher  │       │ Notifier  │
   └───────────┘               └───────────┘  └───────────┘       └───────────┘
         │                           │              │                   │
         └───────────────────────────┴──────────────┴───────────────────┘
                                     │
             [STARVATION PARADOX: Fast processors sit idle at <15% utilization
              because the central mediator cannot feed work fast enough!]
```

---

## 2. The Architectural Bottleneck (The Orchestration Trap)

Mark Richards and Neal Ford explicitly highlight the fundamental trade-off of the Mediator Topology: **Scalability vs. Control**.

While individual event processors can scale horizontally by adding worker instances, **the central Mediator must coordinate the workflow and maintain active state in memory for every in-flight transaction**:

1. **Stateful Barrier Wait:** The mediator cannot release its active workflow slot until all sequential steps complete.
2. **Cascading Latency Shock:** During an unexpected rainstorm or dinner rush:
   * Couriers reject dispatch pings, causing courier matching latency to spike from $1.6\text{s}$ to $4.5\text{s}+$.
   * Because orders take longer to complete, mediator slots remain locked for $5.5\text{s}+$ instead of $2.7\text{s}$.
3. **Queue Backlog Explosion:**
   * With a fixed mediator concurrency pool ($C_{\text{max}} = 35$), effective processing capacity collapses from $\sim 13\text{ orders/sec}$ to $\sim 6.3\text{ orders/sec}$.
   * At an arrival surge of $\lambda = 8.5\text{ orders/sec}$, arrival strictly exceeds service capacity ($\lambda > \mu$).
   * The Initiating Queue explodes to over $300+$ waiting orders, driving average wait times from $0.0\text{s}$ to $20+\text{s}$, and triggering order timeouts/abandonment.
4. **The Starvation Paradox:**
   * While the Mediator is redlined at **100% capacity**, downstream processors like `PaymentProcessor` and `NotificationProcessor` sit largely under-utilized (**< 10% busy workers**). The orchestrator is choked, unable to schedule tasks to available workers.

---

## 3. User Interface & Observability (Interactive UX)

The system features three complementary observability interfaces:

### A. Interactive GUI Window with Sliders & City Map (`./run_gui.sh` or `streamlit run app.py`)
A graphical interactive desktop/browser window providing real-time controls and visual animations:
* **Interactive Sliders in Sidebar:**
  * Order Arrival Rate ($\lambda$ from 0.5 to 12.0 orders/sec)
  * Mediator Concurrency Limit ($C$ from 10 to 150 slots)
  * Courier Travel / Matching Duration
  * 🌧️ Rainstorm Weather Shock Toggle (instantly triggers courier slowdown)
  * Customer SLA Cancellation Timeout
  * Preset scenario buttons (Balanced vs. Surge vs. Scaled Mediator)
* **Live City Dispatch Map & Courier Animation:**
  * Visual 2D radar map showing restaurant hubs (Pizza, Ramen, Burrito, Bowls), customer dropoff pins, and moving courier icons ($\triangle$ / 🛵) with transit paths.
  * When bottlenecked, orders freeze at restaurants with red markers while the central queue explodes.
* **Component Utilization Gauge:**
  * Live horizontal bar chart showing Mediator Saturation vs. Worker Starvation.
* **Real-Time Order State Pipeline:**
  * Interactive data table showing order state transitions: `QUEUED` ➔ `PAYMENT` ➔ `KITCHEN` ➔ `COURIER_TRANSIT` ➔ `DELIVERED`.

### B. Interactive Terminal UI Control Center (`python main.py` or `./run_simulation.sh`)
When launched from the command line, `main.py` opens an interactive control dashboard:
* **[1] ▶ Run Baseline Load Simulation:** Executes standard dinner rush with smooth, balanced order flow.
* **[2] ⚡ Run Surge Shock Simulation:** Triggers high-volume dinner rush + sudden rainstorm shock to reproduce the mediator saturation bottleneck.
* **[3] 🔬 Run Custom Stress Test:** An interactive wizard allowing you to adjust arrival rate, mediator thread concurrency, rainstorm factors, and SLA thresholds.
* **[4] 📊 Generate Visual Telemetry Dashboard:** Re-plots and saves `telemetry_dashboard.png`.
* **[5] 🌐 Launch Interactive Web GUI Window:** Starts the Streamlit graphical app.
* **[6] 📐 View Architecture Diagram & Theory:** Explains Mark Richards' Mediator Topology pattern.
* **[7] 📖 Inspect Architecture Decision Record:** Opens ADR-001.
* **[8] 📋 Inspect Software Requirements Spec:** Opens the full IEEE-830 SRS.

### C. Live In-Flight Topology Diagram & Real-Time Gauges (While Program Runs)
While a scenario executes in the terminal, the screen dynamically renders a split-pane dashboard:
1. **Left Pane (Dynamic Architecture Topology Diagram):**
   * Renders the full Mediator pattern in ASCII/Unicode with live state updates.
   * Node states update in real-time (`EMPTY/CLEAR` ➔ `BACKLOG FORMING` ➔ `CRITICAL BACKLOG`).
   * Mediator shows active concurrency status (`NORMAL` ➔ `⚠️ 100% EXHAUSTED`).
   * Downstream workers highlight the `[STARVED]` paradox!
2. **Right Pane (Live Telemetry Gauges & SLAs):**
   * Visual progress bars for Inbound Queue, Mediator Slots, Payment Workers, Kitchen Workers, Courier Matchers, and Notification Svc.
3. **Bottom Pane (Live Orchestration Activity Log):**
   * Rolling event feed displaying order arrivals, courier delay warnings, thread exhaustions, and SLA breach timeouts.

### D. Visual Telemetry Dashboard (`telemetry_dashboard.png`)
A 4-panel publication-grade image summarizing:
* **Panel 1:** Inbound Queue Depth explosion over time.
* **Panel 2:** Latency Breakdown (Queue Wait Delay vs. Active Processing).
* **Panel 3:** Component Utilization proving the Starvation Paradox.
* **Panel 4:** Cumulative Completed vs. Abandoned Orders.

---

## 4. Repository Structure

```
.
├── docs/
│   ├── ADR-001-event-driven-mediator-topology.md    # Architecture Decision Record
│   └── SRS-order-dispatch-system.md                 # IEEE/ISO Standard Software Requirements Spec
├── src/
│   ├── domain/
│   │   ├── __init__.py
│   │   └── models.py                                # Event, Order, and State Machine definitions
│   ├── mediator/
│   │   ├── __init__.py
│   │   └── orchestrator.py                          # Central Order Fulfillment Mediator
│   ├── processors/
│   │   ├── __init__.py
│   │   └── domain_processors.py                     # Decoupled Payment, Kitchen, Courier, & Notif workers
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── engine.py                                # Discrete-event simulation queue (heapq-based)
│   │   └── scenarios.py                             # Baseline Normal vs. Surge Shock scenarios
│   ├── telemetry/
│   │   ├── __init__.py
│   │   ├── console_ui.py                            # Static metric comparison & ANSI tables
│   │   ├── live_tui.py                              # Dynamic real-time split-pane terminal UI & diagram
│   │   └── dashboard_plotter.py                     # High-res 4-panel visual dashboard generator
│   └── ui/
│       ├── __init__.py
│       └── models.py                                # Visual mapping and city coordinates
├── app.py                                           # Streamlit GUI application with sliders & map
├── main.py                                          # Interactive UI and CLI application entry point
├── run_gui.sh                                       # One-click launcher for the graphical window
├── run_simulation.sh                                # One-click execution shell script for terminal UI
├── requirements.txt                                 # Python dependencies (matplotlib, pandas, numpy, rich, streamlit)
└── telemetry_dashboard.png                          # Pre-rendered 4-panel visual telemetry UI
```

---

## 5. Quick Start Guide

### Prerequisites
* Python 3.10+
* Dependencies: `pip install -r requirements.txt`

### Launch the Interactive Graphical Window (Streamlit GUI)
```bash
./run_gui.sh
# or
streamlit run app.py
# or
python main.py --gui
```

### Launch Interactive Terminal Control Center
```bash
python main.py
# or
./run_simulation.sh
```

---

## 6. Git Version History (October 2026 Commit Milestones)

The repository includes a Git commit history reflecting architectural development across October 2026:

* `2026-10-08`: `feat(core): initial repository layout, domain models, and architecture design draft`
* `2026-10-14`: `feat(mediator): implement central event mediator with barrier state machine`
* `2026-10-19`: `feat(processors): add payment, kitchen, courier, and notification event processors`
* `2026-10-23`: `feat(sim): discrete-event simulation engine with Poisson arrival and surge generator`
* `2026-10-27`: `feat(ui): terminal console dashboard and visual telemetry generation`
* `2026-10-29`: `fix(perf): instrument mediator thread exhaustion and queue backlog metrics (reproduce bottleneck)`
* `2026-10-31 15:10:00`: `docs(arch): finalize IEEE-standard SRS and ADR-001 (Mediator topology trade-offs & fitness functions)`
* `2026-10-31 22:30:00`: `feat(ux): interactive terminal UI control center, live dynamic mediator topology diagram, and real-time gauges`
* `2026-10-31 23:45:00`: `feat(gui): interactive control center window with dynamic parameter sliders, live courier transit animations, and city dispatch map`


---

## 7. Real-Time Incremental Simulation Engine & True Courier State Tracking

The v6 engine completely replaces static batch simulations () with an **incremental event generator**:
* ****: Increments virtual time by 0.5s ticks, yielding to the Streamlit UI loop so that intermediate states render smoothly.
* **Separation of Concerns**: Sliders can be dynamically adjusted while the simulation runs without resetting in-flight orders or restarting the clock.
* **True Simulation Consuming UI**: The city radar map and pipeline table consume real  instances from memory. Couriers move along actual coordinate trails from restaurants to customers, and blocked orders display live red backlogs directly at the restaurant nodes.
