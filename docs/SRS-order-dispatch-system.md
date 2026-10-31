# Software Requirements Specification (SRS)

## System: On-Demand Food Delivery Order Dispatch Engine
**Document Version:** 1.0.0  
**Specification Standard:** ISO/IEC/IEEE 29148 / IEEE Std 830-1998 Format  
**Architectural Framework:** Mark Richards & Neal Ford (*Fundamentals of Software Architecture*)  
**Date:** 2026-10-31  

---

### Table of Contents
1. [Introduction](#1-introduction)
   - 1.1 Purpose
   - 1.2 Document Conventions
   - 1.3 Intended Audience
   - 1.4 Architectural References
2. [Overall Description](#2-overall-description)
   - 2.1 Product Perspective
   - 2.2 System Topology & Component Model
   - 2.3 User Classes and Characteristics
   - 2.4 Operating Environment & Constraints
3. [Functional Requirements (System Features)](#3-functional-requirements-system-features)
   - 3.1 Initiating Event Ingestion (FR-1)
   - 3.2 Workflow Orchestration & Barrier Synchronization (FR-2)
   - 3.3 Domain Processor Coordination (FR-3)
   - 3.4 SLA Monitoring & Auto-Cancellation (FR-4)
4. [External Interface Requirements](#4-external-interface-requirements)
   - 4.1 Message Queue Interfaces
   - 4.2 Ingress Gateway Protocol
5. [Non-Functional Requirements & Architecture Characteristics](#5-non-functional-requirements--architecture-characteristics)
   - 5.1 Scalability & Elasticity
   - 5.2 Performance & Latency Budgets
   - 5.3 Reliability, Availability & Recovery
   - 5.4 Testability & Deployability
6. [Architectural Fitness Functions (Governance)](#6-architectural-fitness-functions-governance)
7. [Bottleneck Mathematical Analysis (Queuing Model)](#7-bottleneck-mathematical-analysis-queuing-model)

---

### 1. Introduction

#### 1.1 Purpose
This Software Requirements Specification (SRS) defines the functional, structural, and behavioral requirements for the **On-Demand Food Delivery Order Dispatch Engine**. It details the adoption of the **Event-Driven Mediator Topology** for multi-step order coordination, establishes quantitative non-functional criteria (architecture characteristics), and specifies formal automated fitness functions to detect and mitigate orchestrator bottlenecks.

#### 1.2 Document Conventions
- **MUST / SHALL:** Mandatory architectural constraint or functional requirement.
- **SHOULD:** Recommended practice or target threshold.
- **Architectural Quanta:** Independent deployment units with high functional cohesion and synchronous boundaries, as defined by Richards & Ford.

#### 1.3 Intended Audience
- Software Architects, Principal Backend Engineers, Site Reliability Engineers (SRE), and Performance Engineering Teams.

#### 1.4 Architectural References
- Richards, Mark, and Neal Ford. *Fundamentals of Software Architecture: An Engineering Approach*. O'Reilly Media.
- Richards, Mark. *Software Architecture Patterns*. O'Reilly Media.

---

### 2. Overall Description

#### 2.1 Product Perspective
The Order Dispatch Engine serves as the core real-time fulfillment subsystem within a hyper-local food delivery platform. It receives raw order placements from consumer mobile clients and drives them through the end-to-end lifecycle: payment authorization, merchant kitchen acceptance, spatial courier assignment, and push notification delivery.

#### 2.2 System Topology & Component Model
The architecture is structured strictly according to the **Event-Driven Architecture — Mediator Topology**:

1. **Initiating Queue (`order-fulfillment-inbound`):** High-throughput FIFO message buffer decoupling ingress API gateways from the fulfillment core.
2. **Order Fulfillment Mediator:** Central stateful orchestrator. Maintains state machines for active orders, coordinates step dependencies, and manages compensation sagas.
3. **Processing Channels (Point-to-Point Queues):**
   - `queue.payment.command` & `queue.payment.reply`
   - `queue.kitchen.command` & `queue.kitchen.reply`
   - `queue.courier.command` & `queue.courier.reply`
   - `queue.notification.command` & `queue.notification.reply`
4. **Decoupled Event Processors:** Autonomous, single-purpose worker microservices executing domain logic as competing consumers.

#### 2.3 Operating Environment & Constraints
- Execution must run in a containerized environment (Docker/Kubernetes).
- Zero in-process synchronous HTTP chaining between domain processors.
- Mediator must enforce a bounded concurrency ceiling ($C_{\text{max}}$) to prevent out-of-memory thread exhaustion.

---

### 3. Functional Requirements (System Features)

#### 3.1 Initiating Event Ingestion (FR-1)
- **FR-1.1:** The system SHALL ingest an `OrderPlaced` event payload containing `order_id`, `customer_id`, `restaurant_id`, `items`, and `order_value`.
- **FR-1.2:** Ingress message acknowledgment SHALL occur immediately upon persistent write to the `order-fulfillment-inbound` queue (sub-10ms ingress response).

#### 3.2 Workflow Orchestration & Barrier Synchronization (FR-2)
- **FR-2.1:** The Mediator SHALL pull pending orders from the initiating queue when active orchestration slots are below $C_{\text{max}}$.
- **FR-2.2:** The Mediator SHALL enforce the following sequential execution barriers:
  1. *Step 1:* Dispatch payment authorization command.
  2. *Step 2 (Barrier):* Only upon receiving `PAYMENT_AUTHORIZED`, dispatch kitchen ticket notification.
  3. *Step 3 (Barrier):* Only upon receiving `KITCHEN_ACCEPTED` (which provides estimated food prep time), dispatch geospatial courier matching.
  4. *Step 4:* Upon receiving `COURIER_ACCEPTED`, dispatch consumer push notification and mark order `COMPLETED`.
- **FR-2.3:** Upon completion of Step 4, the Mediator SHALL release the workflow thread slot and immediately poll the initiating queue for the next awaiting order.

#### 3.3 Domain Processor Coordination (FR-3)
- **FR-3.1:** `PaymentProcessor` SHALL authenticate and authorize funds via external payment gateways within a target mean latency of $180\text{ms} \pm 40\text{ms}$.
- **FR-3.2:** `KitchenNotifierProcessor` SHALL transmit kitchen orders to restaurant POS systems within a target mean latency of $850\text{ms} \pm 200\text{ms}$.
- **FR-3.3:** `CourierMatcherProcessor` SHALL search, rank, and ping nearby delivery couriers within a nominal latency of $1,600\text{ms} \pm 450\text{ms}$. Under adverse weather (rainstorm/snow), retry loops may extend latency up to $6,000\text{ms}$.
- **FR-3.4:** `NotificationProcessor` SHALL publish customer mobile push alerts within a mean latency of $50\text{ms} \pm 10\text{ms}$.

#### 3.4 SLA Monitoring & Auto-Cancellation (FR-4)
- **FR-4.1:** The system SHALL enforce an Initiating Queue Dwell Timeout threshold of $T_{\text{timeout}} = 40.0\text{ seconds}$.
- **FR-4.2:** Any order dwelling in the initiating queue for $>40.0\text{s}$ due to mediator saturation SHALL be automatically flagged as `TIMED_OUT` / abandoned, bypassing mediator admission, and triggering a customer notification.

---

### 4. External Interface Requirements

#### 4.1 Message Queue Interfaces
All internal communication uses standard AMQP / Kafka message envelopes with JSON schema validation:
```json
{
  "event_id": "evt-9a8b7c6d-5e4f",
  "event_type": "AUTHORIZE_PAYMENT",
  "order_id": "ORD-00142",
  "timestamp": 1793574900.12,
  "payload": {
    "amount": 42.50,
    "currency": "USD"
  }
}
```

---

### 5. Non-Functional Requirements & Architecture Characteristics

Following the architectural taxonomy established by Richards & Ford (*Fundamentals of Software Architecture*, Chapter 4):

#### 5.1 Scalability & Elasticity
- **NFR-SC-1:** Individual event processors SHALL scale horizontally as independent consumer groups based on processing queue lag.
- **NFR-SC-2:** The overall fulfillment engine SHALL sustain nominal loads of $100\text{ orders/minute}$ per metropolitan deployment partition with zero queue backlog.

#### 5.2 Performance & Latency Budgets
- **NFR-PF-1:** Under nominal conditions ($<50\%$ mediator capacity), the p95 end-to-end assignment latency ($T_{\text{total}} = T_{\text{wait}} + T_{\text{orchestration}}$) SHALL remain under $5.0\text{ seconds}$.
- **NFR-PF-2:** Active orchestration time across all 4 stages under normal operating conditions SHALL average $2.6\text{ to }3.0\text{ seconds}$.

#### 5.3 Reliability, Availability & Recovery
- **NFR-RA-1:** The Mediator state store SHALL maintain persistent state checkpoints to enable deterministic in-flight order recovery within 5 seconds of container restart.
- **NFR-RA-2:** Zero message loss: Processing queues must use persistent acknowledgments (manual ACK after state transition persist).

#### 5.4 Testability & Deployability
- **NFR-TD-1:** All event processors MUST be testable in complete isolation through synthetic message injection into their respective command queues.

---

### 6. Architectural Fitness Functions (Governance)

In accordance with evolutionary architecture principles, the following automated fitness functions are integrated into continuous testing and operational telemetry:

#### Fitness Function 1: Mediator Concurrency Headroom Guard
- **Metric:** Mediator Thread Utilization ($U_{\text{mediator}}$).
- **Rule:** Under sustained average traffic, $U_{\text{mediator}}$ MUST NOT exceed $70\%$.
- **Formula:**
  $$U_{\text{mediator}} = \frac{\text{Active Orchestration Slots}}{C_{\text{max}}} \le 0.70$$
- **Enforcement:** Automated load tests fail if $U_{\text{mediator}} > 0.85$ for $>60\text{ seconds}$.

#### Fitness Function 2: Queue Dwell-to-Service Ratio
- **Metric:** Ingestion Delay Ratio ($R_{\text{dwell}}$).
- **Rule:** The time an order spends waiting for mediator admission must not exceed $50\%$ of its active processing duration.
- **Formula:**
  $$R_{\text{dwell}} = \frac{T_{\text{queue\_wait}}}{T_{\text{orchestration}}} \le 0.50$$
- **Violation Action:** Triggers automated alert: *Mediator Orchestration Bottleneck Detected*.

#### Fitness Function 3: Downstream Worker Starvation Coefficient
- **Metric:** Coefficient of Utilization Disparity ($\Delta_{\text{util}}$).
- **Rule:** If $U_{\text{mediator}} \ge 95\%$, fast worker utilization ($U_{\text{payment}}$, $U_{\text{notification}}$) MUST NOT drop below $20\%$.
- **Detection:** Flags the **Starvation Paradox** where the central orchestrator chokes worker productivity.

---

### 7. Bottleneck Mathematical Analysis (Queuing Model)

The architectural bottleneck in the Mediator Topology can be formally modeled as an **$M/M/c/K$ Queuing System**:

1. **Arrival Stream ($\lambda$):** Order arrivals follow a Poisson distribution with arrival rate $\lambda$.
2. **Service Capacity ($\mu$):** The service time $S$ is the sum of sequential barrier delays:
   $$E[S] = E[S_{\text{payment}}] + E[S_{\text{kitchen}}] + E[S_{\text{courier}}] + E[S_{\text{notification}}]$$
   Nominally: $E[S] = 0.18 + 0.85 + 1.60 + 0.05 \approx 2.68\text{ seconds}$.
   Hence, individual thread service rate $\mu = 1 / 2.68 \approx 0.373\text{ orders/sec/thread}$.
3. **Total Mediator Throughput ($\mu_{\text{total}}$):**
   With $c = 35$ concurrent mediator threads:
   $$\mu_{\text{total}} = c \cdot \mu = 35 \cdot 0.373 \approx 13.06\text{ orders/sec} \approx 783\text{ orders/minute}$$
4. **The Surge Shock:**
   During a dinner surge accompanied by severe weather:
   - Arrival rate increases to $\lambda_{\text{surge}} = 8.5\text{ orders/sec}$.
   - Courier matching latency degrades due to ping rejections: $E[S_{\text{courier}}] \uparrow 4.5\text{s}$, driving $E[S] \uparrow 5.5\text{s}$.
   - New degraded service rate: $\mu_{\text{degraded}} = 1 / 5.5 \approx 0.182\text{ orders/sec/thread}$.
   - Maximum mediator capacity collapses to:
     $$\mu_{\text{total\_degraded}} = 35 \cdot 0.182 \approx 6.36\text{ orders/sec}$$
5. **The Collapse Condition ($\lambda > \mu_{\text{total}}$):**
   $$\lambda_{\text{surge}} (8.5) > \mu_{\text{total\_degraded}} (6.36)$$
   Because the arrival rate strictly exceeds the orchestrator's processing boundary, the **Initiating Queue grows unbounded at a rate of $\lambda - \mu \approx +2.14\text{ orders/second}$**, causing exponential delay, worker starvation across downstream processors, and catastrophic SLA timeouts.
