import os

import pytest

from maf_a2a.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:4000/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    s = Settings(_env_file=None)
    assert s.llm_base_url == "http://localhost:4000/v1"
    assert s.llm_api_key == "test-key"
    assert s.llm_model == "gpt-4o"
    assert s.a2a_port == 5000


def test_settings_requires_llm_base_url():
    clean = {k: v for k, v in os.environ.items() if not k.startswith("LLM_")}
    with pytest.raises(Exception):
        Settings(_env_file=None, **{})


def test_graphiti_disabled_by_default(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x")
    monkeypatch.setenv("LLM_API_KEY", "k")
    s = Settings()
    assert s.graphiti_enabled is False


def test_graphiti_enabled_when_uri_set(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("GRAPHITI_URI", "bolt://localhost:7687")
    s = Settings()
    assert s.graphiti_enabled is True
