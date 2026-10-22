# Local Dev Containers onboarding

## Requirements

- FR-001: Provide a local VS Code Dev Containers launch badge in the README and
  external blog, targeting the public repository rather than an unpublished branch.
- FR-002: Install Python 3.12, Microsoft-feed uv 0.13.0, Ollama 0.40.6, GitHub CLI,
  curl and jq.
  Use the locked application dependencies and preserve an existing local `.env`.
- FR-003: Run a dedicated nested Docker daemon. Existing emulator helpers must
  retain loopback-only endpoints, dynamic ports and exact-owned-resource cleanup.
  Do not mount the host Docker socket or relax application URL validation.
- FR-004: Keep the Linux virtual environment separate from a host Windows `.venv`.
  Persist explicitly downloaded models, but never download model weights or start
  inference/application services silently during setup.
- FR-005: Document the Docker Desktop/Linux-container and x86-64 requirements,
  privileged Docker-in-Docker trust boundary, explicit model setup, API forwarding,
  first-build downloads and retained development volumes.
- FR-006: Preserve the host setup and existing application/CI behavior. Do not
  advertise Codespaces, native macOS or ARM compatibility without validation.

## Acceptance

Build and open the actual configuration with the Dev Containers CLI. Verify tool
versions, setup, environment preservation and Linux `.venv` isolation. Run the
emulator component gate and real model test inside the development container.
Verify before/update/after HTTP requests and cleanup. The badge and external
article must match the committed configuration, then both existing GitHub jobs
must pass at the published revision.
