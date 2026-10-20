# Implementation plan

Add typed dispatch input/document/answer contracts, a small dispatch service and
two FastAPI routes. Reuse the repository point read, model client, source parsing
and existing error envelope. Provision and seed one additional depot partitioned
container. Use a fixed current-snapshot ID; do not add event ordering or a broker.
Keep charging arithmetic and the vehicle endpoint unchanged.

Observe the two extra real provider calls in the existing live test. Reports
must include both briefings and all 20 complete inference records. Direct
component tests cover ingestion/storage and pure output guards, never substitute
model responses for application runs.

| Requirement | Task | Verification |
|---|---|---|
| FR-001 | T001 | Feed API, real SDK read and replacement, depot isolation |
| FR-002 | T002 | Real generated briefing before and after update |
| FR-003 | T003 | Invalid/missing-source and exact output validation tests |
| FR-004 | T004 | Live transcript, assertions, report completeness |
| FR-005 | T005 | README, package build, HTTP smoke, branch/main CI |

Local emulator routes are unauthenticated and loopback-only. The feed is not a
production integration or deployment pipeline; production identity, authorization,
event ordering and CD require separate work.
