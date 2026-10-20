# Plan

Promote the already-locked provider to an application dependency. Keep Microsoft
Agent Framework, typed guarded tools, real SDK operations and the structured API
unchanged; remove only the scripted execution path and injection parameter.

Convert deterministic agent-replay tests into explicitly direct component tests
of the real tools/SDK. A test-only helper prepares their tool state and never
calls or substitutes for an agent, API response or model. Extract the terminal
response guard for pure validation coverage. Retain API input validation tests.

`scripts.ci` runs component checks followed by the existing actual-model runner.
`--components-only` selects the fast job; the independent Actions application job
continues to provision Ollama/Phi-3.5 using readable releases/tags and call the real app.
Local commands require installed weights. Keep bounded deadlines and owned cleanup.
Use a 2048-token model context. The two late review turns retain only the actual
computed decision or acknowledged write; earlier source reads and all 20 real
inference calls remain covered. CI sets model threads to its available CPUs.

A live-test wrapper observes the real provider method without changing arguments
or responses. Save each input/output and expose immediate inference/CRUD progress
with pytest tee capture. The report checks transcript identity and completeness.
The read-only `/agent/ask-vehicles` endpoint answers a count/list question from
actual retrieved vehicle records. It supplies no expected count, validates the
generated count/IDs, and leaves the charging rules unchanged. Two extra bounded
single-turn questions prove the answer changes after an SDK insertion.

| Requirement | Task | Verification |
|---|---|---|
| FR-001 | T001 | Contract tests, no scripted client/injection, real default demo |
| FR-002 | T002 | Component emulator gate including failure and terminal guards |
| FR-003 | T003 | Runner tests and hosted two-job workflow |
| FR-004 | T004 | Transcript/report unit tests and independently downloaded live evidence |
| FR-005 | T005 | Branch/main hosted runs, PR merge and local article isolation |
| FR-006 | T006 | Real model answers 3 then 4 after a database change |
| FR-007 | T007 | Dotenv precedence tests and real HTTP startup/inference |

Constitution amendment 1.1.0 authorizes a required real-model application gate;
the component gate remains independent. No cloud resources, secrets or new
frameworks are needed.
