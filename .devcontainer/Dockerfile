FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

USER root
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl jq zstd \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-deps \
    "https://pkgs.dev.azure.com/azure-sdk/public/_packaging/azure-sdk-for-python/pypi/download/uv/0.13/uv-0.13.0-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"

RUN test "$(uname -m)" = x86_64 \
    && mkdir -p /opt/ollama \
    && curl --fail --location --retry 2 --connect-timeout 15 --max-time 300 \
       https://github.com/ollama/ollama/releases/download/v0.40.6/ollama-linux-amd64.tar.zst \
       --output /tmp/ollama-linux-amd64.tar.zst \
    && tar --zstd -xf /tmp/ollama-linux-amd64.tar.zst -C /opt/ollama \
    && ln -s /opt/ollama/bin/ollama /usr/local/bin/ollama \
    && rm /tmp/ollama-linux-amd64.tar.zst
