# AgentAnycast Python SDK

Python SDK for AgentAnycast -- decentralized A2A agent-to-agent communication over P2P.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)

> **AgentAnycast is fully decentralized.** On a local network, it works with zero configuration. For cross-network communication, just deploy your own relay with a single command.

## Installation

```bash
pip install agentanycast
```

## How It Works

```
┌─────────────┐         mDNS / Relay         ┌─────────────┐
│  Agent A    │◄──────────────────────────────►│  Agent B    │
│  (Python)   │     E2E encrypted (Noise)     │  (Python)   │
└──────┬──────┘                               └──────┬──────┘
       │ gRPC                                        │ gRPC
┌──────┴──────┐                               ┌──────┴──────┐
│ agentanycastd│                               │ agentanycastd│
│  (daemon)   │                               │  (daemon)    │
└─────────────┘                               └──────────────┘
```

- **Local network (LAN):** Agents discover each other automatically via mDNS. No relay needed.
- **Cross-network (WAN):** Deploy your own relay server, then point agents to it. One command.

## Quick Start

### 1. Local network -- zero configuration

Two agents on the same LAN can communicate immediately:

**Agent A (server):**

```python
from agentanycast import Node, AgentCard, Skill

card = AgentCard(
    name="echo-agent",
    description="Echoes back any message",
    skills=[Skill(id="echo", description="Echo messages")],
)

async def handler(task):
    text = task.message["parts"][0]["text"]
    await task.complete(message={"role": "agent", "parts": [{"text": text}]})

node = Node(card=card)
node.on_task(handler)
await node.serve_forever()
```

**Agent B (client):**

```python
from agentanycast import Node, AgentCard

card = AgentCard(name="client", description="A client agent", skills=[])

async with Node(card=card) as node:
    # Peer ID is printed by Agent A on startup
    handle = await node.send_task(
        peer_id="12D3KooW...",
        message={"role": "user", "parts": [{"text": "Hello!"}]},
    )
    result = await handle.wait()
    print(result)
```

### 2. Cross-network -- deploy your own relay

```bash
# On any VPS or cloud instance with a public IP:
git clone https://github.com/agentanycast/agentanycast-relay && cd agentanycast-relay
docker-compose up -d

# Note the relay's multiaddr from the logs:
# RELAY_ADDR=/ip4/<YOUR_IP>/tcp/4001/p2p/12D3KooW...
```

Then point your agents to it:

```python
node = Node(
    card=card,
    relay="/ip4/<YOUR_IP>/tcp/4001/p2p/12D3KooW...",
)
```

Or via environment variable:

```bash
export AGENTANYCAST_BOOTSTRAP_PEERS="/ip4/<YOUR_IP>/tcp/4001/p2p/12D3KooW..."
```

## API Reference

| Class | Description |
|---|---|
| `Node` | Main entry point. Manages daemon lifecycle, sends and receives tasks. |
| `AgentCard` | Describes an agent's identity, capabilities, and metadata. |
| `Skill` | Defines a single skill an agent can perform. |
| `TaskHandle` | Returned by `send_task()`. Call `wait()` to block until the remote agent responds. |
| `IncomingTask` | Passed to task handlers. Provides the incoming message and methods to respond (`complete()`, `fail()`). |

## Node Options

| Parameter | Description | Default |
|---|---|---|
| `card` | Your agent's `AgentCard` | Required |
| `relay` | Relay server multiaddr for cross-network communication | None (LAN only) |
| `daemon_path` | Path to a local `agentanycastd` binary | Auto-download |
| `daemon_version` | Version to auto-download | `0.1.0` |

## Requirements

- Python 3.10+
- The [agentanycastd](https://github.com/agentanycast/agentanycast-node) daemon (auto-managed by the SDK, or bring your own)

## License

[Apache License, Version 2.0](LICENSE)
