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
| Restored green | [39315046802](https://github.com/jaydestro/fleetcharge-agent-cosmos-ci/actions/runs/39315046802) | 96 passed; scoped reads restored; diagnostics uploaded; cleanup passed |
| Merged main | [39315371445](https://github.com/jaydestro/fleetcharge-agent-cosmos-ci/actions/runs/39315371445) | 96 passed at merge commit `b21ad157df5db049174b3f2c447b630efd9128c5`; diagnostics uploaded; cleanup passed |

The initial green exposed a diagnostics issue: upload-artifact excludes hidden paths
by default, so it did not upload `.artifacts`. The workflow now explicitly includes
hidden files **only within that directory**. The red run verified a real nonempty
uploaded artifact (ID 12217043774), not merely a successful upload step.

PR #1 was squash-merged only after its restored gate and all PR checks passed.
The intentionally broken intermediate commit is not in main's history. The main push
run verified the exact merge SHA, not a feature-branch substitute.

The merged-main artifact was nonempty (ID 12218275183, 5105 bytes). Artifacts are retained
for seven days; the durable run links and conclusions above remain the evidence after
download retention expires. Later documentation-only merges may produce additional
[main runs](https://github.com/jaydestro/fleetcharge-agent-cosmos-ci/actions/workflows/emulator-ci.yml?query=branch%3Amain).

All human publication operations used process-scoped `jaydestro` credentials. The
shared machine's default GitHub identity was not switched. Repository visibility
remains private; changing it for external blog readers is a separate maintainer decision.

## Hosted Ollama branch verification - 2026-10-20

The separate real-model job was added and tested only on
`004-ollama-seeded-crud`. No merge or main push was performed.

| Stage | Run | Observed outcome |
|---|---|---|
| Initial workflow validation | [39435000121](https://github.com/jaydestro/fleetcharge-agent-cosmos-ci/actions/runs/39435000121) | Failed before jobs: job-level environment did not permit `runner` context; reproduced with actionlint and fixed by setting the path in a step |
| Initial CPU inference | [39435464549](https://github.com/jaydestro/fleetcharge-agent-cosmos-ci/actions/runs/39435464549) | Deterministic 128 tests passed; provisioning/readiness passed; real-model review reached its 300-second deadline; diagnostics and cleanup passed |
| Verified branch green | [39437337625](https://github.com/jaydestro/fleetcharge-agent-cosmos-ci/actions/runs/39437337625) | At `94956496d2b319d085a044a5f80fd07c5f40dd68`: deterministic 133 tests passed; live test passed; both uploads and cleanup passed |

The CPU-only live job explicitly selects a 900-second per-review limit, with a
1900-second test-process deadline and a 45-minute job deadline. Local defaults
remain 300 seconds; scripted reviews remain capped at 60 seconds. Four runner
tests verify deadline propagation and invalid-limit failure before services are
contacted; a settings test verifies the 900-second boundary.

The green run's downloaded JUnit contains **133 required tests** and **one live
test**, with zero failures/errors/skips. The live test took **1111.889 seconds**
and completed two actual-model reviews: exact golden seeded output, followed by
`noAction` after updating telemetry. It independently verified audit reads,
parameterized queries, changed hashes, same-identity replacement and deletion.
Server logs contain **16 successful `/v1/chat/completions` requests**. There is no
scripted fallback or retry-until-correct loop.

The official Ollama 0.40.6 runtime archive was SHA-256-verified, and the downloaded
Microsoft Phi-3.5 base matched digest
`61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba`.
Inference stayed on the job's loopback endpoint, not a hosted model service.
Python packages came from the locked Microsoft feed. Actions used `contents: read`
and no personal tokens, Azure credentials or repository secrets.

The deterministic job took **1m32s** and the live job **20m36s**. The live job's
readiness, model checks, exact-PID shutdown and diagnostics upload all passed.
Nonempty artifacts were independently downloaded and checked:
`emulator-results-1` (ID `12273126770`, 6037 bytes) and `ollama-results-1`
(ID `12274380282`, 19349 bytes). Artifacts retain for seven days; the run link and
recorded conclusions remain after artifact expiry.
