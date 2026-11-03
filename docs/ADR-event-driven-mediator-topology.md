# ADR-001: Adoption of Event-Driven Mediator Topology for Multi-Step Food Delivery Order Fulfillment

**Status:** Accepted  
**Date:** 2026-10-31  
**Architectural Style:** Event-Driven Architecture (EDA)  
**Pattern Category:** Distributed Orchestration (Mark Richards & Neal Ford, *Fundamentals of Software Architecture*, Chapter 14 / *Software Architecture Patterns*, Chapter 2)  
**System Scope:** Core Dispatch & Fulfillment Engine

---

## 1. Context and Problem Statement

The food delivery platform needs to coordinate several services throughout the order fulfillment process. Each order passes through multiple stages, and the successful completion of one stage often depends on the result of the previous one.

The main services involved in this process are:

1. **Payment Gateway Integration** – handles payment authorization, pre-authorization holds, and fraud checks.
2. **Restaurant Kitchen POS Integration** – receives order details, waits for restaurant confirmation, and estimates preparation time.
3. **Geospatial Courier Matching** – finds suitable couriers based on their location, availability, and estimated delivery routes.
4. **Consumer Telemetry & Notification** – sends order updates through push notifications and provides live tracking through WebSockets.

In the previous synchronous REST/gRPC approach, services communicated directly with each other and waited for responses before continuing. This created several problems. For example, if a restaurant's POS system responded slowly, the entire request could remain open for an extended period. During periods of high traffic, this could consume available connections and eventually affect other services as well.

We therefore need an architecture that allows processing stages to operate asynchronously, reduces direct dependencies between services, and provides a clear way to manage the complete order lifecycle.

Another important requirement is handling failures. If an order cannot be fulfilled after payment has been authorized, the system must be able to perform compensating actions, such as releasing the payment hold and notifying the customer.

## 2. Decision Drivers

The following requirements had the greatest influence on the architectural decision:

- **Workflow Determinism & Visibility:** The system must maintain a clear view of every order's current state, including `SUBMITTED`, `PAYMENT_HELD`, `KITCHEN_ACK`, `COURIER_DISPATCHED`, and `COMPLETED`.

- **Transactional Compensation (Saga Pattern):** When a processing step fails, the system must be able to execute compensating actions. For example, if the restaurant rejects an order or no courier can be found within the allowed time, the payment authorization should be released.

- **Independent Service Evolution:** Teams responsible for Payment, Kitchen POS, and Courier Dispatch should be able to develop and deploy their components independently, without depending on each other's internal implementation.

- **Auditability and Observability:** Every important order transition should be recorded. This makes it easier to investigate failed orders, identify bottlenecks, and understand where delays occur.

- **Scalability Under Variable Load:** The architecture should handle changes in order volume without requiring every downstream service to process requests at the same speed.

## 3. Considered Options

### Option A: Event-Driven Architecture — Broker Topology (Choreography)

**Mechanism:**

In this approach, there is no central workflow coordinator. Each service listens for events and publishes new events when its work is completed.

For example, after receiving an `OrderPlaced` event, the Payment service processes the payment and publishes `PaymentAuthorized`. The Kitchen service reacts to that event and publishes `KitchenConfirmed` once the restaurant accepts the order. Courier Dispatch then reacts to the kitchen confirmation.

**Advantages:**
- Services are loosely coupled and can evolve independently.
- There is no central orchestrator that can become a processing bottleneck.
- Individual event processors can scale independently.
- New consumers can be added without significantly changing existing services.

**Disadvantages:**
- Understanding the complete order lifecycle becomes more difficult because workflow logic is distributed across multiple services.
- Error handling and compensation logic are spread across different components.
- Investigating stalled orders requires tracing events across several services.
- Maintaining a consistent view of the overall workflow can become challenging.

This option provides good scalability and loose coupling, but it introduces additional complexity when managing a business process with multiple dependent steps.

### Option B: Event-Driven Architecture — Mediator Topology (Centralized Orchestration)

**Mechanism:**

An incoming `OrderPlaced` event is placed into an Initiating Queue. The Order Fulfillment Mediator consumes the event, creates a workflow instance, and manages the order's progress through a state machine.

The mediator sends commands to dedicated processing queues, such as:

- `payment-queue`
- `kitchen-queue`
- `courier-queue`
- `notification-queue`

Each processor performs its assigned task and sends a reply event back to the mediator. Based on the response, the mediator decides which step should happen next.

For example, courier dispatch is not initiated until the kitchen confirms the order and provides an estimated preparation time.

**Advantages:**
- Workflow logic is maintained in one central component.
- Order state transitions are easier to understand and audit.
- Compensation actions can be coordinated from a single location.
- Failures and timeouts can be handled consistently.
- Dependencies between processing steps are explicitly defined.

**Disadvantages:**
- The mediator can become a bottleneck when the number of active workflows increases.
- Its capacity must be managed carefully to prevent queue accumulation.
- The mediator requires persistent state management and appropriate recovery mechanisms.
- If the mediator becomes unavailable, new workflows may be delayed until it recovers.

Despite these limitations, this approach provides a clearer way to manage the order fulfillment process.

**Selected Option: Option B — Mediator Topology.**

### Option C: Orchestrated REST/gRPC Microservices (Synchronous HTTP Saga)

**Mechanism:**

A central orchestrator communicates directly with individual microservices using synchronous HTTP requests. Each service returns a response before the orchestrator proceeds to the next step.

Retry policies and timeouts are used to handle temporary failures.

**Advantages:**
- Relatively simple to implement and understand.
- Existing REST/gRPC infrastructure can be reused.
- Request and response flows are straightforward to trace.

**Disadvantages:**
- Services remain temporally coupled because each step waits for another service to respond.
- Slow downstream services can increase response times across the entire workflow.
- Traffic spikes can exhaust connection pools and thread resources.
- There is no natural buffering mechanism for requests during temporary processing slowdowns.

This option may work for smaller workflows, but it is less suitable for a multi-step process where individual services can have significantly different response times.

## 4. Decision Outcome

**Chosen Design: Option B — Event-Driven Architecture with Mediator Topology.**

The Mediator Topology was selected because food delivery order fulfillment is a stateful business process with several dependent stages and a need for reliable failure handling.

The `OrderFulfillmentMediator` acts as the central coordinator. It maintains workflow state, decides which processing step should happen next, and handles unsuccessful operations through compensating actions.

For example, the courier search process should only begin after the restaurant confirms the order. If no courier accepts the delivery within the defined timeout, the mediator can initiate order cancellation, release the payment hold, and notify the customer.

This approach makes the overall workflow easier to monitor and maintain. It also allows individual processing services to operate asynchronously and scale according to their own workloads.

However, the decision introduces a potential mediator bottleneck. This limitation is accepted as an architectural trade-off and will be addressed through capacity monitoring, backpressure, and geographical partitioning.

## 5. Architectural Trade-Off Analysis: The Mediator Bottleneck

As discussed by Mark Richards and Neal Ford in *Fundamentals of Software Architecture*, the Mediator Topology introduces a potential scalability and concurrency bottleneck.

The mediator is responsible for coordinating active workflows. When downstream services become slower, workflows may remain active for longer periods. As a result, the mediator has to manage more concurrent workflow instances, while incoming orders continue to arrive.

The following diagram illustrates the main processing flow and the potential bottlenecks:

```text
       [ Incoming Order Stream ]
                  |
                  v
       +----------------------+
       |   INITIATING QUEUE   |  <-- Queue backlog under high load
       +----------+-----------+
                  |
                  v
       +----------------------+
       |    EVENT MEDIATOR    |  <-- Active workflow concurrency limit
       |   (Orchestrator VM)  |
       |                      |
       |  Workflow State      |
       |  Timeout Handling    |
       |  Compensation Logic  |
       +----+----+----+-------+
            |    |    |
       +----+    |    +-------+
       v         v            v
   +-------+ +-------+    +-------+
   | Pay   | | Kit   |    | Cour  |
   | Worker| | Worker|    | Worker|
   +-------+ +-------+    +-------+
            |
            v
       +----------+
       |  Notif.  |
       | Processor|
       +----------+
```

### Detailed Trade-Off Matrix

| Architectural Characteristic | Rating | System Impact |
|---|---|---|
| **Agility / Maintainability** | High (4/5) | Changes to the order fulfillment workflow can be made primarily within the mediator's workflow definitions. |
| **Testability** | High (4/5) | Individual processors can be tested independently by mocking incoming commands and outgoing reply events. |
| **Deployability** | High (4/5) | The mediator and processing services can be deployed as separate architectural components. |
| **Performance** | Medium (3/5) | Additional message exchanges introduce latency compared to direct synchronous communication. |
| **Scalability** | Medium-Low (2/5) | The mediator may become a bottleneck when active workflow concurrency reaches its capacity. |
| **Fault Tolerance** | Medium (3/5) | Persistent workflow state, message durability, and mediator recovery mechanisms are required to prevent workflow loss. |

### The Starvation Paradox Explained

One important issue with this architecture is the relationship between mediator capacity and downstream processor utilization.

Consider a situation where courier acceptance becomes significantly slower during an unexpected rainstorm. The mediator must keep affected workflows active while waiting for courier responses or timeouts.

If the mediator has a limited number of available workflow slots, these long-running workflows can occupy a significant part of its capacity.

This can lead to several consequences:

1. **Initiating Queue Backlog:** New orders spend more time waiting in the initiating queue because the mediator cannot accept and coordinate them quickly enough.

2. **Worker Starvation:** Some processors, such as `PaymentProcessor` and `NotificationProcessor`, may remain underutilized while waiting for the mediator to dispatch new tasks.

3. **Reduced Throughput:** Even though individual processors may have enough capacity to handle more requests, the overall system throughput is limited by the mediator.

This is particularly problematic because increasing the number of downstream workers alone will not necessarily solve the problem. If the mediator remains the limiting component, additional workers may simply remain idle.

## 6. Mitigations and Architectural Fitness Functions

The following measures are proposed to reduce the impact of the mediator bottleneck and make the architecture more predictable under load.

### 6.1 Geographical Sharding of Mediators

The mediator instances should be partitioned by geographical delivery zones, such as metropolitan areas or geohash-based regions.

This prevents a sudden increase in orders in one location from consuming all available mediator capacity across the entire platform.

For example, a rainstorm in one city should not significantly affect order processing in another city.

### 6.2 Dynamic Backpressure and Circuit Breaking

The system should monitor the initiating queue depth and queue waiting time.

If the queue contains more than 500 pending orders or the p95 queue waiting time exceeds 30 seconds, the ingress gateway should temporarily reject non-priority requests.

HTTP 429 responses with appropriate retry information can be used to communicate temporary overload to clients.

Circuit breakers should also prevent repeated requests to downstream services that are currently unavailable or responding too slowly.

### 6.3 Automated Architectural Fitness Functions (CI/CD Quality Gates)

Architectural fitness functions are automated checks that verify whether the system continues to meet its important architectural requirements.

The following checks should be included in performance testing and CI/CD pipelines.

**Fitness Function 1 — Queue Dwell Ratio**

This metric measures how much time an order spends waiting in the initiating queue compared to the time spent on active orchestration.

The goal is to ensure that queue waiting does not become a significant part of the overall processing time.

Under baseline load, automated performance tests should fail if the ratio exceeds 0.5.

$$
\text{Dwell Ratio} =
\frac{T_{\text{queue wait}}}
{T_{\text{active orchestration}}}
\leq 0.5
$$

A value above this threshold indicates that orders are spending too much time waiting to be picked up by the mediator.

**Fitness Function 2 — Worker Starvation Index**

The system should also monitor the utilization of downstream processors.

An alert should be triggered when fast processor utilization drops below 15% while mediator utilization exceeds 90%.

This combination may indicate that the mediator is unable to dispatch work quickly enough, even though downstream processors still have available capacity.

These two fitness functions help identify different aspects of the same problem: the first focuses on delays experienced by incoming orders, while the second helps identify inefficient utilization of processing resources.

## 7. References

1. Richards, Mark. *Software Architecture Patterns*. O'Reilly Media, Chapter 2: "Event-Driven Architecture".
2. Richards, Mark, and Neal Ford. *Fundamentals of Software Architecture: An Engineering Approach*. O'Reilly Media, Chapter 14: "Event-Driven Architecture Style".
3. Nygard, Michael T. *Release It!: Design and Deploy Production-Ready Software*. Pragmatic Bookshelf. (Circuit Breakers and Bulkheads).