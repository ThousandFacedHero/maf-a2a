from __future__ import annotations

import logging
import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers.default_request_handler_v2 import (
    DefaultRequestHandlerV2,
)
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.types.a2a_pb2 import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Artifact,
    Part,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)

from maf_a2a.config import Settings
from maf_a2a.middleware import RequestLoggingMiddleware
from maf_a2a.pipeline import create_pipeline_agent

logger = logging.getLogger(__name__)


class MafAgentExecutor(AgentExecutor):
    """Runs the MAF pipeline agent in response to A2A message/send requests."""

    def __init__(self, settings: Settings):
        self._settings = settings

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id
        context_id = context.context_id

        text = ""
        if context.message:
            for part in context.message.parts:
                if part.text:
                    text += part.text

        await event_queue.enqueue_event(
            Task(
                id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
            )
        )

        if not text.strip():
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.TASK_STATE_FAILED),
                )
            )
            return

        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_WORKING),
            )
        )

        try:
            agent = create_pipeline_agent(self._settings)
            response = await agent.run(messages=text)

            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    artifact=Artifact(
                        artifact_id="result",
                        parts=[Part(text=response.text)],
                    ),
                    last_chunk=True,
                )
            )
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED),
                )
            )
        except Exception:
            logger.exception("Pipeline agent execution failed")
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.TASK_STATE_FAILED),
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_CANCELED),
            )
        )


def _build_agent_card(settings: Settings) -> AgentCard:
    port = settings.a2a_port
    base_url = os.getenv("A2A_PUBLIC_URL", f"http://localhost:{port}")
    return AgentCard(
        name="MAF Data Pipeline",
        description=(
            "Multi-stage data processing pipeline: intake, analyze, enrich, "
            "and report. Built on Microsoft Agent Framework."
        ),
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        skills=[
            AgentSkill(
                id="analyze-enrich",
                name="Analyze and Enrich",
                description=(
                    "Analyze input text for themes and entities, enrich with "
                    "context, produce structured report"
                ),
                tags=["analysis", "enrichment", "reporting"],
            )
        ],
        supported_interfaces=[
            AgentInterface(
                url=base_url,
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
    )


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def _make_agent_card_route(agent_card: AgentCard, base_url: str):
    from a2a.server.routes.agent_card_routes import agent_card_to_dict

    async def _get_agent_card(request: Request) -> JSONResponse:
        card_dict = agent_card_to_dict(agent_card)
        # Include top-level url for clients that haven't adopted supportedInterfaces yet
        card_dict.setdefault("url", f"{base_url}/")
        return JSONResponse(card_dict)

    return Route("/.well-known/agent-card.json", _get_agent_card, methods=["GET"])


def create_app(settings: Settings | None = None) -> Starlette:
    if settings is None:
        settings = Settings()

    agent_card = _build_agent_card(settings)
    base_url = os.getenv("A2A_PUBLIC_URL", f"http://localhost:{settings.a2a_port}")
    executor = MafAgentExecutor(settings)
    task_store = InMemoryTaskStore()

    handler = DefaultRequestHandlerV2(
        agent_executor=executor,
        task_store=task_store,
        agent_card=agent_card,
    )

    routes = [
        Route("/healthz", health, methods=["GET"]),
        _make_agent_card_route(agent_card, base_url),
        *create_jsonrpc_routes(handler, rpc_url="/"),
    ]

    app = Starlette(routes=routes)
    app.add_middleware(RequestLoggingMiddleware)

    return app


def _disable_ssl_verification():
    import httpx

    _orig_async = httpx.AsyncClient.__init__

    def _async_no_verify(self, *args, **kwargs):
        kwargs.setdefault("verify", False)
        _orig_async(self, *args, **kwargs)

    httpx.AsyncClient.__init__ = _async_no_verify


def main():
    import uvicorn

    settings = Settings()
    logging.basicConfig(level=getattr(logging, settings.log_level))
    if not settings.ssl_verify:
        _disable_ssl_verification()
    app = create_app(settings)
    uvicorn.run(app, host="0.0.0.0", port=settings.a2a_port)


if __name__ == "__main__":
    main()
