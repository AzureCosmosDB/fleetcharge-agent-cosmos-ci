# FleetCharge Agent Constitution

## Core Principles

### I. Spec-driven, reviewable development

Application features MUST begin with a Spec Kit specification, measurable acceptance criteria, a technical plan, and traceable tasks. Material behavior gaps MUST be resolved before implementation. Specs, contracts, implementation, and tests MUST stay consistent.

### II. One framework, one real tool path

The application MUST use Microsoft Agent Framework for Python and actual local Ollama inference. Application/end-to-end tests MUST use that real model through the framework and guarded tools. Scripted models, injected model substitutes and silent fallbacks are prohibited. Direct component tests may exercise rules, tools and SDK operations without claiming to execute the agent.

### III. Deterministic, database-backed verification

Required PR checks MUST use the real Cosmos DB vNext emulator and Python SDK with complete seeded fixtures, a fixed clock, and isolated data. The separate required application job MUST use actual Ollama; the component job remains independent of inference. Neither requires a paid Azure resource or production secret. Assertions MUST cover actual model output, retrieved records and partition keys, structured output, evidence, and persisted audit contents.

### IV. Domain correctness and explicit failures

Reviews MUST respect depot boundaries, valid current telemetry, maintenance holds, depot policy, connector compatibility, charger reservations, and wave deadlines. Evidence MUST be traceable to actual retrieved records. Audit writes MUST implement a specified idempotency contract. Invalid inputs, unusable data, and tool/framework failures MUST have explicit outcomes; no silent live-model fallback or invented successful recommendation is permitted.

### V. Small, CI-focused sample

The project MUST prioritize a beginner-friendly backend integration and PR regression test. The React/Vite dashboard is a later demonstration surface. Production deployment, IaC, production identity, RU benchmarking, multi-region guarantees, production scheduling guarantees, and full live-model evaluations are outside the required scope.

## Architecture and constraints

- Target Python 3.12, FastAPI, typed schemas, pytest, Microsoft Agent Framework, and the Azure Cosmos DB Python SDK.
- Keep the API, orchestration, tools, repository, and deterministic fleet rules separate; prefer a single agent.
- Use the six containers and partition keys in [app requirements](../../docs/app-requirements.md).
- Treat recommendations as advisory audit records, not charger reservations.
- Do not claim constrained model/tool integration proves unrestricted reasoning, production authorization, RU cost, or production performance.
- Human GitHub operations for this workspace MUST use `jaydestro`, never the emu account. Actions MUST use least-privilege automation credentials, not a personal login/token. The required PR gate MUST run without Azure credentials or repository secrets.
- The vNext emulator does not enforce authentication. Keep it isolated with loopback-only published ports; do not claim SDK test-key configuration proves authentication or authorization.

## Development workflow and quality gates

Use specify, clarify, plan, tasks, analyze, and implement through the generated Copilot integration. Planning MUST check these principles and document justified deviations. Required tests MUST cover charging rebalance, depot isolation, maintenance exclusion, latest telemetry, and repeat-review audit behavior.

The CI feature MUST demonstrate that removing the depot filter makes the regression test fail, then restore the correct implementation and verify it passes. Test diagnostics and cleanup MUST work on failure as well as success.

## Governance

This constitution governs project implementation. Amendments MUST explain the change, update the version and amendment date, and reconcile affected specifications, plans, tasks, tests, and Copilot instructions. Use semantic versioning: major for incompatible principle changes, minor for new principles or material additions, patch for clarifications. The initial version captures the chosen development tools and the supplied outline's CI requirements; it does not approve unresolved domain behavior.

Amendment 1.1.0: the user's real-model-only direction supersedes the scripted
client strategy. Features, instructions, dependency/configuration, component tests
and the required application job are reconciled in feature 005.

**Version**: 1.1.0 | **Ratified**: 2026-10-19 | **Last Amended**: 2026-10-20
