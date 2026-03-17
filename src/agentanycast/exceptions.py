"""Exception hierarchy for AgentAnycast SDK."""


class AgentAnycastError(Exception):
    """Base exception for all AgentAnycast errors."""


# ── Daemon Errors ─────────────────────────────────────────


class DaemonError(AgentAnycastError):
    """Base for daemon-related errors."""


class DaemonNotFoundError(DaemonError):
    """Daemon binary not found and could not be downloaded."""


class DaemonStartError(DaemonError):
    """Daemon process failed to start."""


class DaemonConnectionError(DaemonError):
    """Failed to connect to daemon via gRPC."""


# ── Peer Errors ───────────────────────────────────────────


class PeerError(AgentAnycastError):
    """Base for peer-related errors."""


class PeerNotFoundError(PeerError):
    """The specified peer is not reachable."""


class PeerDisconnectedError(PeerError):
    """The peer connection was lost."""


class PeerAuthenticationError(PeerError):
    """Noise handshake failed — peer identity verification failed."""


# ── Task Errors ───────────────────────────────────────────


class TaskError(AgentAnycastError):
    """Base for task-related errors."""


class TaskNotFoundError(TaskError):
    """The specified task ID does not exist."""


class TaskTimeoutError(TaskError):
    """Task wait() exceeded the specified timeout."""


class TaskCanceledError(TaskError):
    """The task was canceled."""


class TaskFailedError(TaskError):
    """The remote agent failed to process the task."""

    def __init__(self, message: str = "", error_detail: str = "") -> None:
        self.error_detail = error_detail
        super().__init__(message or error_detail)


class TaskRejectedError(TaskError):
    """The remote agent rejected the task."""


# ── Card Errors ───────────────────────────────────────────


class CardError(AgentAnycastError):
    """Base for card-related errors."""


class CardNotAvailableError(CardError):
    """The peer has not provided an Agent Card."""
