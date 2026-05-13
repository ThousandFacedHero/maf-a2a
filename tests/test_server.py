import pytest
from starlette.testclient import TestClient


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:4000/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from maf_a2a.server import create_app
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


def test_health_check(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_agent_card(client):
    resp = client.get("/.well-known/agent-card.json")
    assert resp.status_code == 200
    card = resp.json()
    assert card["name"] == "MAF Data Pipeline"
    assert "supportedInterfaces" in card
    assert "skills" in card
    assert card["capabilities"]["streaming"] is False


def test_agent_card_has_required_fields(client):
    resp = client.get("/.well-known/agent-card.json")
    card = resp.json()
    assert "defaultInputModes" in card
    assert "defaultOutputModes" in card
    assert "version" in card
    assert card["version"] == "0.1.0"
