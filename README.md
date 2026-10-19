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

## GitHub Actions: the same gate

The [workflow](.github/workflows/emulator-ci.yml) runs `scripts.ci` for PRs and main
pushes, and uploads diagnostics even on failure. It uses `contents: read`, pinned
GitHub-owned actions, no repository secrets and no Azure credentials.

See [verification evidence](docs/verification.md) for actual local/hosted outcomes
and the intentional failing-depot-query demonstration.

## Sources, limitations and the article

- Python packages use only Microsoft's public Azure Artifacts feed, with locked hashes.
  Several advertised wheel-metadata URLs are missing; exact, verified wheel metadata
  is recorded in the manifest. See [dependency research](specs/001-wave-review/research.md).
- **vNext does not enforce authentication.** The public base64 SDK test value is not a
  secret or a security control. Never expose the emulator to an untrusted network.
- This does not prove production authorization, RU cost, performance, live-model
  reasoning, snapshot consistency or collision-free charger bookings.
- [Blog walkthrough](docs/blog-emulator-ci.md): focus the article on the CI loop.
- [Spec Kit walkthrough](docs/speckit-walkthrough.md): development artifacts, not reader prerequisites.
- [API contract](specs/001-wave-review/contracts/api.md) and
  [CI feature](specs/002-pr-ci-gate/spec.md): exact behavior and acceptance criteria.
