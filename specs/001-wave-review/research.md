# Research and Decisions: Wave Review

**Date**: 2026-10-19
**Status**: Locked installation, framework dispatch, real HTTP/audit smoke and local emulator CI verified. Hosted outcomes are recorded separately in [verification](../../docs/verification.md).

## R1. Runtime framework

**Decision**: Use `agent-framework-core` and its standard Python `Agent`, with a scripted client implementing the selected release's chat-client protocol. Register local typed function tools.

**Evidence**: [Agent concepts](https://learn.microsoft.com/en-us/agent-framework/concepts/agents/) documents `Agent` with `SupportsChatGetResponse`; [tools overview](https://learn.microsoft.com/en-us/agent-framework/agents/tools/) documents Python function tools.

**Rationale**: Uses the requested Microsoft Agent Framework without installing every optional provider integration. No hosted service, live provider SDK, or second framework is necessary.

**Rejected**: Replacing the whole agent with a fixed list of direct Python calls; mocking final output; installing a live provider just to make CI run.

**Verification gate**: Inspect the exact pinned client/message/function-call interfaces, implement one scripted tool round trip and terminal result, then verify errors, cancellation, max turns, and no live provider construction. Do not copy old `ChatAgent` or `BaseChatClient` examples blindly across versions.

## R2. Candidate dependency baseline

Public PyPI metadata on the research date reports the following versions. All declare support for Python 3.12. This is availability evidence, not a compatibility resolution.

| Package | Candidate version |
|---|---|
| agent-framework-core | 1.22.0 |
| azure-cosmos | 4.17.1 |
| fastapi | 0.148.0 |
| pydantic | 2.14.1 |
| uvicorn | 0.54.0 |
| pytest | 9.1.1 |
| pytest-asyncio | 1.4.0 |
| httpx | 0.28.1 |
| ruff | 0.17.1 |
| mypy | 2.4.0 |

**Selected baseline**: The table above is the historical PyPI survey, not the installed environment. The sole default index is [Microsoft's public Azure Artifacts feed](https://pkgs.dev.azure.com/azure-sdk/public/_packaging/azure-sdk-for-python/pypi/simple/). There is no public-registry fallback.

| Installed direct package | Version |
|---|---|
| agent-framework-core | 1.21.0 |
| azure-cosmos | 4.17.1 |
| aiohttp | 3.14.5 |
| fastapi | 0.143.0 |
| pydantic | 2.14.1 |
| uvicorn | 0.54.0 |
| pytest / pytest-asyncio | 9.1.1 / 1.4.0 |
| httpx | 0.28.1 |
| ruff / mypy | 0.15.9 / 1.19.1 |
| hatchling (build) | 1.32.4 |

**Decision**: Pin the newest stable compatible versions found with anonymously downloadable
artifacts for both Windows x64 and Linux x64 Python 3.12. A feed listing is not
proof the actual platform wheel can be downloaded. Newer Ruff 0.16.8/0.16.7 and
mypy 2.3.1 were unusable on one or both platforms (HTTP 401); no authentication
restriction was bypassed. Constrain msgspec to 0.21.1 because its newer Windows wheel
was unavailable. `uv pip check`, runtime imports and actual framework dispatch passed.

**Source**: `https://pypi.org/pypi/<package>/json` for each package. No packages were installed or manifests created during planning.

**Initial blocker, resolved**: Downloads from `files.pythonhosted.org` failed TLS
negotiation. Native TLS/independent clients reproduced it. The user requested
Microsoft-hosted sources instead; no certificate checks were disabled.

**Missing feed metadata**: Some advertised `.whl.metadata` URLs return 404.
For those exact package versions, the manifest's `tool.uv.dependency-metadata`
copies Name, Version, Requires-Python, Requires-Dist and Provides-Extra from full
Microsoft-hosted wheels after SHA-256 validation against Microsoft's simple index.
Dependency constraints were preserved, not invented or ignored. Source wheel URLs
and hashes are in `uv.lock`. Ordinary `uv lock` and `uv sync --locked --extra test`
now work without session configuration. Refresh these exact metadata records whenever
upgrading their versions; verify full wheel hashes and dependencies again.

Lock validation confirmed every registry and wheel/sdist URL is Microsoft-hosted.
All 46 applicable Linux distributions were downloaded and verified separately.
Actual Linux execution is a hosted CI gate, not inferred from this Windows download check.

**Framework API evidence**: The installed 1.21.0 uses `FunctionInvocationLayer`
with `BaseChatClient._inner_get_response`; it does not export the older
`use_function_invocation` decorator found in some examples. Tests prove the standard
Agent dispatches a real typed function, then the complete seven-tool path. Iterations
are capped at 20 and a review has a 60-second deadline.

**Observed emulator capability**: The pinned digest in `scripts/emulator.py`
passed real partitioned point reads, parameterized queries, same-ID cross-partition
identity, six-container provisioning, upsert replacement and independent read-back.
The full local gate passed 96 tests. Widening the charger query caused 16 real-test
failures and preserved cleanup; the mutation was restored.

## R3. vNext connectivity and capability

**Decision**: Use the documented image `mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-latest`, API for NoSQL, gateway HTTP, loopback-only ports 8081 (SDK) and 8080 (readiness). Port 1234 is optional for Data Explorer.

**Evidence**: [Linux emulator documentation](https://learn.microsoft.com/en-us/azure/cosmos-db/emulator-linux) describes `/ready`, HTTP default, SDK compatibility notes, feature limitations, and lack of authentication enforcement.

**Rationale**: The Python SDK path does not need the HTTPS/certificate setup described for .NET/Java. Do not disable TLS validation globally.

**Verification gate**: Pull/run a concrete image, record its digest, then prove the planned SDK operations. Replace the mutable tag with the tested digest in the later workflow. A documentation feature table is not proof this application works.

**Constraints**: No production performance/RU, identity, or index-equivalence claims. Composite/range index support is not assumed. Do not use stored procedures, triggers, or UDFs.

## R4. Telemetry ordering

**Decision**: Query the requested vehicle partition, validate ownership, filter out future readings, and sort timestamps/IDs in application code for this tiny sample.

**Rationale**: Deterministic ordering without a composite-index dependency. Freshness is 30 minutes inclusive, measured against the injected clock.

**Rejected**: Arbitrary first record; vehicle summary as silent fallback; cross-partition telemetry scan; assuming all old readings are valid.

## R5. Charging and scheduling

**Decision**: Use the explicit percentage-point math and constant-rate demonstration model in [spec.md](spec.md). Golden duration is 11 minutes, starting at 12:30.

**Rationale**: The outline's sample 35-minute duration cannot be derived from its inputs. Supplying capacity, efficiency, and power makes assertions defensible without adding a fleet optimizer.

**Rejected**: Hard-coded duration; learning fleet math from model prose; taper/production optimization; route swaps.

## R6. Audit semantics and failure boundaries

**Decision**: Upsert one deterministic recommendation identity per depot/wave after validating the complete decision. Repeat reviews recompute and replace it. Concurrent reviews are last-write-wins. Include decision hash and consumed source versions.

**Rationale**: Matches the outline's documented replacement option and proves real writes without overstating exactly-once execution.

**Verification gate**: Upsert/read-back smoke test, ten repeated reviews, changed data, two concurrent equivalent reviews, and failed-write error mapping. No cross-container transaction is claimed. A transport failure can leave write outcome uncertain.

## R7. Blog and feature boundaries

**Decision**: First finish the local real-data test workload. A separate `002-pr-ci-gate` feature will add Actions, diagnostics uploads, least-privilege token configuration, isolated cleanup, and passing/failing/fixed run evidence.

**Rationale**: The agent is the workload; Cosmos DB emulator CI is the lesson. Dashboard and live-model integrations cannot become prerequisites.

## R8. Authentication and reader portability

**Decision**: No Azure login or live-model secret. vNext credentials are SDK configuration only, not enforced authentication. Emulator is isolated on loopback. Readers do not need the maintainer's account.

**Evidence**: [vNext authentication limitations](https://learn.microsoft.com/en-us/azure/cosmos-db/emulator-linux#authentication).

The repository's human identity rule (`jaydestro`) governs maintainer operations, not reader runtime. The future Actions job uses the automatic minimal-permission GitHub token, not a personal account token.
