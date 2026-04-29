# AI Copilot System

A local-first full-stack scaffold for a retrieval-augmented AI copilot with:

- FastAPI backend
- React/Vite frontend console
- OpenRouter chat and embedding adapter
- Gemini Flash-Lite fallback for chat generation
- Chroma embedded vector store
- SQLite session memory
- Explicit planner/executor agent pipeline
- RAG citations, visible agent steps, first-class traces, and JSON metrics
- Built-in evaluation dataset/report workflow
- Docker deployment scaffold with a swappable SQLite/PostgreSQL memory layer

## Project Layout

```text
backend/
  app/
    main.py
    evaluation/
    services/
  tests/
frontend/
  src/
  tests/
```

## Backend Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn app.main:app --reload --app-dir backend
```

Set these values in `.env` before calling OpenRouter-backed endpoints:

- `OPENROUTER_API_KEY`
- `OPENROUTER_CHAT_MODEL`
- `OPENROUTER_EMBEDDING_MODEL`

Optional chat fallback when OpenRouter chat generation fails:

- `GEMINI_API_KEY`
- `GEMINI_CHAT_MODEL=gemini-2.5-flash-lite`

RAG embeddings intentionally stay on `OPENROUTER_EMBEDDING_MODEL` so one Chroma collection does not mix incompatible embedding spaces.

Storage defaults to SQLite in local/dev mode. To switch memory to PostgreSQL, set:

- `ENV=prod` or `STORAGE_BACKEND=postgres`
- `POSTGRES_DSN=postgresql://postgres:postgres@postgres:5432/copilot`

## Frontend Quickstart

```powershell
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/v1`, `/health`, and `/metrics` to `http://localhost:8000`.

## API

- `POST /v1/query`
- `POST /v1/query/stream`
- `POST /v1/documents/upload`
- `GET /v1/documents`
- `GET /v1/sessions/{session_id}/history`
- `GET /v1/sessions/{session_id}/metrics`
- `GET /v1/evaluation/dataset`
- `GET /v1/evaluation/report`
- `POST /v1/evaluation/run`
- `GET /health`
- `GET /metrics`
- `GET /metrics/prometheus`

`POST /v1/query` returns the production response contract:

```json
{
  "answer": "...",
  "trace": [{"step": "retrieve", "meta": {"chunks": 3}}],
  "metrics": {
    "latency_ms": 120,
    "tokens": 450,
    "retrieval_time_ms": 40,
    "cache_hit": false
  }
}
```

`POST /v1/query/stream` returns newline-delimited JSON events:

```json
{"type":"token","text":"partial answer"}
```

Queries accept optional `filters.document_id` and `filters.section`, and uploads accept optional `session_id` for session-scoped document isolation.

Set `PRICE_PER_1K_TOKENS` to enable request and session cost tracking.

`GET /metrics` returns aggregate observability data:

```json
{
  "avg_latency": 110,
  "p95_latency": 180,
  "cache_hit_rate": 0.42,
  "scale": {
    "documents": 500,
    "chunks": 25000,
    "avg_latency_ms": 120,
    "accuracy": 0.78
  }
}
```

## Docker

```powershell
docker compose up --build
```

The backend is exposed at `http://localhost:8000`; the public API URL is reported by `/health` and `/`.

## Tests

```powershell
pytest
cd frontend
npm test
```
