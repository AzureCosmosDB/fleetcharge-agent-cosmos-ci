# Make Cosmos DB integration tests part of CI

FleetCharge is a small teaching workload for **CI with the Azure Cosmos DB vNext
Emulator**. The point is not fleet software: it is testing real database queries and
writes before merging a pull request.

The sample runs a real Microsoft Agent Framework agent with seven typed tools.
Only the model responses are scripted. Cosmos SDK calls, rules, data and audit writes
are real. No model subscription, Azure login or production secrets are required.

## Try the local CI gate

Prerequisites: **Python 3.12, uv, Git, and Docker running Linux containers**.
Clone this repository and open its root directory. The repository is currently private;
read access is needed to clone it.

```powershell
uv sync --locked --extra test
uv run --locked --extra test python -m scripts.ci
```

The same commands work in a Linux shell. The runner:

1. Checks the lock, lint, formatting and strict types.
2. Starts a digest-pinned emulator with dynamically allocated **loopback-only** ports.
3. Waits up to 120 seconds for `/ready`.
4. Runs unit and real-SDK integration tests with a unique seeded database per test.
5. Saves JUnit results and emulator logs in `.artifacts`.
6. Removes only its own container, including when a test fails.

It never stops other Docker containers or reuses an existing emulator. A test failure
is a nonzero gate result; skipped or mocked database tests are not a substitute.

## Inspect the teaching app

```powershell
uv run --locked python -m scripts.demo
```

This starts a disposable seeded emulator and an HTTP API at `http://127.0.0.1:8000`.
Use `/docs`, or from another PowerShell terminal:

```powershell
$body = @{
    depotId = "SEA-01"
    deliveryWaveId = "wave-2026-10-19-1400"
} | ConvertTo-Json
Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:8000/agent/review-delivery-wave" `
    -ContentType "application/json" -Body $body |
    ConvertTo-Json -Depth 10
```

Expected: `rebalanceCharging`, `van-042`, `charger-fast-03`, **11 minutes**, and a
persisted audit ID/hash. Ctrl+C stops the app and cleans up its disposable database
and emulator. `--port 8001` chooses a different API port.

For a bounded real-HTTP smoke check with independent audit read-back:

```powershell
uv run --locked python -m scripts.demo --smoke
```

The review clock is deliberately fixed at `2026-10-19T12:30:00-07:00` so the fixture
does not expire as the reader's calendar changes.

## What the tests catch

| Scenario | Why a database mock is insufficient |
|---|---|
| Charging rebalance | Reads policy, wave, routes, vehicles, telemetry and chargers; writes an audit |
| Depot isolation | SEA and PDX have the same charger ID in different partitions |
| Maintenance hold | A held vehicle is actually assigned to the reviewed wave |
| Latest telemetry | Summary 95%, old reading 92%, current reading 58% produce different outcomes |
| Repeat reviews | Ten reviews and concurrent equivalents keep one audit; changed data replaces it |

Additional checks cover reservations, freshness boundaries, malformed requests,
source errors, tool tampering, timeouts and uncertain write acknowledgements.
Seeded SDK tests also exercise create, point read, parameterized query, replace,
upsert and delete, including duplicate-create conflicts, not-found outcomes and
identical document IDs in separate depot partitions.

## Optional: test an actual local LLM with Ollama

The required gate stays scripted and never contacts a model. To run a separate
real-model smoke test, have Ollama running locally with **`phi3.5:latest` already
installed**, then create a context-bounded alias from those existing weights:

```powershell
ollama create fleetcharge-phi3.5 -f scripts\Ollama.modelfile
uv sync --locked --extra test --extra ollama
uv run --locked --extra test --extra ollama python -m scripts.test_ollama --model fleetcharge-phi3.5:latest
```

Use the [Modelfile](scripts/Ollama.modelfile) path appropriate to your shell.
The test command does not install Ollama, create model aliases or download weights. It checks local
model availability, owns a separate seeded emulator and tests the real API/model/
framework/tool path. The test verifies the golden 11-minute recommendation, reads
and queries the audit independently, changes telemetry to 90%, reviews again to
verify the same audit is updated to `noAction`, then deletes it and proves it is
absent. CRUD here is test-side SDK work, not destructive tools exposed to the LLM.

Each local live review defaults to a 300-second deadline. `--review-timeout`
can explicitly allow up to 900 seconds on CPU-only machines. Missing models, invalid tool calls,
incorrect output and timeouts fail the test: there is no scripted fallback.
Results, model identity and emulator logs are saved under `.artifacts`. Default
pytest collection excludes these explicitly opt-in tests, not the database tests.
Small models may fail the tool/JSON contract; a failed smoke test is meaningful,
not proof the emulator is broken. This is not a model benchmark.
The installed `qwen2.5:0.5b` failed the original native-tool approach. The bounded
Microsoft Phi-3.5 alias passed two complete live runs in **351.47 seconds** and
**408.38 seconds**, each including both reviews and output CRUD. The feature's
required local gate passed **128 tests**, with lint, formatting, strict types and
the real HTTP smoke also passing. No new weights were downloaded.

Ollama native `tool_choice` is not relied on. The model generates schema-constrained
JSON proposals; an adapter converts validated proposals to real framework function
calls. Only the next valid tool is exposed, request identities are constrained to
the requested depot/wave, and actual tool results are supplied as compact context.
Fleet rules and write validation are unchanged. The final model JSON must still
match the acknowledged persisted response exactly. This is a constrained tool
workflow, not a claim of unconstrained autonomous planning.

For an interactive Ollama demo in PowerShell:

```powershell
$env:AGENT_MODEL_MODE = "ollama"
$env:OLLAMA_MODEL = "fleetcharge-phi3.5:latest"
$env:FLEETCHARGE_TIMEOUT_SECONDS = "300"
uv run --locked --extra test --extra ollama python -m scripts.demo --port 8001
```

Remove those environment variables afterward to return to the default scripted
demo. `OLLAMA_ENDPOINT` can select another loopback HTTP `/v1` endpoint. Cloud
models and non-loopback model endpoints are not supported.

## GitHub Actions: the same gate

The [workflow](.github/workflows/emulator-ci.yml) runs `scripts.ci` for PRs and main
pushes, and uploads diagnostics even on failure. It uses `contents: read`, pinned
GitHub-owned actions, no repository secrets and no Azure credentials.

Pushes to `004-ollama-seeded-crud` also run a separate **Ollama expected output and
CRUD** job; manual workflow dispatch runs it on the selected ref too. This job
installs checksum-verified Ollama 0.40.6 from its official GitHub release, polls
loopback readiness for at most 60 seconds, explicitly pulls Microsoft Phi-3.5
from Ollama's official registry and verifies the known model digest before
creating the context-bounded alias. Python dependencies still come exclusively
from the locked Microsoft feed. No hosted inference service or secret is needed.

It runs the same live test described above: exact seeded golden response, updated
`noAction` response and independently verified output CRUD. Incorrect responses
are not retried until green. A failing live job stays failed; it does not fall
back to scripted responses. The deterministic job runs independently. Each job
uploads separate diagnostics on success or failure; the live job stops only its
own Ollama process. CI provisions its own weights on an ephemeral runner; local
test commands still require an already-installed model.
The CPU-only hosted job explicitly allows 900 seconds per review, a 1900-second
test-process deadline and a 45-minute job deadline. The local default remains
300 seconds per review; neither mode retries an incorrect model answer.

See [verification evidence](docs/verification.md) for actual local/hosted outcomes
and the intentional failing-depot-query demonstration.
The implementation PR is merged: local, hosted PR and merged-main gates passed all
96 tests. The deliberate bad-query run failed as expected before the fix was merged.

## Sources, limitations and the article

- Python packages use only Microsoft's public Azure Artifacts feed, with locked hashes.
  Several advertised wheel-metadata URLs are missing; exact, verified wheel metadata
  is recorded in the manifest. See [dependency research](specs/001-wave-review/research.md).
  The lock targets the supported Windows and Linux environments. The optional
  provider uses `agent-framework-openai` 1.16.0 and OpenAI SDK 3.29.0 from that feed;
  Chat Completions is used for Ollama compatibility, not a hosted OpenAI service.
- **vNext does not enforce authentication.** The public base64 SDK test value is not a
  secret or a security control. Never expose the emulator to an untrusted network.
- This does not prove production authorization, RU cost, performance, live-model
  reasoning, snapshot consistency or collision-free charger bookings.
- [Blog walkthrough](docs/blog-emulator-ci.md): focus the article on the CI loop.
- [Spec Kit walkthrough](docs/speckit-walkthrough.md): development artifacts, not reader prerequisites.
- [API contract](specs/001-wave-review/contracts/api.md) and
  [CI feature](specs/002-pr-ci-gate/spec.md): exact behavior and acceptance criteria.
