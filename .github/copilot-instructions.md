# FleetCharge development guidance

## Purpose and scope

This sample teaches repeatable GitHub Actions testing of a Cosmos DB-backed
agent before deployment. FleetCharge reviews an electric fleet's delivery wave
and saves a data-grounded charging recommendation. Keep the application small
enough to explain alongside the CI workflow.

- Treat the directory containing `pyproject.toml` as the project root.
- Read [requirements](../docs/app-requirements.md), the
  [constitution](../.specify/memory/constitution.md) and the active feature spec.
  [Feature 005](../specs/005-real-model-app-tests/spec.md) supersedes the historical
  scripted-model strategy. The application uses real Ollama inference only.
  [Feature 006](../specs/006-dispatch-feed/spec.md) adds the dispatch feed and
  exact-source briefing requirements.
- Production deployment, cloud identity, RU benchmarking and a custom frontend
  are separate work. Do not imply emulator CI proves production readiness.

## Spec-driven changes

- Use GitHub Spec Kit: specify, clarify, plan, tasks, analyze, then implement.
  Keep requirements, contracts, tasks, code and tests consistent.
- Use Microsoft Agent Framework for Python; Spec Kit is the development workflow,
  not the agent runtime. Do not add another agent framework.
- Preserve the API, orchestration, typed tools, repository and fleet-rule layers.
- Make focused changes and verify them before marking tasks complete.
- Follow the repository's contribution workflow. Do not commit, push, merge or
  change repository visibility unless the contributor requests it.

## Runtime and dependencies

- Use Python 3.12, FastAPI, the async Cosmos SDK and the locked dependencies.
  Resolve packages through the configured public Microsoft feed. Do not bypass
  TLS checks or silently change package sources.
- Ollama must be running with the documented model installed. Local application
  commands must not download weights or silently choose another model.
- Every agent/application test uses actual Ollama through the framework and
  guarded tools. Do not add scripted model responses, model injection seams,
  canned final answers or fallback behavior.
- Retain schema-constrained proposals, validation, tool-loop limits and deadlines.
  Application rules calculate charging decisions; the model invokes tools and
  returns the acknowledged result. Do not claim unrestricted model reasoning.

## Data and test boundaries

- Use the real vNext emulator and SDK for integration tests. Keep ports on
  loopback, wait for readiness, isolate seeded databases and remove only owned
  resources on success and failure.
- Direct component tests can exercise rules, tools and SDK operations without
  inference. Label them accordingly; they are not substitutes for the real
  application test.
- Include partition keys on point reads and scope queries to the depot. Use
  parameters and validate source ownership, latest telemetry, maintenance,
  charger availability, evidence and repeat-review audit behavior.
- Keep a fixed test clock and known fixtures. Assert expected results and
  independent database read-back, not just HTTP 200 or nonempty model text.
- Stream useful progress and preserve real inference inputs/outputs, JUnit
  results and service diagnostics. Never log credentials or real customer data.
- Run the full local gate with `uv run --locked --extra test python -m scripts.ci`.
  Use `--components-only` for focused component work, not as proof the agent works.
- Do not retry incorrect model answers until green or claim unrun checks passed.

## CI authentication

- Verify the contributor's intended repository and authenticated identity before
  remote operations. Never embed a maintainer's account, token or machine path.
- Actions uses `pull_request`, supported action release tags and `contents: read`. Do not execute
  untrusted PR code through `pull_request_target` or add personal tokens.
- Emulator tests require no Azure credentials. Its public SDK test key does not
  prove authentication; the emulator does not enforce authorization.
- A future Azure deployment job can use narrowly scoped OIDC federation and
  `id-token: write`. Do not add deployment permissions to emulator CI.
