import httpx
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agent_framework import Agent
from maf_a2a.pipeline import (
    validate_input,
    format_report,
    _make_delegate_tool,
    load_agent_config,
    create_pipeline_agent,
)


class TestValidateInput:
    def test_returns_cleaned_text(self):
        result = validate_input.func("  hello world  ")
        assert "hello world" in result
        assert "[Validated at" in result

    def test_rejects_empty_input(self):
        with pytest.raises(ValueError, match="empty"):
            validate_input.func("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValueError, match="empty"):
            validate_input.func("   ")


class TestFormatReport:
    def test_formats_structured_report(self):
        result = format_report.func(
            title="Test Report",
            themes="AI, safety",
            entities="GPT, OpenAI",
            analysis="This is the analysis.",
            enrichment="Additional context here.",
        )
        assert "# Test Report" in result
        assert "- AI" in result
        assert "- safety" in result
        assert "- GPT" in result
        assert "- OpenAI" in result
        assert "This is the analysis." in result
        assert "Additional context here." in result
        assert "Processed:" in result

    def test_handles_single_theme(self):
        result = format_report.func(
            title="Single",
            themes="AI",
            entities="GPT",
            analysis="a",
            enrichment="b",
        )
        assert "- AI" in result


class TestDelegateToPeer:
    async def test_returns_message_when_no_peer(self, mock_settings):
        delegate = _make_delegate_tool(mock_settings)
        result = await delegate.func("test query")
        assert "No peer service configured" in result

    async def test_calls_peer_when_configured(self, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "http://localhost:4000/v1")
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setenv("A2A_PEER_URL", "http://crewai:5000")
        from maf_a2a.config import Settings
        settings = Settings()
        delegate = _make_delegate_tool(settings)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "task": {
                    "status": {"state": "TASK_STATE_COMPLETED"},
                    "artifacts": [{"parts": [{"text": "Research from CrewAI"}]}],
                }
            }
        }

        with patch("maf_a2a.pipeline.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await delegate.func("research AI safety")
            assert "Research from CrewAI" in result

    async def test_falls_back_on_peer_failure(self, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "http://localhost:4000/v1")
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setenv("A2A_PEER_URL", "http://crewai:5000")
        from maf_a2a.config import Settings
        settings = Settings()
        delegate = _make_delegate_tool(settings)

        with patch("maf_a2a.pipeline.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await delegate.func("research AI safety")
            assert "failed" in result.lower()


class TestAgentConfig:
    def test_loads_agent_yaml(self):
        config = load_agent_config()
        assert config["name"] == "MAF Data Pipeline"
        assert "instructions" in config
        assert "description" in config

    def test_creates_agent_with_correct_name(self, mock_settings):
        agent = create_pipeline_agent(mock_settings)
        assert isinstance(agent, Agent)
        assert agent.name == "MAF Data Pipeline"
