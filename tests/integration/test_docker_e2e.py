"""Docker Compose E2E tests.

These tests run inside the test-runner container and connect to the
relay and node services via environment variables set by docker-compose.

Environment variables:
    RELAY_REGISTRY  — gRPC address of the relay's registry (e.g., relay:50052)
    NODE_A_GRPC     — gRPC address of node A (e.g., node-a:50051)
    NODE_B_GRPC     — gRPC address of node B (e.g., node-b:50051)
"""

from __future__ import annotations

import os

import pytest

# These tests only run when the Docker env vars are set.
RELAY_REGISTRY = os.environ.get("RELAY_REGISTRY")
NODE_A_GRPC = os.environ.get("NODE_A_GRPC")
NODE_B_GRPC = os.environ.get("NODE_B_GRPC")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not RELAY_REGISTRY,
        reason="RELAY_REGISTRY not set (not running in Docker Compose)",
    ),
]

grpc = pytest.importorskip("grpc")

from agentanycast._generated.agentanycast.v1 import (  # noqa: E402
    node_service_pb2 as ns_pb2,
    node_service_pb2_grpc as ns_grpc,
    registry_service_pb2 as reg_pb2,
    registry_service_pb2_grpc as reg_grpc,
)


class TestDockerRegistry:
    """Test the registry service running in the relay container."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        assert RELAY_REGISTRY
        self.channel = grpc.insecure_channel(RELAY_REGISTRY)
        self.client = reg_grpc.RegistryServiceStub(self.channel)

    def test_register_and_discover(self) -> None:
        """Register a skill and discover it through the relay."""
        self.client.RegisterSkills(reg_pb2.RegisterSkillsRequest(
            peer_id="12D3KooWDockerTestA",
            skills=[reg_pb2.SkillInfo(
                skill_id="docker-echo",
                description="Echo from Docker",
            )],
            agent_name="Docker Echo Agent",
            agent_description="A test agent in Docker",
        ))

        resp = self.client.DiscoverBySkill(reg_pb2.DiscoverBySkillRequest(
            skill_id="docker-echo",
        ))
        assert len(resp.agents) >= 1

        found = False
        for agent in resp.agents:
            if agent.peer_id == "12D3KooWDockerTestA":
                assert agent.agent_name == "Docker Echo Agent"
                found = True
        assert found, "registered agent not found in discovery results"

    def test_heartbeat_known_peer(self) -> None:
        """Heartbeat for a registered peer should return an expiry time."""
        self.client.RegisterSkills(reg_pb2.RegisterSkillsRequest(
            peer_id="12D3KooWDockerHB",
            skills=[reg_pb2.SkillInfo(skill_id="docker-hb")],
            agent_name="HB Agent",
        ))

        resp = self.client.Heartbeat(reg_pb2.HeartbeatRequest(
            peer_id="12D3KooWDockerHB",
        ))
        assert resp.expires_at is not None

    def test_heartbeat_unknown_peer_fails(self) -> None:
        """Heartbeat for an unknown peer should return NOT_FOUND."""
        with pytest.raises(grpc.RpcError) as exc_info:
            self.client.Heartbeat(reg_pb2.HeartbeatRequest(
                peer_id="12D3KooWNonExistent",
            ))
        assert exc_info.value.code() == grpc.StatusCode.NOT_FOUND

    def test_unregister_skills(self) -> None:
        """Unregistering a skill should remove it from discovery."""
        self.client.RegisterSkills(reg_pb2.RegisterSkillsRequest(
            peer_id="12D3KooWDockerUnreg",
            skills=[
                reg_pb2.SkillInfo(skill_id="docker-unreg-a"),
                reg_pb2.SkillInfo(skill_id="docker-unreg-b"),
            ],
            agent_name="Unreg Agent",
        ))

        self.client.UnregisterSkills(reg_pb2.UnregisterSkillsRequest(
            peer_id="12D3KooWDockerUnreg",
            skill_ids=["docker-unreg-a"],
        ))

        resp = self.client.DiscoverBySkill(reg_pb2.DiscoverBySkillRequest(
            skill_id="docker-unreg-a",
        ))
        for agent in resp.agents:
            assert agent.peer_id != "12D3KooWDockerUnreg"

    def test_tag_filtering(self) -> None:
        """Tag-based filtering should work in Docker."""
        self.client.RegisterSkills(reg_pb2.RegisterSkillsRequest(
            peer_id="12D3KooWDockerTagEN",
            skills=[reg_pb2.SkillInfo(
                skill_id="docker-translate",
                tags={"lang": "en"},
            )],
            agent_name="EN Translator",
        ))
        self.client.RegisterSkills(reg_pb2.RegisterSkillsRequest(
            peer_id="12D3KooWDockerTagZH",
            skills=[reg_pb2.SkillInfo(
                skill_id="docker-translate",
                tags={"lang": "zh"},
            )],
            agent_name="ZH Translator",
        ))

        resp = self.client.DiscoverBySkill(reg_pb2.DiscoverBySkillRequest(
            skill_id="docker-translate",
            tags={"lang": "zh"},
        ))
        peer_ids = [a.peer_id for a in resp.agents]
        assert "12D3KooWDockerTagZH" in peer_ids
        assert "12D3KooWDockerTagEN" not in peer_ids


class TestDockerNodes:
    """Test the daemon nodes running in Docker containers."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        assert NODE_A_GRPC
        assert NODE_B_GRPC
        self.channel_a = grpc.insecure_channel(NODE_A_GRPC)
        self.channel_b = grpc.insecure_channel(NODE_B_GRPC)
        self.client_a = ns_grpc.NodeServiceStub(self.channel_a)
        self.client_b = ns_grpc.NodeServiceStub(self.channel_b)

    def test_node_a_responds(self) -> None:
        """Node A should respond to GetNodeInfo."""
        resp = self.client_a.GetNodeInfo(ns_pb2.GetNodeInfoRequest())
        info = resp.node_info
        assert info.peer_id, "Node A should return a peer ID"
        assert info.peer_id.startswith("12D3KooW")

    def test_node_b_responds(self) -> None:
        """Node B should respond to GetNodeInfo."""
        resp = self.client_b.GetNodeInfo(ns_pb2.GetNodeInfoRequest())
        assert resp.node_info.peer_id, "Node B should return a peer ID"

    def test_nodes_have_different_ids(self) -> None:
        """Two nodes should have unique identities."""
        resp_a = self.client_a.GetNodeInfo(ns_pb2.GetNodeInfoRequest())
        resp_b = self.client_b.GetNodeInfo(ns_pb2.GetNodeInfoRequest())
        assert resp_a.node_info.peer_id != resp_b.node_info.peer_id
