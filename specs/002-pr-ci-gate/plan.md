# Plan: Emulator PR gate

Reuse `scripts.ci` without a second implementation of the test lifecycle. It owns a
uniquely labelled container, dynamically allocated loopback ports, diagnostics, and cleanup.
Each integration test creates a unique `fleetchargetest-` database.

Use Ubuntu 24.04 and Python 3.12. Bootstrap pinned uv from a hash-verified wheel on
Microsoft's Azure Artifacts feed, then run the checked-in Microsoft-only `uv.lock`.
Pin GitHub-owned checkout/setup-python/upload-artifact actions to immutable commits.
Keep `persist-credentials: false`; no credentials are needed by tests.

Run local green, temporarily widen the charger query, observe red, restore green.
Publish the implementation and workflow together on the existing feature branch,
open a PR, wait for its gate, merge only after success, then wait for the main push gate.
Capture run URLs and useful assertion failures in verification documentation.

This combines the two planned feature deliveries in one user-authorized PR, while
preserving their separate specs. No new runtime frameworks or package sources.
