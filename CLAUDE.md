# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Copilot Console is a full-stack production-grade AI system combining RAG (Retrieval-Augmented Generation) and Agent-based reasoning. It features real-time streaming responses, session memory, and built-in evaluation.

**Live URLs:** Frontend: https://ai-copilot-console.vercel.app/ | Backend API: https://your-link.onrender.com (Render)

## Architecture

### Backend (FastAPI + Python)

The backend uses a **service container pattern** for dependency injection. All services are wired in `build_container()` in `backend/app/main.py` and accessed via `app.state.container`.

**Core services:**
- **Orchestrator** (`backend/app/services/orchestrator.py`) — Routes queries to LLM/RAG/Agent modes, handles caching, and builds responses with trace + metrics
- **RetrievalService** (`backend/app/services/retrieval.py`) — Hybrid search (dense + keyword) with ChromaDB, BM25-style reranking, section detection
- **AgentPipeline** (`backend/app/services/agent.py`) — Planner-executor pattern with tools: retrieval, calculator, summarize_context, extract_risks
- **ProviderFallbackClient** (`backend/app/services/llm_provider.py`) — OpenRouter (primary) with Gemini fallback, supports streaming
- **MemoryStore** (`backend/app/services/memory.py`) — Session-based conversation history (SQLite or PostgreSQL)
- **ResponseCache** (`backend/app/services/cache.py`) — Caches query responses keyed by session + query + mode + retrieval revision

**Query flow:**
```
User Query → Orchestrator.route() → LLM / RAG / AGENT
                                    ↓
                              Cache Check
                                    ↓
                              Retrieval (if RAG/Agent)
                                    ↓
                              Agent Execution (if Agent)
                                    ↓
                              LLM Response
                                    ↓
                              Metrics + Memory + Cache
```

**Query modes** (see `backend/app/models.py`):
- `auto` — Orchestrator decides based on query keywords
- `llm` — Direct generation without retrieval
- `rag` — Retrieval-augmented generation
- `agent` — Multi-step reasoning with tool usage

**Key design decisions:**
- Responses include trace steps, metrics, and citations for observability
- Cache keys include retrieval revision so cache invalidates when documents are added
- Email extraction has special-case handling in the orchestrator
- Evaluation system (`backend/app/evaluation/evaluator.py`) uses dataset-based scoring

### Frontend (React + Vite)

Single-page app in `frontend/src/App.jsx` with tabbed response display:
- **Answer** — Streaming response with citations
- **Context** — Retrieved chunks with scores
- **Trace** — Step-by-step execution trace
- **Agent Steps** — Tool execution details
- **Metrics** — Latency, tokens, cost, provider info

API integration in `frontend/src/api.js` supports both streaming (`/v1/query/stream`) and non-streaming (`/v1/query`) endpoints. Vite dev server proxies `/v1`, `/health`, `/metrics` to backend (configured in `vite.config.js`).

## Development Commands

### Backend
**Requires Python 3.11+** (see `pyproject.toml`)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"     # Installs package with dev dependencies from pyproject.toml
uvicorn app.main:app --reload
```
Backend runs on `http://127.0.0.1:8000`. Set `PYTHONPATH=backend` for running tests outside the backend directory.

**Note:** `pyproject.toml` is the authoritative dependency file. `requirements.txt` may be legacy - migrate dependencies there if needed.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Frontend runs on `http://127.0.0.1:5173` with API proxy to backend.

### Tests
```bash
# Backend tests (from project root)
pytest backend/tests/

# Single test file
pytest backend/tests/test_orchestrator.py -v

# With coverage
pytest backend/tests/ --cov=app

# Frontend tests (Vitest)
cd frontend
npm test              # Runs Vitest (configured in vite.config.js)
npm test -- --run     # Single run (CI mode)
```

### Build
```bash
cd frontend
npm run build
```

### Linting
```bash
# Backend (ruff - if installed)
ruff check backend/app/
ruff format backend/app/

# Frontend (if ESLint configured)
cd frontend
npm run lint  # Add "lint": "eslint src/" to package.json if needed
```

### Docker
```bash
# Run with docker-compose (backend + redis)
docker-compose up --build

# Run with postgres profile
docker-compose --profile postgres up

# Backend only
docker build -t ai-copilot-backend .
docker run -p 8000:8000 --env-file .env ai-copilot-backend
```

## Environment Variables

Copy `.env.example` to `.env` and configure:
- `OPENROUTER_API_KEY` + `OPENROUTER_CHAT_MODEL` + `OPENROUTER_EMBEDDING_MODEL` — Primary LLM provider
- `OPENROUTER_BASE_URL` — OpenRouter API URL (default: `https://openrouter.ai/api/v1`)
- `GEMINI_API_KEY` + `GEMINI_CHAT_MODEL` — Fallback LLM provider
- `GEMINI_BASE_URL` — Gemini API URL (default: `https://generativelanguage.googleapis.com/v1beta`)
- `CORS_ORIGINS` — Comma-separated allowed origins (default: `http://localhost:5173,http://127.0.0.1:5173`)
- `DATA_DIR` — Data directory (default: `data/`, contains ChromaDB and SQLite)
- `CHROMA_COLLECTION` — Vector store collection name (default: `knowledge_base`)
- `SQLITE_PATH` — SQLite database path (default: `data/copilot.sqlite3`)
- `STORAGE_BACKEND` — `sqlite` (default) or `postgres`
- `POSTGRES_DSN` — PostgreSQL connection string (if using postgres)
- `ENV` — `dev` or `prod` (affects CORS and storage defaults)
- `MAX_UPLOAD_MB` — Max file upload size (default: 15)
- `PUBLIC_API_URL` — Public API URL for CORS (default: `http://localhost:8000`)
- `CHUNK_SIZE` / `CHUNK_OVERLAP` — Text chunking parameters (default: 1000/150)
- `RETRIEVAL_TOP_K` — Number of chunks to retrieve (default: 5)
- `PRICE_PER_1K_TOKENS` — Cost tracking per 1k tokens (default: 0.0)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/query` | POST | Non-streaming query |
| `/v1/query/stream` | POST | Streaming query (ndjson) |
| `/v1/documents/upload` | POST | Upload document for indexing (.pdf, .txt, .md) |
| `/v1/documents` | GET | List indexed documents |
| `/v1/sessions/{id}/history` | GET | Session conversation history |
| `/v1/sessions/{id}/metrics` | GET | Per-session metrics |
| `/metrics` | GET | Aggregate metrics (JSON) |
| `/metrics/prometheus` | GET | Prometheus-format metrics |
| `/v1/evaluation/run` | POST | Run evaluation suite |
| `/v1/evaluation/dataset` | GET | View evaluation dataset |
| `/v1/evaluation/report` | GET | View evaluation report |
| `/health` | GET | Health check |

## Data Storage

- **ChromaDB**: `data/chroma/` — Vector store for document embeddings
- **SQLite**: `data/copilot.sqlite3` — Session memory and conversation history (default for dev)
- **PostgreSQL**: Optional via `STORAGE_BACKEND=postgres` and `POSTGRES_DSN`
- **Redis**: Included in docker-compose for future caching/session use (not yet integrated)
- **Evaluation**: `backend/app/evaluation/dataset.json` and `report.json`

## Deployment

- **Backend (Render):** Start command `uvicorn app.main:app --host 0.0.0.0 --port 10000`. Uses Dockerfile with `pyproject.toml` for dependencies.
- **Frontend (Vercel):** Root directory `frontend/`, build `npm run build`, output `frontend/dist`. Set env var `VITE_API_URL` to backend URL.
