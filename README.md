# Test a Cosmos DB-backed agent in GitHub Actions

FleetCharge is a small Python sample for testing an agent before deployment.
Microsoft Agent Framework runs the agent, Ollama serves Microsoft Phi-3.5 locally,
and the Azure Cosmos DB vNext emulator stores the application data.
The application has **no scripted model, injected model substitute or fallback**.

The agent reviews delivery vehicles and saves charging recommendations. A simpler
question endpoint demonstrates grounding: ask how many vehicles are in a depot,
and the model counts actual records retrieved from Cosmos DB.
The dispatch feed adds changing operational data: publish a pickup-bay update,
then ask the agent where drivers should collect their paperwork. Its answer must
cite the exact bay and update reference stored in Cosmos DB.

## Prerequisites

- Python 3.12, uv and Git.
- Docker running Linux containers.
- Ollama running locally with Microsoft Phi-3.5 installed.
- Windows or Linux, enough memory for the emulator and the roughly 2.2-GB model.
  CPU inference can take several minutes per review.

Clone this repository and open its root directory. Explicitly install the model
and create the bounded alias; these commands download weights only when requested:

```powershell
ollama pull phi3.5:latest
ollama create fleetcharge-phi3.5 -f scripts\Ollama.modelfile
uv sync --locked --extra test
Copy-Item .env.example .env
```

On Linux use `scripts/Ollama.modelfile` and `cp .env.example .env`.
The app loads `.env`; process environment variables take precedence.
The local file is ignored by Git. Start Ollama through its desktop app or
`ollama serve` if it is not already running. Application/test commands never
download weights automatically or silently select another model.

## Run the same complete gate locally

```powershell
uv run --locked --extra test python -m scripts.ci
```

This checks lint, formatting and types, runs direct rules/tool/SDK component
checks against an isolated emulator, then runs the actual-model application test.
The app test:

1. Asks for the seeded dispatch bay, publishes `dispatch-007`/`BAY-7` through the
   feed API, independently reads the stored update, then asks the same question.
   The model must change from `BAY-2` to `BAY-7` and cite `dispatch-007`.
2. Asks the real model to count three seeded vehicles from actual Cosmos records.
3. Inserts a fourth vehicle through the SDK and verifies a new answer says four.
4. Reviews the seeded delivery wave and checks the expected charging recommendation.
5. Independently reads and queries the saved audit, updates telemetry, reviews
   again, and verifies replacement and deletion through the SDK.

The expected counts/results are test assertions, not answers supplied to the
model. Actual provider messages, raw completions, model identity and timing are
recorded in `.artifacts/ollama-inference.json`. Progress appears at inference
start/completion and every 30 seconds while waiting.

For focused component work without running inference:

```powershell
uv run --locked --extra test python -m scripts.ci --components-only
```

These are direct component tests, not simulated agent runs. To run just the
actual application test:

```powershell
uv run --locked --extra test python -m scripts.test_ollama
```

Local reviews default to 300 seconds. Pass `--review-timeout 900` explicitly on
CPU-only machines when needed. The two count questions each have a maximum
180-second deadline, as do the two dispatch questions.
Timeouts, unavailable models and wrong answers fail;
incorrect output is not retried until green.

## Ask the agent locally

```powershell
uv run --locked python -m scripts.demo --port 8001
```

Open `http://127.0.0.1:8001/docs`. The demo owns a seeded emulator and cleans it
up when stopped with Ctrl+C. It uses the actual model by default.
Keep the terminal open while sending requests. Restarting the demo reseeds the
fixtures, including the original `BAY-2` dispatch snapshot; it is disposable.

### Publish and ask about a dispatch update

The following examples run in a second PowerShell terminal. First, ask about
the seeded bay:

```powershell
$base = "http://127.0.0.1:8001"
$question = @{
    depotId = "SEA-01"
    question = "Where should drivers collect dispatch paperwork? Include the update reference."
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/agent/ask-dispatch" `
    -ContentType "application/json" -Body $question
```

The answer contains `pickupBay: BAY-2` and `updateId: dispatch-001`, and the
generated sentence includes both values. Now simulate an incoming dispatch feed:

```powershell
$update = @{
    depotId = "SEA-01"
    updateId = "dispatch-007"
    pickupBay = "BAY-7"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/feeds/dispatch-updates" `
    -ContentType "application/json" -Body $update
Invoke-RestMethod -Method Post -Uri "$base/agent/ask-dispatch" `
    -ContentType "application/json" -Body $question
```

The feed acknowledgement contains the stored snapshot. The second question must
return these fields, with a model-generated sentence such as:

```json
{
  "answer": "Collect your dispatch paperwork at BAY-7, per update dispatch-007.",
  "pickupBay": "BAY-7",
  "updateId": "dispatch-007"
}
```

Wording can vary; the bay and reference cannot. The application reads
`current-dispatch` from the requested depot's partition and supplies the stored
document to the model. It rejects wrong fields or a sentence missing either
literal value instead of inserting the expected text into the model's answer.

The feed is a current-snapshot API: the last acknowledged write replaces the
previous snapshot for that depot. It does not reorder events or keep a history.
`PDX-02` has its own `BAY-99` snapshot with the same document ID in a different
partition. The feed does not alter charging recommendations or control equipment.

### Count vehicles

Try `POST /agent/ask-vehicles`:

```json
{
  "depotId": "SEA-01",
  "question": "How many vehicles are stored for this depot? List their vehicle IDs."
}
```

The generated answer must report `vehicleCount: 3` and the IDs `van-042`,
`van-088`, `van-099`. The server verifies the count and IDs against retrieved
records; it does not replace a wrong model answer with the expected answer.

### Review a delivery wave

Try `POST /agent/review-delivery-wave`:

```json
{
  "depotId": "SEA-01",
  "deliveryWaveId": "wave-2026-10-19-1400"
}
```

Expected: an 11-minute charging assignment and a persisted audit ID/hash.
Charging arithmetic remains in application rules; the real model generates
validated tool arguments and returns the acknowledged structured result.
The question endpoint separately demonstrates a model-generated count and sentence.
This is not a benchmark of unrestricted reasoning.

`uv run --locked python -m scripts.demo --smoke` starts a temporary HTTP server,
publishes a dispatch update, asks about it, counts vehicles and reviews a wave.
It verifies the stored dispatch snapshot and audit through independent SDK reads,
then stops the server and its owned emulator. `.env.example` lists optional process
environment settings. The fixed sample clock keeps dated seed data repeatable;
it is not a Cosmos DB or Ollama requirement.
Legacy `AGENT_MODEL_MODE=scripted` is rejected explicitly.

### API reference and failures

| Method and path | Request | Success |
|---|---|---|
| `POST /feeds/dispatch-updates` | `depotId`, `updateId`, `pickupBay` | Stored current dispatch snapshot |
| `POST /agent/ask-dispatch` | `depotId`, `question` | Generated `answer`, `pickupBay`, `updateId` |
| `POST /agent/ask-vehicles` | `depotId`, `question` | Generated `answer`, `vehicleCount`, `vehicleIds` |
| `POST /agent/review-delivery-wave` | `depotId`, `deliveryWaveId` | Recommendation, assignments and persisted audit |

All routes return HTTP 200 on success. Use `/docs` for complete schemas and
request forms, or `/openapi.json` for the machine-readable contract.
Inputs reject unknown fields. Bays use the form `BAY-` followed by 1-3 digits.
Questions must contain 1-500 characters, and depot/update IDs permit letters,
digits, underscores and hyphens.

Failures use `{"error":{"code":"...","message":"...","retryable":false}}`:
422 means invalid input, 409 means required source data is missing/invalid,
503 means the model or data service is unavailable, and 504 means a deadline
expired. A model answer that fails grounding validation returns 500, not a
corrected answer. A failed/timed-out write may have reached the database; verify
the stored state before resubmitting. A missing delivery wave returns 404.

If the model is unavailable, check `ollama list`, the alias name and
`OLLAMA_ENDPOINT` in `.env`. If Docker startup fails, confirm Linux containers
are running and inspect `.artifacts/emulator.log` or
`.artifacts/ollama-emulator.log`. If CPU inference times out, use
`--review-timeout 900` for the test runner or set
`FLEETCHARGE_TIMEOUT_SECONDS=900` before starting the demo. Questions still have
a 180-second maximum. Do not disable validation to accept an incorrect answer.

## GitHub Actions

The [workflow](.github/workflows/emulator-ci.yml) runs two independent jobs for
pull requests, main pushes and manual dispatch:

- **Emulator component checks:** locked install, quality gates and real SDK/tool tests.
- **Real agent, grounded answers and CRUD:** checksum-verified Ollama runtime,
  digest-verified Phi-3.5, a separate emulator and the actual application test.

CI uses a disposable Ubuntu runner, loopback services, pinned actions and
`contents: read`. It needs no Azure subscription, inference API key or repository
secret. Both jobs fail on incorrect results; configure repository rules to make
their checks mandatory before merge.

The app job allows 900 seconds per charging review, 180 seconds per question,
2620 seconds for the test process and 55 minutes for the job. Each run saves
readable Markdown in the Actions summary/log plus JUnit, inference transcripts
and service diagnostics as artifacts. Artifact downloads use GitHub's ZIP wrapper.
Cleanup stops only the recorded job-owned process and labelled emulator container.
The live transcript contains 20 completed real inference calls: four grounded
questions and two eight-turn charging reviews. Direct component tests cover
feed validation, replacement, partition isolation and missing source without
pretending to run a model.

Generate local reports after their respective tests:

```powershell
uv run --no-sync python -m scripts.ci_report --suite emulator
uv run --no-sync python -m scripts.ci_report --suite ollama
```

Build the source distribution and wheel with `uv build`; output goes to `dist`.
The component CI job also builds both distributions. Run the demo from the source
checkout so its seed fixtures are available.

## Limits and development

The emulator does not enforce authentication. Its public SDK test key is not a
production secret or an authorization test. Keep it on loopback.
The local API has no authentication and binds only to loopback. Do not expose it
as a production feed. Production requires authenticated publishers and callers,
an event-ordering policy, Cosmos/Foundry identities, Entra authorization and
cloud performance/RU validation.

During development, CI verifies changes before merge. After development is
complete, a separate CD workflow can authenticate to Azure through GitHub OIDC,
deploy the app and run cloud smoke tests. This repository does not deploy Azure
resources or configure production credentials.

Dependencies use the configured public Microsoft feed and a hashed lock.
See [requirements](docs/app-requirements.md), [Spec Kit guidance](docs/speckit-walkthrough.md),
[real-model requirements](specs/005-real-model-app-tests/spec.md),
[dispatch feed requirements](specs/006-dispatch-feed/spec.md) and
[verification evidence](docs/verification.md). Historical specs record the earlier
scripted approach; feature 005 and constitution 1.1.0 supersede it.
