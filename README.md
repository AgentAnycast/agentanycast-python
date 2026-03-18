# AgentAnycast Python SDK

Python SDK for AgentAnycast -- decentralized A2A agent-to-agent communication over P2P.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)

> **AgentAnycast is fully decentralized.** On a local network, it works with zero configuration. For cross-network communication, just deploy your own relay with a single command.

## Installation

```bash
pip install agentanycast
```

With framework adapters:

```bash
pip install agentanycast[crewai]      # CrewAI integration
pip install agentanycast[langgraph]   # LangGraph integration
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

### CLI

```bash
# Start an echo agent
agentanycast demo

# Discover agents by skill
agentanycast discover translate

# Send a task to a specific agent
agentanycast send 12D3KooW... "Hello!"

# Check node status
agentanycast status
```

### Python API

**Server agent:**

```python
from agentanycast import Node, AgentCard, Skill

card = AgentCard(
    name="EchoAgent",
    description="Echoes back any message",
    skills=[Skill(id="echo", description="Echo messages")],
)

async with Node(card=card) as node:
    @node.on_task
    async def handle(task):
        text = task.messages[-1].parts[0].text
        await task.complete(artifacts=[{"parts": [{"text": f"Echo: {text}"}]}])

    await node.serve_forever()
```

**Client agent:**

```python
from agentanycast import Node, AgentCard

card = AgentCard(name="Client", description="A client agent", skills=[])

async with Node(card=card) as node:
    handle = await node.send_task(
        peer_id="12D3KooW...",
        message={"role": "user", "parts": [{"text": "Hello!"}]},
    )
    result = await handle.wait()
    print(result.artifacts[0].parts[0].text)  # "Echo: Hello!"
```

### Three Ways to Send a Task

```python
# 1. Direct — by Peer ID
await node.send_task(peer_id="12D3KooW...", message=msg)

# 2. Anycast — by skill (relay resolves the target)
await node.send_task(skill="translate", message=msg)

# 3. HTTP Bridge — to standard HTTP A2A agents
await node.send_task(url="https://agent.example.com", message=msg)
```

### Skill Discovery

```python
# Find all agents offering a skill
agents = await node.discover("translate")
for agent in agents:
    print(f"{agent.name}: {agent.skills}")

# With tag filtering
agents = await node.discover("translate", tags={"lang": "fr"})
```

## Framework Adapters

### CrewAI

Expose a CrewAI crew as a P2P agent:

```python
from agentanycast.adapters.crewai import serve_crew

await serve_crew(crew, card=card, relay="...")
```

### LangGraph

Expose a LangGraph graph as a P2P agent:

```python
from agentanycast.adapters.langgraph import serve_graph

await serve_graph(compiled_graph, card=card, relay="...")
```

## Interoperability

### W3C DID

Convert between libp2p Peer IDs and W3C Decentralized Identifiers:

```python
from agentanycast.did import peer_id_to_did_key, did_key_to_peer_id

did = peer_id_to_did_key("12D3KooW...")    # "did:key:z6Mk..."
pid = did_key_to_peer_id("did:key:z6Mk...")  # "12D3KooW..."
```

### MCP (Model Context Protocol)

Map MCP tools to A2A skills:

```python
from agentanycast.mcp import mcp_tools_to_agent_card

card = mcp_tools_to_agent_card(mcp_tools, name="MCPAgent")
```

### AGNTCY Directory

Query the AGNTCY agent directory for cross-ecosystem discovery:

```python
from agentanycast.compat.agntcy import AGNTCYDirectory

directory = AGNTCYDirectory(base_url="https://directory.agntcy.org")
agents = await directory.search("translation")
```

## API Reference

| Class | Description |
|---|---|
| `Node` | Main entry point. Manages daemon lifecycle, sends and receives tasks. |
| `AgentCard` | Describes an agent's identity, capabilities, and metadata. |
| `Skill` | Defines a single skill an agent can perform. |
| `TaskHandle` | Returned by `send_task()`. Call `wait()` to block until the remote agent responds. |
| `IncomingTask` | Passed to task handlers. Provides the incoming message and methods to respond. |

## Node Options

| Parameter | Description | Default |
|---|---|---|
| `card` | Your agent's `AgentCard` | Required |
| `relay` | Relay server multiaddr for cross-network communication | `None` (LAN only) |
| `daemon_path` | Path to a local `agentanycastd` binary | Auto-download |
| `daemon_addr` | Address of an externally managed daemon | Auto-managed |
| `key_path` | Path to Ed25519 identity key file | `<home>/key` |
| `home` | Data directory for daemon state. Use different values to run multiple nodes on the same machine. | `~/.agentanycast` |

## Requirements

- Python 3.10+
- The [agentanycastd](https://github.com/AgentAnycast/agentanycast-node) daemon (auto-managed by the SDK, or bring your own)

## License

[Apache License, Version 2.0](LICENSE)
