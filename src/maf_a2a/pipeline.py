from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import httpx
import yaml

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient

from maf_a2a.config import Settings

logger = logging.getLogger(__name__)

_AGENTS_YAML = Path(__file__).parent / "agents.yaml"


@tool
def validate_input(text: str) -> str:
    """Validate and clean the input text. Returns the cleaned text with a timestamp, or raises an error if empty."""
    text = text.strip()
    if not text:
        raise ValueError("Input text is empty")
    timestamp = datetime.now(timezone.utc).isoformat()
    return f"[Validated at {timestamp}]\n{text}"


def _make_delegate_tool(settings: Settings):
    @tool
    async def delegate_to_peer(
        query: Annotated[str, "The research query to send to the external CrewAI research service"],
    ) -> str:
        """Send a research query to the external CrewAI service via A2A protocol.
        Use this when deeper research or multi-perspective analysis would improve the report.
        Only available when a peer service is configured."""
        if not settings.a2a_peer_url:
            return "No peer service configured — use your own knowledge to enrich."

        try:
            async with httpx.AsyncClient(verify=settings.ssl_verify) as client:
                resp = await client.post(
                    f"{settings.a2a_peer_url}/",
                    json={
                        "jsonrpc": "2.0",
                        "id": "enrich-1",
                        "method": "SendMessage",
                        "params": {
                            "message": {
                                "role": "ROLE_USER",
                                "parts": [{"text": query}],
                                "messageId": "enrich-msg-1",
                            },
                        },
                    },
                    headers={
                        "Content-Type": "application/json",
                        "A2A-Version": "1.0",
                    },
                    timeout=300,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    task = result.get("result", {}).get("task", {})
                    artifacts = task.get("artifacts", [])
                    if artifacts:
                        parts = artifacts[0].get("parts", [])
                        text_parts = [p["text"] for p in parts if p.get("text")]
                        if text_parts:
                            return "\n".join(text_parts)
                    return f"Peer returned no artifacts: {result}"
                return f"Peer returned HTTP {resp.status_code}"
        except Exception:
            logger.warning("A2A peer delegation failed, falling back to self-enrichment", exc_info=True)
            return "Peer delegation failed — use your own knowledge to enrich."

    return delegate_to_peer


@tool
def format_report(
    title: Annotated[str, "A concise title for the report"],
    themes: Annotated[str, "Comma-separated list of key themes identified"],
    entities: Annotated[str, "Comma-separated list of named entities found"],
    analysis: Annotated[str, "The detailed analysis text"],
    enrichment: Annotated[str, "Additional context, background, or research findings"],
) -> str:
    """Format the analysis results into a structured markdown report."""
    theme_list = [t.strip() for t in themes.split(",") if t.strip()]
    entity_list = [e.strip() for e in entities.split(",") if e.strip()]

    return f"""# {title}

## Key Themes
{chr(10).join(f'- {t}' for t in theme_list)}

## Entities
{chr(10).join(f'- {e}' for e in entity_list)}

## Analysis
{analysis}

## Enrichment
{enrichment}

## Metadata
- Processed: {datetime.now(timezone.utc).isoformat()}
"""


def load_agent_config() -> dict[str, Any]:
    with open(_AGENTS_YAML) as f:
        return yaml.safe_load(f)


def create_pipeline_agent(settings: Settings) -> Agent:
    config = load_agent_config()
    client = OpenAIChatClient(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )
    return Agent(
        client=client,
        name=config["name"],
        description=config["description"],
        instructions=config["instructions"],
        tools=[validate_input, _make_delegate_tool(settings), format_report],
    )
