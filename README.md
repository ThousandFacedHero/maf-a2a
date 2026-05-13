# maf-a2a

A data processing pipeline agent built with [Microsoft Agent Framework](https://github.com/microsoft/agent-framework), exposed as an [A2A](https://google.github.io/A2A/) service. Send it text via A2A's `SendMessage` and it returns a structured analysis report.

## Architecture

A single MAF agent with a three-stage `@tool` pipeline:

```
Input  -->  validate_input  -->  delegate_to_peer (optional)  -->  format_report  -->  Output
```

- **validate_input** cleans and timestamps the input text.
- **delegate_to_peer** sends a query to an external A2A agent for deeper research (when `A2A_PEER_URL` is configured).
- **format_report** produces a structured markdown report with themes, entities, analysis, and enrichment sections.

The agent is configured via `src/maf_a2a/agents.yaml`, which defines the agent's name, description, and instructions. The LLM decides when and how to use each tool based on those instructions.

### A2A Protocol

The server implements the [A2A protocol](https://google.github.io/A2A/specification/) (JSON-RPC 2.0 binding, protocol version 1.0):

- Agent card at `/.well-known/agent-card.json`
- `SendMessage` accepts text input, returns a completed task with the report as an artifact
- Task lifecycle: `SUBMITTED` -> `WORKING` -> `COMPLETED` / `FAILED`
- Health check at `/healthz`

### A2A Peer Delegation

When `A2A_PEER_URL` is set, the `delegate_to_peer` tool sends A2A JSON-RPC requests to the configured peer agent via httpx. The peer's response artifacts are extracted and incorporated into the report's enrichment section.

## Quickstart

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone and enter the repo
git clone <repo-url> maf-a2a && cd maf-a2a

# Create your environment file
cp .env.example .env
# Edit .env — set LLM_BASE_URL and LLM_API_KEY at minimum

# Install dependencies
uv sync

# Run the server
uv run python -m maf_a2a.server
```

The server starts on port 5000 (configurable via `A2A_PORT`).

### Test it

```bash
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -H "A2A-Version: 1.0" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "SendMessage",
    "params": {
      "message": {
        "role": "ROLE_USER",
        "parts": [{"text": "Analyze the impact of transformer architectures on NLP"}],
        "messageId": "msg-1"
      }
    }
  }'
```

### Docker

```bash
docker compose up --build
```

### Cross-Framework Test

To test A2A delegation between this agent and a CrewAI peer:

```bash
docker compose -f docker-compose.cross-test.yaml up --build
```

This starts both agents and a test runner that verifies bidirectional A2A delegation.

## Configuration

All configuration is via environment variables. See `.env.example` for the full list.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_BASE_URL` | Yes | | OpenAI-compatible API base URL |
| `LLM_API_KEY` | Yes | | API key for the LLM endpoint |
| `LLM_MODEL` | No | `gpt-4o` | Model name |
| `A2A_PORT` | No | `5000` | Server listen port |
| `A2A_PEER_URL` | No | | A2A peer for delegation (e.g. `http://localhost:5001`) |
| `SSL_VERIFY` | No | `true` | Set `false` for self-signed certificate environments |
| `LOG_LEVEL` | No | `INFO` | Python logging level |

## Customization

- **Agent behavior**: Edit `src/maf_a2a/agents.yaml` to change the agent's instructions and pipeline stages.
- **Pipeline tools**: Add or modify `@tool` functions in `src/maf_a2a/pipeline.py`.
- **Server**: The A2A server setup is in `src/maf_a2a/server.py`. The `MafAgentExecutor` bridges MAF's agent runtime to the a2a-sdk server stack.

## Tests

```bash
uv run pytest
```

## Project Structure

```
src/maf_a2a/
  server.py            # A2A server (Starlette + a2a-sdk)
  pipeline.py          # MAF agent with @tool pipeline stages
  config.py            # Pydantic settings
  middleware.py        # Request logging middleware
  agents.yaml          # Agent configuration
tests/
  test_server.py       # A2A server + agent card tests
  test_pipeline.py     # Pipeline tool tests
  test_config.py       # Settings tests
  test_middleware.py    # Middleware tests
  cross-framework/     # Cross-framework A2A integration tests
```

## License

MIT
