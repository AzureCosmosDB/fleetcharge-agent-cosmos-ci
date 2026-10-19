# Verified quickstart: Wave review

Prerequisites: Python 3.12, uv, Git, Docker with Linux containers and repository access.
No Azure subscription, Azure login or model endpoint is required.

From the child repository root (PowerShell or Linux shell):

```text
uv sync --locked --extra test
uv run --locked --extra test python -m scripts.ci
```

The runner performs locked install, Ruff/format/mypy checks, starts a uniquely owned
digest-pinned emulator with dynamic loopback ports, waits up to 120 seconds for `/ready`,
runs all tests, saves diagnostics and cleans up even on failure. Tests use isolated
`fleetchargetest-` databases and real SDK operations. No unrelated container is reused,
stopped or deleted.

To inspect the actual HTTP application:

```text
uv run --locked python -m scripts.demo
```

Open `http://127.0.0.1:8000/docs` and call `POST /agent/review-delivery-wave` with:

```json
{"depotId":"SEA-01","deliveryWaveId":"wave-2026-10-19-1400"}
```

Expect `rebalanceCharging`, a van-042 battery risk and an 11-minute assignment to
charger-fast-03. The fixed review time is `2026-10-19T12:30:00-07:00`; fixtures do
not age relative to the reader's calendar. Ctrl+C cleans up this disposable demo.

For bounded HTTP/audit verification:

```text
uv run --locked python -m scripts.demo --smoke
```

Verified locally: HTTP 200 plus independent SDK audit read-back; full local CI had
96 passing tests with lint/format/types clean. The intentional widened-depot query
failed real tests with exit 1 and still cleaned up. See
[verification evidence](../../docs/verification.md) for restored and hosted outcomes.

## Troubleshooting

- Docker failure: check Docker is running Linux containers; no fake database fallback.
- Readiness timeout: inspect `.artifacts/emulator.log`; startup fails rather than seeding.
- Test failure: inspect `.artifacts/results.xml` and logs; runner returns nonzero.
- API port occupied: use `scripts.demo --port 8001`; never stop an unrelated service.
- Package download failures: use the checked-in Microsoft-only lock. Do not disable TLS
  or silently switch package sources. See [research](research.md).
- Cleanup refuses settings: use only loopback endpoints and the `fleetchargetest-`
  namespace. Do not broaden deletion to unrelated data.

The [Actions feature](../002-pr-ci-gate/spec.md) reuses the same runner.
vNext does not enforce authentication; this demo tests neither production authorization
nor RU/performance or live-model reasoning.
