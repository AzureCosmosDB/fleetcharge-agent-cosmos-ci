# Tasks

- [x] T001 (FR-001, FR-002): Add real-SDK seeded CRUD/query/isolation tests.
- [x] T002 (FR-003, FR-005): Add optional local Ollama selection and unit coverage.
- [x] T003 (FR-004): Verify real-model output and independent read/query/update/delete.
- [x] T004 (FR-006): Add the bounded optional runner and reader documentation.
- [x] T005 (all): Run required gate and actual local LLM test; push verified work.

## Verification

Required gate: **128 passed, 0 failed, 0 skipped**, with lint, formatting and
strict mypy passing. The gate was run after removing all seven optional provider
dependencies. Real TCP HTTP smoke returned 200 with the 11-minute recommendation
and independently matching audit. Missing model preflight returned nonzero before
starting an emulator. Optional dependency consistency and the Linux jiter wheel
were verified. Strict mypy also passed with the optional provider installed.
Spec Kit prerequisites passed with the required tasks artifact present.

The installed `qwen2.5:0.5b` failed the original native-tool approach. Native
tool-choice enforcement was unreliable, so the optional transport now requests
schema-constrained JSON proposals and converts them into real Agent Framework
function calls. The same guarded tools, real SDK operations and strict terminal
validation apply. Generated arguments are not repaired and no scripted fallback
or weakened golden assertions were added.

The existing Microsoft `phi3.5:latest` weights were reused through the bounded
`fleetcharge-phi3.5:latest` alias. Two complete live runs passed in **351.47 seconds**
and **408.38 seconds** respectively. Each run performed two actual-model reviews:
the seeded 11-minute recommendation followed by `noAction` after changing the
latest telemetry. Independent SDK assertions verified the persisted audit,
queries, same-identity replacement, changed hashes and deletion.

No new model weights were downloaded and unrelated services were not stopped.
Verification is local evidence for this feature branch; it is not a hosted
Actions result or authorization to merge.
