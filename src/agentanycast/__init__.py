"""AgentAnycast — A2A protocol over P2P.

Python SDK for building distributed AI agent systems with end-to-end encryption
and automatic NAT traversal.
"""

# Extend __path__ so generated protobuf stubs (which import ``agentanycast.v1``)
# resolve correctly within the ``_generated/agentanycast/`` sub-tree.
import pathlib as _pathlib

_generated_pkg = str(_pathlib.Path(__file__).parent / "_generated" / "agentanycast")
if _generated_pkg not in __path__:
    __path__.append(_generated_pkg)
del _pathlib, _generated_pkg

from agentanycast.card import AgentCard, Skill
from agentanycast.exceptions import (
    AgentAnycastError,
    BridgeConnectionError,
    BridgeError,
    BridgeTranslationError,
    CardNotAvailableError,
    DaemonConnectionError,
    DaemonNotFoundError,
    DaemonStartError,
    PeerAuthenticationError,
    PeerDisconnectedError,
    PeerNotFoundError,
    RoutingError,
    SkillNotFoundError,
    TaskCanceledError,
    TaskFailedError,
    TaskNotFoundError,
    TaskRejectedError,
    TaskTimeoutError,
)
from agentanycast.did import did_key_to_peer_id, peer_id_to_did_key
from agentanycast.mcp import MCPTool, mcp_tool_to_skill, mcp_tools_to_agent_card, skill_to_mcp_tool
from agentanycast.node import Node

# v0.3: Lazy imports for optional compat modules (avoid hard httpx dependency at import time).
def __getattr__(name: str):  # type: ignore[no-untyped-def]
    if name == "AGNTCYDirectory":
        from agentanycast.compat.agntcy import AGNTCYDirectory
        return AGNTCYDirectory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
from agentanycast.task import Artifact, IncomingTask, Message, Part, Task, TaskHandle, TaskStatus

__version__ = "0.3.0"

__all__ = [
    # Core
    "Node",
    "AgentCard",
    "Skill",
    # Task types
    "Task",
    "TaskHandle",
    "IncomingTask",
    "TaskStatus",
    "Message",
    "Artifact",
    "Part",
    # Exceptions
    "AgentAnycastError",
    "DaemonNotFoundError",
    "DaemonStartError",
    "DaemonConnectionError",
    "PeerNotFoundError",
    "PeerAuthenticationError",
    "PeerDisconnectedError",
    "CardNotAvailableError",
    "TaskNotFoundError",
    "TaskTimeoutError",
    "TaskCanceledError",
    "TaskFailedError",
    "TaskRejectedError",
    # v0.2: Routing errors
    "RoutingError",
    "SkillNotFoundError",
    # v0.2: Bridge errors
    "BridgeError",
    "BridgeConnectionError",
    "BridgeTranslationError",
    # v0.3: DID utilities
    "peer_id_to_did_key",
    "did_key_to_peer_id",
    # v0.3: MCP interop
    "MCPTool",
    "mcp_tool_to_skill",
    "skill_to_mcp_tool",
    "mcp_tools_to_agent_card",
    # v0.3: AGNTCY compat
    "AGNTCYDirectory",
]
