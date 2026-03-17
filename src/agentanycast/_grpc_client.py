"""gRPC client wrapper for communicating with the agentanycastd daemon."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import grpc

from agentanycast._generated.agentanycast.v1 import (
    a2a_models_pb2,
    agent_card_pb2,
    common_pb2,
    node_service_pb2,
    node_service_pb2_grpc,
)
from agentanycast.exceptions import (
    CardNotAvailableError,
    DaemonConnectionError,
    PeerNotFoundError,
    TaskNotFoundError,
)

logger = logging.getLogger(__name__)


class GrpcClient:
    """Async gRPC client wrapping NodeService calls.

    Translates gRPC errors into AgentAnycast exception types.
    """

    def __init__(self, address: str) -> None:
        self._address = address
        self._channel: grpc.aio.Channel | None = None
        self._stub: node_service_pb2_grpc.NodeServiceStub | None = None

    async def connect(self) -> None:
        """Establish the gRPC channel and validate the connection."""
        target = self._address
        if target.startswith("unix://"):
            target = self._address  # grpc.aio handles unix:// natively
        elif target.startswith("tcp://"):
            target = target[6:]

        self._channel = grpc.aio.insecure_channel(target)
        self._stub = node_service_pb2_grpc.NodeServiceStub(self._channel)
        logger.debug("gRPC channel created for %s", target)

        # Validate the connection by performing a health check
        try:
            await self._stub.GetNodeInfo(
                node_service_pb2.GetNodeInfoRequest(),
                timeout=5,
            )
            logger.debug("gRPC connection validated to %s", target)
        except grpc.aio.AioRpcError as e:
            # Clean up the channel on failure
            await self._channel.close()
            self._channel = None
            self._stub = None
            raise DaemonConnectionError(
                f"Failed to connect to daemon at {self._address}: {e.details() or e.code()}. "
                f"Ensure the daemon is running and reachable."
            ) from e

    async def close(self) -> None:
        """Close the gRPC channel."""
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None

    def _ensure_connected(self) -> node_service_pb2_grpc.NodeServiceStub:
        if self._stub is None:
            raise DaemonConnectionError("gRPC client not connected")
        return self._stub

    # ── Node Management ────────────────────────────────────────

    async def get_node_info(self) -> common_pb2.NodeInfo:
        """Get the local node's info (PeerID, addresses, etc.)."""
        stub = self._ensure_connected()
        resp = await stub.GetNodeInfo(node_service_pb2.GetNodeInfoRequest())
        return resp.node_info

    async def set_agent_card(self, card: agent_card_pb2.AgentCard) -> None:
        """Set or update the local agent card."""
        stub = self._ensure_connected()
        await stub.SetAgentCard(node_service_pb2.SetAgentCardRequest(card=card))

    # ── Peer Management ────────────────────────────────────────

    async def connect_peer(
        self, peer_id: str, addresses: list[str] | None = None
    ) -> common_pb2.PeerInfo:
        """Connect to a remote peer."""
        stub = self._ensure_connected()
        try:
            resp = await stub.ConnectPeer(
                node_service_pb2.ConnectPeerRequest(
                    peer_id=peer_id,
                    addresses=addresses or [],
                )
            )
            return resp.peer_info
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                raise PeerNotFoundError(f"Cannot connect to peer {peer_id}: {e.details()}")
            raise

    async def list_peers(self) -> list[common_pb2.PeerInfo]:
        """List all connected peers."""
        stub = self._ensure_connected()
        resp = await stub.ListPeers(node_service_pb2.ListPeersRequest())
        return list(resp.peers)

    async def get_peer_card(self, peer_id: str) -> agent_card_pb2.AgentCard:
        """Get the agent card of a connected peer."""
        stub = self._ensure_connected()
        try:
            resp = await stub.GetPeerCard(node_service_pb2.GetPeerCardRequest(peer_id=peer_id))
            return resp.card
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                raise CardNotAvailableError(f"No card for peer {peer_id}")
            if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                raise PeerNotFoundError(f"Invalid peer_id: {peer_id}")
            raise

    # ── Task Client Operations ─────────────────────────────────

    async def send_task(
        self,
        peer_id: str,
        message: a2a_models_pb2.Message,
        target_skill_id: str = "",
        context_id: str = "",
    ) -> a2a_models_pb2.Task:
        """Send a task to a remote agent. Returns the created Task."""
        stub = self._ensure_connected()
        try:
            resp = await stub.SendTask(
                node_service_pb2.SendTaskRequest(
                    peer_id=peer_id,
                    message=message,
                    target_skill_id=target_skill_id,
                    context_id=context_id,
                )
            )
            return resp.task
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                raise PeerNotFoundError(f"Cannot reach peer {peer_id}: {e.details()}")
            raise

    async def get_task(self, task_id: str) -> a2a_models_pb2.Task:
        """Get the current state of a task."""
        stub = self._ensure_connected()
        try:
            resp = await stub.GetTask(node_service_pb2.GetTaskRequest(task_id=task_id))
            return resp.task
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                raise TaskNotFoundError(f"Task {task_id} not found")
            raise

    async def cancel_task(self, task_id: str) -> a2a_models_pb2.Task:
        """Cancel a task."""
        stub = self._ensure_connected()
        try:
            resp = await stub.CancelTask(node_service_pb2.CancelTaskRequest(task_id=task_id))
            return resp.task
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                raise TaskNotFoundError(f"Task {task_id} not found")
            raise

    async def subscribe_task_updates(
        self, task_id: str
    ) -> AsyncIterator[node_service_pb2.SubscribeTaskUpdatesResponse]:
        """Stream status updates for a specific task."""
        stub = self._ensure_connected()
        async for event in stub.SubscribeTaskUpdates(
            node_service_pb2.SubscribeTaskUpdatesRequest(task_id=task_id)
        ):
            yield event

    # ── Task Server Operations ─────────────────────────────────

    async def subscribe_incoming_tasks(
        self,
    ) -> AsyncIterator[node_service_pb2.SubscribeIncomingTasksResponse]:
        """Stream new incoming task requests from remote agents."""
        stub = self._ensure_connected()
        async for event in stub.SubscribeIncomingTasks(
            node_service_pb2.SubscribeIncomingTasksRequest()
        ):
            yield event

    async def update_task_status(
        self,
        task_id: str,
        status: a2a_models_pb2.TaskStatus.ValueType,
        message: a2a_models_pb2.Message | None = None,
    ) -> None:
        """Update the status of a task this node is processing."""
        stub = self._ensure_connected()
        await stub.UpdateTaskStatus(
            node_service_pb2.UpdateTaskStatusRequest(
                task_id=task_id,
                status=status,
                message=message,
            )
        )

    async def complete_task(
        self,
        task_id: str,
        artifacts: list[a2a_models_pb2.Artifact] | None = None,
        message: a2a_models_pb2.Message | None = None,
    ) -> None:
        """Complete a task with artifacts."""
        stub = self._ensure_connected()
        await stub.CompleteTask(
            node_service_pb2.CompleteTaskRequest(
                task_id=task_id,
                artifacts=artifacts or [],
                message=message,
            )
        )

    async def fail_task(self, task_id: str, error_message: str) -> None:
        """Fail a task with an error message."""
        stub = self._ensure_connected()
        await stub.FailTask(
            node_service_pb2.FailTaskRequest(
                task_id=task_id,
                error_message=error_message,
            )
        )
