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

## Boundaries

The backend exposes the next valid tool and constrains request identities; the
real model generates schema-constrained tool-call proposals and arguments.
The adapter validates their structure before framework dispatch; deterministic
code still computes and validates charging decisions. This is a constrained tool-using agent smoke test,
not a broad model benchmark. CRUD operations are test-side SDK assertions, not
new destructive agent tools or public API endpoints. No production resources,
new framework, dashboard or automatic model download is authorized.
