# Tasks: Emulator PR gate

- [x] CI-T001 / CI-001: Implement and pass shared local CI, real emulator tests and cleanup.
- [x] CI-T002 / CI-005: Prove widened charger scope fails, then restore and pass.
- [x] CI-T003 / CI-002, CI-003, CI-004: Add pinned, secret-free Actions wrapper and diagnostics.
- [ ] CI-T004 / CI-006: Publish feature PR as jaydestro and verify hosted gate.
- [ ] CI-T005 / CI-006: Merge green PR and verify main workflow at merged SHA.
- [ ] CI-T006: Reconcile reader commands, limitations and actual verification evidence.

Dependencies: CI-T002 follows CI-T001; CI-T003 follows CI-T001; CI-T004 follows
CI-T002 and CI-T003; CI-T005 follows CI-T004; CI-T006 records all prior outcomes.
