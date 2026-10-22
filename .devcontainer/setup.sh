#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
sudo chown "$(id -u):$(id -g)" .venv /home/vscode/.ollama
uv sync --locked --extra test
if [[ ! -e .env ]]; then
  cp .env.example .env
fi
docker info > /dev/null
printf '%s\n' \
  "Ready: Python 3.12, uv, Docker, GitHub CLI, curl, jq and Ollama are installed." \
  "In another container terminal, run: ollama serve" \
  "Then follow the README to pull phi3.5 and create fleetcharge-phi3.5." \
  "No model weights were downloaded and no application server was started."
