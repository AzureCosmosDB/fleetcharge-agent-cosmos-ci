# Catch Cosmos DB regressions before merge with the vNext Emulator

Integration tests are more useful when they exercise the database behavior your
application relies on. For Cosmos DB, that includes document identities, partition
keys, queries and writes, not just whether a mocked repository returns a dictionary.

The Azure Cosmos DB vNext Emulator lets us put that feedback loop inside CI without
provisioning a cloud database for every pull request.

## A small agent as the workload, not the lesson

FleetCharge reviews a delivery wave and recommends charging for a low-battery van.
It uses Microsoft Agent Framework, but only its model responses are scripted in tests.
The framework dispatches the tools; those tools read and write through the real
Cosmos DB Python SDK.

That keeps the CI check deterministic and secret-free while testing an application
shape developers are building today. We are not evaluating an LLM or shipping a
fleet-management product.

## Make the data expose bugs

Our seeded scenario contains:

- Two depots with the **same charger ID in different partitions**.
- A vehicle summary at 95%, old telemetry at 92%, and current telemetry at 58%.
- A maintenance-held vehicle that a named scenario actually assigns to a route.
- An occupied charger and explicit charging reservations.

These are deliberate traps. A test that asserts only "the response contains a
charger" can pass even when the application reads the wrong depot or stale data.
Instead, we assert the decision, evidence partitions, tool arguments and independently
read the persisted recommendation.

## One local command

With Python 3.12, uv and Docker with Linux containers:

```text
uv sync --locked --extra test
uv run --locked --extra test python -m scripts.ci
```

The runner starts a pinned emulator image, publishes only loopback ports, waits for
`/ready`, provisions the six containers and seeds an isolated database for each test.
It then runs pytest and cleans up its own container even when tests fail.

The expected charging duration is derived, not hard-coded into the app:
target 82% minus measured 58% in a 100-kWh battery means 24 kWh;
150 kW at a demo efficiency of 0.90 gives 11 minutes after rounding up.

## Prove that CI can go red

In the charger query, retain both the depot predicate and explicit partition key:

```python
return await self.query(
    "chargers",
    "SELECT * FROM c WHERE c.depotId = @depot",
    [{"name": "@depot", "value": depot_id}],
    depot_id,
)
```

For the demonstration, temporarily remove **both effective scope restrictions**.
Removing only the predicate while retaining the partition key does not demonstrate
the same bug.

With the widened query, the real emulator returns the PDX charger too. The ownership
guard rejects that result, and the CI gate fails. We do not weaken the guard to
manufacture an attractive but unsafe recommendation.

Restore the scoped query, rerun the gate, and it passes. The bug is caught before merge.
See [recorded verification](verification.md) for measured results rather than invented
screenshots or promised run outcomes.

The sample's actual PR demonstrated this: its initial Linux run passed 96 tests;
the intentionally widened query produced 16 failures, including the depot-isolation
test. The failure run still uploaded diagnostics and removed its owned emulator.

## Move the same command to GitHub Actions

The [workflow](../.github/workflows/emulator-ci.yml) sets up Python and uv, then invokes
the same Python runner. No separate copy of the emulator lifecycle is needed in YAML.
JUnit results and emulator diagnostics are uploaded with `if: always()`.
Because this sample stores them in `.artifacts`, the upload step also sets
`include-hidden-files: true` and restricts its path to that directory.

The job has `contents: read`. It uses `pull_request`, not `pull_request_target`,
and requires no model key, Azure credential or personal GitHub token. Human
repository access and test runtime authentication are separate concerns.

## What this check does not prove

The vNext emulator does **not enforce authentication**. Keep it isolated; an SDK
test key is not evidence of authorization. Emulator tests also do not establish
production RU cost, performance, every production indexing behavior, live-model
quality or operational booking guarantees.

This environment uses Microsoft's public package feed because external artifact
downloads were unavailable. The checked-in lock and verified metadata keep that
environment-specific setup out of the central lesson.

The useful takeaway is small: seed meaningful data, test the real SDK path locally,
and reuse that same disposable-database gate on every pull request.
