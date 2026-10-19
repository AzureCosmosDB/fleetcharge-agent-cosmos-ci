# Tasks: Deterministic FleetCharge Wave Review

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [API](contracts/api.md), [tools](contracts/tools.md).
**Status**: T001-T025 complete: implementation, local real-emulator verification and clean-clone rehearsal passed. Companion Actions tasks track hosted PR/main outcomes separately.
**Tests**: Required. Write the corresponding failing test before implementation; do not record an emulator-backed test as passed if it was skipped.

## Build progress - 2026-10-19

Microsoft-only locked installation, imports and real framework tool dispatch pass.
The seven-tool API uses the real SDK, complete fixtures and isolated emulator databases.

The full local gate passed **96 tests**, Ruff/format and strict mypy. Actual HTTP returned
200 and independent audit read-back matched. Temporarily widening the effective charger
scope failed 16 real tests (exit 1); restoring it passed all 96. Cleanup completed on
both red and green runs without touching unrelated containers.

See [verification](../../docs/verification.md) for measured evidence. The user authorized
the [Actions feature](../002-pr-ci-gate/spec.md), merge and post-merge test in this delivery.

## Format and dependency rules

`Tnnn [P] [USn]` identifies a task, optional safe parallelism, and story. Paths are relative to the repository root and are planned unless already present. Each task's prerequisites are explicit below. Tasks touching the same file are sequential even when other prerequisites permit parallel work.

## Phase 1: Setup and compatibility gate

- [x] T001 Add Python 3.12 manifest, test extra, pinned candidate dependencies, Ruff/mypy/pytest settings in `pyproject.toml`; resolve `uv.lock` without ignored dependency constraints. Update `specs\001-wave-review\research.md` with actual compatible versions. Covers FR-011, FR-014.
- [x] T002 Add package scaffolding `app\__init__.py`, `scripts\__init__.py`; write a minimal standard Agent + scripted client + typed function round-trip test in `tests\unit\test_scripted_model_client.py` and prove the resolved framework interfaces work without model credentials. Covers FR-011, FR-015.
- [x] T003 [P] Write strict configuration/fixed-clock and sanitized error-envelope tests in `tests\unit\test_contracts.py`, including invalid mode, non-loopback endpoint and unknown request fields. Covers FR-001, FR-012, FR-015.
- [x] T004 Implement typed configuration/clock in `app\settings.py`, base error/request models in `app\schemas.py`, and emulator-only `.env.example`; satisfy T003 and refuse silent live mode. Covers FR-001, FR-012, FR-015.

**Checkpoint**: Do not build on assumed framework APIs; T002 must pass first.

## Phase 2: Emulator and complete fixtures

- [x] T005 [P] Write bounded readiness, Docker failure, port/name conflict, ownership-safe stop, and cleanup-guard tests in `tests\unit\test_lifecycle.py`. Test double only Docker process execution, never use this to claim Cosmos integration. Covers FR-014, FR-016.
- [x] T006 Implement `scripts\emulator.py` as an ownership-guarded context manager using loopback ports, 120-second readiness and failure diagnostics; `scripts.ci` and `scripts.demo` own start/stop instead of persistent state files. Record tested image digest. Covers FR-014.
- [x] T007 [P] Create all golden documents and maintenance-scenario changes in `tests\fixtures\depots.json`, `routes.json`, `vehicles.json`, `chargers.json`, `telemetry.json`; validate references/partitions and conflicting telemetry explicitly. Covers FR-002, FR-003, FR-004, FR-013.
- [x] T008 Implement `scripts\provision_cosmos.py`, `scripts\seed_cosmos.py`, `scripts\cleanup_cosmos.py` and isolated fixture lifecycle in `tests\conftest.py`; cleanup only owned explicitly named databases. Pytest reports test and teardown failures separately. Covers FR-013, FR-014.
- [x] T009 Write and run `tests\integration\test_cosmos_smoke.py` against the actual emulator: six partitioned containers, duplicate IDs across partitions, scoped parameterized queries, upsert/replace/read-back, cleanup and diagnostics. Update research with observed capabilities; stop/replan rather than substitute fakes if an operation is unsupported. Covers FR-003, FR-010, FR-014.

**Checkpoint**: Framework seam and real SDK/emulator operations both work before agent integration.

## Phase 3: US1 - Real data-backed review (Priority P1)

- [x] T010 [US1] Write deterministic golden, healthy-wave, charge math, half-open interval, duration-limit, deadline, ordering and hash tests in `tests\unit\test_fleet_rules.py`; derive 11 minutes from domain inputs. Covers FR-005, FR-007, FR-008, FR-009, FR-010.
- [x] T011 [US1] Implement `app\fleet_rules.py` and decision/evidence/audit models in `app\schemas.py`; include one canonical hash-normalization helper and fixed reason strings. Covers FR-005, FR-007, FR-008, FR-009, FR-010.
- [x] T012 [US1] Write scoped source-read and write/read-back integration assertions in `tests\integration\test_delivery_wave_tools.py`, including explicit policy read, all referenced routes/vehicles, correct physical IDs and partitions. Covers FR-002, FR-003, FR-009, FR-010.
- [x] T013 [US1] Implement application-scoped async SDK access in `app\cosmos_repository.py`, parameterized reads/queries, strict ownership/reference checks, trace provenance and deterministic audit upsert. Satisfy T012. Covers FR-002, FR-003, FR-004, FR-009, FR-010.
- [x] T014 [US1] Prove single-function dispatch in the unit seam and the complete eight-turn sequence, derived arguments and persistence in emulator integration tests. Covers FR-011.
- [x] T015 [US1] Implement seven typed registered tools in `app\tools.py`, scripted chat client in `app\scripted_model_client.py`, and standard framework orchestration/request trace in `app\agent.py`. Include proposal validation and per-request session isolation. Covers FR-001 through FR-012, FR-015.
- [x] T016 [US1] Write API integration test `test_agent_recommends_rebalance_for_seeded_delivery_wave` and healthy-wave test in `tests\integration\test_agent_review_delivery_wave.py`; assert exact tool sequence/arguments, evidence provenance, structured response, decision hash and independent SDK audit read-back. Covers FR-001, FR-002, FR-008, FR-009, FR-011.
- [x] T017 [US1] Implement `app\api.py`, explicit application lifespan/SDK close and error mapping; make T016 pass with real framework/tools/emulator. Covers FR-001, FR-012.

**Checkpoint**: One real API-to-database review works; no UI or live model is required.

## Phase 4: US2 - Regression-sensitive tests (Priority P1)

- [x] T018 [P] [US2] Add `test_agent_does_not_use_charger_from_other_depot` and reserved/occupied cases in emulator integration; cover connector/power/deadline scheduling boundaries in pure-rule tests. Assert actual source partitions. Covers FR-003, FR-007, FR-013.
- [x] T019 [P] [US2] Add `test_agent_never_assigns_vehicle_on_maintenance_hold` and `test_agent_uses_latest_telemetry_for_battery_decision` in `tests\integration\test_delivery_wave_tools.py`. Include considered van-099, stale summary, tie/freshness/future/ownership errors and missing sources. Covers FR-002, FR-003, FR-004, FR-006, FR-013.
- [x] T020 [US2] Add `test_agent_writes_one_recommendation_for_repeated_wave_review` in `tests\integration\test_agent_review_delivery_wave.py`: ten identical requests, changed-input replacement, two concurrent equivalent reviews, exactly one final identity with validated contents. Covers FR-010.
- [x] T021 [US2] Extend configuration/client tests and `tests\integration\test_failure_boundaries.py` for error codes, wrong/duplicate/unknown turns, proposal tampering, malformed terminal, turn/deadline limits and failed/uncertain writes. Covers FR-012, FR-015.
- [x] T022 [US2] Complete rule/repository/tool/API behavior in `app\fleet_rules.py`, `app\cosmos_repository.py`, `app\tools.py`, `app\agent.py`, `app\api.py` to satisfy T018-T021. Preserve valid prior audit on pre-write failure and report acknowledged/uncertain writes honestly. Covers FR-002 through FR-012, FR-015.

**Checkpoint**: All five named core scenarios and specified failure boundaries pass independently on isolated data.

## Phase 5: US3 - Reader reproduction and handoff (Priority P2)

- [x] T023 [US3] Add `tests\fixtures\expected-golden.json`, exact reader commands and fixed-clock explanation in `README.md`; replace preview commands in `specs\001-wave-review\quickstart.md` with verified instructions, cleanup wrappers, prerequisites and expected response. Covers FR-001, FR-013, FR-016.
- [x] T024 [US3] Run locked installation, Ruff, mypy, unit suite, real emulator integration suite and clean-checkout quickstart rehearsal, including lifecycle failure tests, actual failed-test cleanup and unrelated-resource survival. Record commands/results/digest; clean only owned resources. Fresh-clone gate passed 96/96. Covers FR-014, FR-016 and SC-001 through SC-006.
- [x] T025 [US3] Reconcile analysis, tasks, walkthrough and contracts with actual behavior. Companion CI spec/workflow reuses the runner with least privilege and diagnostics; local green/red/restored-green proof recorded, PR #1 published. Hosted outcomes tracked separately, not assumed. Covers FR-016.

## Dependencies and Execution Order

| Task | Prerequisites |
|---|---|
| T001 | None |
| T002 | T001 |
| T003 | T001 |
| T004 | T003 |
| T005 | T001 |
| T006 | T004, T005 |
| T007 | T004 |
| T008 | T006, T007 |
| T009 | T008 |
| T010 | T004, T007 |
| T011 | T010 |
| T012 | T009 |
| T013 | T011, T012 |
| T014 | T002, T011 |
| T015 | T013, T014 |
| T016 | T015 |
| T017 | T016 |
| T018 | T017 |
| T019 | T017 |
| T020 | T017 |
| T021 | T017 |
| T022 | T018, T019, T020, T021 |
| T023 | T022 |
| T024 | T023 |
| T025 | T024 |

T018/T019 may run concurrently because they edit different files. T020/T021 both touch the API test file and are sequential in practice. The dependency graph gives prerequisites, not permission for simultaneous same-file edits. Each story adds independently runnable assertions to the shared foundation.

## Requirement Traceability

| Requirement | Tasks | Verification focus |
|---|---|---|
| FR-001 | T003, T004, T015, T016, T017, T023 | Request/response schema, real API path |
| FR-002 | T007, T012, T013, T015, T019, T022 | Complete source references and explicit policy |
| FR-003 | T007, T009, T012, T013, T015, T018, T019, T022 | Partition parameters and actual provenance |
| FR-004 | T013, T015, T019, T022 | Latest valid telemetry and ownership |
| FR-005 | T010, T011, T015, T022 | Percentage-point math, >100% result |
| FR-006 | T015, T019, T022 | Considered held/unavailable vehicles |
| FR-007 | T010, T011, T015, T018, T022 | Interval/power/connector/deadline boundaries |
| FR-008 | T010, T011, T015, T016, T022 | All operational recommendation outcomes |
| FR-009 | T010, T011, T012, T013, T015, T016, T022 | Evidence resolves to consumed records |
| FR-010 | T009, T010, T011, T012, T013, T015, T020, T022 | One identity, repeated/changed/concurrent reviews |
| FR-011 | T001, T002, T014, T015, T016, T022 | Framework tool-loop, no bypass/live call |
| FR-012 | T003, T004, T015, T017, T021, T022 | Explicit errors and write uncertainty |
| FR-013 | T007, T008, T018, T019, T023 | Complete deterministic non-vacuous fixtures |
| FR-014 | T001, T005, T006, T008, T009, T024 | Real emulator lifecycle/isolation/cleanup |
| FR-015 | T002, T003, T004, T015, T021, T022 | Mode, sequence, max turns and deadline |
| FR-016 | T005, T023, T024, T025 | Reader rehearsal and honest lesson boundaries |

## MVP and Future Work

MVP is US1 plus the US2 regression-sensitive assertions and reproducible US3 commands. It is not sufficient to return a plausible recommendation without exercising the seeded traps.

Next feature: GitHub Actions and the intentional depot-scope regression demonstration. Dashboard, live-model adapter and full blog drafting remain outside these implementation tasks.
