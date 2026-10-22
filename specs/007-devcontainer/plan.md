# Local development container plan

Use the Microsoft Python 3.12 Debian development image and the official
Docker-in-Docker Feature. Install the same uv and Ollama releases used by CI.
Keep setup in one fail-fast Bash script and use a named volume for the container's
Linux `.venv` so it cannot overwrite the host interpreter.

The nested daemon keeps emulator loopback mappings in the same network namespace
as the Python SDK. A host-socket setup would publish those ports on the host,
breaking the existing loopback contract. The official Feature requires a
privileged container; document that this is for trusted local development.

Expose only the application port through VS Code, not the emulator or Ollama.
Keep model preparation explicit. Use existing emulator, tests, requests and
reports rather than introducing a separate container-specific application path.

Validate real startup and runtime locally, and retain the existing GitHub jobs
as the cross-platform regression gate. The local article remains ignored.
