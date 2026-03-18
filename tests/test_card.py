"""Tests for AgentCard and Skill data models."""

from agentanycast import AgentCard, Skill


def test_skill_roundtrip():
    skill = Skill(id="analyze_csv", description="Analyze CSV data")
    d = skill.to_dict()
    restored = Skill.from_dict(d)
    assert restored.id == "analyze_csv"
    assert restored.description == "Analyze CSV data"


def test_agent_card_roundtrip():
    card = AgentCard(
        name="DataAnalyst",
        description="Analyzes data",
        skills=[
            Skill(id="analyze_csv", description="Analyze CSV"),
            Skill(id="generate_chart", description="Generate chart"),
        ],
    )
    d = card.to_dict()
    assert d["name"] == "DataAnalyst"
    assert len(d["skills"]) == 2

    restored = AgentCard.from_dict(d)
    assert restored.name == "DataAnalyst"
    assert len(restored.skills) == 2
    assert restored.skills[0].id == "analyze_csv"


def test_agent_card_with_p2p_extension():
    card = AgentCard(
        name="Test",
        peer_id="12D3KooWTest",
        supported_transports=["tcp", "quic"],
        relay_addresses=["/ip4/1.2.3.4/tcp/4001/p2p/12D3KooWRelay"],
    )
    d = card.to_dict()
    assert "agentanycast" in d
    assert d["agentanycast"]["peer_id"] == "12D3KooWTest"

    restored = AgentCard.from_dict(d)
    assert restored.peer_id == "12D3KooWTest"
    assert restored.supported_transports == ["tcp", "quic"]


def test_agent_card_with_did_key():
    card = AgentCard(
        name="DIDTest",
        peer_id="12D3KooWTest",
        did_key="did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
    )
    d = card.to_dict()
    assert d["agentanycast"]["did_key"] == "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"

    restored = AgentCard.from_dict(d)
    assert restored.did_key == "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"
    assert restored.peer_id == "12D3KooWTest"


def test_agent_card_without_p2p_extension():
    card = AgentCard(name="Simple")
    d = card.to_dict()
    assert "agentanycast" not in d
