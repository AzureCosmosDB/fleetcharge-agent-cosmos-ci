# CI Blog Outline: Test a Domain-specific Cosmos DB-backed Agent in GitHub Actions

## Working Title

**Test a Cosmos DB-backed EV fleet agent in GitHub Actions with the vNext emulator**

## Alternate Titles

- **How to test a data-grounded AI agent with Cosmos DB before merging a pull request**
- **CI for domain agents: Cosmos DB emulator, seeded data, and deterministic tool-call tests**
- **Testing an EV fleet operations agent with Azure Cosmos DB and GitHub Actions**

## App and Repo Name

App name:

**FleetCharge Agent**

Recommended repo name:

**`fleetcharge-agent-cosmos-ci`**

Other options:

- `cosmos-fleetcharge-agent`
- `ev-fleet-agent-cosmos-ci`
- `fleet-ops-agent-cosmosdb`
- `cosmosdb-agent-ci-fleet-demo`

## One-sentence Promise

Learn how to build a GitHub Actions CI check that starts the Azure Cosmos DB vNext emulator, seeds EV fleet operations data, runs deterministic agent integration tests without calling a live LLM, and fails the pull request when the agent retrieves, filters, or writes the wrong Cosmos DB data.

## Audience

Primary audience:

- Developers building AI agents that depend on domain data.
- Developers new to CI who want a practical GitHub Actions example.
- Azure Cosmos DB users who want to test agent tools before merge.
- App teams building operational copilots or domain agents.

Secondary audience:

- Architects evaluating CI patterns for AI agents.
- PMs and engineering leads looking for a concrete data-grounding test story.
- Developers exploring the Cosmos DB vNext emulator in automated workflows.

## Scope

This article covers **continuous integration only**.

It does cover:

- A realistic 2026 business scenario.
- A domain-specific agent.
- Cosmos DB container design.
- Seeded EV fleet test data.
- Mocking or scripting the LLM in CI.
- Starting the Cosmos DB vNext emulator in GitHub Actions.
- Running deterministic integration tests.
- Proving a bad data-access change fails CI.
- Explaining where live model and CD testing fit later.

It does not cover:

- Full production deployment.
- Azure hosting setup.
- Infrastructure as Code.
- Fleet optimization at production scale.
- Production identity and authorization.
- RU cost benchmarking.
- Multi-region behavior.
- Full live-model evaluation pipelines.

Mention CD only as a follow-up topic.

## Fake Company and Business Context

### Company

**Northwind Freight**

Northwind Freight operates electric delivery vans across several urban depots. Each depot has delivery waves, vehicle battery telemetry, charger reservations, route energy estimates, maintenance constraints, driver shift windows, and weather adjustments.

The team is small. They ship updates quickly, but every agent change is risky because a bad query or wrong partition key can produce a recommendation that assigns the wrong vehicle, ignores a maintenance hold, or double-books a charger.

### Application

**FleetCharge Agent**

FleetCharge Agent helps dispatch and depot operations teams answer:

> Which delivery vans should charge before the next wave, which chargers should they use, and which routes are at risk?

The agent does not solve general chat. It performs a specific business task using Cosmos DB domain data.

## Why this is a better 2026-style agent sample

This is more specific than a shopping assistant and more modern than a generic support workflow.

It reflects current business problems:

- Electrified delivery fleets.
- Time-sensitive operations.
- High-volume telemetry.
- Semi-structured domain data.
- Local depot constraints.
- Rapid operational decision-making.
- Agentic workflows that must cite and write data.

The key point:

> The model cannot know whether van `van-042` can complete route `route-77`. It must retrieve the right Cosmos DB records and use them correctly.

## Central Question

The article should answer:

> How can a team prove in CI that a domain agent retrieves the right Cosmos DB data and makes the expected operational recommendation before a pull request is merged?

Short answer:

> Use the Cosmos DB vNext emulator for real data integration, seed deterministic fleet operations fixtures, replace the LLM with a scripted planner, and assert the exact tool calls, retrieved records, recommendation, evidence, and database writes.

## Main Scenario

An operations coordinator asks:

> Review the 2 PM delivery wave for depot `SEA-01`. Identify vans at risk of missing their route because of battery state or charger availability, then recommend charging assignments.

The frontend sends:

```http
POST /agent/review-delivery-wave
Content-Type: application/json

{
  "depotId": "SEA-01",
  "deliveryWaveId": "wave-2026-10-19-1400"
}
```

Expected recommendation:

```json
{
  "depotId": "SEA-01",
  "deliveryWaveId": "wave-2026-10-19-1400",
  "recommendation": "rebalanceCharging",
  "assignments": [
    {
      "vehicleId": "van-042",
      "chargerId": "charger-fast-03",
      "start": "2026-10-19T12:40:00-07:00",
      "durationMinutes": 35,
      "reason": "Battery state is below route requirement with safety buffer"
    }
  ],
  "routeRisks": [
    {
      "routeId": "route-77",
      "vehicleId": "van-042",
      "risk": "batteryShortfall"
    }
  ],
  "evidence": [
    "vehicle-van-042",
    "route-77",
    "telemetry-van-042-latest",
    "charger-fast-03",
    "policy-SEA-01"
  ]
}
```

## Core Architecture

```text
React/Vite depot operations dashboard
        |
        v
POST /agent/review-delivery-wave
        |
        v
FleetCharge Agent orchestrator
        |
        +--> scripted LLM planner in CI
        |
        +--> tool calls
              |
              +--> get_delivery_wave
              +--> get_vehicle_status
              +--> get_latest_telemetry
              +--> get_route_requirements
              +--> find_available_chargers
              +--> write_charging_recommendation
                    |
                    v
              Cosmos DB vNext emulator
```

The frontend makes the app feel real, but the CI article focuses on the backend API and data-backed agent behavior.

## Why Not Use a Live LLM in Required CI?

Explain this early.

A live LLM in every pull request can introduce:

- Cost.
- Rate limits.
- Network dependency.
- Secret management.
- Nondeterministic output.
- Model drift.
- Slower workflows.
- Hard-to-debug failures.

For CI, the goal is not to prove the model is clever. The goal is to prove the code retrieves, filters, evaluates, and writes the right domain data.

Use a live model later in a staging or scheduled evaluation workflow.

## Testing Strategy

### Required pull-request gate

Use:

- Real Cosmos DB vNext emulator.
- Real application code.
- Real Cosmos DB SDK calls.
- Seeded test data.
- Scripted model planner.
- Deterministic assertions.

Do not use:

- Live LLM.
- Production Cosmos DB.
- Random data.
- Soft assertions like "response is not empty."

### Optional future release gate

Use:

- Real model endpoint.
- Small golden prompt set.
- Staging Cosmos DB or isolated emulator data.
- Structured scoring.

Mention this in the conclusion only.

## Cosmos DB Container Design

| Container | Partition key | Documents | Why it exists |
|---|---|---|---|
| `depots` | `/depotId` | Depot policy, charging rules, operating windows | Depot-specific operational constraints |
| `vehicles` | `/depotId` | Vehicle profile, assigned route, maintenance flags, battery summary | Depot-scoped fleet state |
| `routes` | `/depotId` | Delivery wave, route distance, payload, energy requirement | Wave and route planning |
| `chargers` | `/depotId` | Charger status, power rating, reservations | Depot-scoped charging availability |
| `telemetry` | `/vehicleId` | Recent battery and consumption readings | Vehicle time-series-style readings |
| `recommendations` | `/depotId` | Agent decisions, evidence, audit records | Decision trace and idempotency |

For a beginner-friendly post, the implementation can keep `recommendations` in the same database but still separate from operational source data.

## Why Cosmos DB Fits This Domain

This scenario uses document-shaped data with mixed structures and high-volume operational updates:

- Vehicle records have maintenance flags, battery properties, capabilities, and assigned route references.
- Route records contain distance, payload, stops, promised delivery windows, and energy estimates.
- Charger records contain port type, power rating, reservations, and live status.
- Telemetry records arrive frequently and vary by vehicle hardware.
- Recommendation records need an auditable evidence trail.

Cosmos DB is useful here because the application needs low-latency reads and writes, flexible JSON documents, and partitioned operational state.

## Seed Data

### Seed record 1: depot policy

Purpose: proves the agent applies depot-specific constraints.

```json
{
  "id": "policy-SEA-01",
  "depotId": "SEA-01",
  "type": "depotPolicy",
  "timezone": "America/Los_Angeles",
  "minimumBatteryBufferPercent": 12,
  "allowRouteSwap": true,
  "allowPartialCharge": true,
  "chargerReservationWindowMinutes": 45
}
```

### Seed record 2: delivery wave

Purpose: defines the operational task.

```json
{
  "id": "wave-2026-10-19-1400",
  "depotId": "SEA-01",
  "type": "deliveryWave",
  "startTime": "2026-10-19T14:00:00-07:00",
  "routeIds": ["route-77", "route-88"],
  "status": "planning"
}
```

### Seed record 3: route with energy requirement

Purpose: proves the agent must use route energy, not only current battery.

```json
{
  "id": "route-77",
  "depotId": "SEA-01",
  "type": "route",
  "deliveryWaveId": "wave-2026-10-19-1400",
  "assignedVehicleId": "van-042",
  "distanceMiles": 68,
  "payloadPounds": 940,
  "requiredBatteryPercent": 64,
  "weatherAdjustmentPercent": 6,
  "deliveryWindowEnd": "2026-10-19T17:30:00-07:00"
}
```

### Seed record 4: vehicle at risk

Purpose: gives the test a clear expected charging assignment.

```json
{
  "id": "vehicle-van-042",
  "depotId": "SEA-01",
  "type": "vehicle",
  "vehicleId": "van-042",
  "status": "available",
  "maintenanceHold": false,
  "batteryPercent": 58,
  "connectorType": "CCS",
  "maxChargeKw": 150,
  "assignedRouteId": "route-77"
}
```

### Seed record 5: latest telemetry

Purpose: proves the agent uses the latest battery data and not stale vehicle summary alone.

```json
{
  "id": "telemetry-van-042-latest",
  "vehicleId": "van-042",
  "type": "batteryTelemetry",
  "depotId": "SEA-01",
  "observedAt": "2026-10-19T12:20:00-07:00",
  "batteryPercent": 58,
  "estimatedRangeMiles": 61,
  "temperatureF": 48
}
```

### Seed record 6: available fast charger

Purpose: proves the agent chooses a valid charger.

```json
{
  "id": "charger-fast-03",
  "depotId": "SEA-01",
  "type": "charger",
  "chargerId": "charger-fast-03",
  "status": "available",
  "connectorType": "CCS",
  "maxKw": 150,
  "reservations": []
}
```

### Seed record 7: occupied charger trap

Purpose: catches agents that pick the first high-power charger without checking reservations.

```json
{
  "id": "charger-fast-01",
  "depotId": "SEA-01",
  "type": "charger",
  "chargerId": "charger-fast-01",
  "status": "occupied",
  "connectorType": "CCS",
  "maxKw": 150,
  "reservations": [
    {
      "vehicleId": "van-031",
      "start": "2026-10-19T12:15:00-07:00",
      "end": "2026-10-19T13:10:00-07:00"
    }
  ]
}
```

### Seed record 8: maintenance-hold trap

Purpose: catches recommendations that assign a van that should not be dispatched.

```json
{
  "id": "vehicle-van-099",
  "depotId": "SEA-01",
  "type": "vehicle",
  "vehicleId": "van-099",
  "status": "available",
  "maintenanceHold": true,
  "batteryPercent": 92,
  "connectorType": "CCS",
  "maxChargeKw": 150
}
```

### Seed record 9: cross-depot trap

Purpose: catches code that ignores `depotId` and pulls charger or vehicle data from another depot.

```json
{
  "id": "charger-fast-03",
  "depotId": "PDX-02",
  "type": "charger",
  "chargerId": "charger-fast-03",
  "status": "available",
  "connectorType": "CCS",
  "maxKw": 350,
  "reservations": []
}
```

## Agent Tools

| Tool | Input | Output | Test focus |
|---|---|---|---|
| `get_delivery_wave` | `depotId`, `deliveryWaveId` | Delivery wave document | Uses depot partition correctly |
| `get_route_requirements` | `depotId`, `routeIds` | Route documents | Reads required battery and route assignments |
| `get_vehicle_status` | `depotId`, `vehicleIds` | Vehicle documents | Respects maintenance holds and depot boundaries |
| `get_latest_telemetry` | `vehicleIds` | Latest telemetry records | Uses current battery data |
| `find_available_chargers` | `depotId`, `connectorType`, time window | Charger candidates | Excludes occupied chargers and wrong depot |
| `write_charging_recommendation` | `depotId`, recommendation | Recommendation audit record | Persists decision exactly once |

## How to Mock the LLM

Create an interface:

```python
class ModelPlanner:
    def plan(self, prompt: str, context: dict) -> list[ToolCall]:
        ...
```

Production implementation:

```python
class LiveModelPlanner(ModelPlanner):
    ...
```

CI implementation:

```python
class ScriptedModelPlanner(ModelPlanner):
    def plan(self, prompt: str, context: dict) -> list[ToolCall]:
        return [
            ToolCall("get_delivery_wave", {
                "depotId": "SEA-01",
                "deliveryWaveId": "wave-2026-10-19-1400"
            }),
            ToolCall("get_route_requirements", {
                "depotId": "SEA-01",
                "routeIds": ["route-77", "route-88"]
            }),
            ToolCall("get_vehicle_status", {
                "depotId": "SEA-01",
                "vehicleIds": ["van-042"]
            }),
            ToolCall("get_latest_telemetry", {
                "vehicleIds": ["van-042"]
            }),
            ToolCall("find_available_chargers", {
                "depotId": "SEA-01",
                "connectorType": "CCS",
                "startAfter": "2026-10-19T12:30:00-07:00"
            }),
            ToolCall("write_charging_recommendation", {
                "depotId": "SEA-01",
                "deliveryWaveId": "wave-2026-10-19-1400",
                "recommendation": "rebalanceCharging"
            })
        ]
```

Explain:

> The model is mocked, but Cosmos DB is not. This keeps CI deterministic while still proving the data path is real.

## Core Test Cases

### Test 1: agent recommends charging rebalance

Name:

```text
test_agent_recommends_rebalance_for_seeded_delivery_wave
```

Assertions:

- Response recommendation is `rebalanceCharging`.
- `van-042` is identified as at risk.
- `route-77` is identified as `batteryShortfall`.
- `charger-fast-03` is selected.
- `charger-fast-01` is not selected because it is occupied.
- Recommendation evidence includes vehicle, route, telemetry, charger, and depot policy records.
- Recommendation audit record is written.

### Test 2: data does not cross depot partitions

Name:

```text
test_agent_does_not_use_charger_from_other_depot
```

Assertions:

- Agent uses `SEA-01` charger data.
- Agent does not use `PDX-02` charger data with the same charger ID.
- Evidence does not cite `PDX-02`.

### Test 3: maintenance-hold vehicles are excluded

Name:

```text
test_agent_never_assigns_vehicle_on_maintenance_hold
```

Assertions:

- `van-099` is not assigned to a route.
- `van-099` is not assigned to a charger.
- Response includes a maintenance-hold reason if the vehicle was considered.

### Test 4: latest telemetry is used

Name:

```text
test_agent_uses_latest_telemetry_for_battery_decision
```

Assertions:

- Recommendation is based on `telemetry-van-042-latest`.
- Stale telemetry records are ignored.
- Route risk uses the latest battery percentage.

### Test 5: recommendation audit is idempotent

Name:

```text
test_agent_writes_one_recommendation_for_repeated_wave_review
```

Assertions:

- Running the same review twice does not create duplicate recommendation records.
- Existing recommendation is reused or replaced according to documented behavior.

## Best Intentional Failure for the Blog

Break the charger lookup so it ignores `depotId`.

Bad behavior:

```text
find_available_chargers(connectorType="CCS")
```

instead of:

```text
find_available_chargers(depotId="SEA-01", connectorType="CCS")
```

Expected CI failure:

```text
Expected selected charger to belong to depot SEA-01,
but recommendation used charger-fast-03 from depot PDX-02.
```

Why this works well:

- It is easy to understand.
- It is realistic for multi-site operations.
- It proves seeded data matters.
- It catches a bug that a mocked repository might miss.

Alternative intentional failure:

> The agent assigns `van-099` because it has high battery, but ignores `maintenanceHold: true`.

Expected failure:

```text
Expected maintenance-hold vehicle van-099 to be excluded,
but it appeared in charging assignments.
```

## Repository Layout

```text
fleetcharge-agent-cosmos-ci/
  app/
    api.py
    agent.py
    model_planner.py
    scripted_model_planner.py
    live_model_planner.py
    tools.py
    cosmos_repository.py
    fleet_rules.py
    schemas.py
    settings.py
  tests/
    unit/
      test_fleet_rules.py
      test_response_composer.py
    integration/
      test_delivery_wave_tools.py
      test_charger_tools.py
      test_agent_review_delivery_wave.py
    fixtures/
      depots.json
      vehicles.json
      routes.json
      chargers.json
      telemetry.json
    conftest.py
  scripts/
    provision_cosmos.py
    seed_cosmos.py
    cleanup_cosmos.py
  .github/
    workflows/
      ci.yml
  README.md
  pyproject.toml
  .env.example
```

## GitHub Actions Workflow

Use this as the central workflow example:

```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[test]"

      - name: Start Cosmos DB vNext emulator
        run: |
          docker run --detach \
            --name cosmos-emulator \
            --publish 8081:8081 \
            --publish 8080:8080 \
            --publish 1234:1234 \
            mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-latest

      - name: Wait for emulator readiness
        run: |
          for i in {1..60}; do
            if curl --fail http://localhost:8080/ready; then
              exit 0
            fi
            sleep 2
          done
          docker logs cosmos-emulator
          exit 1

      - name: Run unit tests
        run: pytest tests/unit --junitxml=test-results-unit.xml

      - name: Run Cosmos DB-backed agent integration tests
        env:
          COSMOS_ENDPOINT: http://localhost:8081
          COSMOS_DATABASE: fleetcharge_ci_${{ github.run_id }}_${{ github.run_attempt }}
          AGENT_MODEL_MODE: scripted
        run: pytest tests/integration --junitxml=test-results-integration.xml

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: test-results-*.xml

      - name: Upload emulator logs on failure
        if: failure()
        run: docker logs cosmos-emulator > cosmos-emulator.log
```

## Beginner CI Explanation

Include a short section:

### What is CI doing here?

CI means GitHub runs the test workflow automatically when a pull request is opened or updated.

In this article, CI does six things:

1. Downloads the code.
2. Installs dependencies.
3. Starts the Cosmos DB emulator.
4. Seeds known fleet operations data.
5. Runs unit and integration tests.
6. Reports pass or fail before the pull request is merged.

### Why this matters

If a developer changes charger lookup logic and accidentally removes the depot filter, the workflow fails before the bug reaches the main branch.

## Branch Protection Mention

Keep this short.

After the workflow passes locally and in GitHub Actions, configure the repository so the CI job is a required status check before merging.

Do not go deep into GitHub organization policy, rulesets, or deployment environments in this post.

## What the Cosmos DB vNext Emulator Is Best Used For

Use it to prove:

- Point reads use the right partition key.
- Queries return the expected seeded documents.
- Flexible JSON documents serialize and deserialize correctly.
- Writes persist as expected.
- Transactional batch behavior works within a partition.
- Data-access regressions fail fast in CI.

Do not use it to prove:

- Production authentication.
- RU cost.
- Throttling behavior.
- Multi-region replication.
- Production latency.
- Full indexing behavior.
- Model quality.

## Article Section-by-section Outline

### 1. Introduction: agents need data tests, not just prompt tests

Open with the problem:

> An agent can sound correct while using the wrong depot, stale telemetry, or an occupied charger.

Introduce Northwind Freight and FleetCharge Agent.

State what the reader will build.

### 2. The sample scenario

Explain the 2 PM delivery wave and at-risk van.

Show the request:

```json
{
  "depotId": "SEA-01",
  "deliveryWaveId": "wave-2026-10-19-1400"
}
```

Show expected recommendation: `rebalanceCharging`.

### 3. What we are testing in CI

Explain:

- We are not testing prose quality.
- We are testing data grounding and tool behavior.
- The model will be scripted.
- Cosmos DB will be real via emulator.

### 4. Application architecture

Show the flow from frontend to API to agent to tools to Cosmos DB.

Explain that frontend exists for demo realism, but CI tests the API.

### 5. Cosmos DB data model

Explain containers:

- `depots`
- `vehicles`
- `routes`
- `chargers`
- `telemetry`
- `recommendations`

Explain partition keys.

### 6. Seed the data

Show depot policy, delivery wave, route, vehicle, telemetry, chargers, maintenance-hold trap, and cross-depot trap.

Explain what bug each fixture catches.

### 7. Replace the LLM with a scripted planner

Show model interface.

Show scripted tool calls.

Explain why this is better than running a local LLM for required CI.

### 8. Write the integration tests

Show the main test:

- Arrange: seed data.
- Act: call `POST /agent/review-delivery-wave`.
- Assert: recommendation, evidence, charger assignment, route risk, audit write.

Include shorter references to the additional tests.

### 9. Run the tests locally

Show commands:

```bash
docker run --detach --name cosmos-emulator --publish 8081:8081 --publish 8080:8080 --publish 1234:1234 mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-latest
pytest tests/unit
pytest tests/integration
```

Mention readiness endpoint:

```text
http://localhost:8080/ready
```

### 10. Add the GitHub Actions workflow

Show workflow.

Explain each stage in plain language.

### 11. Prove the test catches a real bug

Break the depot filter in charger lookup.

Show the failing test message.

Fix the filter.

Show the workflow passing.

### 12. Make the check required

Briefly explain required status checks.

Keep this beginner-friendly and short.

### 13. What this proves and what it does not

Use a table.

| Proves | Does not prove |
|---|---|
| Agent tools retrieve expected Cosmos DB records | Live model always reasons correctly |
| Depot partition is respected | Production authorization |
| Charger availability logic works | RU efficiency |
| Latest telemetry influences recommendation | Multi-region behavior |
| Recommendation audit write persists | Production performance |
| Bad data-access changes fail CI | Fleet optimization at scale |

### 14. Where live LLM tests fit later

Short final section:

> Once this CI gate is reliable, add a separate staging or scheduled workflow that calls the real model with a small set of golden prompts.

Do not include full CD instructions.

### 15. Conclusion

Close with:

> The required CI check should prove the agent used the right data. A live model evaluation can come later, but a deterministic Cosmos DB-backed integration test is the foundation.

## AEO/EAO Headings and Short Answers

Use these as headings or FAQ blocks.

### Can you test an AI agent without calling an LLM?

Yes. Replace the model with a scripted planner that emits deterministic tool calls, then run the real tools against the Cosmos DB emulator.

### Why use the Cosmos DB emulator in CI?

It lets the workflow test real Cosmos DB SDK calls, queries, partition keys, and writes without using production infrastructure.

### Should I run a local LLM in GitHub Actions?

Usually no for required CI. Local models make workflows slower and less deterministic. Use a scripted model for PR checks and a live model eval later if needed.

### What should an agent integration test assert?

It should assert tool calls, retrieved document IDs, partition boundaries, final structured recommendation, evidence, and persisted audit records.

### Should this article cover deployment?

No. This article should stop at CI. Deployment and live model staging evaluations should be a follow-up post.

## Final Positioning

This blog should be practical, beginner-friendly, and CI-focused:

> Northwind Freight uses a scripted model and the Cosmos DB vNext emulator to prove that FleetCharge Agent reads the right depot, vehicle, route, telemetry, and charger data before code can merge.

The article should go deep on the CI workflow and tests, not on deployment.

