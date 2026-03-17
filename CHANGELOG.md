# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-03-17

### Added

- `Node` class — async context manager for P2P agent communication
- `AgentCard` and `Skill` dataclasses for agent capability description
- `TaskHandle` for tracking outgoing tasks with `wait()` support
- `IncomingTask` for receiving and responding to tasks (`complete()`, `fail()`, `update_status()`)
- Automatic daemon lifecycle management (start, stop, health check)
- Auto-download of daemon binary when not provided
- gRPC client for SDK-daemon communication over Unix domain socket
- `home` parameter for running multiple nodes on the same machine
- Hello world example with server and client agents
- PEP 561 `py.typed` marker for type checking support
- CI pipeline with ruff lint, mypy type check, and multi-version pytest

[0.1.0]: https://github.com/AgentAnycast/agentanycast-python/releases/tag/v0.1.0
