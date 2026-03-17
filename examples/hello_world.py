"""AgentAnycast Hello World — Two agents exchanging an A2A Task.

This example demonstrates the target API for v0.1.
Run two instances of this script with different roles:

  # Terminal 1 (Server Agent)
  python hello_world.py --role server

  # Terminal 2 (Client Agent)
  python hello_world.py --role client --peer <PEER_ID_FROM_TERMINAL_1>
"""

import argparse
import asyncio

from agentanycast import AgentCard, Node, Skill


async def run_server():
    """Run as the server agent that processes incoming tasks."""
    card = AgentCard(
        name="EchoAgent",
        description="Echoes back any message it receives",
        skills=[Skill(id="echo", description="Echo the input message back")],
    )

    async with Node(card=card) as node:
        print(f"Server started. Peer ID: {node.peer_id}")
        print("Waiting for incoming tasks...")

        @node.on_task
        async def handle(task):
            print(f"Received task {task.task_id} from {task.peer_id}")
            text = task.messages[-1].parts[0].text if task.messages else "no message"
            print(f"Message: {text}")

            await task.update_status("working")
            await task.complete(
                artifacts=[{"name": "echo_result", "parts": [{"text": f"Echo: {text}"}]}]
            )
            print(f"Task {task.task_id} completed.")

        await node.serve_forever()


async def run_client(peer_id: str):
    """Run as the client agent that sends a task."""
    card = AgentCard(
        name="ClientAgent",
        description="Sends tasks to other agents",
        skills=[],
    )

    async with Node(card=card) as node:
        print(f"Client started. Peer ID: {node.peer_id}")

        # Check what the remote agent can do
        remote_card = await node.get_card(peer_id)
        print(f"Remote agent: {remote_card.name}")
        print(f"Skills: {[s.id for s in remote_card.skills]}")

        # Send a task
        task = await node.send_task(
            peer_id=peer_id,
            message={
                "role": "user",
                "parts": [{"text": "Hello from AgentAnycast!"}],
            },
        )

        print(f"Task sent: {task.task_id}")
        result = await task.wait(timeout=30)
        print(f"Result: {result.artifacts[0].parts[0].text}")


def main():
    parser = argparse.ArgumentParser(description="AgentAnycast Hello World")
    parser.add_argument("--role", choices=["server", "client"], required=True)
    parser.add_argument("--peer", help="Peer ID of the server (for client role)")
    args = parser.parse_args()

    if args.role == "server":
        asyncio.run(run_server())
    else:
        if not args.peer:
            parser.error("--peer is required for client role")
        asyncio.run(run_client(args.peer))


if __name__ == "__main__":
    main()
