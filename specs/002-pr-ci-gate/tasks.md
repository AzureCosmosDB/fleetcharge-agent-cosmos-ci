# Tasks: Emulator PR gate

- [x] CI-T001 / CI-001: Implement and pass shared local CI, real emulator tests and cleanup.
- [x] CI-T002 / CI-005: Prove widened charger scope fails, then restore and pass.
- [x] CI-T003 / CI-002, CI-003, CI-004: Add pinned, secret-free Actions wrapper and diagnostics.
- [x] CI-T004 / CI-006: PR #1 published as jaydestro. Initial green, intentional red and restored green verified on hosted Linux.
- [x] CI-T005 / CI-006: Squash-merged PR #1 after green checks; main run 39315371445 passed 96 tests at exact merge SHA b21ad157df5db049174b3f2c447b630efd9128c5.
- [x] CI-T006: Reader commands, limitations and actual local/hosted evidence reconciled in README, blog and docs/verification.md.

Dependencies: CI-T002 follows CI-T001; CI-T003 follows CI-T001; CI-T004 follows
CI-T002 and CI-T003; CI-T005 follows CI-T004; CI-T006 records all prior outcomes.
