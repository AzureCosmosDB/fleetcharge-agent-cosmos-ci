# Verify the application before deployment

Run these commands from the source checkout with Docker and the documented
Ollama model running. See the [README](../README.md) for installation and requests.

## Local checks

```powershell
uv run --locked --extra test python -m scripts.ci --components-only
uv build
uv run --no-sync python -m scripts.test_ollama --review-timeout 900
uv run --locked python -m scripts.demo --smoke
```

The component gate checks formatting, lint, types, rules, tool behavior and
real Cosmos SDK operations. It starts its own emulator and does not invoke a
substitute model. The build produces source and wheel distributions.
The strict type-check allows 600 seconds for a cold dependency cache; lint and
formatting remain bounded at 180 seconds each. A timeout still fails the gate.
The distribution regression builds a synthetic project containing local `.env`
overrides and checks the archives exclude them while retaining `.env.example`.

The actual-model test checks:

- The stored dispatch bay and reference before and after a feed update.
- An independent SDK read of the accepted snapshot and isolation from another
  depot with the same document ID.
- Actual provider context and generated text containing the exact stored bay
  and update reference.
- Vehicle counts of three then four after an SDK insertion.
- The expected charging recommendation, persisted audit, updated telemetry,
  same-identity replacement and deletion.

The HTTP smoke starts a temporary server and exercises all four POST endpoints.
It independently reads the dispatch snapshot and recommendation through the SDK.
Each runner removes only its own emulator and temporary database.

## Inspect the results

```powershell
uv run --no-sync python -m scripts.ci_report --suite emulator
uv run --no-sync python -m scripts.ci_report --suite ollama
```

JUnit results and reports live in `.artifacts`. The live test also saves actual
requests/responses in `ollama-review-output.json`, model metadata in
`ollama-model.json`, and 20 real provider calls in `ollama-inference.json`.
Expected values are test assertions, not model completions.

The runtime default, `.env.example` and local `.env` use Microsoft's documented
public emulator key. Configuration tests verify the template matches defaults
and process endpoint overrides take precedence for managed emulator runs.
Follow [Microsoft's vNext guidance](https://learn.microsoft.com/azure/cosmos-db/emulator-linux)
for protocol, readiness probes and authentication limitations. The older
emulator's TLS/authentication behavior must not be assumed for vNext.

The [Actions workflow](../.github/workflows/emulator-ci.yml) repeats the component
and real-agent checks on separate Ubuntu runners. Inspect both jobs at the tested
commit, their summaries and uploaded diagnostics. A successful artifact upload
alone is not a successful test. Configure repository rules to require both checks
before merge. The workflow reruns when a commit is pushed to an open PR's
branch; it does not start another run merely because the PR was merged.

## What these checks do not prove

The emulator does not enforce production authentication. Local inference and
seeded records do not prove cloud networking, Foundry model compatibility, real
workload latency, RU usage or production authorization. Add cloud smoke tests
and a separately authorized CD deployment workflow after development.
