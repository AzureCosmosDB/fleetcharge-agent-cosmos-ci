# FleetCharge Agent: Spec Kit walkthrough

## 1. Decisions and current state

We will use **GitHub Spec Kit to drive development** and **Microsoft Agent Framework for Python to run the agent**. They solve different problems: Spec Kit produces reviewable requirements, plans, and tasks; Agent Framework handles the application's model/tool interaction.

The starting requirements are preserved in [app-requirements.md](app-requirements.md). They describe FleetCharge Agent, an EV fleet operations sample whose main deliverable is a deterministic Cosmos DB-backed GitHub Actions PR check.

The repository is the `fleetcharge-agent-cosmos-ci` child directory. The parent working folder is not a repository. Open this child directory as the VS Code workspace so its Copilot instructions and Spec Kit commands are discovered.

Already prepared:

- A child Git repository with `main` as the setup baseline; subsequent work uses short-lived branches and reviewed pull requests. The GitHub publication destination is `jaydestro/fleetcharge-agent-cosmos-ci`; verify `origin` before pushing.
- Official Spec Kit scaffolding for Copilot: agents, prompt commands, templates, and PowerShell scripts.
- Project-wide [Copilot instructions](../.github/copilot-instructions.md).
- An initial [constitution](../.specify/memory/constitution.md) based on the requirements.
- A self-contained copy of the original requirements.

Not built yet: feature specs, application code, dependency manifests, emulator setup, tests, workflows, and frontend. This walkthrough prepares that work; it does not claim the app or CI is running.

## 2. What we need installed

| Need | Purpose | When |
|---|---|---|
| VS Code and GitHub Copilot | Invoke the generated Spec Kit prompt commands | Now |
| Git | Child-repo branches and later PRs | Initialized locally |
| Python 3.11+ and `uv` | Run the Specify CLI | Already available on this machine |
| Specify CLI | Generate and maintain Spec Kit artifacts | Already scaffolded with installed CLI 0.4.3 |
| Python 3.12 and a virtual environment | Run the backend and pytest | Implementation |
| Docker with Linux containers | Run Cosmos DB vNext emulator locally | Integration-test implementation |
| Node.js and the selected package manager | Build React/Vite dashboard | Later UI slice |
| GitHub repository and Actions | Execute required PR checks and configure branch protection | CI slice |

No live model endpoint, model API key, paid Cosmos DB account, or Azure deployment is needed for the required CI path.

### Workspace identity and GitHub Actions authentication

**Persistent workspace rule: `jaydestro` is the only human GitHub identity for this project. Never use the emu account.** This is also recorded in the always-on Copilot instructions so future work retains the rule.

The stored `jaydestro` CLI credential was verified with an authenticated user lookup. The shared machine's default account was different and was not changed. Future GitHub operations must select and verify `jaydestro` explicitly, including checking Git transport credentials before a push. Verify the `jaydestro/fleetcharge-agent-cosmos-ci` destination before configuring or pushing to `origin`.

Authentication has three separate boundaries:

| Boundary | Required approach | What this proves |
|---|---|---|
| Local GitHub operations | Select the stored `jaydestro` credential in the current process and verify the authenticated login and destination | The intended human identity is making repo/API operations |
| GitHub Actions | Use the automatic job-scoped `GITHUB_TOKEN`; declare `permissions: contents: read` for the normal checkout/test job, adding permissions only for a specific justified operation | Automation has only the GitHub access it needs; it does not log in interactively as `jaydestro` |
| Cosmos DB vNext emulator | Configure the SDK's test key as needed, but keep the emulator on a trusted local network with published ports bound to `127.0.0.1` | Real data access works; **authentication is not enforced by vNext and is not tested here** |
| Optional future live Azure resources | GitHub OIDC, tightly matched repo/ref or environment federation, and least-privilege Azure RBAC; grant `id-token: write` only to the relevant job | A separate integration can verify actual Azure identity/access; it is not part of this emulator-only gate |

Do not store a personal GitHub token or Azure client secret in the workflow. Do not print credentials. Use the `pull_request` event for untrusted PR tests; do not execute PR code in an elevated `pull_request_target` context. The required gate must work without repository secrets, including for fork PRs. Turn off persisted checkout credentials when later steps do not need Git authentication.

The current [vNext documentation](https://learn.microsoft.com/en-us/azure/cosmos-db/emulator-linux#authentication) explicitly says authentication is not enforced, including when HTTPS or a custom key is configured. An SDK accepting a configured key is therefore not an authentication acceptance test. Production identity remains out of scope, but workflow credential handling and isolation are required now.

Initialization used the installed CLI's bundled assets, without upgrading shared tools:

```powershell
# Already run from the parent working folder; do not rerun over existing files.
specify init fleetcharge-agent-cosmos-ci --ai copilot --script ps --offline --no-git --ignore-agent-tools
git init --initial-branch=main .\fleetcharge-agent-cosmos-ci
```

`--no-git` kept CLI Git side effects separate; Git was then initialized explicitly in the child. The tool's agent availability check was skipped because Copilot is provided by VS Code.

On Windows terminals with an encoding error from Specify's banner, set `$env:PYTHONIOENCODING = "utf-8"` before running it.

**Version note:** this installed integration exposes `/speckit.specify`-style prompt commands. Newer upstream documentation also shows `--integration copilot`, hyphenated skills, and convergence commands. Use the commands generated here; do not mix CLI generations or assume `/speckit-converge` is installed. Review upgrades separately.

## 3. The constitution: our non-negotiables

The initial constitution requires:

1. Specs and measurable acceptance criteria before application implementation.
2. Microsoft Agent Framework with the same tool execution path in scripted and live modes.
3. A real Cosmos emulator and SDK, but no live LLM, in required CI.
4. Depot isolation, current telemetry, maintenance/charger constraints, validated evidence, and auditable idempotent writes.
5. Beginner-friendly CI scope, not production deployment or fleet optimization.

Use `/speckit.constitution` to amend these principles, not to silently replace them with unrelated template principles.

## 4. Break the work into bounded feature specs

Start with one useful backend vertical slice, rather than generating a single giant spec for the entire blog and UI.

| Suggested feature | Scope | Completion evidence |
|---|---|---|
| `001-wave-review` | Request/response contract; six-container data model; complete fixtures; typed tools; framework/scripted-client seam; deterministic rules; audit writes; local emulator integration | The five core scenarios pass through the API, framework, tools, SDK, and emulator |
| `002-pr-ci-gate` | GitHub Actions; least-privilege authentication; secret-free PR tests; loopback-only emulator; readiness; isolated provisioning/seeding; test reports; uploaded diagnostics; cleanup; regression demonstration | A clean run passes without Azure login/secrets; removing the depot filter makes the relevant test fail; restoring it passes |
| `003-depot-dashboard` | React/Vite form, structured recommendations, risks/evidence, loading/empty/error states | UI renders the API contract and its failure states without changing backend rules |

Keep optional live-model evaluation and CD as follow-up work, outside these required features. The CI slice depends on the backend; the frontend is not required to prove the blog's central promise.

## 5. Run Spec Kit for the first feature

Open the child repository in VS Code and invoke these in **Copilot Chat**, not PowerShell. Review each artifact before proceeding.

### Specify: what and why

```text
/speckit.specify Build FleetCharge Agent's deterministic delivery-wave review vertical slice using docs/app-requirements.md. A dispatcher submits depotId and deliveryWaveId to POST /agent/review-delivery-wave. Return a structured, data-grounded charging recommendation, route risks, and evidence; persist an idempotent recommendation audit record. Cover rebalanceCharging for SEA-01, cross-depot isolation, maintenance holds, latest telemetry, and repeat reviews. Required tests must exercise real database integration without a live LLM. Exclude UI, deployment, production identity, and live-model evaluation from this first slice. Use docs/speckit-walkthrough.md section 6 to identify unresolved behavior before planning.
```

Expected output: a feature branch/directory with a `spec.md` containing prioritized user stories, requirements, measurable acceptance scenarios, and explicit out-of-scope items.

### Clarify: close behavior gaps

```text
/speckit.clarify Resolve policy retrieval, complete fixture coverage, telemetry freshness and ownership, battery/weather/buffer math, scheduling feasibility and reservation boundaries, audit idempotency, evidence identity, and API error semantics. Distinguish agreed decisions from assumptions and do not present sample timestamps or durations as proven calculations.
```

The questions in section 6 are spec inputs, not permission to guess silently. Record resolved decisions in the spec; retain a visible blocker for unresolved correctness-critical behavior.

### Plan: how

```text
/speckit.plan Use Python 3.12, FastAPI, typed schemas, Microsoft Agent Framework for Python, the Azure Cosmos DB Python SDK, and pytest. Use a single agent with typed tools and a scripted framework-compatible model client for CI; execute the real framework tool loop and real Cosmos calls. Separate repository access, tools, fleet rules, API, and orchestration. Inject a fixed clock. Plan six containers, complete deterministic fixtures, validated evidence, idempotent audit writes, isolated emulator integration, explicit error contracts, and no live-model fallback. Research and pin compatible SDK versions and verify emulator capabilities. Produce research.md, data-model.md, contracts, and quickstart instructions.
```

Expected planning artifacts:

| Artifact | FleetCharge-specific contents |
|---|---|
| `research.md` | Framework version and scripted client approach; SDK compatibility; emulator image/protocol/readiness; supported queries and write semantics |
| `data-model.md` | Six containers, partition keys, document IDs, timestamps, policy fields, evidence provenance, and audit identity |
| `contracts/` | API request/response/errors; typed tool arguments/results; scripted model turns; audit document shape |
| `quickstart.md` | Reproducible local setup, emulator readiness, seed/test/cleanup commands, and expected golden result |
| `plan.md` | Component boundaries, constitution checks, dependency choices, test strategy, and implementation order |

### Tasks, analysis, implementation

```text
/speckit.tasks
/speckit.analyze
/speckit.implement
```

Tasks should connect requirement IDs to tests and implementation. Resolve material gaps reported by analysis before implementation. Use `/speckit.checklist` when requirement completeness needs another pass.

These commands guide the coding assistant; they do not themselves guarantee a test passed. Run the implemented checks and keep actual results with the feature.

## 6. Requirement gaps to settle in the first spec

The outline is good product context but deliberately illustrative in several places.

| Gap | What the spec must decide |
|---|---|
| Policy is cited but never explicitly retrieved | Add `get_depot_policy` or explicitly return policy through another tool. Test its real read and evidence provenance. |
| Fixture relationships are incomplete | Specify where the wave lives (the `routes` container is a natural fit), add `route-88` and its vehicle/telemetry, and ensure every reference resolves. |
| Latest telemetry test is currently weak | Add older readings and a vehicle summary with different battery values. Define deterministic latest selection, timestamp ties, future/stale/missing readings, and behavior when data is unusable. |
| Telemetry is partitioned by vehicle, not depot | Scope its read by vehicle partition and validate the record's depot against the review. Vehicle IDs alone must not authorize cross-depot data use. |
| Battery math is not defined | Clarify whether weather adjustment adds percentage points or multiplies energy, how the 12% safety buffer applies, and how values over 100% are handled. |
| The sample's 35-minute charge is not derivable | Supply usable battery capacity, charging efficiency/rate assumptions, and scheduling rules before asserting duration or the 12:40 start. Do not reverse-engineer constants to match the example. |
| Charger availability needs a full interval | Define start/end inputs, connector compatibility, effective power, reservation overlap boundaries, turnaround, charger state, deterministic tie-breaking, and completion before 14:00. |
| The maintenance trap is not in the shown wave | Make a fixture actually consider `van-099`, so excluding it is not a vacuous assertion. Route swaps are optional; define whether they belong in this slice. |
| Evidence IDs collide across depots | Retain container/partition/document provenance internally. Decide whether public evidence stays the illustrated string array or becomes a structured contract. Test source partitions, not just strings. |
| Repeat-review behavior is ambiguous | Choose reuse or replacement, deterministic audit identity within the depot partition, and expected behavior on changed data or concurrent retries. "Exactly once" requires more than a sequential count assertion. |
| A static tool list is not a complete agent loop | Script sequential framework model turns that consume tool results and terminate. Define unexpected tool/argument/turn errors and loop limits. Final assignments and audit writes must come from validated data, not a canned model answer. |
| The shown write call lacks the full decision | Define how validated assignments, risks, evidence, and audit identity reach `write_charging_recommendation`; verify its persisted contents match the response. |
| API failures and no-action outcomes are unspecified | Define invalid IDs, missing wave/policy, invalid references, unusable telemetry, no feasible charger, healthy waves, database errors, and whether each returns an error or a structured operational result. |
| Draft workflow is not a verified recipe | Verify emulator image, HTTP/TLS, ports/readiness, configuration, and SDK support; add actual provisioning, seeding, artifact upload, and cleanup. Redirecting logs to a file alone does not upload them. |
| Workflow authentication and emulator isolation | Require explicit token permissions, no personal token or Azure login for required PR tests, safe fork-PR execution, and loopback port bindings. vNext does not enforce authentication, so do not claim it tests credentials or RBAC. |

A recommendation is advisory. Persisting an audit does not reserve a charger or guarantee that simultaneous production operators cannot double-book it.

## 7. Acceptance tests the specs must require

| Scenario | Required evidence |
|---|---|
| Golden SEA-01 review | Exact `rebalanceCharging` response; `van-042` / `route-77` battery risk; valid `charger-fast-03` assignment; retrieved policy and evidence; matching persisted audit |
| Depot boundary | Same charger ID exists in SEA-01 and PDX-02; selected record, tool arguments, and evidence provenance all remain SEA-01 |
| Maintenance hold | `van-099` is genuinely considered but excluded from assignments with a defined reason |
| Latest telemetry | Conflicting old/current readings prove the latest valid reading determines the result |
| Repeated review | Two equivalent requests satisfy the chosen reuse/replacement contract and leave one audit identity; cover retry/concurrency guarantees actually claimed |
| Scheduling and policy | Battery math and time-window boundary tests use a fixed clock and explicit domain inputs |
| Framework seam | Scripted model calls flow through the real framework and tools; unexpected turns fail explicitly; no live network model call is possible |
| CI identity boundary | Required PR tests run with a read-only GitHub token, no Azure login or production secrets, and no externally exposed emulator; emulator integration is not labeled an authentication test |
| Input/data failures | Contract-defined errors or no-action outcomes occur, with no invalid audit or operational write |
| Regression demonstration | Dropping the depot constraint fails on the PDX trap; the normal implementation passes after restoration |

Assertions must inspect tool names/arguments, records and partitions, output structure, evidence, and database contents. A nonempty response is not sufficient. The live model's ability to select the right tools remains unproven by scripted CI.

## 8. Suggested task order and definition of done

For `001-wave-review`:

1. Resolve section 6 and finalize request/response, tool, and document contracts.
2. Add the dependency manifest and pin compatible framework/SDK versions.
3. Implement fixed clock, complete fixtures, emulator provisioning/seeding, and isolated cleanup.
4. Write domain-rule and contract tests, then implement the rules and schemas.
5. Implement repository reads/writes and test tools against the emulator.
6. Wire the scripted client through the framework agent and API; run the five core integration scenarios and edge cases.
7. Update the quickstart and reconcile spec, plan, tasks, and test results.

For `002-pr-ci-gate`, add Actions setup, readiness, tests, artifacts, and cleanup; then reproduce the failing depot-filter regression and restore the fix. Required-status-check configuration happens after publishing to GitHub and observing the actual passing check name.

Done means the documented commands work, the targeted checks pass, the regression is demonstrated, and completed tasks have evidence. At the current scaffolding stage there is no application test suite to run.

## Official references

- [GitHub Spec Kit](https://github.com/github/spec-kit)
- [Spec Kit existing-project workflow](https://github.github.io/spec-kit/guides/existing-projects.html)
- [Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [Python BaseChatClient reference](https://learn.microsoft.com/python/api/agent-framework-core/agent_framework.basechatclient?view=agent-framework-python-latest)
- [GitHub Actions automatic token authentication](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token)
- [Cosmos DB vNext emulator authentication limitations](https://learn.microsoft.com/en-us/azure/cosmos-db/emulator-linux#authentication)

Use the reference matching the pinned implementation version; current online examples can differ from installed APIs.
