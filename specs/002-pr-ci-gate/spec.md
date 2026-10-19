# Feature: Reuse the emulator test gate in GitHub Actions

**Date**: 2026-10-19

**Scope approval**: User requested finishing the teaching app, tests, local CI, then Actions,
merge and post-merge verification. This extends the existing implementation branch;
it does not introduce dashboard, live-model or production deployment work.

## Reader outcome

As a Cosmos DB developer, I can run the same emulator-backed checks locally and on a PR,
without provisioning an Azure account or supplying model/cloud secrets.

## Acceptance criteria

- CI-001: One local command runs locked install, lint/format/type checks, real emulator
  readiness, complete pytest integration tests and owned-resource cleanup.
- CI-002: GitHub Actions calls that same runner on `pull_request`, pushes to `main`,
  and manual dispatch, with `contents: read`, no secrets and no `pull_request_target`.
- CI-003: Pin the tested emulator digest and GitHub-owned action commits; acquire Python
  packages and the Linux uv bootstrap only from accessible Microsoft-hosted artifacts.
- CI-004: Upload JUnit XML and emulator diagnostics even on failure, and bound the job.
- CI-005: Removing the effective charger depot scope fails a real emulator test.
  Restore it and verify passing. Never remove the ownership guard.
- CI-006: Publish a feature PR as `jaydestro`, verify hosted checks before merging,
  and verify the merge commit's `main` workflow. Record actual URLs/outcomes.

## Non-goals and limits

The emulator is not a production authorization boundary or an RU/performance benchmark.
The model is scripted; the framework, tool execution and database operations are real.
The repository remains private unless the maintainer explicitly changes visibility.
