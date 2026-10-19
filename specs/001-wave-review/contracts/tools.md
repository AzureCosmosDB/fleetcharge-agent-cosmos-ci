# Tool and Scripted Model Contract

**Status**: Implemented with Agent Framework 1.21.0; the real loop, typed dispatch, tampering and persisted result checks are tested.

## Context and typed results

Tools are registered framework functions. Each receives typed business arguments, while request-scoped depot/wave/clock/trace context is injected by application code and is not model-controlled. Every input/output uses strict validation; no unrestricted SQL tool is exposed.

Reads return validated documents with `{container, id, partitionKey, etag}` provenance. Tool traces record name, validated arguments, returned identities, success/error status, and call ID; exclude credentials and nondeterministic timing from golden comparisons.

| Tool | Model-visible input | Result | Preconditions |
|---|---|---|---|
| `get_depot_policy` | `depotId` | Validated policy | Matches request depot |
| `get_delivery_wave` | `depotId`, `deliveryWaveId` | Validated wave | Matches request; valid policy loaded |
| `get_route_requirements` | `depotId`, `routeIds` | Routes sorted by ID | IDs exactly equal wave route set; valid wave loaded |
| `get_vehicle_status` | `depotId`, `vehicleIds` | Vehicles sorted by ID | IDs exactly equal assigned vehicle set; valid routes loaded |
| `get_latest_telemetry` | `vehicleIds` | Latest eligible reading per vehicle, sorted by vehicle ID | Exact vehicle set and validated depot ownership |
| `find_available_chargers` | `depotId`, `connectorTypes`, `startAfter`, `endBefore` | Available owned candidates plus validated `decision` with assignments/risks/evidence | Inputs exactly match known connector set, clock, wave departure; all prior data loaded |
| `write_charging_recommendation` | `depotId`, `deliveryWaveId`, `decision` | Persisted validated response and audit ID/hash | Decision exactly equals computed context decision, including evidence; one write call only |

All array inputs are sorted unique arrays. Tool calls supply complete expected identity sets; missing or surplus identities fail rather than silently narrowing the review. `connectorTypes` is the sorted set from wave vehicles. No arbitrary vehicle query or caller-selected partition is accepted.

Telemetry selects for all wave vehicles, including held ones, to keep a single explicit complete-data contract. Missing telemetry fails validation even when a maintenance risk could otherwise be inferred. Do not fall back to vehicle summaries.

`find_available_chargers` queries available candidates of expected connectors in the depot; reservations are assessed by pure rules over the full proposed interval. Do not equate `status=available` with an unreserved charging window. Candidate ordering must not determine selection accidentally. Every returned candidate's depot is validated before scheduling, so a widened query that leaks PDX records fails explicitly rather than being silently filtered away.

## Required framework conversation

One model request emits one tool call at a time for this sample:

1. Call `get_depot_policy` with request depot.
2. Validate matching tool result/call ID; call `get_delivery_wave`.
3. Consume wave result; derive route IDs; call `get_route_requirements`.
4. Consume routes; derive vehicle IDs; call `get_vehicle_status`.
5. Consume vehicles; call `get_latest_telemetry`.
6. Consume telemetry; call `find_available_chargers` with connectors and exact review/departure times.
7. Consume its computed decision; call `write_charging_recommendation` with that decision.
8. Consume the persisted result; emit terminal acknowledgement containing the identical structured response.

The client supports arbitrary valid seeded depot/wave IDs, not only a canned SEA-01 transcript. It is deterministic but not a live language model. Tool result values, not the natural-language prompt or untrusted document instructions, determine subsequent arguments. Fail on an unexpected call ID/name, changed request identity, duplicates, reordered turns, additional calls after persistence, script exhaustion or invalid terminal output.

The framework, not the scripted client, dispatches tools. The client must not directly invoke the repository or construct a successful recommendation. Fleet rules are shared application logic called by the tool path. Read-only request context is authoritative; the model's proposal cannot rewrite maintenance flags, change depot, drop risks, substitute evidence, or alter assignments.

## Write validation and normalized audit payload

The write tool validates the complete decision against the in-context computed result, adds deterministic review/audit metadata, calculates hashes, and upserts the recommendations record. It returns the acknowledged response payload from that operation. Test separate read-back through the SDK; do not trust only an HTTP 200 or the return value of a mocked write.

`rulesVersion` starts at `fleetcharge-demo-v1`. Hash normalization and evidence/source version shapes follow [data-model.md](../data-model.md). `decisionHash` excludes itself and matches the hash of the response before that field is added; `inputHash` is stored only in the audit.

Any pre-write tool failure aborts the run, logs context, and leaves no newly written recommendation. Existing audit records from earlier reviews remain untouched. Failures after an acknowledged write do not delete valid state to pretend atomicity.

## Scheduling rules

For each route in ascending ID:

1. Apply maintenance/status/target-over-100 checks in that priority.
2. If latest battery meets target, no charging/risk is needed.
3. Otherwise record `batteryShortfall`; charge energy is capacity times percentage shortfall / 100.
4. Effective input power is minimum(vehicle max kW, charger max kW) times 0.90. Duration is whole minutes rounded up.
5. Inspect every compatible available charger's earliest free interval starting at review time. Merge existing reservations and earlier proposed assignments when searching gaps. Occupied/offline chargers are excluded for the whole review window.
6. Reject intervals longer than the policy limit or ending after departure. Pick earliest end, earliest start, then ascending charger ID.
7. If no interval fits, add `noFeasibleCharger`. Otherwise add one assignment per at-risk vehicle.

Timezone-aware comparison is by instant, not display string. Intervals are half-open. Invalid reservation timestamps or nonpositive intervals are source-data errors, not ignorable candidates.

## Regression teaching note

The later intentional mutation must remove the effective depot restriction, not just a redundant predicate while leaving an explicit depot partition key. Real integration tests should fail either on the provenance guard or an incorrect result. Do not weaken ownership validation to manufacture the blog's failure. If the emulator rejects a widened cross-partition query, record that failure honestly and use a supported wrong-partition mutation to demonstrate the same boundary.
