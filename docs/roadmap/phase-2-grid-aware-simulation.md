# Phase 2 — Grid-Aware Data Center Simulation

## Objective

Transform the project from a telemetry simulator into a realistic AI data center digital twin capable of simulating electrical infrastructure, thermal behavior, utility constraints, operational decision making, and asset lifecycle history.

## Priority Implementation Scenario

### Demand-Response Event Scenario

Implement one end-to-end demand-response scenario in `DataCenterDigitalTwin`:

- [x] Simulate a utility power price spike
- [x] Trigger GPU load shedding based on configurable demand-response policy
- [x] Model the cooling loop response after compute load reduction
- [x] Store power, GPU, cooling, KPI, and alert telemetry in ClickHouse
- [ ] Emit durable domain events for the price spike, policy decision, command, equipment response, alert lifecycle, and recovery
- [ ] Correlate ClickHouse telemetry windows with event-store records using shared asset, scenario, correlation, and causation identifiers
- [ ] Display the event timeline in Grafana
- [ ] Surface the active alert and recovery status in the React operator console
- [x] Expose the scenario trigger and reset controls through FastAPI

**Scenario flow:** power price spike → domain event → GPU load-shed command → equipment response → ClickHouse telemetry + event-store history → Grafana/operator alert and recovery timeline.

## Electrical Infrastructure

### Utility Power

- [x] Simulate dynamic utility power pricing
- [x] Model varying utility capacity limits
- [ ] Simulate brownouts and utility disturbances
- [ ] Support configurable utility rate schedules
- [ ] Model time-of-use pricing
- [ ] Model peak demand charges

### Power Distribution

- [ ] Simulate UPS systems
- [ ] Simulate backup generators
- [ ] Model battery discharge behavior
- [ ] Simulate electrical distribution hierarchy
- [ ] Calculate available electrical capacity
- [ ] Simulate demand response events
- [ ] Implement load shedding logic
- [ ] Model critical and non-critical loads

## Compute Infrastructure

### GPU Clusters

- [ ] Simulate AI training workloads
- [ ] Model GPU power consumption
- [ ] Simulate burst workloads
- [ ] Simulate idle and peak operating modes
- [ ] Configure multiple compute halls
- [ ] Simulate rack-level power consumption
- [ ] Model workload priority levels
- [ ] Model job interruption behavior

## Cooling System

### Air and Liquid Cooling

- [ ] Simulate CRAH/CRAC operation
- [ ] Add chilled-water system behavior
- [ ] Simulate liquid cooling loops
- [ ] Model coolant flow rate
- [ ] Model supply and return temperatures
- [ ] Simulate heat rejection
- [ ] Simulate cooling tower performance
- [ ] Simulate pump failures
- [ ] Model cooling capacity limits

## Thermal Modeling

- [ ] Calculate rack temperatures
- [ ] Model rack heat generation
- [ ] Simulate thermal hotspots
- [ ] Model airflow between aisles
- [ ] Simulate cold aisle and hot aisle containment
- [ ] Calculate thermal efficiency
- [ ] Model temperature rise during cooling degradation

## Hybrid Telemetry and Event Architecture

Use two complementary persistence paths rather than treating every process value as an event-sourced aggregate.

### Telemetry Path — ClickHouse

ClickHouse remains the analytical system of record for high-volume numeric process data.

- [ ] Store raw and normalized equipment telemetry in ClickHouse
- [ ] Design high-performance telemetry tables using appropriate partitioning, ordering keys, codecs, and retention policies
- [ ] Preserve event time, ingestion time, site, zone, asset class, asset ID, metric name, engineering unit, quality, and source metadata
- [ ] Add shared `correlation_id`, `scenario_id`, and `event_id` fields where telemetry is associated with a domain event
- [ ] Create materialized views for minute, hourly, and daily rollups
- [ ] Create feature-oriented views for predictive-maintenance windows
- [ ] Define retention tiers for raw, downsampled, and derived telemetry
- [ ] Benchmark sustained ingestion rate and representative analytical queries

### Event Path — Append-Only Event Store

Use a separate durable event store for lower-volume, higher-value facts describing equipment behavior and system decisions.

- [x] Select and document the first event-store implementation
  - [x] Start with PostgreSQL using an append-only `events` table for local learning and operational simplicity
  - [ ] Keep the event envelope portable so EventStoreDB can be evaluated later without redesigning producers
  - [ ] Continue using MQTT for device-facing transport; evaluate NATS JetStream later for durable internal delivery and replay
- [x] Define a canonical event envelope with:
  - [x] `event_id`
  - [x] `event_type`
  - [x] `event_version`
  - [x] `stream_id`
  - [x] `stream_version`
  - [x] `asset_id` and `asset_type`
  - [x] `occurred_at` and `recorded_at`
  - [x] `correlation_id` and `causation_id`
  - [x] `scenario_id`
  - [x] `source`
  - [x] `payload`
  - [x] `metadata`
- [x] Enforce append-only writes and unique stream-version constraints
- [x] Implement optimistic concurrency when appending to an asset or workflow stream
- [ ] Define event-schema versioning and upcasting rules
- [ ] Define event-retention, backup, and restore expectations

### Initial Domain Events

- [x] `ScenarioStarted`
- [ ] `ScenarioCompleted`
- [x] `UtilityPriceSpikeDetected`
- [x] `DemandResponsePolicyEvaluated`
- [x] `LoadSheddingRequested`
- [x] `EquipmentCommandIssued`
- [ ] `EquipmentStateChanged`
- [ ] `ThresholdExceeded`
- [ ] `AlertRaised`
- [ ] `AlertAcknowledged`
- [ ] `AlertCleared`
- [ ] `AnomalyDetected`
- [ ] `MaintenanceRiskScored`
- [ ] `MaintenanceRecommended`
- [ ] `MaintenanceWorkStarted`
- [ ] `MaintenanceCompleted`
- [ ] `EquipmentFailureSimulated`
- [ ] `EquipmentRecovered`

### Event Producers and Projectors

- [x] Add a reusable Python event-envelope package shared by API and workers
- [x] Add an event-writer abstraction so application code does not depend directly on PostgreSQL or EventStoreDB APIs
- [ ] Emit events from scenario control, alerting, maintenance scoring, operator actions, and simulated equipment state transitions
- [ ] Build an event projector that creates an asset timeline read model
- [ ] Build an event projector that creates alert-lifecycle views
- [ ] Build an event projector that creates maintenance-history views
- [ ] Make projectors idempotent and track checkpoints
- [ ] Add replay commands for rebuilding projections from the event store
- [ ] Add dead-letter handling and observable retry behavior for failed event processing

### Telemetry-to-Event Derivation

Raw samples should remain in ClickHouse. Stateful workers should convert meaningful telemetry patterns into durable domain events.

- [ ] Implement threshold-crossing detection with hysteresis and debounce
- [ ] Implement state-change detection rather than emitting repeated unchanged states
- [ ] Implement rate-of-change and rolling-baseline detectors
- [ ] Implement equipment-cycle and runtime accumulation events
- [ ] Implement data-quality and sensor-health events
- [ ] Store the ClickHouse query window or telemetry references used to derive each event
- [ ] Prevent duplicate events by using deterministic detection keys or idempotency keys

### Predictive-Maintenance Integration

- [ ] Build model features from ClickHouse telemetry windows
- [ ] Join telemetry features with event-store maintenance, alarm, intervention, and failure history
- [ ] Emit `MaintenanceRiskScored` for every scored asset window
- [ ] Emit `MaintenanceRecommended` only when policy thresholds and cooldown rules are met
- [ ] Capture model name, model version, feature-set version, threshold, score, and explanation metadata in inference events
- [ ] Record whether a recommendation was acknowledged, acted upon, dismissed, or followed by failure
- [ ] Create labeled training datasets from telemetry preceding known failure and maintenance events
- [ ] Backtest new detectors and models by replaying historical telemetry windows and comparing generated events with actual outcomes

### Query and API Surfaces

- [ ] Add an asset timeline API combining event records with links to surrounding ClickHouse telemetry
- [ ] Add event queries by asset, type, scenario, correlation ID, and time range
- [ ] Add an endpoint for retrieving the telemetry window that explains a selected event
- [ ] Add an operator action endpoint that writes commands and acknowledgements as events
- [ ] Add a maintenance-history endpoint
- [ ] Add a model-inference history endpoint

## KPIs

- [ ] Calculate PUE in real time
- [ ] Calculate cooling efficiency
- [ ] Calculate electrical utilization
- [ ] Calculate rack utilization
- [ ] Calculate power cost
- [ ] Calculate energy consumption
- [ ] Calculate carbon-aware operating metrics
- [ ] Calculate workload efficiency

## Monitoring and Alerting

Generate alerts for:

- [ ] Power capacity limits
- [ ] Cooling capacity limits
- [ ] Thermal hotspots
- [ ] UPS failures
- [ ] Pump failures
- [ ] Utility events
- [ ] Equipment failures
- [ ] High PUE
- [ ] Sensor failures
- [ ] Demand response events
- [ ] Abnormal GPU power draw

## Dashboard

### Grafana

- [ ] Electrical dashboard
- [ ] Cooling dashboard
- [ ] Thermal dashboard
- [ ] Utility pricing dashboard
- [ ] Historical trend dashboard
- [ ] PUE dashboard
- [ ] Demand response dashboard
- [ ] Event annotations over telemetry trends
- [ ] Predictive-maintenance score and intervention dashboard

### React Operator Console

- [ ] Facility overview
- [ ] Rack visualization
- [ ] Alarm console
- [ ] Equipment status
- [ ] Simulation controls
- [ ] KPI dashboard
- [ ] Cooling loop visualization
- [ ] Electrical capacity visualization
- [ ] Asset event timeline
- [ ] Correlated telemetry drill-down
- [ ] Maintenance recommendation workflow

## FastAPI Controls

- [ ] Expose simulation controls
- [ ] Configure utility pricing
- [ ] Configure weather assumptions
- [ ] Configure workloads
- [ ] Trigger equipment failures
- [ ] Trigger demand response events
- [ ] Reset simulation
- [ ] Export simulation results
- [ ] Update cooling setpoints
- [ ] Update load shedding policies

## Suggested Implementation Increments

### Increment 2A — Event Foundation

- [x] Add PostgreSQL to Docker Compose
- [x] Create the append-only event schema and migration
- [x] Implement the canonical Python event envelope and event writer
- [ ] Emit scenario, operator-command, and alert-lifecycle events
- [ ] Add unit and integration tests for ordering, idempotency, and optimistic concurrency

### Increment 2B — Asset Timeline

- [ ] Add event projectors and checkpoint storage
- [ ] Build an asset timeline read model
- [ ] Expose the timeline through FastAPI
- [ ] Link timeline events to surrounding ClickHouse telemetry
- [ ] Display the timeline and trend drill-down in the React console

### Increment 2C — Predictive Maintenance

- [ ] Add telemetry-derived anomaly and health-state events
- [ ] Version feature definitions and maintenance models
- [ ] Persist risk scores and recommendations as events
- [ ] Capture maintenance outcomes and failure labels
- [ ] Add replay-based backtesting and model evaluation

### Increment 2D — Durable Internal Messaging

- [ ] Evaluate NATS JetStream for internal event delivery
- [ ] Introduce transactional outbox publishing from PostgreSQL
- [ ] Add idempotent consumers, durable subscriptions, retries, and dead-letter handling
- [ ] Retain PostgreSQL or EventStoreDB as the authoritative event history rather than relying on the broker alone

## Stretch Goals

### AI Features

- [ ] Predictive load forecasting
- [ ] AI-assisted cooling optimization
- [ ] Failure prediction
- [ ] Capacity planning recommendations

### Workload Scheduling

- [ ] Automatic workload migration between simulated halls
- [ ] Multi-hall balancing
- [ ] Power-aware scheduling
- [ ] Cooling-aware scheduling
- [ ] Priority-based workload throttling

### Utility Integration

- [ ] Financial demand-response simulation
- [ ] Utility demand-response mode with configurable financial incentives
- [ ] Cost optimization mode
- [ ] Peak shaving
- [ ] Renewable energy integration

### Digital Twin Visualization

- [ ] Rack-level temperature visualization
- [ ] Coolant flow visualization
- [ ] Electrical one-line diagram
- [ ] Heat map visualization
- [ ] Live facility animation
- [ ] Digital twin showing rack temperatures, coolant flow, and electrical distribution

## Deliverable

A realistic grid-aware AI data center simulation that models the interaction between power, cooling, compute load, high-volume telemetry, durable domain events, predictive maintenance, alerting, and operator control.
