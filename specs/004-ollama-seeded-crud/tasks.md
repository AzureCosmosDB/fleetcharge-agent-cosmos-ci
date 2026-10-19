# Tasks

- [x] T001 (FR-001, FR-002): Add real-SDK seeded CRUD/query/isolation tests.
- [x] T002 (FR-003, FR-005): Add optional local Ollama selection and unit coverage.
- [ ] T003 (FR-004): Verify real-model output and independent read/query/update/delete.
- [x] T004 (FR-006): Add the bounded optional runner and reader documentation.
- [ ] T005 (all): Run required gate and actual local LLM test; push verified work.

## Verification

Required gate: **117 passed, 0 failed, 0 skipped**, with lint, formatting and
strict mypy passing. The gate was run after removing all seven optional provider
dependencies. Real TCP HTTP smoke returned 200 with the 11-minute recommendation
and independently matching audit. Missing model preflight returned nonzero before
starting an emulator. Optional dependency consistency and the Linux jiter wheel
were verified.

The actual local `qwen2.5:0.5b` test was executed and **failed**. It called a tool
out of order, then failed to complete the sequence even after progressive tool
exposure and required tool selection. The most recent run completed only
`get_depot_policy`, persisted no recommendation, and returned the explicit 500
envelope. No fallback or weakened golden assertions were added.

T003 and final T005 verification remain blocked on an approved, sufficiently
capable local model. Download authorization was requested but unavailable; no
new model weights were downloaded and the shared machine's other services were
not stopped. The branch may be pushed for review, but this is not a green
live-model claim or authorization to merge.
