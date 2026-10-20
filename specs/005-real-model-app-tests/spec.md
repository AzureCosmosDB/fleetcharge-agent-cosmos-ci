# Real-model application tests

The user requires the application and its end-to-end tests to use the actual
local Ollama model, not a scripted model or a fallback. This supersedes the
scripted-client portions of features 001 and 004 and constitution version 1.0.0.

## Requirements

- FR-001: Remove the scripted client, model injection seam and scripted mode.
  The default app/demo uses Ollama. Reject legacy scripted configuration explicitly.
- FR-002: Keep direct rules/tool/SDK tests, clearly labelled as component tests,
  without presenting them as agent runs. Valid API/agent runs occur only in the
  actual-model suite. Preserve seeded CRUD, partition, telemetry, ownership,
  idempotency and failure coverage without fabricated model responses.
- FR-003: The complete local gate and required Actions app job use real Ollama.
  Keep a separate fast component job. A missing model, transport failure,
  invalid response or timeout fails; no fallback or retry-until-correct.
- FR-004: Capture actual provider inputs, raw model outputs, model/response IDs
  and timing in test artifacts before adapter conversion. Stream start/completion
  and CRUD progress. Reports distinguish seeded inputs from generated responses.
- FR-005: Verify both seeded and changed-data responses and independent persisted
  output CRUD on the feature branch, merge through PR, then verify main.
  Preserve the unpublished local article.
- FR-006: Expose a real-model vehicle question endpoint. Retrieve the requested
  depot's vehicle records through a partition-scoped SDK query, supply records
  rather than an expected count, and require the model to count/list them.
  In CI, ask against the three seeded vehicles, add a fourth vehicle through
  the SDK and ask again. Assert 3 then 4 and the actual IDs in the model output.
  Preserve a readable generated answer and raw inference evidence.
- FR-007: Load an ignored local `.env`, with process variables taking precedence.
  Ship only `.env.example`. Start and exercise the local HTTP app with the same
  pinned emulator and model as CI; preserve the separate article draft.

## Acceptance

No production/test code imports a scripted model. Both real reviews match their
assertions; transcript contains 18 completed provider calls and no golden-answer
prompt injection. Component tests require no inference server. Both CI jobs,
cleanup and nonempty reports pass on branch and main.

Feature 006 adds two dispatch questions, expanding the required transcript to
20 completed calls without changing these vehicle/review assertions.
