# Plan: Optional Ollama and seeded database verification

Use the existing `store` fixture for mandatory database coverage. Add an optional
Microsoft-hosted `agent-framework-openai` dependency and its Chat Completions
client pointed explicitly at local Ollama; preserve the existing framework
function invocation limits and tool guards. Keep scripted turn assertions only
for scripted clients, and retain persisted/terminal equality in both modes.

Optional live mode progressively exposes only the next valid tool through
framework function middleware. The original contract requires a fixed tool order;
this prevents a small model from selecting a tool before its prerequisites exist.
The LLM still generates the arguments and final response. Scripted tests continue
to expose all tools so out-of-order and unknown-call regressions remain covered.

Select optional live tests explicitly through a dedicated runner. Default test
collection excludes them without skipping required integration coverage. The
runner creates its own emulator and invokes pytest with a bounded deadline.
Use the existing installed model; never pull weights automatically.

The optional provider is 1.16.0 with OpenAI SDK 3.29.0, downloaded from Microsoft's
feed. SDK 3.29.0 and jiter 0.17.0 have missing metadata sidecars; exact dependency
metadata was read from SHA-256-verified wheels (OpenAI:
`860d3bad424c5d38cd9ba0a0a2050d558b58ce027596a39f9ccbc0f51a2090b7`;
jiter Windows:
`9bd3caac219df476dd0cc3fe01d2f1581ed588906feac767abd9614c1c12f8b3`).
The Linux jiter 0.17.0 CPython 3.12 x86_64 wheel was also downloaded and verified:
`8c21265b251d99bbb40080d178a8953e35601d3a1564e05c4de4c0d2ca616797`.
The lock resolves the documented Windows/Linux targets; OpenAI's browser-only
`httpx2-jsfetch` dependency is not available on this feed.

## Requirement mapping

| Requirement | Implementation | Verification |
|---|---|---|
| FR-001, FR-002 | Seeded SDK integration tests | Required `scripts.ci` |
| FR-003, FR-005 | Settings and framework client selection | Unit/failure tests and live execution |
| FR-004 | Live golden/output CRUD test | Optional `scripts.test_ollama` |
| FR-006 | Owned emulator runner and README | Success/failure cleanup and documented commands |

See [tasks and actual outcomes](tasks.md). Required verification is green;
the installed small model's live smoke test is not.

## Constitution check

One framework and shared tools remain mandatory. The required PR gate requires no
LLM or secrets. Optional local model execution is explicitly user-authorized.
All arithmetic and write validation stay in application code; partitions and
the isolated database namespace remain enforced. No principle amendment needed.
