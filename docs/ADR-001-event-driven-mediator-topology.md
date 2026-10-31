# Architecture Decision Record (ADR)

## ADR-001: Adoption of Event-Driven Mediator Topology for Multi-Step Food Delivery Order Fulfillment

* **Status:** Accepted (with documented operational trade-offs and fitness functions)
* **Date:** 2026-10-31
* **Architectural Style:** Event-Driven Architecture (EDA)
* **Pattern Category:** Distributed Orchestration (Mark Richards & Neal Ford, *Fundamentals of Software Architecture*, Chapter 14 / *Software Architecture Patterns*, Chapter 2)
* **System Scope:** Core Dispatch & Fulfillment Engine

---

### 1. Context and Problem Statement

The on-demand food delivery platform coordinates order lifecycles across diverse domain microservices:
1. **Payment Gateway Integration** (pre-authorization holds and fraud scoring)
2. **Restaurant Kitchen POS Integration** (ticket ingestion, kitchen acceptance, prep duration estimation)
3. **Geospatial Courier Matching** (haversine spatial clustering, route optimization, acceptance ping timeouts)
4. **Consumer Telemetry & Notification** (APNs/FCM push updates, live tracking WebSockets)

The previous direct synchronous RPC (REST/gRPC) choreography suffered from cascading connection timeouts, partial failure states, and tight point-to-point temporal coupling. When a restaurant's POS was slow, the client's HTTP connection hung, tying up ingress gateway threads. 

We require an architectural pattern that decouples processing stages, supports asynchronous processing, provides centralized workflow governance, and guarantees deterministic compensation (e.g., releasing a payment hold if no courier is found).

---

### 2. Decision Drivers

* **Workflow Determinism & Visibility:** The business requires complete visibility into active order states (`SUBMITTED`, `PAYMENT_HELD`, `KITCHEN_ACK`, `COURIER_DISPATCHED`, `COMPLETED`).
* **Transactional Compensation (Saga Pattern):** If a downstream step fails (e.g., kitchen rejects order or courier search times out after 10 minutes), preceding steps must be compensated in reverse order (void payment, notify customer).
* **Decoupled Evolution of Event Processors:** Teams owning Payment, Kitchen POS, and Courier Dispatch must deploy independently without knowing each other's schemas or internal APIs.
* **Auditability and Observability:** Operational support requires a single audit trail for every order transition.

---

### 3. Considered Options

#### Option A: Event-Driven Architecture — Broker Topology (Choreography)
* **Mechanism:** No central coordinator. Components publish domain events (`OrderPlaced`, `PaymentAuthorized`, `KitchenConfirmed`, `CourierAssigned`) to a central message bus (Kafka/RabbitMQ). Processors react to events and emit subsequent events.
* **Pros:** Maximum decoupling, high horizontal scalability, no central orchestrator bottleneck.
* **Cons:** High complexity in tracking end-to-end workflow state; distributed error handling and compensation logic scattered across multiple microservices; difficult to monitor SLA progress and detect stalled orders.

#### Option B: Event-Driven Architecture — Mediator Topology (Centralized Orchestration) — **[SELECTED]**
* **Mechanism:** An `OrderPlaced` initiating event enters an Initiating Queue. A dedicated **Order Fulfillment Mediator** consumes the event, maintains the workflow state machine, and issues specific command events to dedicated processing queues (`payment-queue`, `kitchen-queue`, `courier-queue`, `notification-queue`). Event processors execute domain tasks and return reply events to the mediator.
* **Pros:** Centralized workflow governance, explicit compensation logic, straightforward state auditing, simple error recovery.
* **Cons:** The mediator becomes a concurrency bottleneck and potential single point of failure; requires careful capacity management.

#### Option C: Orchestrated REST/gRPC Microservices (Synchronous HTTP Saga)
* **Mechanism:** A centralized orchestrator issues synchronous HTTP POST/PUT calls to each microservice with retry policies.
* **Cons:** Temporal coupling, thread pool exhaustion across microservices, lack of queuing buffers during traffic surges.

---

### 4. Decision Outcome

**Chosen Design:** **Option B: Event-Driven Architecture — Mediator Topology.**

We adopt the Mediator Topology because food delivery fulfillment represents an intrinsically stateful, multi-step business process with high compensation requirements. Centralizing workflow orchestration inside the `OrderFulfillmentMediator` allows strict enforcement of step dependencies (e.g., courier cannot be summoned until kitchen confirms estimated prep time) and deterministic SLA monitoring.

---

### 5. Architectural Trade-Off Analysis (The Mediator Bottleneck)

As documented by Mark Richards and Neal Ford in *Fundamentals of Software Architecture*, the primary trade-off of the Mediator Topology is **Scalability and Concurrency Bottlenecking**:

```
 [ Incoming Order Stream ]
            │
            ▼
 ┌──────────────────────┐
 │   INITIATING QUEUE   │  <─── [CRITICAL BOTTLENECK: Exponential Queue Backlog]
 └──────────┬───────────┘
            │
 ┌──────────▼───────────┐
 │   EVENT MEDIATOR     │  <─── Active Workflow Concurrency Limit (Thread Saturation)
 │  (Orchestrator VM)   │       Stateful Barrier Coordination
 └────┬────┬────┬────┬──┘
      │    │    │    │
 ┌────┘    │    │    └────┐
 ▼         ▼    ▼         ▼
┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
│ Pay │ │ Kit │ │ Cou │ │ Not │ <── [STARVATION PARADOX: Processors sit idle
└─────┘ └─────┘ └─────┘ └─────┘      waiting for mediator to dispatch tasks]
```

#### Detailed Trade-Off Matrix

| Architectural Characteristic | Rating (Richards & Ford) | System Impact |
| :--- | :--- | :--- |
| **Agility / Maintainability** | **High (4/5)** | Excellent. Modifying order fulfillment steps only requires editing mediator workflow definitions. |
| **Testability** | **High (4/5)** | Mocking individual processor reply events enables thorough isolated unit and integration testing. |
| **Deployability** | **High (4/5)** | Processors and mediator deploy as separate architectural quanta. |
| **Performance** | **Medium (3/5)** | Degrades under surge due to message hops (initiating queue -> mediator -> processing queue -> processor -> reply queue -> mediator). |
| **Scalability** | **Medium-Low (2/5)** | **Primary Vulnerability:** The central mediator holds workflow context in memory. Under surge, active slots saturate, causing queue backlog explosion. |
| **Fault Tolerance** | **Medium (3/5)** | Requires persistent state storage and mediator clustering to avoid single point of failure. |

#### The Starvation Paradox Explained
When a single downstream step experiences latency degradation (e.g., couriers taking 4x longer to accept dispatch offers during an unexpected rainstorm), the Mediator must hold that order's session in memory. This ties up mediator thread pool capacity. Consequently:
1. The **Initiating Queue backs up exponentially**, delaying new orders from being picked up.
2. Fast, highly scalable processors (such as `PaymentProcessor` and `NotificationProcessor`) experience **worker starvation**, sitting idle despite having ample compute capacity.

---

### 6. Mitigations and Architectural Fitness Functions

To operate this architecture safely in production, the following engineering mitigations are mandated:

1. **Geographical Sharding of Mediators:**
   * Mediators are partitioned by geographical delivery zones (e.g., geohash / metropolitan area) so a rainstorm surge in one city does not bottleneck fulfillment in another.
2. **Dynamic Backpressure & Circuit Breaking:**
   * If the Initiating Queue depth exceeds 500 orders or p95 queue wait exceeds 30 seconds, ingress gateways reject non-priority requests with HTTP 429 / retry headers.
3. **Automated Architectural Fitness Functions (CI/CD Quality Gates):**
   * **Fitness Function 1 (Queue Dwell Ratio):** Automated performance suites fail if the ratio of Ingestion Queue Delay to Active Processing Latency exceeds $0.5$ under baseline load:
     $$\text{Dwell Ratio} = \frac{T_{\text{queue\_wait}}}{T_{\text{active\_orchestration}}} \le 0.5$$
   * **Fitness Function 2 (Worker Starvation Index):** Automated tests alert if fast processor utilization drops below $15\%$ while mediator utilization is $>90\%$.

---

### 7. References

* Richards, Mark. *Software Architecture Patterns*, O'Reilly Media, Chapter 2: "Event-Driven Architecture".
* Richards, Mark, and Neal Ford. *Fundamentals of Software Architecture: An Engineering Approach*, O'Reilly Media, Chapter 14: "Event-Driven Architecture Style".
* Nygard, Michael T. *Release It!: Design and Deploy Production-Ready Software*, Pragmatic Bookshelf (Circuit Breakers and Bulkheads).
