"""Bounded, invocation-owned Cosmos emulator lifecycle (no shared-container cleanup)."""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import TracebackType
from typing import Any
from uuid import uuid4

IMAGE = "mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-latest"
OWNER_LABEL = "io.fleetcharge.emulator-owner"
ROOT = Path(__file__).resolve().parents[1]


class EmulatorError(RuntimeError):
    """Docker, readiness, or ownership verification failed."""


class Emulator:
    """Own one isolated container; expose HTTP ``endpoint`` and ``ready_url``.

    Use ``with Emulator() as emulator: ...``. Ports are dynamically allocated on
    loopback by default. Explicit ports (for example 18081/18080) are optional;
    occupied ports fail rather than reusing or removing an existing container.
    """

    def __init__(
        self,
        *,
        sdk_port: int | None = None,
        readiness_port: int | None = None,
        readiness_timeout: float = 120,
        poll_interval: float = 1,
        log_path: Path = ROOT / ".artifacts" / "emulator.log",
    ) -> None:
        for port in (sdk_port, readiness_port):
            if port is not None and not 1 <= port <= 65535:
                raise ValueError("Host ports must be between 1 and 65535")
        if not 0 < readiness_timeout <= 120 or not 0 < poll_interval <= 5:
            raise ValueError("Readiness timeout must be <=120s and poll interval <=5s")
        self.sdk_port = sdk_port
        self.readiness_port = readiness_port
        self.readiness_timeout = readiness_timeout
        self.poll_interval = poll_interval
        self.log_path = log_path
        self.owner_token = uuid4().hex
        self.name = f"fleetcharge-{self.owner_token}"
        self.container_id: str | None = None
        self.endpoint = ""
        self.ready_url = ""
        self._created = False
        self._closed = False
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @staticmethod
    def _docker(
        *args: str, timeout: float = 30, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["docker", *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise EmulatorError(f"Docker {' '.join(args[:2])} failed: {error}") from error
        if check and result.returncode:
            raise EmulatorError(
                f"Docker {' '.join(args[:2])} exited {result.returncode}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return result

    def _inspect_owned(self) -> dict[str, Any] | None:
        target = self.container_id or self.name
        result = self._docker("container", "inspect", target, check=False)
        if result.returncode:
            if "No such" in result.stderr:
                return None
            raise EmulatorError(f"Cannot inspect owned container: {result.stderr.strip()}")
        try:
            info: dict[str, Any] = json.loads(result.stdout)[0]
            identifier = info["Id"]
            label = info["Config"]["Labels"].get(OWNER_LABEL)
            valid_id = isinstance(identifier, str) and re.fullmatch(r"[0-9a-f]{64}", identifier)
            if (
                not valid_id
                or label != self.owner_token
                or (self.container_id is not None and identifier != self.container_id)
                or (self.container_id is None and info["Name"] != f"/{self.name}")
            ):
                raise EmulatorError("Ownership guard refused access to an unowned container")
        except (ValueError, KeyError, TypeError, IndexError) as error:
            raise EmulatorError("Malformed Docker container inspection") from error
        self.container_id = identifier
        return info

    @staticmethod
    def _port(info: dict[str, Any], port: int) -> str:
        try:
            bindings = info["NetworkSettings"]["Ports"][f"{port}/tcp"]
            if len(bindings) != 1 or bindings[0]["HostIp"] != "127.0.0.1":
                raise EmulatorError("Emulator port is not exclusively bound to IPv4 loopback")
            host_port = int(bindings[0]["HostPort"])
            if not 1 <= host_port <= 65535:
                raise ValueError("invalid port")
        except (KeyError, TypeError, ValueError, IndexError) as error:
            raise EmulatorError(f"Missing or invalid Docker port mapping for {port}") from error
        return f"http://127.0.0.1:{host_port}"

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + self.readiness_timeout
        last_error = "no readiness response"
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                with self._opener.open(self.ready_url, timeout=min(2, remaining)) as response:
                    if response.status == 200:
                        return
                    last_error = f"HTTP {response.status}"
            except (OSError, urllib.error.URLError) as error:
                last_error = str(error)
            time.sleep(min(self.poll_interval, max(0, deadline - time.monotonic())))
        raise EmulatorError(
            f"Emulator readiness timed out after {self.readiness_timeout}s at "
            f"{self.ready_url}: {last_error}"
        )

    def __enter__(self) -> Emulator:
        if self._created or self._closed:
            raise EmulatorError("An Emulator instance cannot be reused")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(f"Image: {IMAGE}\nOwner: {self.owner_token}\n", encoding="utf-8")
        try:
            print("[emulator] Check vNext image availability", flush=True)
            if self._docker("image", "inspect", IMAGE, check=False).returncode:
                self._docker("pull", IMAGE, timeout=180)
            print("[emulator] Create isolated loopback container", flush=True)
            # Mark the attempt before Docker: a timed-out create may have succeeded.
            self._created = True
            result = self._docker(
                "create",
                "--name",
                self.name,
                "--label",
                f"{OWNER_LABEL}={self.owner_token}",
                "-p",
                f"127.0.0.1:{self.sdk_port or ''}:8081",
                "-p",
                f"127.0.0.1:{self.readiness_port or ''}:8080",
                IMAGE,
                "--protocol",
                "http",
                timeout=120,
            )
            identifier = result.stdout.strip()
            if not re.fullmatch(r"[0-9a-f]{64}", identifier):
                raise EmulatorError("Docker create did not return a full container ID")
            self.container_id = identifier
            if self._inspect_owned() is None:
                raise EmulatorError("Created container disappeared before startup")
            self._docker("start", identifier)
            info = self._inspect_owned()
            if info is None:
                raise EmulatorError("Created container disappeared during startup")
            self.endpoint = self._port(info, 8081)
            self.ready_url = f"{self._port(info, 8080)}/ready"
            print(f"[emulator] Wait for {self.ready_url} (<=120s)", flush=True)
            self._wait_ready()
            print(f"[emulator] Ready: COSMOS_ENDPOINT={self.endpoint}", flush=True)
            return self
        except BaseException as primary:
            try:
                self.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup(
                    "Emulator startup and cleanup failed", [primary, cleanup]
                ) from None
            raise

    def close(self) -> None:
        """Capture diagnostics, then remove only the exact ID with our UUID label."""
        if self._closed:
            return
        errors: list[Exception] = []
        info: dict[str, Any] | None = None
        try:
            info = self._inspect_owned() if self._created else None
        except Exception as error:
            errors.append(error)
        if info is not None:
            try:
                logs = self._docker("logs", "--timestamps", info["Id"])
                with self.log_path.open("a", encoding="utf-8") as output:
                    output.write(f"\nState: {json.dumps(info.get('State', {}))}\n")
                    output.write(logs.stdout + logs.stderr)
            except Exception as error:
                errors.append(error)
            try:
                # Recheck immediately before removal; never remove by name or image.
                if self._inspect_owned() is not None:
                    self._docker("rm", "--force", info["Id"])
            except Exception as error:
                errors.append(error)
        try:
            if errors:
                with self.log_path.open("a", encoding="utf-8") as output:
                    output.write("\nLifecycle errors:\n" + "\n".join(map(str, errors)) + "\n")
        except OSError as error:
            errors.append(error)
        if errors:
            raise ExceptionGroup("Emulator diagnostics/cleanup failed", errors)
        self._closed = True
        print(f"[emulator] Cleanup complete; diagnostics: {self.log_path}", flush=True)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.close()
        except BaseException as cleanup:
            if exc is not None:
                raise BaseExceptionGroup(
                    "Workload and emulator cleanup failed", [exc, cleanup]
                ) from None
            raise
