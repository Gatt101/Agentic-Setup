# OrthoAssist Backend

Backend scaffold for an agentic orthopedic assistant using FastAPI, LangGraph, LangSmith, and MCP.

Supported Python version: `3.11` to `3.13`.

## Quick Start

```bash
uv sync
uvicorn main:app --reload --port 8000
```

Run MCP server (stdio):

```bash
python mcp/server.py
```

## API Endpoints

- `GET /api/health`
- `GET /api/metrics`
- `POST /api/analyze`
- `POST /api/chat`
- `POST /api/reports`
- `GET /api/reports/{report_id}`

## Notes

- Tool implementations are currently safe fallbacks and should be replaced with production model inference.
- Set `OPENAI_API_KEY` and LangSmith variables in `.env` before running agent flows.
