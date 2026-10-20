# Feature: Optional Ollama and seeded database verification

**Branch**: `004-ollama-seeded-crud` | **Date**: 2026-10-19

The user requested an actual local Ollama test against seeded data, CRUD tests
based on the output, and independent seeded database tests regardless of LLM
availability. This extends the scripted-only first slice, not the required
gate's no-live-model contract.

## Requirements and acceptance scenarios

- **FR-001**: The required emulator gate must test actual SDK create, point read,
  parameterized query, replace, upsert, and delete against isolated seeded data.
  Duplicate creates must conflict; missing/deleted reads must return not found.
- **FR-002**: Tests must prove that identical IDs in different depot partitions
  remain isolated and that writes are visible through a fresh read and query.
- **FR-003**: Explicit optional Ollama mode must use Microsoft Agent Framework
  and the same seven guarded tools, repository, fleet rules and audit validation.
  It must never fall back to scripted success. Required CI stays scripted.
- **FR-004**: The live test must use an already installed local JSON-capable
  model and seeded golden data, verify the 11-minute recommendation and evidence,
  independently read/query the persisted output, update it by reviewing changed
  telemetry, and delete it with an independently verified not-found result.
- **FR-005**: Model absence, bad responses, tool errors and exhausted deadlines
  must fail explicitly. The optional test must not download models or use a
  hosted model service. Diagnostics must identify the model and test outcome.
- **FR-006**: A documented bounded command must own its emulator, preserve
  diagnostics and clean up on success or failure without stopping local Ollama
  or unrelated services.
- **FR-007**: A separate live-model Actions job must provision pinned Ollama and
  Microsoft Phi-3.5 on a disposable runner, poll loopback readiness with a deadline,
  and run the existing exact-output/output-CRUD test without fallback or retries
  of incorrect model answers. Runtime checksums and the model digest must be
  verified. Publish diagnostics on failure and stop only the job-owned process.
  Run both CI jobs on `004-ollama-seeded-crud` without merging or modifying main.
  The deterministic PR gate must remain independent of live-model availability.
- **FR-008**: Record the synthetic test request, both actual API responses,
  expected-output comparisons and completed SDK checks. Publish Markdown in the
  job log, Actions summary and artifacts; incomplete or missing evidence must not
  produce a successful report. Never record credentials or claim a full model
  transcript. Run both jobs for PRs and main pushes after integration.
- **FR-009**: After a fresh full branch run passes, merge the approved working
  code through a PR and verify main. Keep the article draft local and untracked;
  do not publish the locally committed draft or alter that user's local commit.

## Boundaries

The backend exposes the next valid tool and constrains request identities; the
real model generates schema-constrained tool-call proposals and arguments.
The adapter validates their structure before framework dispatch; deterministic
code still computes and validates charging decisions. This is a constrained tool-using agent smoke test,
not a broad model benchmark. CRUD operations are test-side SDK assertions, not
new destructive agent tools or public API endpoints. No production resources,
new framework or dashboard is authorized. The user-authorized Actions provisioning
step may download the pinned Microsoft model from Ollama's official registry and
the pinned runtime from its official GitHub release. This is separate from the
application and local test runner, which never download models automatically.
