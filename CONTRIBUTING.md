# Contributing

Thank you for your interest in contributing to AgentAnycast!

Please see the [Contributing Guide](https://github.com/AgentAnycast/agentanycast/blob/main/CONTRIBUTING.md) in the main repository for guidelines on:

- Contribution workflow
- Coding standards
- Commit message conventions
- Cross-repository changes
- DCO sign-off requirements

## Python SDK-Specific Guidelines

- Run `ruff check .` and `ruff format --check .` before submitting
- All public APIs must have type hints and docstrings
- Tests use pytest with `asyncio_mode = "auto"`
- Do not modify files under `src/agentanycast/_generated/` — those are auto-generated from proto
