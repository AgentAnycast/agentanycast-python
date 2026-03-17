"""Tests for Task, Message, Part, and TaskHandle."""

import asyncio

import pytest

from agentanycast import Artifact, Message, Part, Task, TaskStatus
from agentanycast.task import TaskHandle


def test_part_text_roundtrip():
    part = Part(text="Hello world")
    d = part.to_dict()
    assert d["text"] == "Hello world"
    restored = Part.from_dict(d)
    assert restored.text == "Hello world"


def test_part_data_roundtrip():
    part = Part(data={"total": 42, "items": ["a", "b"]})
    d = part.to_dict()
    restored = Part.from_dict(d)
    assert restored.data == {"total": 42, "items": ["a", "b"]}


def test_message_roundtrip():
    msg = Message(
        role="user",
        parts=[Part(text="Analyze Q4 sales")],
        message_id="msg-1",
    )
    d = msg.to_dict()
    assert d["role"] == "user"
    assert len(d["parts"]) == 1

    restored = Message.from_dict(d)
    assert restored.role == "user"
    assert restored.parts[0].text == "Analyze Q4 sales"


def test_artifact_roundtrip():
    artifact = Artifact(
        artifact_id="art-1",
        name="result",
        parts=[Part(data={"status": "ok"})],
    )
    d = artifact.to_dict()
    restored = Artifact.from_dict(d)
    assert restored.name == "result"
    assert restored.parts[0].data == {"status": "ok"}


def test_task_status_terminal():
    assert TaskStatus.COMPLETED.is_terminal
    assert TaskStatus.FAILED.is_terminal
    assert TaskStatus.CANCELED.is_terminal
    assert TaskStatus.REJECTED.is_terminal
    assert not TaskStatus.SUBMITTED.is_terminal
    assert not TaskStatus.WORKING.is_terminal
    assert not TaskStatus.INPUT_REQUIRED.is_terminal


@pytest.mark.asyncio
async def test_task_handle_wait_completed():
    task = Task(task_id="t1", status=TaskStatus.SUBMITTED)

    async def noop() -> None:
        pass

    handle = TaskHandle(task=task, cancel_fn=noop)

    # Simulate async update
    async def update_later():
        await asyncio.sleep(0.05)
        handle._update(TaskStatus.WORKING)
        await asyncio.sleep(0.05)
        handle._update(TaskStatus.COMPLETED, [Artifact(name="result")])

    asyncio.create_task(update_later())
    result = await handle.wait(timeout=2.0)
    assert result.status == TaskStatus.COMPLETED
    assert len(result.artifacts) == 1


@pytest.mark.asyncio
async def test_task_handle_wait_timeout():
    task = Task(task_id="t2", status=TaskStatus.SUBMITTED)

    async def noop() -> None:
        pass

    handle = TaskHandle(task=task, cancel_fn=noop)

    from agentanycast.exceptions import TaskTimeoutError
    with pytest.raises(TaskTimeoutError):
        await handle.wait(timeout=0.1)


@pytest.mark.asyncio
async def test_task_handle_already_terminal():
    task = Task(task_id="t3", status=TaskStatus.COMPLETED)

    async def noop() -> None:
        pass

    handle = TaskHandle(task=task, cancel_fn=noop)
    result = await handle.wait(timeout=1.0)
    assert result.status == TaskStatus.COMPLETED
