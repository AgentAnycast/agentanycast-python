"""AgentAnycast — A2A protocol over P2P.

Python SDK for building distributed AI agent systems with end-to-end encryption
and automatic NAT traversal.
"""

from agentanycast.card import AgentCard, Skill
from agentanycast.exceptions import (
    AgentAnycastError,
    CardNotAvailableError,
    DaemonConnectionError,
    DaemonNotFoundError,
    DaemonStartError,
    PeerAuthenticationError,
    PeerDisconnectedError,
    PeerNotFoundError,
    TaskCanceledError,
    TaskFailedError,
    TaskNotFoundError,
    TaskRejectedError,
    TaskTimeoutError,
)
from agentanycast.node import Node
from agentanycast.task import Artifact, IncomingTask, Message, Part, Task, TaskHandle, TaskStatus

__version__ = "0.1.0"

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
]
