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

Runtime traces showed two compatibility boundaries. The framework clears required
tool choice after the first call, and native Ollama tool choice was unreliable.
Use the official client's chat middleware to request schema-constrained JSON
instead, then convert validated proposals to framework function-call content.
Request depot/wave identities constrain the schema, not post-generation repairs.
Only real function results enter compact provider-local context; the framework
retains its full correlated tool history. The write schema reuses `Decision`.
Timestamp inputs retain JSON string types with a date-time schema: framework
normalization rejects already-coerced datetime objects against string schemas.
Domain datetime/equality checks and proposal equality remain unchanged.

Select optional live tests explicitly through a dedicated runner. Default test
collection excludes them without skipping required integration coverage. The
runner creates its own emulator and invokes pytest with a bounded deadline.
Use the existing installed model; never pull weights automatically. The installed
Microsoft Phi-3.5 model is wrapped in a 4096-token alias using
`scripts/Ollama.modelfile`. Preflight requires local chat completion, not native
tools, since JSON proposals are dispatched by the framework.

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
| FR-007 | Separate branch/manual live-model Actions job | Hosted branch run: readiness, exact output, output CRUD and diagnostics |

## Branch live-model CI extension

Keep the existing deterministic job unchanged and independent. Add push coverage
for this feature branch and a separate live-model job on branch pushes or manual
dispatch. Do not make real-model inference a prerequisite of the deterministic PR
gate. Use GitHub-hosted Ubuntu, loopback Ollama, no personal tokens/secrets and
`contents: read`. Install Python dependencies only from the locked Microsoft feed.

Provision official Ollama 0.40.6 from its SHA-256-verified Linux release and pull
the Microsoft Phi-3.5 model from Ollama's official registry. Verify its exact known
digest before creating the existing context-bounded alias. This explicit CI-only
download is authorized by the user's CI wiring request; local commands continue
to require installed weights. Poll only runtime readiness, never model answers.
Run the unchanged golden/output-CRUD assertions with bounded deadlines and fail
on any timeout or unexpected output. Preserve runtime/provisioning/test/emulator
logs even on failure and terminate the exact job-owned PID in an always step.

The first hosted inference run reached the 300-second review deadline after
five successful model turns on a one-physical-core CPU runner. Keep local defaults
at 300 seconds; explicitly select a bounded 900-second per-review deadline for
CPU-only CI, with 1900 seconds for the two-review test process and 45 minutes for
the job. Test deadline propagation and invalid limits without contacting services.
Do not alter golden assertions, prompts or model output to conceal timeouts.

See [tasks and actual outcomes](tasks.md). The actual bounded Phi-3.5 live test
passed both reviews and persisted-output CRUD in two runs (351.47 and 408.38
seconds). The required local gate passed 128 tests. Its alias digest
is `7202f39ac4b8d07f768ce41af5df7c7b04f10c9f61f6c3da6b3343dbf6d504ec`;
the existing base digest is
`61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba`.

## Constitution check

One framework and shared tools remain mandatory. The required PR gate requires no
LLM or secrets. Optional local model execution is explicitly user-authorized.
All arithmetic and write validation stay in application code; partitions and
the isolated database namespace remain enforced. No principle amendment needed.
