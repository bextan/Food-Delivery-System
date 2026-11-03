# Software Requirements Specification (SRS)

## System: On-Demand Food Delivery Order Dispatch Engine

**Document Version:** 1.0.0  
**Specification Standard:** ISO/IEC/IEEE 29148 / IEEE Std 830-1998 Format  
**Architectural Framework:** Mark Richards & Neal Ford, *Fundamentals of Software Architecture*  
**Date:** 2026-10-31

---

## Table of Contents

1. [Introduction](#1-introduction)
   - 1.1 Purpose
   - 1.2 Document Conventions
   - 1.3 Intended Audience
   - 1.4 Architectural References
2. [Overall Description](#2-overall-description)
   - 2.1 Product Perspective
   - 2.2 System Topology & Component Model
   - 2.3 Operating Environment & Constraints
3. [Functional Requirements](#3-functional-requirements)
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
6. [Architectural Fitness Functions](#6-architectural-fitness-functions)
7. [Bottleneck Mathematical Analysis](#7-bottleneck-mathematical-analysis)

---

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification (SRS) defines the functional, structural, and behavioral requirements for the **On-Demand Food Delivery Order Dispatch Engine**.

The document describes the adoption of an **Event-Driven Architecture using the Mediator Topology** to coordinate the different stages of food delivery order fulfillment.

It also defines the expected system behavior, performance targets, reliability requirements, and automated architectural fitness functions. Particular attention is given to identifying and preventing potential bottlenecks in the central orchestration component.

The main goal is to provide a clear technical specification that can guide the implementation, testing, and evaluation of the system.

### 1.2 Document Conventions

The following terms are used throughout this document:

- **MUST / SHALL:** Indicates a mandatory requirement that the system is expected to satisfy.
- **SHOULD:** Indicates a recommended requirement or target that should be achieved whenever possible.
- **Architectural Quanta:** Independently deployable units with high functional cohesion and relatively independent deployment boundaries, as described by Richards and Ford.

### 1.3 Intended Audience

This document is primarily intended for:

- Software Architects
- Backend Developers
- Site Reliability Engineers (SRE)
- Performance Engineering Teams
- Developers responsible for implementing and testing the dispatch engine

### 1.4 Architectural References

The architectural decisions and terminology used in this specification are based on the following references:

- Richards, Mark, and Neal Ford. *Fundamentals of Software Architecture: An Engineering Approach*. O'Reilly Media.
- Richards, Mark. *Software Architecture Patterns*. O'Reilly Media.

---

## 2. Overall Description

### 2.1 Product Perspective

The Order Dispatch Engine serves as the core fulfillment subsystem of an on-demand food delivery platform.

Its responsibility is to coordinate the complete order fulfillment process, starting from the moment a customer places an order and ending when a courier has accepted the delivery assignment and the customer receives an update.

The main processing stages include:

1. Payment authorization.
2. Restaurant kitchen acceptance.
3. Courier discovery and assignment.
4. Customer notification.

These stages depend on one another and must be executed in the correct order. For example, courier assignment should not begin until the restaurant confirms that it can prepare the order.

The system uses asynchronous messaging to coordinate these operations, allowing individual processors to perform their tasks without requiring the initiating request to remain open.

### 2.2 System Topology & Component Model

The architecture follows the **Event-Driven Architecture — Mediator Topology**.

The system consists of the following main components:

1. **Initiating Queue (`order-fulfillment-inbound`):**  
   A high-throughput FIFO message buffer that separates incoming requests from the fulfillment process. It allows the system to temporarily store orders when the mediator cannot process them immediately.

2. **Order Fulfillment Mediator:**  
   The central orchestration component. It maintains the state of active orders, controls the execution sequence, coordinates processing steps, and manages compensation actions when failures occur.

3. **Processing Channels (Point-to-Point Queues):**  
   Dedicated command and reply queues are used for communication between the mediator and individual processors.

   - `queue.payment.command` and `queue.payment.reply`
   - `queue.kitchen.command` and `queue.kitchen.reply`
   - `queue.courier.command` and `queue.courier.reply`
   - `queue.notification.command` and `queue.notification.reply`

4. **Decoupled Event Processors:**  
   Independent workers responsible for executing specific business operations. Each processor consumes commands from its respective queue and returns a reply event to the mediator.

This separation allows processors to be developed, maintained, and scaled independently.

### 2.3 Operating Environment & Constraints

The system must operate under the following technical constraints:

- The application must support execution in a containerized environment, such as Docker or Kubernetes.
- Domain processors must communicate through asynchronous messaging rather than relying on direct synchronous HTTP calls between processing stages.
- The mediator must enforce a bounded concurrency limit, represented by \(C_{\max}\), to prevent excessive resource consumption and thread exhaustion.
- Message processing must support reliable acknowledgment and recovery mechanisms.
- The system must maintain enough workflow information to recover active orders after a mediator restart.

---

## 3. Functional Requirements

### 3.1 Initiating Event Ingestion (FR-1)

- **FR-1.1:** The system SHALL accept an `OrderPlaced` event containing the following information:
  - `order_id`
  - `customer_id`
  - `restaurant_id`
  - `items`
  - `order_value`

- **FR-1.2:** The ingress message SHALL be acknowledged after the event has been successfully and persistently written to the `order-fulfillment-inbound` queue.

- **FR-1.3:** Under normal operating conditions, the ingress response time SHOULD remain below 10 ms.

### 3.2 Workflow Orchestration & Barrier Synchronization (FR-2)

- **FR-2.1:** The Mediator SHALL retrieve pending orders from the initiating queue only when the number of active orchestration workflows is below the configured maximum concurrency limit \(C_{\max}\).

- **FR-2.2:** The Mediator SHALL enforce the following execution sequence:

  1. **Step 1 — Payment Authorization:** Send a payment authorization command to the Payment Processor.

  2. **Step 2 — Kitchen Confirmation:** Only after receiving `PAYMENT_AUTHORIZED`, send the order details to the Kitchen Processor.

  3. **Step 3 — Courier Assignment:** Only after receiving `KITCHEN_ACCEPTED`, including the estimated food preparation time, initiate geospatial courier matching.

  4. **Step 4 — Order Completion:** After receiving `COURIER_ACCEPTED`, send a customer notification and mark the order as `COMPLETED`.

- **FR-2.3:** After the workflow has completed successfully, the Mediator SHALL release its occupied orchestration slot and continue processing pending orders from the initiating queue.

- **FR-2.4:** The Mediator SHALL maintain the current state of each active workflow so that processing can resume correctly after temporary failures or restarts.

### 3.3 Domain Processor Coordination (FR-3)

Each processor is responsible for a specific business operation and must return a reply event after completing its task.

The following latency values represent the expected processing targets under normal operating conditions:

- **FR-3.1 — PaymentProcessor:** SHALL authenticate and authorize payments through external payment gateways. The target mean processing latency is:

  \[
  18 \text{ ms} \pm 4 \text{ ms}
  \]

- **FR-3.2 — KitchenNotifierProcessor:** SHALL transmit order information to restaurant POS systems. The target mean processing latency is:

  \[
  85 \text{ ms} \pm 20 \text{ ms}
  \]

- **FR-3.3 — CourierMatcherProcessor:** SHALL search for nearby couriers, rank suitable candidates, and send delivery acceptance requests.

  The nominal processing latency is:

  \[
  1600 \text{ ms} \pm 450 \text{ ms}
  \]

  Under adverse weather conditions, such as heavy rain or snow, retry attempts and courier rejection may increase the processing latency to approximately 6000 ms.

- **FR-3.4 — NotificationProcessor:** SHALL publish customer mobile push notifications. The target mean processing latency is:

  \[
  5 \text{ ms} \pm 1 \text{ ms}
  \]

These values are performance targets for the simulation and should be treated as assumptions that can be adjusted during testing.

### 3.4 SLA Monitoring & Auto-Cancellation (FR-4)

- **FR-4.1:** The system SHALL enforce an initiating queue dwell timeout of:

  \[
  T_{\text{timeout}} = 40 \text{ seconds}
  \]

- **FR-4.2:** An order that remains in the initiating queue for more than 40 seconds because of mediator saturation SHALL be marked as `TIMED_OUT` or abandoned.

- **FR-4.3:** When an order reaches the timeout threshold, the system SHALL trigger an appropriate customer notification.

- **FR-4.4:** Timed-out orders must not be silently discarded. Their final state and reason for failure should be recorded for auditing and monitoring purposes.

---

## 4. External Interface Requirements

### 4.1 Message Queue Interfaces

Internal communication between the mediator and domain processors uses asynchronous messages with JSON payloads.

The message format must contain enough information to identify the event, determine its purpose, associate it with an order, and process its payload.

The following example illustrates a payment authorization command:

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

Each message should include:

- A unique event identifier.
- An event type describing the requested operation.
- An order identifier for workflow correlation.
- A timestamp.
- A payload containing the information required by the receiving processor.

Messages must be validated against the expected JSON schema before processing.

### 4.2 Ingress Gateway Protocol

The ingress gateway is responsible for receiving order placement requests from consumer applications and converting them into `OrderPlaced` events.

The gateway must validate the incoming request and publish the corresponding event to the initiating queue.

Once the message has been successfully persisted, the gateway can acknowledge the request without waiting for the complete fulfillment workflow to finish.

This prevents customers from having to wait for payment, kitchen confirmation, and courier assignment before receiving an initial response.

---

## 5. Non-Functional Requirements & Architecture Characteristics

The following requirements describe the expected quality attributes of the system. They are based on the architectural characteristics discussed by Richards and Ford in *Fundamentals of Software Architecture*, particularly Chapter 4.

### 5.1 Scalability & Elasticity

- **NFR-SC-1:** Individual event processors SHALL support horizontal scaling. The number of workers should be adjustable based on processing queue depth or consumer lag.

- **NFR-SC-2:** Each metropolitan deployment partition SHALL support a nominal workload of 10 incoming orders per minute without a continuously increasing queue backlog.

- **NFR-SC-3:** The system SHOULD allow different processors to scale independently according to their individual workloads.

### 5.2 Performance & Latency Budgets

- **NFR-PF-1:** Under nominal conditions, when mediator utilization remains below 50%, the p95 end-to-end assignment latency SHALL remain below 5 seconds.

  The total assignment time is defined as:

  \[
  T_{\text{total}} =
  T_{\text{wait}} + T_{\text{orchestration}}
  \]

- **NFR-PF-2:** The average active orchestration time across all four processing stages SHOULD remain between 2.6 and 3.0 seconds under normal operating conditions.

- **NFR-PF-3:** Queue waiting time and active orchestration time SHOULD be measured separately to make it possible to identify whether delays originate from mediator saturation or slow downstream processors.

### 5.3 Reliability, Availability & Recovery

- **NFR-RA-1:** The Mediator state store SHALL maintain persistent workflow checkpoints. After a container restart, the system SHOULD be able to recover in-flight orders within 5 seconds.

- **NFR-RA-2:** The messaging infrastructure SHALL support reliable message delivery through persistent messages and manual acknowledgments.

- **NFR-RA-3:** A message should only be acknowledged after the corresponding workflow state transition has been successfully persisted.

- **NFR-RA-4:** The system SHOULD support retry mechanisms and idempotent processing to reduce the risk of duplicate operations after message redelivery.

### 5.4 Testability & Deployability

- **NFR-TD-1:** All event processors MUST be testable independently by injecting synthetic messages into their respective command queues.

- **NFR-TD-2:** The mediator and individual processors SHOULD be deployable as separate components.

- **NFR-TD-3:** Automated tests SHOULD verify both successful workflows and failure scenarios, including payment rejection, kitchen rejection, courier timeout, and mediator overload.

---

## 6. Architectural Fitness Functions

Architectural fitness functions are automated checks used to verify whether the system continues to satisfy its architectural requirements as it evolves.

For this system, they are particularly important because the Mediator Topology introduces a central coordination component that can become a bottleneck under high traffic.

The following fitness functions should be included in automated performance tests and operational monitoring.

### Fitness Function 1: Mediator Concurrency Headroom Guard

**Metric:** Mediator thread utilization (\(U_{\text{mediator}}\)).

This metric measures how much of the mediator's available orchestration capacity is currently being used.

**Rule:** Under sustained average traffic, mediator utilization SHOULD remain below 70%.

**Formula:**

\[
U_{\text{mediator}} =
\frac{\text{Active Orchestration Slots}}{C_{\max}}
\leq 0.70
\]

**Enforcement:** Automated load tests SHALL fail if mediator utilization exceeds 85% continuously for more than 60 seconds.

This threshold provides an early warning that the mediator is approaching its processing capacity. Maintaining sufficient headroom is important because sudden increases in traffic or downstream latency can quickly consume the remaining available slots.

### Fitness Function 2: Queue Dwell-to-Service Ratio

**Metric:** Ingestion Delay Ratio (\(R_{\text{dwell}}\)).

This metric compares the amount of time an order spends waiting in the initiating queue with the time spent on active orchestration.

**Rule:** Under baseline load, queue waiting time SHOULD NOT exceed 50% of active orchestration time.

**Formula:**

\[
R_{\text{dwell}} =
\frac{T_{\text{queue wait}}}
{T_{\text{orchestration}}}
\leq 0.50
\]

**Violation Action:** If the ratio exceeds the defined threshold, the system SHALL trigger an alert:

`Mediator Orchestration Bottleneck Detected`

A high ratio indicates that orders spend too much time waiting for the mediator to accept them rather than being actively processed. This can be an early indication of insufficient mediator capacity or an unexpected increase in incoming traffic.

### Fitness Function 3: Downstream Worker Starvation Coefficient

**Metric:** Coefficient of Utilization Disparity (\(\Delta_{\text{util}}\)).

This fitness function monitors the relationship between mediator utilization and downstream processor utilization.

**Rule:** When mediator utilization reaches or exceeds 95%, fast processor utilization, particularly Payment and Notification workers, SHOULD remain above 20%.

**Detection:** An alert SHALL be triggered when both of the following conditions occur:

- Mediator utilization is at least 95%.
- Payment or Notification worker utilization falls below 20%.

This combination may indicate the **Starvation Paradox**: the mediator is too busy coordinating existing workflows to dispatch new tasks, while downstream processors still have available processing capacity.

Monitoring these metrics together helps distinguish a mediator bottleneck from a general lack of system resources.

---

## 7. Bottleneck Mathematical Analysis (Queuing Model)

The potential bottleneck in the Mediator Topology can be analyzed using an **M/M/c/K queuing model**.

This model represents a system with:

- Poisson-distributed incoming requests.
- Exponentially distributed service times.
- \(c\) parallel service channels.
- A finite system capacity of \(K\) requests.

For the purposes of this simplified analysis, each mediator thread is assumed to remain occupied for the entire active orchestration period of an order.

### 7.1 Arrival Rate (\(\lambda\))

The arrival rate represents the average number of incoming orders per second.

Under nominal conditions, the system is designed to handle approximately 10 orders per minute per metropolitan deployment partition.

During peak periods, the arrival rate may increase significantly.

### 7.2 Service Time (\(S\))

The service time is assumed to be the sum of the sequential processing stages.

Using the nominal latency values defined in Section 3.3:

\[
E[S] =
E[S_{\text{payment}}] +
E[S_{\text{kitchen}}] +
E[S_{\text{courier}}] +
E[S_{\text{notification}}]
\]

Substituting the expected values:

\[
E[S] = 0.018 + 0.085 + 1.60 + 0.005
\]

\[
E[S] = 1.708 \text{ seconds}
\]

**Important modeling assumption:** The original performance estimate uses an orchestration time of approximately 2.68 seconds. This value includes an additional 0.972 seconds of coordination or messaging overhead.

Therefore, the nominal service time used for the following capacity calculations is:

\[
E[S] = 2.68 \text{ seconds}
\]

The service rate of one mediator thread is:

\[
\mu = \frac{1}{E[S]}
\]

\[
\mu = \frac{1}{2.68}
\approx 0.373 \text{ orders/sec/thread}
\]

### 7.3 Total Mediator Throughput

Assuming the mediator supports:

\[
c = 35
\]

concurrent orchestration threads, its theoretical maximum throughput is:

\[
\mu_{\text{total}} = c \cdot \mu
\]

\[
\mu_{\text{total}} = 35 \cdot 0.373
\]

\[
\mu_{\text{total}} \approx 13.06 \text{ orders/sec}
\]

Converting this value into orders per minute:

\[
13.06 \cdot 60 \approx 783.6
\]

Therefore, the theoretical processing capacity under nominal conditions is approximately:

**783 orders per minute.**

This is a theoretical estimate rather than a guaranteed production throughput. Actual capacity depends on message broker overhead, resource contention, external service latency, and the accuracy of the assumed service time.

### 7.4 The Surge Scenario

Consider a dinner-time traffic surge accompanied by severe weather.

During this period:

- The arrival rate increases to:

\[
\lambda_{\text{surge}} = 8.5 \text{ orders/sec}
\]

- Courier matching becomes slower because of increased rejection rates and repeated acceptance attempts.

The average courier processing time increases to approximately:

\[
E[S_{\text{courier}}] = 4.5 \text{ seconds}
\]

The total orchestration time is assumed to increase to:

\[
E[S] = 5.5 \text{ seconds}
\]

The degraded service rate of one mediator thread becomes:

\[
\mu_{\text{degraded}} =
\frac{1}{5.5}
\]

\[
\mu_{\text{degraded}} \approx 0.182
\text{ orders/sec/thread}
\]

With 35 concurrent threads, the maximum theoretical throughput becomes:

\[
\mu_{\text{total degraded}} =
35 \cdot 0.182
\]

\[
\mu_{\text{total degraded}} \approx 6.36
\text{ orders/sec}
\]

### 7.5 The Collapse Condition

The system becomes unstable when the arrival rate exceeds its available processing capacity.

The condition is:

\[
\lambda_{\text{surge}} >
\mu_{\text{total degraded}}
\]

Substituting the calculated values:

\[
8.5 > 6.36
\]

The incoming traffic therefore exceeds the mediator's processing capacity.

The difference between the arrival rate and service capacity is:

\[
\Delta =
8.5 - 6.36
\]

\[
\Delta = 2.14 \text{ orders/sec}
\]

This means that approximately 2.14 additional orders arrive every second beyond the system's theoretical processing capacity.

If the queue has sufficient available capacity, its backlog will increase by approximately this amount per second while the overload continues.

In an M/M/c/K system, the queue has a finite capacity. Once that capacity is reached, additional incoming orders must be rejected, blocked, or handled through an explicit overload policy.

Without backpressure and admission control, this situation can result in increasing queue delays, SLA violations, and reduced utilization of downstream processors.

**Conclusion:** The analysis demonstrates that the mediator can become the limiting component when downstream processing times increase significantly. Increasing the number of downstream workers alone will not resolve this issue if the mediator remains unable to dispatch tasks quickly enough.

This supports the need for bounded concurrency, queue monitoring, backpressure, and geographical partitioning as part of the selected architecture.