# Implementation Plan: Deterministic FleetCharge Wave Review

**Branch**: `001-wave-review` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)
**Input**: A real agent workload supporting a Cosmos DB vNext emulator CI lesson.
**Status**: Implemented and locally verified against the real emulator. User authorized the companion Actions feature in the same implementation PR; see [CI plan](../002-pr-ci-gate/plan.md).

## Summary

Build one FastAPI operation around one Microsoft Agent Framework agent with registered typed tools. Inject a scripted model client that emits actual framework function-call messages, reads tool results, and terminates. Tools call the real Cosmos DB SDK. Pure fleet rules compute decisions; neither model output nor a repository fake substitutes for computation.

This first slice delivers local emulator lifecycle, fixture seeding, domain tests, framework seam tests, and API-to-database integration tests. The next feature reuses those commands in GitHub Actions and demonstrates the depot-filter regression. No UI or live-model adapter is needed to teach that lesson.

## Technical Context

**Language/Version**: Python 3.12.
**Primary Dependencies**: `agent-framework-core`, FastAPI, Pydantic, `azure-cosmos`, Uvicorn; candidate versions and unresolved compatibility checks are in [research.md](research.md).
**Storage**: Cosmos DB vNext emulator, API for NoSQL, gateway HTTP on loopback.
**Testing**: pytest, pytest-asyncio, HTTPX ASGI transport, real Cosmos SDK integration; Ruff and mypy.
**Target Platform**: Windows PowerShell local commands and Linux/Docker for later Actions runners.
**Project Type**: Small backend service plus executable integration-test sample.
**Performance Goals**: No latency/RU benchmark. Startup readiness deadline 120 seconds; review deadline 60 seconds; maximum 20 model turns.
**Constraints**: No live LLM, Azure login, subscription, or production secret in the required path. No exposed emulator ports.
**Scale/Scope**: Two fixture depots, two golden routes, a named maintenance variation, seven data tools, one endpoint.

## Constitution Check

*Checked before research and again against this design. PASS means design alignment, not successful runtime validation.*

| Principle | Design evidence | Result |
|---|---|---|
| I. Spec-driven development | Requirements, contracts, decisions, traceable tasks and measurable scenarios are committed to feature artifacts before implementation | PASS |
| II. One framework/tool path | Scripted client plugs into the standard Agent; all tool calls execute through framework registration | PASS |
| III. Real deterministic integration | SDK and emulator with fixed clock, complete fixtures, isolated databases, exact assertions | PASS |
| IV. Domain correctness | Explicit scheduling, telemetry, error, evidence and audit contracts | PASS |
| V. CI-focused scope | No UI, deployment, live-model adapter or production optimization | PASS |
| Identity and credential constraints | Maintainer operations use jaydestro; reader commands require no maintainer credentials; emulator is loopback-only | PASS |

No constitution amendments or exceptions are required.

## Project Structure

### Documentation (this feature)

```text
specs\001-wave-review\
  spec.md
  plan.md
  research.md
  data-model.md
  quickstart.md
  tasks.md
  analysis.md
  contracts\
    api.md
    tools.md
  checklists\
    requirements.md
```

### Planned source code (not created by this planning step)

```text
app\
  __init__.py
  api.py
  agent.py
  scripted_model_client.py
  tools.py
  cosmos_repository.py
  fleet_rules.py
  schemas.py
  settings.py
tests\
  conftest.py
  unit\
    test_fleet_rules.py
    test_contracts.py
    test_scripted_model_client.py
    test_lifecycle.py
  integration\
    test_cosmos_smoke.py
    test_delivery_wave_tools.py
    test_charger_tools.py
    test_agent_review_delivery_wave.py
  fixtures\
    depots.json
    routes.json
    vehicles.json
    chargers.json
    telemetry.json
    expected-golden.json
scripts\
  __init__.py
  emulator.py
  provision_cosmos.py
  seed_cosmos.py
  cleanup_cosmos.py
pyproject.toml
uv.lock
.env.example
README.md
```

**Structure Decision**: Follow the outline's flat Python application structure, not a multi-service scaffold. One lifecycle helper uses Docker's CLI through Python subprocess calls to avoid separate Windows/Linux lifecycle implementations. It never shells out with interpolated command strings.

## Runtime Design

1. API validates strict input and creates request-scoped review context with fixed/configured clock, trace, and session. SDK client is application-scoped and closed at shutdown.
2. Construct the standard framework agent with the scripted client and seven registered tools. Disable parallel tool invocation for this sample.
3. Scripted turns request policy, wave, referenced routes, assigned vehicles, eligible telemetry, and charger candidates. IDs come from prior tool results, never a hard-coded successful tool list tied only to SEA-01.
4. Tools enforce the reviewed depot/wave and exact expected identity sets against request context. They record returned document identity, partition, `_etag`, and consumed values.
5. `find_available_chargers` returns candidates plus the deterministic fleet-rule decision. Its implementation delegates computation to pure functions; the model does not invent assignments.
6. The scripted client uses that tool result to propose the final write. The write tool compares it with the stored validated decision and provenance before persisting.
7. A terminal model response carries the write result. The API returns the validated persisted payload, not free-form model prose. Any malformed terminal output fails and is logged; audit write completion is tracked separately.
8. Error mapping is explicit. Tools do not swallow SDK errors; orchestration treats tool-error results as fatal rather than letting the model issue a success. No audit is written until source data and decision are valid.

The error contract distinguishes failures before persistence from uncertain/failed responses after an acknowledged write. A client timeout does not imply rollback, and no exactly-once invocation claim is made.

## Data Access and Rules

- Use `azure.cosmos.aio.CosmosClient` and parameterized queries/point reads with explicit partition keys. Validate the exact asynchronous APIs against the pinned version.
- Read policy/wave/routes/vehicles by known identities. Query chargers within the depot partition and with a depot predicate; query telemetry within each vehicle partition.
- For the small telemetry fixture, fetch that vehicle's readings and select valid latest telemetry in Python. This avoids relying on multi-field ordering or composite indexes absent from vNext; do not present it as a production high-volume telemetry query.
- Validate every returned document's ownership even when the SDK request was scoped correctly.
- Use Decimal arithmetic with specified ceiling-to-whole-minute rounding. Normalize aware timestamps to UTC for comparison/hashing; serialize API times with explicit offsets.
- Scheduler checks charger and vehicle power limits, maintenance/status, connector, all reservation overlaps, proposed allocations, 45-minute maximum duration, and wave deadline. Route swapping is excluded.
- Sort every externally visible collection using contract-defined ordering.
- Audit uses deterministic depot/wave ID and upsert. No transactional batch or optimistic-concurrency guarantee is needed. Verify upsert support by smoke test before building the recommendation path.

## Isolation, Lifecycle and Configuration

- `AGENT_MODEL_MODE=scripted` is the only permitted mode; unknown values fail startup.
- `FLEETCHARGE_REVIEW_AT` defaults to the fixed demo timestamp and is logged as demo time.
- `COSMOS_ENDPOINT` defaults to `http://localhost:8081`; this sample rejects non-loopback hosts for both application and destructive lifecycle commands.
- `COSMOS_KEY` supplies the emulator SDK test key, never an Azure credential. `.env.example` documents emulator-only usage and limitations.
- `COSMOS_DATABASE` uses a `fleetcharge_` prefix. Integration tests generate `fleetcharge_test_<unique-id>` databases per test; parallel workers cannot share mutable fixture state.
- Cleanup accepts only an explicit database name in that namespace and loopback endpoint. It must not enumerate/delete arbitrary databases. Test resource ownership is registered before creation to allow cleanup after partial setup.
- Emulator lifecycle binds 8081 and 8080 to `127.0.0.1`; port 1234 is optional for interactive inspection. It records the container ID and refuses to remove containers it does not own.
- Capture readiness diagnostics and Docker logs before container deletion. On teardown failure, report both the original test/startup error and cleanup failure; do not mask either.

## Validation Strategy

1. Resolve and lock dependencies, import selected APIs, and run a tiny scripted framework tool-loop test without model credentials.
2. Run emulator capability smoke tests: create database/partitioned containers; seed/read colliding IDs; parameterized depot queries; upsert replacement; read-back; delete isolated database.
3. Unit-test rules and contracts, including exactly-at-limit boundaries and failure paths.
4. Run API integration tests with HTTPX ASGI transport and application lifespan enabled explicitly by the fixture.
5. Rehearse quickstart from a clean checkout, record exact dependency versions/image digest and actual commands/results.
6. Verify source partition trace and document identities, not only public evidence strings.
7. Later Actions feature: use the same suite to demonstrate passing/failing/fixed CI. When mutating charger scoping, remove both the query depot predicate and partition scope; otherwise a remaining partition key correctly prevents a cross-depot read.

CI workflow creation, run evidence, artifact uploads, and branch protection are intentionally reserved for the next feature.

## Complexity Tracking

No violations. A fixed clock, request-scoped trace, and scripted framework client are necessary seams for deterministic evidence, not general-purpose abstractions. Do not add a second framework, generic agent platform, frontend, or broad configurability.
