# Develop the sample with Spec Kit

Spec Kit organizes development; Microsoft Agent Framework runs the application.
Readers can run the sample from the [README](../README.md) without regenerating
its specifications.

## Start with requirements

Read [requirements](app-requirements.md), the
[constitution](../.specify/memory/constitution.md) and the active
[real-model feature](../specs/005-real-model-app-tests/spec.md).
Use the generated Copilot commands to specify, clarify, plan, break down tasks,
analyze and implement a change. Resolve behavioral choices before coding.

For example, a vehicle-question feature needs acceptance criteria beyond
"the model responded":

- Retrieve only the requested depot's records through the real SDK.
- Supply retrieved records to the model, not a precomputed expected answer.
- Assert the generated count and IDs against known seeded data.
- Change the database and prove the next generated answer reflects the change.
- Fail on incorrect output, unavailable services or timeouts.

## Keep implementation traceable

Maintain `spec.md`, `plan.md` with a requirement mapping, and `tasks.md` under
`specs/<feature>/`. Update contracts and directly related documentation together.
The active feature maps requirements to runtime changes, direct component tests,
actual-model tests, inference evidence and hosted verification.

Use one framework and guarded tools. Real application tests use actual Ollama.
Direct rules/tool/SDK tests are component checks, not fabricated agent runs.
Do not restore the historical scripted client or add silent fallbacks.

## Verify the change

Run focused tests while implementing, then the complete local gate:

```text
uv run --locked --extra test python -m scripts.ci
```

The [workflow](../.github/workflows/emulator-ci.yml) repeats component and actual
application checks on separate Ubuntu runners. Inspect real responses, transcripts,
saved database results and cleanup, not just a successful upload step.
Keep branches reviewable and merge only after the required verification.

Historical features 001-004 document earlier design decisions and verification.
Feature 005 supersedes their scripted-model portions; it does not change the
charging rules or make the sample production-ready.
