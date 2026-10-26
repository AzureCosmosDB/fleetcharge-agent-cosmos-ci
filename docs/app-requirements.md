# FleetCharge requirements

## Teaching goal

Show how to test a data-grounded agent locally and repeat the check in GitHub
Actions using the Cosmos DB vNext emulator, before deploying to Azure.
The code and instructions must work for contributors cloning the sample;
do not embed personal accounts, machine paths or unpublished article notes.

Provide a local VS Code Dev Containers launch badge and configuration alongside
the manual setup. Both paths use the same application, scripts and CI checks;
see [development container requirements](../specs/007-devcontainer/spec.md).

## Application

Use Python 3.12, FastAPI, Microsoft Agent Framework, the async Cosmos SDK and
actual local Ollama inference. The default model is the documented bounded
Microsoft Phi-3.5 alias. Scripted model responses and runtime injection/fallback
are prohibited. Domain arithmetic stays in validated application code.

`POST /agent/review-delivery-wave` accepts depot and wave IDs. The framework
invokes typed tools to read policy, wave, routes, vehicles, latest valid telemetry
and chargers, then saves an advisory charging recommendation. It returns success
only after an acknowledged audit and matching terminal response.
See the [original domain contract](../specs/001-wave-review/spec.md) and
[API contract](../specs/001-wave-review/contracts/api.md) for detailed review rules.

`POST /agent/ask-vehicles` accepts depot ID and a question. Application retrieval
reads that depot's vehicle records and passes the records, not an expected count,
to the real model. The generated response contains a sentence, `vehicleCount`
and `vehicleIds`. Reject invented counts or IDs; never repair a model answer
into success.

`POST /feeds/dispatch-updates` persists a typed current pickup-bay snapshot.
`POST /agent/ask-dispatch` point-reads that depot's snapshot and generates an
answer containing the exact stored pickup bay and update reference. Reject stale
or invented values rather than repairing output. The live test changes BAY-2 to
BAY-7 through feed ingestion and verifies the stored record, real provider input
and generated answer. See [dispatch requirements](../specs/006-dispatch-feed/spec.md).

## Cosmos DB

Direct local startup uses the emulator's standard ports on loopback: `8081`
for the database endpoint and `8080` for readiness. The application defaults,
environment template and README must agree. Preserve explicit local settings
and process-environment overrides; managed demo and CI runs still allocate
their own dynamic ports.

Containers `depots`, `routes`, `vehicles`, `chargers`, `recommendations`, `dispatchUpdates` use
`/depotId`; `telemetry` uses `/vehicleId`. Point reads include the partition key.
Queries are parameterized and depot scoped. Validate ownership and source data.

The optional `scripts.agent_isolation` component proof must run two owned emulator
containers with distinct dynamic loopback ports and separate diagnostic paths.
Seed the same database/document/partition identities in both, concurrently write
different dispatch updates, and independently verify that each environment sees
only its expected update while the other depot stays unchanged. Remove one
container and verify the survivor still serves its update, then verify both owned
containers are removed. SDK work and coordination must remain bounded. Do not
mutate `.env` or process-global settings, invoke models, contact Azure, or present
this proof as a coding-agent orchestrator, database clone/merge, or deployment.

The additive `scripts.agent_ci --task dispatch|fleet-rules` command must run each
task's existing component tests in an owned emulator with dynamic loopback ports.
Pass explicit owned connection settings to the test subprocess, use the existing
versioned seed fixtures and per-test database cleanup, and keep the parent
environment and `.env` unchanged. Bound the subprocess, preserve distinct JUnit
and emulator diagnostics per invocation, and write a successful result only
after passing checks and verified container removal. Test and cleanup errors
must exit nonzero rather than produce a successful report.

The separate `agentic-ci.yml` workflow must run both task presets in a parallel
matrix and the two-container isolation proof in its own job. Retain diagnostics
on failure and do not cancel one task merely because another fails. Preserve the
original emulator component and real-model workflow unchanged. These additional
jobs validate submitted code, not AI coding-agent execution, migration or CD.

Fixtures use a fixed review time and known records. The seeded depot has three
vehicles. The grounded-answer test asks for the count, inserts a fourth vehicle
at 50% battery through the SDK, and asks the same question again. Assert three
then four and the actual vehicle IDs.

The charging scenario chooses current telemetry rather than the vehicle summary
or an old reading. Preserve maintenance/availability rules, connector and
reservation checks, evidence and idempotent audit behavior. Audits are not
operational charger bookings.

## CI and verification

- The full local gate runs quality checks, direct component tests and the real
  application test. `--components-only` selects focused rules/tool/SDK checks;
  it is not an agent simulation or proof of model behavior.
- The workflow runs independent component and real-agent jobs when a PR opens,
  reopens or receives a commit, and on manual dispatch. It does not run again
  just because a PR was merged. Real app tests require Ollama; neither job
  requires Azure secrets.
- Actual-model assertions cover grounded counts, the expected charging decision,
  saved output, SDK read/query/update/delete and a changed-data response.
- Preserve raw model inputs/outputs, identity, timings, visible progress, JUnit
  and useful service logs. Expected answers belong only in test assertions.
- Use readable runtime/model/image versions and locked Python dependencies, readiness checks, bounded deadlines,
  isolated test databases, loopback ports and exact-owned-resource cleanup.
- Missing models, incorrect responses and failures must fail explicitly.
  Do not skip app verification or retry incorrect answers until green.

The vNext emulator does not enforce authentication. Test-key configuration is
not production authorization. Cosmos/Foundry cloud smoke tests and Entra/OIDC
deployment setup are separate future work.

## Specification precedence

[Feature 005](../specs/005-real-model-app-tests/spec.md) and constitution 1.1.0
supersede the earlier scripted-model strategy in historical specs. Keep the
structured review contract and domain correctness unchanged. The local article
draft must not be committed or shipped in the repository.
