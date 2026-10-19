# Feature Specification: Deterministic FleetCharge Wave Review

**Feature Branch**: `001-wave-review`
**Created**: 2026-10-19
**Status**: Teaching backend implemented; real-emulator local CI verified. See [verification](../../docs/verification.md) for hosted evidence.
**Input**: Build the planned FleetCharge Agent as a realistic workload for teaching Cosmos DB users CI with the vNext emulator. Prepare specification, plan, contracts, and traceable tasks.

## Purpose and Scope

The lesson is emulator-backed CI, not building a fleet management product. This feature supplies the smallest useful agent workload that demonstrates real document reads, partition-scoped queries, and persisted writes. A reader can exercise it locally without a model subscription, then reuse the same tests in the next GitHub Actions feature.

In scope: one delivery-wave review operation, complete sample data, deterministic agent/tool behavior, emulator-backed tests, local lifecycle scripts, and a reproducible command-line walkthrough.

Out of scope: the Actions workflow itself (next feature), dashboard, live-model adapter, route swapping, real charger bookings, production authentication/deployment, optimization, and the finished blog post. Keep the architecture compatible with a separately configured live model later without implementing it now.

Sources: [app requirements](../../docs/app-requirements.md), [walkthrough](../../docs/speckit-walkthrough.md), and [constitution](../../.specify/memory/constitution.md). Concrete assumptions below supersede illustrative details in the outline for this feature only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a real data-backed wave review (Priority: P1)

As a Cosmos DB developer following the lesson, I want the sample agent to retrieve known fleet data and persist a defensible recommendation, so that my integration test covers the real data path rather than a database mock.

**Why this priority**: Provides the agent we intend to build and the passing baseline needed for the CI lesson.

**Independent Test**: Start the isolated emulator, seed the golden scenario, submit a wave review, and inspect its response and stored audit.

**Acceptance Scenarios**:

1. **Given** SEA-01's golden 2 PM wave at the fixed 12:30 review time, **When** reviewed, **Then** the result is `rebalanceCharging`, identifies `van-042` / `route-77` as `batteryShortfall`, and assigns SEA-01's `charger-fast-03` from 12:30 for 11 minutes.
2. **Given** the healthy second route and an occupied charger, **When** reviewed, **Then** `van-088` receives no charging assignment and `charger-fast-01` is never selected.
3. **Given** the completed review, **When** its audit is read back, **Then** assignments, risks, evidence, review time, and decision hash match the response for that write; each evidence entry resolves to a retrieved record.
4. **Given** two equivalent reviews of unchanged data at the same review time, **When** both complete, **Then** their normalized responses match and one audit identity exists for that depot/wave.

### User Story 2 - Detect realistic data-access regressions (Priority: P1)

As a Cosmos DB developer, I want fixtures that expose incorrect partitions and stale reads, so that CI can fail on a change that superficially still returns a plausible recommendation.

**Why this priority**: This is the substance of the emulator integration lesson, not an optional hardening exercise.

**Independent Test**: Run the partition, telemetry, maintenance, and audit tests independently against fresh seeded databases.

**Acceptance Scenarios**:

1. **Given** a faster PDX-02 charger with the same ID as SEA-01's charger, **When** reviewing SEA-01, **Then** selected records, tool arguments, evidence provenance, and audit data never use PDX-02.
2. **Given** a scenario assigning `van-099` to a wave route with a maintenance hold, **When** reviewed, **Then** it has no assignment and has an explicit `maintenanceHold` risk.
3. **Given** a 95% vehicle summary, an older 92% reading, and a current 58% reading for `van-042`, **When** reviewed, **Then** the 58% reading determines the risk and charging calculation.
4. **Given** a subsequent review after valid source data changes, **When** it completes, **Then** the same audit identity contains the newly computed decision, not an additional audit document.
5. **Given** an incompatible, reserved, unavailable, or too-late charger, **When** reviewed, **Then** it is excluded and any unserviceable battery-shortfall vehicle is reported explicitly.

### User Story 3 - Reproduce the lesson without cloud credentials (Priority: P2)

As a reader, I want documented start, seed, test, inspect, and cleanup steps, so that I can reproduce the integration locally before trying the later GitHub Actions workflow.

**Why this priority**: A reproducible sample is necessary for the blog, but depends on the workload and its tests.

**Independent Test**: Follow the final quickstart from a clean checkout using only documented prerequisites, including an emulator startup failure.

**Acceptance Scenarios**:

1. **Given** Python and Docker prerequisites, **When** following the quickstart, **Then** the golden review and all five core tests run without Azure login or live-model credentials.
2. **Given** an emulator that never becomes ready, **When** startup reaches its deadline, **Then** the command exits nonzero with diagnostics rather than continuing to seed.
3. **Given** a failed test, **When** cleanup runs, **Then** the sample's isolated database/container are cleaned up, and unrelated databases/containers remain untouched.
4. **Given** a model script with an unexpected tool or exhausted turn sequence, **When** reviewed, **Then** the request fails explicitly, creates no recommendation, and makes no live-model call.

### Edge Cases

- Malformed IDs or timestamps; missing depot policy, wave, routes, vehicles, or telemetry.
- Cross-depot telemetry, future readings, duplicate observation times, and exactly-30-minute freshness boundary.
- Battery target exactly met, target over 100%, invalid battery/capacity/power/efficiency values.
- Charger connector mismatch, touching reservation boundaries, overlapping proposed assignments, and charging that ends exactly at departure.
- Missing feasible charger, all routes healthy, and a held vehicle whose battery is otherwise sufficient.
- Repeated or concurrent reviews; audit failure after reads; changed source data during a review.
- Tool argument tampering, duplicate/reordered calls, malformed final model output, and loop limits.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Accept a depot and delivery-wave identity and return a structured result containing assignments, route risks, evidence, review time, audit identity, and decision hash.
- **FR-002**: Retrieve the requested depot policy and wave; retrieve all referenced routes and their assigned vehicles. Reject missing or inconsistent references rather than dropping them.
- **FR-003**: Scope source reads to the intended depot, or to an explicitly validated vehicle owner for telemetry. Preserve container, partition, and document provenance for every evidence record.
- **FR-004**: Choose each vehicle's latest reading not later than review time; break equal-time ties by ascending document ID. Accept readings at most 30 minutes old inclusive. Ignore future readings; fail if no eligible reading exists. Validate ownership of all returned telemetry before selecting a reading.
- **FR-005**: Compute target battery as route requirement + weather adjustment + depot buffer, all in percentage points. Do not silently cap targets above 100%; report an unserviceable risk.
- **FR-006**: Exclude maintenance-held or unavailable vehicles from charging and report their reason. Evaluate maintenance first, then status, then battery; do not swap routes.
- **FR-007**: Choose compatible available chargers and feasible nonoverlapping charging intervals ending no later than departure. Use the deterministic scheduling and charge-duration assumptions below.
- **FR-008**: Return `noAction` when no route has risks; `rebalanceCharging` when at least one risk exists and all risks have feasible charging assignments; otherwise `unableToSchedule`, retaining any feasible assignments.
- **FR-009**: Return only evidence actually consumed in evaluation: policy, wave, each route/vehicle/selected telemetry, and selected chargers. Preserve the public ID list and add structured provenance in the audit and test trace.
- **FR-010**: Recompute every review and replace the one audit document keyed by depot/wave. Identical inputs produce identical normalized responses. Concurrent writes may be last-write-wins; do not claim exactly-once execution or booking.
- **FR-011**: Exercise the same registered tools and agent orchestration with a scripted model client, not a canned successful response or alternate bypass path. Validate model-proposed writes against the computed decision.
- **FR-012**: Fail on malformed input, unusable source data, invalid tool sequences/arguments, or persistence failure using the documented error contract. Never fall back to a live model or return a success-shaped substitute.
- **FR-013**: Supply complete, deterministic fixtures, including the second route, conflicting telemetry, a genuinely considered maintenance-held vehicle, an occupied charger, and a same-ID cross-depot trap.
- **FR-014**: Provide isolated provisioning/seeding, bounded readiness checks, diagnostics, and narrowly scoped cleanup. Integration tests must perform real reads/writes rather than replace database access with fakes.
- **FR-015**: Bound each review to at most 20 model turns and 60 seconds of application execution. Reject unexpected turns and suppress no errors. Configuration permits only scripted mode in this feature.
- **FR-016**: Provide reproducible local steps and explain what emulator tests do not prove: production identity, performance, live-model reasoning, or operational booking.

### Key Entities

- **Depot policy**: timezone, battery buffer, telemetry freshness, scheduling window.
- **Delivery wave**: depot, departure, ordered route identities.
- **Route**: depot/wave, assigned vehicle, required battery and weather adjustment.
- **Vehicle**: depot, status/maintenance, connector, battery capacity and maximum charge power.
- **Telemetry**: vehicle/depot ownership, observation time, measured battery.
- **Charger**: depot, connector, status, power, reserved intervals.
- **Recommendation audit**: deterministic identity, review time, source provenance, validated decision, decision hash and rules version.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reader obtains the specified golden recommendation and matching persisted audit using the documented local steps, with no model or cloud-account credential.
- **SC-002**: All five core scenarios have executable checks inspecting returned decisions and real stored/retrieved records; no check passes solely because a response is nonempty.
- **SC-003**: Ten sequential equivalent golden reviews produce identical normalized responses and exactly one audit document; a changed-input review replaces that document.
- **SC-004**: Every emitted evidence identity resolves to the expected container and partition in the review trace; the cross-depot, maintenance, and stale-summary traps are demonstrably exercised.
- **SC-005**: Startup failure, bad source data, unexpected scripted turns, and failed writes all produce nonzero commands or explicit error responses. Pre-write failures leave the existing audit untouched; errors/timeouts after persistence starts explicitly disclose possible completed or uncertain writes rather than claiming rollback.
- **SC-006**: A clean-checkout rehearsal passes and cleanup leaves unrelated resources intact. Actual runtime and dependency/image identities are recorded rather than assuming a performance benchmark.

## Assumptions

These are explicit demo defaults selected to remove ambiguity, not production fleet policy. No open behavior questions block planning; changes require updating the spec and its tests.

- Fixed demo review time: `2026-10-19T12:30:00-07:00`; departure: `2026-10-19T14:00:00-07:00`. A reader's current date must not invalidate the fixture.
- Golden battery target: 64 + 6 + 12 = 82%. Vehicle usable capacity is 100 kWh; charger and vehicle limits are 150 kW; charging efficiency is 0.90. Duration is ceiling(100 * (82 - 58) / 100 / (150 * 0.90) * 60) = 11 minutes. This intentionally replaces the outline's illustrative 35-minute/12:40 assignment.
- Charge rate is constant, with no taper or turnaround. Intervals are half-open `[start, end)`; touching reservations do not overlap. Assignment completion exactly at departure is allowed.
- Process routes in ascending route ID; for each at-risk available vehicle, find each charger's earliest gap starting at review time; choose earliest finish, then earliest start, then ascending charger ID. Previously proposed assignments also block that charger.
- A policy's reservation window limits maximum assignment duration, not how far into the future reservations are inspected. Golden maximum duration is 45 minutes. A 46-minute assignment is infeasible even if the wave deadline allows it.
- Golden wave contains `route-77` / `van-042` and `route-88` / `van-088`. The healthy route has requirement 40%, weather 0%, and latest battery 90%. A named maintenance scenario changes the second route to `van-099` and updates that vehicle's assignment reference.
- Reads are not a cross-container snapshot. A review hashes and records the input versions it actually consumed. No cross-document concurrency guarantees are claimed.
- Audit identity is fixed per depot/wave. Repeated computation and last-write-wins replacement are deliberate; concurrent clients may observe their own returned decision superseded by another review.
- The demo remains local and advisory. Readers use their own environment; the maintainer's `jaydestro` workspace rule is not a reader authentication requirement.

## Dependencies and Risks

| Dependency or risk | Resolution / owner |
|---|---|
| Emulator supports only a subset of database behavior | Implementation owner verifies the exact SDK queries and writes before building on them; no production-equivalence claims |
| Framework and SDK API drift | Implementation owner locks resolved versions and smoke-tests the scripted tool loop before full integration |
| Domain sample distracts from CI lesson | Keep one endpoint, no UI/live-model adapter in this slice, and show database-focused assertions |
| Fork/read access to sample | Repository is currently private; maintainer decides publication/access separately before external readership |
| Review date vs fixture timestamps | Inject the fixed clock for all golden paths and document it |

## Clarifications

### Session 2026-10-19

- CI with Cosmos DB vNext is the teaching goal; FleetCharge remains the real agent workload.
- Authentication is outside the emulator's enforcement capabilities, not absent from workflow design.
- Resolve the outline's illustrative details using the explicit demo assumptions above, not unexplained constants.
- Build the backend/emulator test slice first; Actions and the regression demonstration follow as a separate feature.
