"""Node — the core entry point for AgentAnycast SDK."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Coroutine

from agentanycast._generated.agentanycast.v1 import (
    a2a_models_pb2,
    agent_card_pb2,
)
from agentanycast._grpc_client import GrpcClient
from agentanycast.card import AgentCard
from agentanycast.daemon import DaemonManager
from agentanycast.exceptions import (
    CardNotAvailableError,
    PeerNotFoundError,
)
from agentanycast.task import (
    Artifact,
    IncomingTask,
    Message,
    Part,
    Task,
    TaskHandle,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# Type alias for the on_task handler signature
TaskHandler = Callable[[IncomingTask], Coroutine[Any, Any, None]]

# Maps between proto TaskStatus and Python TaskStatus
_PROTO_STATUS_MAP = {
    a2a_models_pb2.TASK_STATUS_SUBMITTED: TaskStatus.SUBMITTED,
    a2a_models_pb2.TASK_STATUS_WORKING: TaskStatus.WORKING,
    a2a_models_pb2.TASK_STATUS_INPUT_REQUIRED: TaskStatus.INPUT_REQUIRED,
    a2a_models_pb2.TASK_STATUS_COMPLETED: TaskStatus.COMPLETED,
    a2a_models_pb2.TASK_STATUS_FAILED: TaskStatus.FAILED,
    a2a_models_pb2.TASK_STATUS_CANCELED: TaskStatus.CANCELED,
    a2a_models_pb2.TASK_STATUS_REJECTED: TaskStatus.REJECTED,
}

_STATUS_TO_PROTO_MAP = {
    TaskStatus.SUBMITTED: a2a_models_pb2.TASK_STATUS_SUBMITTED,
    TaskStatus.WORKING: a2a_models_pb2.TASK_STATUS_WORKING,
    TaskStatus.INPUT_REQUIRED: a2a_models_pb2.TASK_STATUS_INPUT_REQUIRED,
    TaskStatus.COMPLETED: a2a_models_pb2.TASK_STATUS_COMPLETED,
    TaskStatus.FAILED: a2a_models_pb2.TASK_STATUS_FAILED,
    TaskStatus.CANCELED: a2a_models_pb2.TASK_STATUS_CANCELED,
    TaskStatus.REJECTED: a2a_models_pb2.TASK_STATUS_REJECTED,
}


def _proto_status_to_python(s: int) -> TaskStatus:
    return _PROTO_STATUS_MAP.get(s, TaskStatus.SUBMITTED)


def _python_status_to_proto(s: TaskStatus) -> int:
    return _STATUS_TO_PROTO_MAP.get(s, a2a_models_pb2.TASK_STATUS_UNSPECIFIED)


def _card_to_proto(card: AgentCard) -> agent_card_pb2.AgentCard:
    """Convert Python AgentCard to protobuf AgentCard."""
    skills = [
        agent_card_pb2.Skill(
            id=s.id,
            description=s.description,
            input_schema=s.input_schema or "",
            output_schema=s.output_schema or "",
        )
        for s in card.skills
    ]
    return agent_card_pb2.AgentCard(
        name=card.name,
        description=card.description,
        version=card.version,
        protocol_version=card.protocol_version,
        skills=skills,
    )


def _proto_card_to_python(pb_card: agent_card_pb2.AgentCard) -> AgentCard:
    """Convert protobuf AgentCard to Python AgentCard."""
    from agentanycast.card import Skill

    skills = [
        Skill(
            id=s.id,
            description=s.description,
            input_schema=s.input_schema or None,
            output_schema=s.output_schema or None,
        )
        for s in pb_card.skills
    ]

    p2p = pb_card.p2p_extension
    return AgentCard(
        name=pb_card.name,
        description=pb_card.description,
        version=pb_card.version,
        protocol_version=pb_card.protocol_version,
        skills=skills,
        peer_id=p2p.peer_id if p2p else None,
        supported_transports=list(p2p.supported_transports) if p2p else None,
        relay_addresses=list(p2p.relay_addresses) if p2p else None,
    )


def _message_to_proto(msg: Message) -> a2a_models_pb2.Message:
    """Convert Python Message to protobuf Message."""
    pb_parts = []
    for p in msg.parts:
        pb_part = a2a_models_pb2.Part()
        if p.text is not None:
            pb_part.text_part.CopyFrom(a2a_models_pb2.TextPart(text=p.text))
        elif p.url is not None:
            pb_part.url_part.CopyFrom(a2a_models_pb2.UrlPart(url=p.url))
        elif p.raw is not None:
            pb_part.raw_part.CopyFrom(a2a_models_pb2.RawPart(data=p.raw))
        if p.media_type:
            pb_part.media_type = p.media_type
        if p.metadata:
            pb_part.metadata.update(p.metadata)
        pb_parts.append(pb_part)

    role = a2a_models_pb2.MESSAGE_ROLE_USER
    if msg.role == "agent":
        role = a2a_models_pb2.MESSAGE_ROLE_AGENT

    return a2a_models_pb2.Message(
        message_id=msg.message_id,
        role=role,
        parts=pb_parts,
    )


def _proto_message_to_python(pb_msg: a2a_models_pb2.Message) -> Message:
    """Convert protobuf Message to Python Message."""
    parts = []
    for pb_part in pb_msg.parts:
        p = Part()
        if pb_part.HasField("text_part"):
            p.text = pb_part.text_part.text
        elif pb_part.HasField("url_part"):
            p.url = pb_part.url_part.url
        elif pb_part.HasField("raw_part"):
            p.raw = pb_part.raw_part.data
        if pb_part.media_type:
            p.media_type = pb_part.media_type
        if pb_part.metadata:
            p.metadata = dict(pb_part.metadata)
        parts.append(p)

    role = "user" if pb_msg.role == a2a_models_pb2.MESSAGE_ROLE_USER else "agent"
    return Message(role=role, parts=parts, message_id=pb_msg.message_id)


def _proto_artifact_to_python(pb_art: a2a_models_pb2.Artifact) -> Artifact:
    """Convert protobuf Artifact to Python Artifact."""
    parts = []
    for pb_part in pb_art.parts:
        p = Part()
        if pb_part.HasField("text_part"):
            p.text = pb_part.text_part.text
        elif pb_part.HasField("url_part"):
            p.url = pb_part.url_part.url
        elif pb_part.HasField("raw_part"):
            p.raw = pb_part.raw_part.data
        parts.append(p)

    return Artifact(
        artifact_id=pb_art.artifact_id,
        name=pb_art.name,
        parts=parts,
    )


def _artifact_to_proto(art: Artifact) -> a2a_models_pb2.Artifact:
    """Convert Python Artifact to protobuf Artifact."""
    pb_parts = []
    for p in art.parts:
        pb_part = a2a_models_pb2.Part()
        if p.text is not None:
            pb_part.text_part.CopyFrom(a2a_models_pb2.TextPart(text=p.text))
        elif p.url is not None:
            pb_part.url_part.CopyFrom(a2a_models_pb2.UrlPart(url=p.url))
        elif p.raw is not None:
            pb_part.raw_part.CopyFrom(a2a_models_pb2.RawPart(data=p.raw))
        pb_parts.append(pb_part)

    return a2a_models_pb2.Artifact(
        artifact_id=art.artifact_id,
        name=art.name,
        parts=pb_parts,
    )


def _proto_task_to_python(pb_task: a2a_models_pb2.Task) -> Task:
    """Convert protobuf Task to Python Task."""
    messages = [_proto_message_to_python(m) for m in pb_task.messages]
    artifacts = [_proto_artifact_to_python(a) for a in pb_task.artifacts]

    return Task(
        task_id=pb_task.task_id,
        context_id=pb_task.context_id,
        status=_proto_status_to_python(pb_task.status),
        messages=messages,
        artifacts=artifacts,
        target_skill_id=pb_task.target_skill_id,
        originator_peer_id=pb_task.originator_peer_id,
    )


class Node:
    """AgentAnycast P2P node — the main interface for A2A communication.

    Manages the connection to the local Go daemon via gRPC and provides
    a Pythonic async API for sending/receiving A2A Tasks.

    Usage:
        async with Node(card=my_card) as node:
            task = await node.send_task(peer_id, message)
            result = await task.wait()
    """

    def __init__(
        self,
        card: AgentCard,
        relay: str | None = None,
        key_path: str | Path | None = None,
        daemon_addr: str | None = None,
        daemon_bin: str | Path | None = None,
        daemon_path: str | Path | None = None,
        home: str | Path | None = None,
    ) -> None:
        self._card = card
        self._relay = relay
        self._key_path = key_path
        self._daemon_addr = daemon_addr
        self._home = home
        # daemon_path takes precedence over daemon_bin for user convenience
        self._daemon_bin = daemon_path or daemon_bin

        self._daemon: DaemonManager | None = None
        self._grpc: GrpcClient | None = None
        self._peer_id: str | None = None
        self._running = False
        self._task_handlers: list[TaskHandler] = []
        self._serve_task: asyncio.Task[None] | None = None

        # In-memory task tracking for TaskHandle updates
        self._tasks: dict[str, TaskHandle] = {}

    @property
    def peer_id(self) -> str:
        """This node's PeerID (available after start)."""
        if not self._peer_id:
            raise RuntimeError("Node not started. Call await node.start() first.")
        return self._peer_id

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the node: launch daemon, connect gRPC, set agent card."""
        if self._running:
            return

        # Start or connect to daemon
        if self._daemon_addr:
            logger.info("Connecting to existing daemon at %s", self._daemon_addr)
        else:
            self._daemon = DaemonManager(
                daemon_bin=self._daemon_bin,
                key_path=self._key_path,
                relay=self._relay,
                home=self._home,
            )
            await self._daemon.start()
            self._daemon_addr = self._daemon.grpc_address

        # Establish gRPC channel
        self._grpc = GrpcClient(self._daemon_addr)
        await self._grpc.connect()

        # Set agent card on daemon
        pb_card = _card_to_proto(self._card)
        await self._grpc.set_agent_card(pb_card)

        # Get our PeerID from the daemon
        node_info = await self._grpc.get_node_info()
        self._peer_id = node_info.peer_id

        self._running = True
        logger.info("Node started. Peer ID: %s", self._peer_id)

    async def stop(self) -> None:
        """Stop the node and clean up resources."""
        if not self._running:
            return

        # Cancel serve task if running
        if self._serve_task and not self._serve_task.done():
            self._serve_task.cancel()
            try:
                await self._serve_task
            except asyncio.CancelledError:
                pass

        # Close gRPC channel
        if self._grpc:
            await self._grpc.close()
            self._grpc = None

        if self._daemon:
            await self._daemon.stop()

        self._running = False
        logger.info("Node stopped.")

    async def __aenter__(self) -> Node:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()

    # ── Client Mode: Send Tasks ───────────────────────────────

    async def get_card(self, peer_id: str) -> AgentCard:
        """Get the Agent Card of a connected peer.

        Args:
            peer_id: The PeerID of the remote agent.

        Returns:
            The remote agent's AgentCard.

        Raises:
            PeerNotFoundError: If the peer is not connected.
            CardNotAvailableError: If the peer hasn't shared a card.
        """
        self._ensure_running()
        assert self._grpc is not None
        pb_card = await self._grpc.get_peer_card(peer_id)
        return _proto_card_to_python(pb_card)

    async def send_task(
        self,
        peer_id: str,
        message: dict[str, Any] | Message,
        target_skill_id: str | None = None,
        context_id: str | None = None,
    ) -> TaskHandle:
        """Send an A2A Task to a remote agent.

        Args:
            peer_id: The PeerID of the target agent.
            message: The message to send (dict or Message object).
            target_skill_id: Optional skill to target on the remote agent.
            context_id: Optional context ID for multi-turn conversations.

        Returns:
            A TaskHandle for tracking the task's progress.
        """
        self._ensure_running()
        assert self._grpc is not None

        # Normalize message
        if isinstance(message, dict):
            msg = Message(
                role=message.get("role", "user"),
                parts=[Part.from_dict(p) for p in message.get("parts", [])],
            )
        else:
            msg = message

        # Convert to proto and send via gRPC
        pb_msg = _message_to_proto(msg)
        pb_task = await self._grpc.send_task(
            peer_id=peer_id,
            message=pb_msg,
            target_skill_id=target_skill_id or "",
            context_id=context_id or "",
        )

        # Convert to Python Task
        task = _proto_task_to_python(pb_task)

        # Create cancel function
        grpc_client = self._grpc

        async def cancel_fn() -> None:
            assert grpc_client is not None
            await grpc_client.cancel_task(task.task_id)

        handle = TaskHandle(task=task, cancel_fn=cancel_fn)
        self._tasks[task.task_id] = handle

        # Start background task to receive updates for this task
        asyncio.create_task(self._watch_task_updates(task.task_id, handle))

        logger.info("Task sent: %s -> %s", task.task_id, peer_id)
        return handle

    async def connect_peer(
        self, peer_id: str, addresses: list[str] | None = None
    ) -> dict[str, Any]:
        """Connect to a remote peer by PeerID.

        Args:
            peer_id: The PeerID to connect to.
            addresses: Optional multiaddrs to try.

        Returns:
            Peer info dict.
        """
        self._ensure_running()
        assert self._grpc is not None
        pi = await self._grpc.connect_peer(peer_id, addresses)
        return {"peer_id": pi.peer_id}

    async def list_peers(self) -> list[dict[str, Any]]:
        """List all currently connected peers.

        Returns:
            List of peer info dicts with peer_id, addresses.
        """
        self._ensure_running()
        assert self._grpc is not None
        peers = await self._grpc.list_peers()
        return [
            {
                "peer_id": p.peer_id,
                "addresses": list(p.addresses),
            }
            for p in peers
        ]

    # ── Server Mode: Receive Tasks ────────────────────────────

    def on_task(self, handler: TaskHandler) -> TaskHandler:
        """Decorator to register a task handler.

        Usage:
            @node.on_task
            async def handle(task: IncomingTask):
                await task.complete(artifacts=[...])
        """
        self._task_handlers.append(handler)
        return handler

    async def serve_forever(self) -> None:
        """Run the node, processing incoming tasks until interrupted.

        This starts listening for incoming A2A Tasks via gRPC streaming
        and dispatches them to registered handlers.
        """
        self._ensure_running()
        assert self._grpc is not None
        logger.info("Serving forever. Waiting for incoming tasks...")

        try:
            async for event in self._grpc.subscribe_incoming_tasks():
                pb_task = event.task
                if pb_task is None:
                    continue

                task = _proto_task_to_python(pb_task)
                sender_card = None
                if event.sender_card and event.sender_card.name:
                    sender_card = _proto_card_to_python(event.sender_card)

                # Create update function that calls back to daemon via gRPC
                grpc_ref = self._grpc

                async def _make_update_fn(tid: str) -> Callable[..., Coroutine[Any, Any, None]]:
                    async def update_fn(
                        task_id: str,
                        status: TaskStatus,
                        artifacts: list[Artifact] | None,
                        error: str | None,
                    ) -> None:
                        assert grpc_ref is not None
                        if status == TaskStatus.COMPLETED:
                            pb_artifacts = (
                                [_artifact_to_proto(a) for a in artifacts]
                                if artifacts
                                else []
                            )
                            await grpc_ref.complete_task(task_id, pb_artifacts)
                        elif status == TaskStatus.FAILED:
                            await grpc_ref.fail_task(task_id, error or "unknown error")
                        else:
                            proto_status = _python_status_to_proto(status)
                            await grpc_ref.update_task_status(task_id, proto_status)

                    return update_fn

                update_fn = await _make_update_fn(task.task_id)

                incoming = IncomingTask(
                    task=task,
                    sender_card=sender_card,
                    update_fn=update_fn,
                )

                # Dispatch to all registered handlers
                for handler in self._task_handlers:
                    asyncio.create_task(handler(incoming))

        except asyncio.CancelledError:
            pass

    # ── Internal ──────────────────────────────────────────────

    async def _watch_task_updates(self, task_id: str, handle: TaskHandle) -> None:
        """Background coroutine that watches for task status updates via gRPC streaming."""
        assert self._grpc is not None
        try:
            async for event in self._grpc.subscribe_task_updates(task_id):
                status = _proto_status_to_python(event.status)
                artifacts = (
                    [_proto_artifact_to_python(a) for a in event.artifacts]
                    if event.artifacts
                    else None
                )
                handle._update(status, artifacts)

                if status.is_terminal:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("task update stream ended: %s", e)

    def _ensure_running(self) -> None:
        if not self._running:
            raise RuntimeError("Node not started. Call await node.start() first.")
