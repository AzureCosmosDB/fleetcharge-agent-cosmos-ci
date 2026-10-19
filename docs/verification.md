# Verification evidence

## Local checks - 2026-10-19

- Windows, Python 3.12.13, uv 0.11.3; dependency compatibility check passed.
- Microsoft-only `uv.lock`: all registry/artifact URLs checked; 46 applicable Linux
  distributions were downloaded and hash-checked, not executed on Windows.
- `uv run --no-sync python -m scripts.ci`: **96 passed, zero failures/skips**.
  Ruff, formatting and strict mypy passed before emulator startup.
- `uv run --no-sync python -m scripts.demo --smoke`: actual HTTP **200**,
  11-minute golden assignment, independent SDK read-back matched the response.
- Image: `mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator@sha256:0bd6dbab98295718c85399ad27c38d45733060086528711594a7d52bafcb3447`.
- Every run removed its uniquely labelled container. Two unrelated pre-existing
  containers were not stopped or changed.
- Fresh local clone of commit `f4c967a`: documented locked install and full gate
  passed **96/96**, Ruff/format/types clean, with a newly created virtual environment.
  Cached verified package artifacts were allowed; this was not an offline dependency test.

## Deliberate regression

Temporarily replaced the charger repository query with an unfiltered
`SELECT * FROM c` and omitted its explicit partition key. The ownership guard
was left intact.

The full gate passed lint/types, then failed actual emulator tests:
**16 failed, 80 passed, exit 1**, including
`test_agent_does_not_use_charger_from_other_depot`. The leaked PDX candidate
raised `SourceDataError`; no false successful recommendation was accepted.
Diagnostics were saved and the owned emulator was removed on failure.

The mutation has been removed. Correct code retains both the parameterized depot
predicate and partition key. The restored full gate passed **96/96** in 21.53 seconds
of pytest execution, with lint/format/types clean and owned-container cleanup complete.
This is local evidence, not a claim of hosted success.

## Hosted verification

[Implementation PR #1](https://github.com/jaydestro/fleetcharge-agent-cosmos-ci/pull/1)
has real hosted Linux evidence:

| Stage | Run | Observed outcome |
|---|---|---|
| Initial green | [39314015515](https://github.com/jaydestro/fleetcharge-agent-cosmos-ci/actions/runs/39314015515) | Python 3.12.15; 96 passed; lint/format/types and cleanup passed |
| Intentional red | [39314553343](https://github.com/jaydestro/fleetcharge-agent-cosmos-ci/actions/runs/39314553343) | 16 failed / 80 passed from widened depot scope; job failed; diagnostics uploaded; cleanup passed |

The initial green exposed a diagnostics issue: upload-artifact excludes hidden paths
by default, so it did not upload `.artifacts`. The workflow now explicitly includes
hidden files **only within that directory**. The red run verified a real nonempty
uploaded artifact (ID 12217043774), not merely a successful upload step.

Correct depot scoping has been restored. Its final green run and main-merge verification
are recorded after completion; the intentional bug must never be merged.
