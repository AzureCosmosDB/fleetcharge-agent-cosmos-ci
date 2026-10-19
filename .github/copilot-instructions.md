# FleetCharge Agent

## Project context and boundaries

- This directory is the Git repository root. Its parent is a working folder, not a repository; never initialize Git or put application files there.
- Build FleetCharge Agent for Northwind Freight: review an EV depot's delivery wave and return data-grounded charging recommendations.
- Read [app requirements](../docs/app-requirements.md), the [constitution](../.specify/memory/constitution.md), and the active feature spec before changing behavior. Use the [Spec Kit walkthrough](../docs/speckit-walkthrough.md) for setup, requirement gaps, and acceptance criteria.
- Keep this sample CI-focused. Optional local Ollama smoke/output CRUD testing is authorized in `specs/004-ollama-seeded-crud`; production deployment, IaC, production identity, RU benchmarking, multi-region behavior, and full live-model evaluation pipelines remain out of scope.

## Workspace identity and workflow authentication

- The only permitted human GitHub identity for this workspace is **`jaydestro`**. Never use the emu account or another signed-in identity for this project. This is a persistent workspace rule.
- Before GitHub API, repository creation, remote, push, or PR operations, verify the effective identity is `jaydestro` and verify the destination owner/repository. Do not assume the machine-wide active account is correct.
- Prefer process-scoped selection of the stored `jaydestro` credential; do not change shared machine account defaults. Never print tokens, persist them in files/remotes, or infer a Git author email from the login. Check Git transport credentials separately before pushing.
- GitHub Actions runs as automation, not an interactive `jaydestro` login. Use the job-scoped `GITHUB_TOKEN` with explicit least privilege (`contents: read` for the normal test job); do not put a personal token or `gh auth login` in CI.
- Use `pull_request` for untrusted PR tests. Do not use `pull_request_target` to execute untrusted code with elevated credentials. Keep the emulator CI gate runnable without repository secrets.
- The Cosmos DB vNext emulator does not currently enforce authentication. An SDK test key is not proof of credential validation or authorization. Bind published emulator ports to loopback and never expose the emulator to untrusted networks.
- Only a separately scoped future live-Azure workflow needs Azure authentication. Prefer GitHub OIDC with narrowly scoped federation/RBAC and `id-token: write` only on that job; never add long-lived Azure client secrets to the required emulator gate.

## Spec-driven development is required

- Use GitHub Spec Kit, not an ad hoc implementation checklist, for application features.
- Use the installed Copilot commands: `/speckit.specify`, `/speckit.clarify`, `/speckit.plan`, `/speckit.tasks`, `/speckit.analyze`, then `/speckit.implement`. Use `/speckit.constitution` for principle changes and `/speckit.checklist` for requirement quality.
- Keep business outcomes and measurable acceptance criteria in `specs/<feature>/spec.md`; put technical decisions in `plan.md`, with research, data model, contracts, and quickstart as appropriate.
- Resolve material ambiguities before implementation. Do not treat illustrative JSON, pseudocode, or the blog's draft workflow as a complete executable contract.
- Trace requirements to tasks and tests. Keep the spec, plan, contracts, and tasks current when behavior changes; do not mark tasks complete without verification.
- Preserve these instructions when Spec Kit updates agent context. Do not replace the project rules with generated technology summaries.

## Git workflow

- After the initial setup baseline, start new work on a short-lived branch from an up-to-date `main`; use Spec Kit's generated feature branch for specification-driven features.
- Keep commits focused, verify the relevant checks, and merge completed work back to `main` through a reviewed pull request once a GitHub remote is configured.
- Do not commit directly to `main`, push, or merge without an explicit user request. Do not amend commits or rewrite shared history unless requested.

## Agent framework and architecture

- Resolve packages only from accessible Microsoft-hosted resources, respecting the environment's network security policy. Use the newest stable compatible versions available there, not unavailable PyPI/npm pins. The Python default index is Microsoft's public Azure Artifacts feed; do not silently fall back to public registries, disable TLS validation, or bypass network restrictions. Lock and verify the resolved environment before claiming compatibility.
- Use **Microsoft Agent Framework for Python** for the application agent and tool execution. Spec Kit is the development workflow, not the runtime framework.
- Target Python 3.12, FastAPI with typed request/response models, the Azure Cosmos DB Python SDK, and pytest. React/Vite is the later demo UI, not a prerequisite for the backend CI gate.
- Use a single agent with explicit tools. Do not add a multi-agent system, hosted agent service, or a second agent framework without a documented need.
- Keep API handling, framework orchestration, tools, Cosmos repository access, and deterministic fleet rules separate.
- Register typed tools with the framework. In required CI, inject a scripted framework-compatible model client that emits tool calls and consumes their results through the same agent/tool loop used by live mode.
- Do not bypass the framework in CI, mock the agent's final response, or replace the Cosmos repository with an in-memory fake in integration tests.
- Keep battery rules, maintenance exclusion, scheduling checks, evidence validation, and idempotency in application code, not model prose. Validate tool inputs and model-proposed writes before persistence.
- Fail explicitly on unknown tools, invalid arguments, unexpected scripted turns, exhausted scripts, and tool-loop limits. Never fall back silently to a live model.
- Optional Ollama mode uses an explicitly selected, installed local tool-capable model and the same guarded tools. Do not download models automatically, use hosted/cloud inference, or silently substitute scripted output. Required CI must not require the optional model/provider.
- Verify the selected framework version's client/tool APIs in official documentation and pin compatible dependencies when implementation adds a manifest. Do not assume the outline's `ModelPlanner` pseudocode is a framework API.

## Cosmos DB and deterministic behavior

- Use the six containers and partition keys in the requirements: `depots`, `vehicles`, `routes`, `chargers`, and `recommendations` use `/depotId`; `telemetry` uses `/vehicleId`.
- Include the partition key in point reads and scope depot queries explicitly. Validate telemetry ownership against the requested depot. Prefer parameterized queries.
- Identify evidence by container, document ID, and partition key internally; a bare charger ID cannot distinguish the same ID in different depots. Preserve the agreed public response contract.
- Retrieve depot policy explicitly, choose the latest telemetry with deterministic ordering, exclude maintenance holds and incompatible/occupied/reserved chargers, and check assignment completion before wave departure.
- Inject the clock, use timezone-aware timestamps, and seed complete, fixed fixtures. Never base golden tests on wall-clock time, randomness, or query result order.
- Define charging math, missing-data/error behavior, reservation boundaries, and repeat-review semantics in the feature spec before coding them.
- Persist a recommendation audit record, not an operational charger booking. Do not imply this sample prevents concurrent production bookings.

## Verification and scope of claims

- Required PR checks use the real Cosmos DB vNext emulator, real SDK calls, real framework orchestration, scripted model responses, and isolated seeded databases. No live LLM, Azure subscription, or production secret may be required.
- Assert exact tool names/arguments, retrieved records and partitions, structured recommendations, evidence, and persisted audit contents, including repeat-review behavior.
- Cover the five core scenarios: charging rebalance, cross-depot isolation, maintenance holds, latest telemetry, and idempotent audit writes. Add contract and edge-case tests identified by the spec.
- Demonstrate the missing-depot-filter regression with a failing test, restore the correct code, then show it passing. Never leave the intentional bug enabled in the normal CI gate.
- Wait for emulator readiness, capture/upload useful failure diagnostics, isolate test data, and clean up on success and failure. Verify the emulator image, protocol, ports, readiness endpoint, and supported features rather than blindly copying the draft workflow.
- Once the application and test dependencies exist, run `pytest tests\unit` and `pytest tests\integration` from this root, plus the configured type/lint checks and frontend checks for touched surfaces. Report unavailable prerequisites; do not claim unrun checks passed.
- Keep optional live-model evaluation separate. Deterministic CI proves data access, tool integration, and rules, not live-model quality or production authorization/performance.
