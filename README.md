# Test a Cosmos DB-backed agent in GitHub Actions

[![CI](https://github.com/jaydestro/fleetcharge-agent-cosmos-ci/actions/workflows/emulator-ci.yml/badge.svg?branch=main)](https://github.com/jaydestro/fleetcharge-agent-cosmos-ci/actions/workflows/emulator-ci.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3120/)
[![Microsoft Agent Framework](https://img.shields.io/badge/Microsoft-Agent_Framework-0078D4)](https://github.com/microsoft/agent-framework)
[![Azure Cosmos DB Emulator](https://img.shields.io/badge/Azure-Cosmos_DB_Emulator-0078D4)](https://learn.microsoft.com/azure/cosmos-db/emulator-linux)
[![Ollama](https://img.shields.io/badge/Ollama-Phi--3.5-000000?logo=ollama&logoColor=white)](https://ollama.com/library/phi3.5)
[![Open in Dev Containers](https://img.shields.io/badge/Dev_Container-Open_in_VS_Code-007ACC?logo=docker&logoColor=white)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https%3A%2F%2Fgithub.com%2Fjaydestro%2Ffleetcharge-agent-cosmos-ci)
[![VS Code](https://img.shields.io/badge/VS_Code-007ACC)](https://code.visualstudio.com/)
[![Open in Codespaces](https://img.shields.io/badge/Codespaces-Open_in_Browser-181717?logo=github&logoColor=white)](https://codespaces.new/jaydestro/fleetcharge-agent-cosmos-ci)
[![MIT License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

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

## Open a ready-to-use development environment

If you use GitHub Codespaces, click **Open in Codespaces** above to open a browser
workspace with this repository's existing
[dev container configuration](.devcontainer/devcontainer.json). Then follow the
model setup commands below.

For local development, click **Open in Dev Containers**.
Install [VS Code](https://code.visualstudio.com/) and its
[Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers),
and start Docker with Linux containers on an x86-64 Windows or Linux host. The
button opens VS Code and clones the repository into a Docker volume. For an
existing checkout, use **Dev Containers: Reopen in Container** instead.

The [configuration](.devcontainer/devcontainer.json) installs Python 3.12,
uv 0.13.0, Ollama 0.40.6, GitHub CLI, curl and jq. Setup installs the locked dependencies and
copies `.env.example` only when `.env` is absent. A separate Linux `.venv` volume
does not overwrite a host Windows environment. Initial setup downloads the
development image and tools; model weights are downloaded only by the explicit
commands below.

This trusted local development environment uses **privileged Docker-in-Docker**,
not the host Docker socket. The emulator runs inside that dedicated daemon, so
its loopback endpoints are reachable by the app without exposing the database
to your network. Docker images and model downloads persist in development
volumes; rebuilding the editor container does not remove them.

In a container terminal, start `ollama serve` and leave it running. In another,
run `ollama pull phi3.5:latest` and
`ollama create fleetcharge-phi3.5 -f scripts/Ollama.modelfile`, then continue
with the same demo and CI commands. Setup already ran `uv sync` and prepared `.env`.
VS Code forwards the API's port 8001; use the address in its **Ports** panel if
that host port is occupied. The emulator and model ports are not
automatically forwarded. In Codespaces, use **Open in Browser** for port 8001
in the **Ports** panel.

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

## Configure the emulator connection

The committed `.env.example` and application defaults use the emulator's
standard database port. A fresh copy to `.env` contains:

```dotenv
COSMOS_ENDPOINT=http://127.0.0.1:8081
COSMOS_DATABASE=fleetchargetest-demo
COSMOS_KEY=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==
```

This is Microsoft's [well-known public emulator key](https://learn.microsoft.com/azure/cosmos-db/emulator#authentication),
not an Azure account credential. The
[vNext authentication guidance](https://learn.microsoft.com/azure/cosmos-db/emulator-linux#authentication)
states that vNext does not enforce authentication, even though SDK configuration
requires a key. A passing emulator test does not validate authorization.

There are two ways to use these settings:

- **Managed demo and CI:** `scripts.demo`, `scripts.ci` and `scripts.test_ollama`
  start their own vNext emulator on dynamically assigned loopback ports.
  They override `COSMOS_ENDPOINT` for that run and print the actual endpoint.
  They still load the configured key. Each test fixture uses a unique database;
  the demo uses `COSMOS_DATABASE`. You do not need a separate running emulator.
- **Direct startup:** use the fixed endpoint above with an emulator you start
  explicitly. Seed it, then run Uvicorn directly. This mode keeps data until you
  remove the database or stop a disposable container.

An existing `.env` is not migrated automatically. Update only its
`COSMOS_ENDPOINT` if you want to keep using the standard port, or use the
session override below. Keep any intentional custom port mapping consistent
across the emulator, application and shell.

For direct startup, run this in a dedicated PowerShell terminal:

```powershell
$image = "mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-latest"
docker run --rm --name fleetcharge-local `
    -p 127.0.0.1:8081:8081 -p 127.0.0.1:8080:8080 `
    $image --protocol http
```

In another terminal, wait until `http://127.0.0.1:8080/ready` returns HTTP 200,
then run from the source checkout:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/ready
$env:COSMOS_ENDPOINT = "http://127.0.0.1:8081"
uv run --locked python -m scripts.seed_cosmos
uv run --locked uvicorn app.api:app --host 127.0.0.1 --port 8001
```

If readiness has not returned 200, wait and check again before seeding. Do not
reuse or remove another application's container if a port or name is occupied.
Stop Uvicorn with Ctrl+C; use `uv run --locked python -m scripts.cleanup_cosmos`
to delete only the configured `fleetchargetest-` database while the emulator is
still running. Stop your `docker run` terminal with Ctrl+C when finished.

The container's standard SDK port `8081` and readiness port `8080` are published
unchanged on host loopback. HTTP mode is supported for this Python sample by the
[vNext quickstart](https://learn.microsoft.com/azure/cosmos-db/emulator-linux#running).
It does not disable TLS verification; HTTPS requires the documented certificate
setup. Both the app and container are loopback-only. Settings reject cloud
Cosmos endpoints and non-test database names to prevent accidental production use.

### Optional inspection with Azure Cosmos DB Shell

Shell is not required to run the application or CI. To inspect the directly
started emulator, follow the
[installation guide](https://learn.microsoft.com/azure/cosmos-db/shell/install).
The .NET global-tool option requires the .NET SDK 10.0 or later:

```powershell
dotnet tool install --global CosmosDBShell --prerelease
cosmosdbshell --version
cosmosdbshell
```

If already installed, skip the install command. Inside Cosmos DB Shell, use
these commands (verified with `1.1.280-preview`):

```text
connect http://127.0.0.1:8081/
connect
ls
cd fleetchargetest-demo
cd dispatchUpdates
print current-dispatch SEA-01
print current-dispatch PDX-02
```

Bare `connect` displays the connection information. `print` reads an item by
ID and partition key. A fresh seed returns `BAY-2` for Seattle and `BAY-99` for
Portland. The shell recognizes the local emulator and selects its well-known
key and Gateway mode. Use your actual endpoint if you changed the port mapping.

## Run the same complete gate locally

```powershell
uv run --locked --extra test python -m scripts.ci
```

This checks lint, formatting and types, runs direct rules/tool/SDK component
checks against an isolated emulator, then runs the actual-model application test.
A cold type-check can take several minutes; its timeout is 600 seconds. Lint and
format checks retain their 180-second limits. The app test:

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

With the demo running and a fresh `BAY-2` seed, run the complete before/update/after
check in a second Bash terminal from the repository directory:

```bash
bash scripts/ask-dispatch.sh
```

[`scripts/ask-dispatch.sh`](scripts/ask-dispatch.sh) uses `curl` and `jq` to ask
about the initial bay, publish `BAY-7 / dispatch-007`, and ask the same question
again. It prints both actual responses and exits nonzero on an HTTP error or a
failed assertion. Restart the demo before repeating it; the script leaves the
updated record in place. It requires `jq` and curl with `--fail-with-body` support.

If port 8001 is occupied, start the demo with `--port 8002` and pass that base URL:

```bash
bash scripts/ask-dispatch.sh http://127.0.0.1:8002
```

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

Fork or copy the repository into your own GitHub account. Enable Actions if
GitHub prompts you, then open a pull request or use **Actions > Cosmos emulator
CI > Run workflow**. You do not need Azure credentials, repository secrets or
maintainer-specific variables. GitHub may require approval for a first-time
contributor's fork pull request.

The [workflow](.github/workflows/emulator-ci.yml) runs two independent jobs for
pull-request creation, reopening and commits pushed to an open PR's branch,
plus manual dispatch:

- **Emulator component checks:** locked install, quality gates and real SDK/tool tests.
- **Real agent, grounded answers and CRUD:** Ollama, Microsoft Phi-3.5,
  a separate emulator and the actual application test.

CI uses a disposable Ubuntu runner, loopback services, supported action release tags and
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
The final review turns send only the actual computed decision or acknowledged
write they need, rather than resending every source document. The model uses a
2048-token context; CI sets its thread count to the runner's available CPUs.
These reduce inference work without skipping tests or replacing model responses.
Action major-version tags, `vnext-latest` and `phi3.5:latest` can advance upstream.
The locked Python dependencies and full tests remain the compatibility check;
this sample does not claim its environment is immutable.
Pull requests are checked before merge, regardless of the source branch name.
The `synchronize` activity reruns both jobs when commits are pushed to that
PR's branch. Manual dispatch can test a selected revision. There is no separate
push trigger for main or branches without an open PR.

Generate local reports after their respective tests:

```powershell
uv run --no-sync python -m scripts.ci_report --suite emulator
uv run --no-sync python -m scripts.ci_report --suite ollama
```

Build the source distribution and wheel with `uv build`; output goes to `dist`.
Source distributions retain `.env.example` but exclude local `.env` files and
`.env.*` overrides.

The component CI job also builds both distributions. Run the demo from the source
checkout so its seed fixtures are available.

## Parallel coding-agent database isolation

Run the first component proof for parallel AI coding-agent environments:

```powershell
uv run --locked --extra test python -m scripts.agent_isolation
```

Run from the source checkout with Docker in Linux-container mode. This command
does not need Ollama, Azure credentials, or a separate running emulator. It
explicitly configures its owned endpoints and the public emulator key without
reading or modifying your `.env` or process environment.

The proof starts two invocation-owned emulator containers on four dynamically
allocated loopback ports. Startup is sequential; once both are ready, fixture
seeding and the conflicting writes run concurrently. Both use the **same**
database name, document ID `current-dispatch`, and partition key `SEA-01`.
Agent A writes `BAY-7`; agent B writes `BAY-8`. Independent SDK reads must find
each environment's own update and the unchanged `PDX-02` fixture. The command
then removes A, verifies its container is gone, and reads B again before removing
and verifying B. Any mismatch or lifecycle failure exits nonzero.

Each invocation writes separate agent logs and, only after successful read-back
and cleanup, `result.json` under a unique `.artifacts/agent-isolation/<run-id>`
directory. It records endpoints, container IDs and observed startup/total times.
SDK phases and readiness have deadlines. The existing ownership guard handles
cleanup on ordinary exceptions; forcibly terminating the process or Docker can
still leave resources requiring inspection and exact-ID cleanup.

This is a **component isolation proof**, not an AI coding-agent orchestrator,
model test, security sandbox, database snapshot/clone, or native database
branching feature. It uses the real emulator and SDK, not simulated agents or
model responses. The labels A/B identify two development environments; they do
not claim two coding agents executed. Two emulator containers require sufficient
Docker memory and CPU; do not infer lightweight or instantaneous startup.
No live Azure deployment, migration runner, automatic Git merge, or copying of
disposable database state into a shared environment is implemented here.

For an eventual worktree-based workflow, each coding agent should have its own
checkout, configuration, test artifacts, and owned database environment. Merge
reviewed code, versioned synthetic fixtures and migration/policy scripts through
Git, then rerun checks on the integrated revision. Do not merge emulator data.

### Run task-specific checks in GitHub Actions

The separate [Agent task CI workflow](.github/workflows/agentic-ci.yml) adds
parallel `dispatch` and `fleet-rules` component jobs on pull requests and manual
dispatch. Each matrix job gets its own GitHub-hosted runner and starts one owned
emulator. The existing test fixtures seed versioned data into isolated test
databases. A third job runs the two-container collision and cleanup proof above.

Run the same task checks locally:

```powershell
uv run --locked --extra test python -m scripts.agent_ci --task dispatch
uv run --locked --extra test python -m scripts.agent_ci --task fleet-rules
```

`dispatch` runs the dispatch unit and feed integration tests. `fleet-rules` runs
the fleet-rule unit and delivery-wave tool integration tests. These are bounded,
direct component checks, not coding-agent execution or application inference.
The task runner passes the owned endpoint, readiness URL and public emulator key
to its test subprocess without changing the parent environment or `.env`.
Each test database is seeded and cleaned by the existing fixtures.

Results, JUnit and emulator logs have unique
`.artifacts/agent-ci/<task>/<run-id>` paths. A success JSON report is written only
after the tests pass and owned-container removal is verified. Failures exit
nonzero; the workflow uploads diagnostics even when a test fails.
The matrix uses `fail-fast: false` so one task's failure does not cancel the
other task's diagnostics.

Both jobs in the original [Cosmos emulator CI workflow](.github/workflows/emulator-ci.yml)
remain unchanged. Task-specific checks are additional feedback, not replacements
for the full component gate or the real Ollama application job. Require all
relevant checks before merging the integrated revision. No workflow launches
coding agents, merges pull requests, runs live-account migrations or deploys
the application.

### Check the parallel workflow end to end

```powershell
uv run --locked --extra test python -m scripts.agent_swarm
```

This runs three tasks at once, each in its own Git worktree with its own
emulator. After each agent step it reads the task's own endpoint back and fails
if the stored dispatch update is not that agent's, then runs the task's tests.
It then runs the same two agents against one shared emulator and requires a
lost update, so a pass shows that isolation changed the outcome. Finally it
merges the three branches into an integration worktree, runs the combined tests
against a fresh emulator and verifies every owned container is removed.

The default agent step is a deterministic stand-in that makes one small file
change and one database write, so the check needs no model. To run a real coding
agent instead, pass a command that `{prompt}` and `{agent}` are substituted into;
it runs in each worktree with that task's `COSMOS_*` settings:

```powershell
uv run --locked --extra test python -m scripts.agent_swarm --agent-command 'copilot -p "{prompt}" --allow-all-tools'
```

A real agent must follow the prompt's contract (record its dispatch update and
commit). In GitHub Actions the stand-in version is the `Parallel worktree swarm
check` job, which runs only when you start **Agent task CI** manually
(`gh workflow run agentic-ci.yml --ref <branch>`); pull requests do not run it.

## Limits and development

The emulator does not enforce authentication. Its public SDK test key is not a
production secret or an authorization test. Keep it on loopback.
This is a local-development and CI example, not a production application. The
API has no authentication and binds only to loopback; do not expose it publicly.
The repository does not deploy Azure resources or configure production credentials.
You can apply its CI pattern to your own project and add CD separately when
that project is ready to deploy.

Dependencies use the configured public Microsoft feed and a hashed lock.
See [requirements](docs/app-requirements.md), [Spec Kit guidance](docs/speckit-walkthrough.md),
[real-model requirements](specs/005-real-model-app-tests/spec.md),
[dispatch feed requirements](specs/006-dispatch-feed/spec.md) and
[verification guide](docs/verification.md).

## License

This project is licensed under the [MIT License](LICENSE).
Third-party dependencies and model weights retain their own licenses.
