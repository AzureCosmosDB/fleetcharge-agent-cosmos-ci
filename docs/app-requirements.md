# FleetCharge requirements

## Teaching goal

Show how to test a data-grounded agent locally and repeat the check in GitHub
Actions using the Cosmos DB vNext emulator, before deploying to Azure.
The code and instructions must work for contributors cloning the sample;
do not embed personal accounts, machine paths or unpublished article notes.

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

Containers `depots`, `routes`, `vehicles`, `chargers`, `recommendations`, `dispatchUpdates` use
`/depotId`; `telemetry` uses `/vehicleId`. Point reads include the partition key.
Queries are parameterized and depot scoped. Validate ownership and source data.

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
- The required workflow runs independent component and real-agent jobs for PRs
  and main. Real app tests require Ollama; neither job requires Azure secrets.
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
