"""Fixtures for integration tests.

These tests start real relay and daemon processes. They are skipped unless
the required binaries are available and the ``integration`` marker is active.

Run integration tests:

    pytest tests/integration/ -m integration -v

Skip in normal test runs:

    pytest tests/ -m "not integration"
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import time
from collections.abc import Generator
from pathlib import Path

import pytest

# ── Marker registration ──────────────────────────────────────────────


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: mark test as integration test")


# ── Binary discovery ─────────────────────────────────────────────────

RELAY_BINARY_CANDIDATES = [
    os.environ.get("RELAY_BINARY", ""),
    str(Path(__file__).parents[3] / "agentanycast-relay" / "bin" / "relay"),
    str(Path(__file__).parents[3] / "agentanycast-relay" / "agentanycast-relay"),
    shutil.which("agentanycast-relay") or "",
]

NODE_BINARY_CANDIDATES = [
    os.environ.get("NODE_BINARY", ""),
    str(Path(__file__).parents[3] / "agentanycast-node" / "bin" / "agentanycastd"),
    str(Path(__file__).parents[3] / "agentanycast-node" / "agentanycastd"),
    shutil.which("agentanycastd") or "",
]


def _find_binary(candidates: list[str]) -> str | None:
    for p in candidates:
        if p and Path(p).is_file() and os.access(p, os.X_OK):
            return p
    return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 10.0) -> bool:
    """Wait until a TCP port is accepting connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def relay_binary() -> str:
    binary = _find_binary(RELAY_BINARY_CANDIDATES)
    if not binary:
        pytest.skip(
            "Relay binary not found. Build with:\n"
            "  cd agentanycast-relay && go build -o bin/relay ./cmd/relay\n"
            "Or set RELAY_BINARY env var."
        )
    return binary


@pytest.fixture(scope="session")
def node_binary() -> str:
    binary = _find_binary(NODE_BINARY_CANDIDATES)
    if not binary:
        pytest.skip(
            "Node binary not found. Build with:\n"
            "  cd agentanycast-node && make build\n"
            "Or set NODE_BINARY env var."
        )
    return binary


@pytest.fixture(scope="session")
def relay_process(
    relay_binary: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[dict[str, str], None, None]:
    """Start a real relay process for the test session.

    Yields a dict with connection info:
        {
            "p2p_port": "12345",
            "registry_port": "12346",
            "registry_addr": "127.0.0.1:12346",
            "p2p_multiaddr": "/ip4/127.0.0.1/tcp/12345",
        }
    """
    p2p_port = _free_port()
    registry_port = _free_port()
    key_path = str(tmp_path_factory.mktemp("relay") / "key")

    cmd = [
        relay_binary,
        "--listen",
        f"/ip4/127.0.0.1/tcp/{p2p_port}",
        "--registry-listen",
        f"127.0.0.1:{registry_port}",
        "--registry-ttl",
        "30s",
        "--log-level",
        "error",
        "--key",
        key_path,
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for registry gRPC port.
    if not _wait_for_port(registry_port):
        proc.kill()
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        pytest.fail(f"Relay failed to start within 10s.\nStderr: {stderr}")

    # Parse peer ID from stdout.
    relay_multiaddr = ""
    if proc.stdout:
        for line in iter(proc.stdout.readline, b""):
            text = line.decode().strip()
            if text.startswith("RELAY_ADDR="):
                relay_multiaddr = text.split("=", 1)[1]
            if text.startswith("REGISTRY_ADDR="):
                break

    info = {
        "p2p_port": str(p2p_port),
        "registry_port": str(registry_port),
        "registry_addr": f"127.0.0.1:{registry_port}",
        "p2p_multiaddr": relay_multiaddr or f"/ip4/127.0.0.1/tcp/{p2p_port}",
    }

    yield info

    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def daemon_factory(
    node_binary: str,
    relay_process: dict[str, str],
    tmp_path: Path,
) -> Generator:
    """Factory fixture that creates daemon processes on demand.

    Usage in tests:

        info_a = daemon_factory("agent-a")
        info_b = daemon_factory("agent-b")
        # info_a["grpc_addr"] is the Unix socket or TCP address
    """
    processes: list[subprocess.Popen] = []  # type: ignore[type-arg]
    counter = 0

    def _create(name: str = "test-agent") -> dict[str, str]:
        nonlocal counter
        counter += 1

        home = tmp_path / f"daemon-{counter}"
        home.mkdir()
        grpc_port = _free_port()
        grpc_addr = f"tcp://127.0.0.1:{grpc_port}"

        bootstrap = relay_process["p2p_multiaddr"]

        cmd = [
            node_binary,
            "--grpc-listen",
            grpc_addr,
            "--key",
            str(home / "key"),
            "--log-level",
            "error",
            "--bootstrap-peers",
            bootstrap,
        ]

        # Set config via env to avoid needing a config file.
        env = os.environ.copy()
        env["AGENTANYCAST_STORE_PATH"] = str(home / "data")
        env["AGENTANYCAST_ENABLE_MDNS"] = "false"

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        processes.append(proc)

        # Wait for gRPC port.
        if not _wait_for_port(grpc_port):
            stderr = proc.stderr.read().decode() if proc.stderr else ""
            pytest.fail(f"Daemon {name} failed to start.\nStderr: {stderr}")

        # Parse peer ID from stdout.
        peer_id = ""
        if proc.stdout:
            for line in iter(proc.stdout.readline, b""):
                text = line.decode().strip()
                if text.startswith("PEER_ID="):
                    peer_id = text.split("=", 1)[1]
                    break

        return {
            "name": name,
            "peer_id": peer_id,
            "grpc_addr": grpc_addr,
            "grpc_port": str(grpc_port),
            "home": str(home),
        }

    yield _create

    # Cleanup all daemon processes.
    for proc in processes:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
