"""End-to-end integration tests for the Python SDK.

These tests start real relay and daemon processes, then use the SDK
to verify agent-to-agent communication works.

Run:
    pytest tests/integration/ -m integration -v

Prerequisites:
    - Build relay: cd agentanycast-relay && go build -o bin/relay ./cmd/relay
    - Build node:  cd agentanycast-node && make build
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agentanycast import AgentCard, Message, Part, Skill
from agentanycast.task import Artifact, IncomingTask


@pytest.mark.integration
class TestEndToEnd:
    """End-to-end tests using real relay and daemon processes."""

    def test_daemon_starts_and_returns_peer_id(self, daemon_factory: Any) -> None:
        """A daemon should start and return a valid peer ID."""
        info = daemon_factory("echo-agent")
        assert info["peer_id"], "daemon should return a peer ID"
        assert info["peer_id"].startswith("12D3KooW") or len(info["peer_id"]) > 10

    def test_two_daemons_get_different_peer_ids(self, daemon_factory: Any) -> None:
        """Two daemons should have different identities."""
        a = daemon_factory("agent-a")
        b = daemon_factory("agent-b")
        assert a["peer_id"] != b["peer_id"]
