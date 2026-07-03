# AI Copilot Console - Project Report

Generated from the current codebase on 2026-05-06.

## 1. Executive Summary

AI Copilot Console is a full-stack AI application that combines a React/Vite frontend with a FastAPI backend. The product acts as an authenticated AI workspace where users can upload documents, ask questions, receive streaming answers, inspect retrieved context, view reasoning traces, review agent steps, and track usage metrics.

The system is designed around Retrieval-Augmented Generation (RAG), direct LLM responses, and a lightweight agent pipeline. It supports session memory, document indexing, hybrid retrieval, response caching, metrics collection, and Clerk-based authentication.

Production deployment is split across:

- Frontend: Vercel at `https://ai-copilot-console.vercel.app/`
- Backend: Render at `https://ai-copilot-console.onrender.com`

## 2. Project Goals

The project appears to target the following goals:

- Provide an AI copilot interface for document-aware question answering.
- Allow authenticated users to upload PDFs, text, and Markdown files.
- Index uploaded documents into a persistent vector store.
- Support multiple response modes: direct LLM, RAG, and agent.
- Stream answers to the frontend for a responsive user experience.
- Maintain per-user session history.
- Expose observability through traces, citations, metrics, and Prometheus output.
- Support local development and cloud deployment.

## 3. High-Level Architecture

The application uses a classic client-server architecture:

```text
Browser
  |
  | React/Vite SPA
  | Clerk auth token
  v
Vercel Frontend
  |
  | HTTPS API calls with Authorization: Bearer <Clerk JWT>
  v
Render FastAPI Backend
  |
  | Service container
  v
Backend Services
  |
  |-- Auth: Clerk JWT validation
  |-- Orchestrator: mode routing, cache, memory, trace
  |-- LLM Provider: OpenRouter primary, Gemini fallback
  |-- Retrieval: ChromaDB vector store plus keyword scoring
  |-- Agent: planner, tools, synthesis
  |-- Memory: SQLite or PostgreSQL
  |-- Metrics: in-memory metrics and Prometheus rendering
  v
Persistent Data
  |-- ChromaDB document vectors
  |-- SQLite/PostgreSQL conversation turns
```

## 4. Technology Stack

### Frontend

| Area | Technology |
| --- | --- |
| Framework | React 18 |
| Build tool | Vite 6 |
| Language | JavaScript / JSX |
| Auth UI and auth token provider | Clerk React |
| Icons | lucide-react |
| Markdown rendering | react-markdown, remark-gfm |
| Toast notifications | sonner |
| Routing dependency | react-router-dom |
| Tests | Vitest, Testing Library, jsdom |
| Deployment target | Vercel |

### Backend

| Area | Technology |
| --- | --- |
| Framework | FastAPI |
| ASGI server | Uvicorn |
| Runtime language | Python 3.11+ |
| Data validation | Pydantic v2 |
| Settings | pydantic-settings |
| HTTP client | httpx |
| Auth/JWT | PyJWT with crypto extra |
| Vector database | ChromaDB persistent client |
| PDF extraction | pypdf |
| Database options | SQLite, PostgreSQL through psycopg |
| Tests | pytest |
| Deployment target | Render |

### AI and Retrieval

| Area | Implementation |
| --- | --- |
| Primary LLM provider | OpenRouter |
| Fallback LLM provider | Gemini |
| Streaming | OpenRouter streaming API, Gemini fallback simulated by word chunks |
| Embeddings | OpenRouter embedding model or Gemini embedding fallback |
| Retrieval storage | ChromaDB |
| Retrieval method | Dense vector search plus keyword candidates and reranking |
| Agent tools | Retrieval, calculator, summarize context, extract risks |

## 5. Repository Structure

Important project directories and files:

```text
AI-Copilot-Console/
  README.md
  pyproject.toml
  .env.example
  report.md

  backend/
    requirements.txt
    app/
      main.py
      config.py
      auth.py
      models.py
      services/
        orchestrator.py
        retrieval.py
        agent.py
        llm_provider.py
        memory.py
        metrics.py
        cache.py
        document_loader.py
        suggestions.py
        extraction.py
        errors.py
      evaluation/
        evaluator.py
        dataset.json
        report.json
    tests/

  frontend/
    package.json
    vite.config.js
    src/
      App.jsx
      main.jsx
      styles.css
      hooks/
        useApi.js
      lib/
        apiClient.js
        accountStorage.js
        hashQuery.js
        idbCache.js
        lruCache.js
      components/
        AppHeader.jsx
        Sidebar.jsx
        QueryInput.jsx
        ResponsePanel.jsx
        ModeSelector.jsx
        MetricsCard.jsx
        ConfirmModal.jsx
```

## 6. Backend Architecture

### 6.1 FastAPI Application Entry Point

The backend entry point is `backend/app/main.py`.

Responsibilities:

- Creates the FastAPI application.
- Builds a service container.
- Registers CORS middleware.
- Registers exception handlers.
- Defines API routes for health, metrics, queries, documents, sessions, and evaluation.

The application uses a service container pattern:

```python
@dataclass
class ServiceContainer:
    settings: Settings
    llm: ProviderFallbackClient
    retriever: RetrievalService
    memory: MemoryStore
    cache: ResponseCache
    metrics: MetricsRecorder
    agent: AgentPipeline
    orchestrator: Orchestrator
```

This container is built once at startup and stored on `app.state.container`.

### 6.2 Settings and Configuration

Settings are defined in `backend/app/config.py` using `BaseSettings` from `pydantic-settings`.

Important configuration areas:

- App environment: `ENV`
- Public backend URL: `PUBLIC_API_URL`
- CORS allowed origins: `CORS_ORIGINS`
- Data paths: `DATA_DIR`, `SQLITE_PATH`
- Storage backend: `STORAGE_BACKEND`, `POSTGRES_DSN`
- ChromaDB collection: `CHROMA_COLLECTION`
- LLM provider keys and models
- Upload limits
- Retrieval chunking settings
- Clerk JWT validation settings

CORS is configured through:

```python
settings.cors_origin_list
```

For production, Render should include:

```text
CORS_ORIGINS=https://ai-copilot-console.vercel.app
```

### 6.3 Authentication and Authorization

Authentication is implemented in `backend/app/auth.py`.

The backend expects every protected API request to include:

```text
Authorization: Bearer <Clerk JWT>
```

The account ID is derived from the JWT `sub` claim. This is an important security design choice because the account identity is not trusted from request bodies or frontend state.

Key behavior:

- If `AUTH_DISABLED=true`, the backend returns `DEV_ACCOUNT_ID`. This is intended for tests only.
- If `CLERK_JWKS_URL` is configured, the backend verifies the Clerk JWT using `PyJWKClient`.
- In `dev`, if JWKS is missing, it can decode an unverified local JWT `sub` for developer convenience.
- In non-dev environments, missing JWT configuration returns a 503.
- Invalid or expired tokens return 401.
- Session ownership is enforced by requiring session IDs to start with `{account_id}:`.

### 6.4 CORS

CORS is handled by Starlette/FastAPI `CORSMiddleware` in `main.py`.

Current design:

- Uses `get_settings().cors_origin_list` through `app.state.container.settings`.
- Allows credentials.
- Allows all methods and headers.
- Relies on Starlette's built-in preflight behavior.

This is the correct pattern because a custom `@app.options` route can interfere with automatic browser preflight handling.

### 6.5 API Models

API request and response schemas live in `backend/app/models.py`.

Important models:

- `QueryRequest`
- `QueryResponse`
- `ResponseMetrics`
- `RetrievedChunk`
- `Citation`
- `AgentStep`
- `TraceStep`
- `DocumentUploadResponse`
- `DocumentRecord`
- `HistoryResponse`
- `SessionMetricsResponse`
- `SessionSummary`

Supported query modes:

```text
auto
llm
rag
agent
```

### 6.6 Orchestrator

The orchestrator is implemented in `backend/app/services/orchestrator.py`.

It is the central brain of the backend.

Responsibilities:

- Routes each query to the correct mode.
- Pulls recent conversation history from memory.
- Builds cache keys.
- Checks and writes response cache.
- Runs retrieval when needed.
- Runs the agent pipeline when needed.
- Calls the LLM provider for generation.
- Handles streaming token callbacks.
- Builds citations, traces, and metrics.
- Persists conversation turns.
- Returns structured `QueryResponse` objects.

Routing logic:

- Explicit mode wins if the user chooses `llm`, `rag`, or `agent`.
- Document field lookups route to RAG when documents exist.
- Multi-step or tool-like queries route to agent.
- Context/document-related queries route to RAG.
- If indexed documents exist and the query is not small talk, the system prefers RAG.
- Small talk or direct generation routes to LLM.

### 6.7 Retrieval System

Retrieval is implemented in `backend/app/services/retrieval.py`.

Major components:

- `TextChunker`
- `RetrievalService`
- `chunks_to_citations`

Document ingestion:

1. Text is extracted from uploaded file.
2. Text is split into chunks.
3. Sections are derived from headings or short title-like lines.
4. Chunk metadata is created.
5. Embeddings are generated.
6. Chunks and embeddings are stored in ChromaDB.

Chunk metadata includes:

- `account_id`
- `document_id`
- `file_name`
- `chunk_index`
- `chunk_hash`
- `embedding_model`
- `session_id`
- `section`
- `created_at`
- `file_size_bytes`
- `mime_type`
- `ingest_status`

Retrieval flow:

```text
User query
  |
  |-- Dense vector search through ChromaDB
  |-- Keyword candidate scoring
  |-- Score normalization
  |-- Hybrid score = 0.7 dense + 0.3 keyword
  |-- Reranking with query-term coverage and phrase boost
  v
Top chunks returned as RetrievedChunk records
```

The retriever filters by account ID and can also filter by session, document ID, or section.

### 6.8 LLM Provider Layer

The LLM provider abstraction is implemented in `backend/app/services/llm_provider.py`.

Main classes:

- `OpenRouterClient`
- `GeminiClient`
- `ProviderFallbackClient`
- `LLMResponse`

OpenRouter is the primary provider. It supports:

- Chat completions
- Streaming chat completions
- Embeddings
- Retry behavior for transient failures
- Model fallback candidates

Gemini is the fallback provider. It supports:

- Chat generation
- Simulated streaming from a full completion
- Batch embeddings

`ProviderFallbackClient` attempts OpenRouter first and falls back to Gemini when configuration or provider errors occur.

### 6.9 Agent Pipeline

The agent system is implemented in `backend/app/services/agent.py`.

Main components:

- `AgentPlanner`
- `AgentPipeline`
- `SafeCalculator`
- `AgentRun`

Available tools:

- `retrieval`
- `calculator`
- `summarize_context`
- `extract_risks`
- `db` placeholder

Agent flow:

```text
Query
  |
  v
Planner chooses tool steps
  |
  v
Each tool executes and records AgentStep
  |
  v
LLM synthesizes final answer using retrieved context and tool results
```

The calculator uses Python AST parsing and only supports arithmetic operations, which is safer than evaluating arbitrary code.

### 6.10 Memory Store

Memory is implemented in `backend/app/services/memory.py`.

The backend supports two memory storage implementations:

- `SQLiteMemoryStore`
- `PostgresMemoryStore`

The selected backend is controlled by:

```text
STORAGE_BACKEND=sqlite|postgres
```

If no backend is specified:

- `ENV=prod` defaults to PostgreSQL.
- Other environments default to SQLite.

The memory store persists conversation turns with:

- Account ID
- Session ID
- User input
- System response
- Query mode
- Request ID
- Metadata JSON
- Created timestamp

The metadata includes metrics, citations, trace steps, and retrieved chunks.

### 6.11 Response Cache

Server-side response caching is implemented in `backend/app/services/cache.py`.

Characteristics:

- In-memory LRU-style cache using `OrderedDict`.
- Default max entries: 256.
- Default TTL: 900 seconds.
- Cache key is generated using SHA-256 over query/session/mode/context/filter/retrieval revision data.

Including retrieval revision in the cache key helps invalidate stale answers when documents change.

### 6.12 Metrics and Observability

Metrics are implemented in `backend/app/services/metrics.py`.

The backend records:

- HTTP request counts by endpoint/status.
- Query counts by mode.
- Query latency.
- Retrieval latency.
- Token counts.
- Cost totals.
- Cache hit rate.
- Error counts.
- Session-level totals.
- Latest evaluation accuracy.

Metrics are exposed through:

- `/metrics` as JSON.
- `/metrics/prometheus` as Prometheus text format.

Responses also include rich observability payloads:

- `trace`
- `metrics`
- `citations`
- `retrieved_chunks`
- `agent_steps`

### 6.13 Document Loading

Document extraction is implemented in `backend/app/services/document_loader.py`.

Supported extensions:

- `.pdf`
- `.txt`
- `.md`
- `.markdown`

Upload safety:

- Rejects unsupported file types.
- Rejects empty files.
- Enforces `MAX_UPLOAD_MB`.
- Uses `pypdf` for PDF text extraction.

## 7. Frontend Architecture

### 7.1 Application Entry

The main UI is implemented in `frontend/src/App.jsx`.

The app uses Clerk to split signed-out and signed-in states:

- Signed out: login screen with `SignIn`.
- Signed in: main AI console workspace.

Main UI areas:

- Sidebar
- Header
- Query input
- Mode selector
- Response panel
- Confirmation modal
- Toast notifications

### 7.2 API Client

API concerns are split between:

- `frontend/src/lib/apiClient.js`
- `frontend/src/hooks/useApi.js`

`apiClient.js` handles:

- Backend base URL resolution.
- JWT parsing helper.
- Authenticated fetch wrapper.
- Error normalization.

`useApi.js` handles:

- Clerk `getToken()`.
- Session ID generation.
- Query requests.
- Streaming query requests.
- Document upload.
- Document listing and deletion.
- Session listing, history, deletion, and metrics.

All API calls use:

```text
Authorization: Bearer <token>
```

If Clerk does not return a token, the API helper throws an authentication error before making the backend request.

### 7.3 Streaming Response Handling

The backend returns streaming responses as newline-delimited JSON from:

```text
POST /v1/query/stream
```

The frontend reads the stream through:

```javascript
response.body.getReader()
```

It decodes chunks with `TextDecoder`, buffers incomplete lines, parses JSON events, and handles:

- `token`
- `final`
- `error`

This gives the user incremental answer rendering while still receiving the final structured response.

### 7.4 Frontend State Management

The app uses React local state and refs instead of a global state library.

Important state areas:

- Current user/account ID.
- Current session ID.
- Session list.
- Uploaded documents.
- Conversation history.
- Query text.
- Selected query mode.
- Current response.
- Metrics snapshot.
- Upload and query loading states.
- Error messages.
- Suggested queries.
- Confirmation modal state.

### 7.5 Client-Side Caching

The frontend uses two caching layers:

1. In-memory LRU cache from `frontend/src/lib/lruCache.js`.
2. IndexedDB persisted cache from `frontend/src/lib/idbCache.js`.

Cache keys are generated from:

- Session ID
- Mode
- Normalized query text

The app can:

- Serve repeated answers from memory cache.
- Serve older answers from IndexedDB.
- Clear in-memory cache.
- Clear persisted account cache.
- Invalidate cached entries related to deleted documents.

### 7.6 Local Account Session Registry

`frontend/src/lib/accountStorage.js` stores lightweight session metadata in `localStorage`.

Stored data includes:

- Active session ID.
- Session registry per account.
- Last active timestamp.
- Last query preview.
- Mode.

Server-side history remains the source of truth for actual conversation turns.

### 7.7 Vite Development Server

`frontend/vite.config.js` configures:

- React plugin.
- Environment directory as project root.
- Dev server port `5173`.
- Proxy routes for backend endpoints.
- Vitest with jsdom setup.

Development proxy targets:

```text
http://127.0.0.1:8000
```

## 8. Request and Data Flows

### 8.1 Authenticated Query Flow

```text
User submits query
  |
  v
React App builds payload
  |
  v
useApi gets Clerk token
  |
  v
fetchWithAuth adds Authorization header
  |
  v
FastAPI validates Clerk JWT
  |
  v
Session ownership check
  |
  v
Orchestrator routes query
  |
  |-- LLM
  |-- RAG
  |-- Agent
  v
Response streamed or returned
  |
  v
Frontend renders answer, citations, trace, metrics
```

### 8.2 Document Upload Flow

```text
User uploads file
  |
  v
Frontend sends FormData with Clerk token
  |
  v
Backend validates auth and optional session ownership
  |
  v
Document loader extracts text
  |
  v
Retriever chunks text and derives sections
  |
  v
Embedding provider creates vectors
  |
  v
ChromaDB stores chunks, embeddings, metadata
  |
  v
Frontend receives upload status and suggested queries
```

### 8.3 RAG Query Flow

```text
Query
  |
  v
Route decision = rag
  |
  v
Retrieve top chunks from ChromaDB plus keyword candidates
  |
  v
Build prompt with retrieved context
  |
  v
Call LLM provider
  |
  v
Return answer with citations, chunks, trace, and metrics
```

### 8.4 Agent Query Flow

```text
Query
  |
  v
Route decision = agent
  |
  v
Retrieve initial context if needed
  |
  v
Planner chooses tools
  |
  v
Tools execute and emit AgentStep records
  |
  v
LLM synthesizes final answer
  |
  v
Return answer, context, tool steps, trace, and metrics
```

## 9. API Endpoints

| Endpoint | Method | Auth | Description |
| --- | --- | --- | --- |
| `/` | GET | No | Basic API info |
| `/health` | GET | No | Health and provider configuration status |
| `/metrics` | GET | No | JSON aggregate metrics |
| `/metrics/prometheus` | GET | No | Prometheus metrics |
| `/v1/query` | POST | Yes | Non-streaming AI query |
| `/v1/query/stream` | POST | Yes | Streaming AI query with NDJSON |
| `/v1/documents/upload` | POST | Yes | Upload and index a document |
| `/v1/documents` | GET | Yes | List account/session documents |
| `/v1/documents/{document_id}` | DELETE | Yes | Delete indexed document chunks |
| `/v1/sessions` | GET | Yes | List user sessions |
| `/v1/sessions/{session_id}/history` | GET | Yes | Get session history |
| `/v1/sessions/{session_id}` | DELETE | Yes | Delete server-side session turns |
| `/v1/sessions/{session_id}/metrics` | GET | Yes | Get session metrics |
| `/v1/evaluation/dataset` | GET | No | Return evaluation dataset |
| `/v1/evaluation/report` | GET | No | Return latest evaluation report |
| `/v1/evaluation/run` | POST | Yes | Run evaluation suite |

## 10. Environment Variables

### Backend

| Variable | Purpose |
| --- | --- |
| `ENV` | Runtime environment, such as `dev` or `prod` |
| `PUBLIC_API_URL` | Public backend URL |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `DATA_DIR` | Base data directory |
| `SQLITE_PATH` | SQLite DB path |
| `STORAGE_BACKEND` | `sqlite` or `postgres` |
| `POSTGRES_DSN` | PostgreSQL connection string |
| `CHROMA_COLLECTION` | ChromaDB collection name |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `OPENROUTER_CHAT_MODEL` | Primary OpenRouter chat model |
| `OPENROUTER_CHAT_FALLBACK_MODELS` | Additional OpenRouter model fallback list |
| `OPENROUTER_EMBEDDING_MODEL` | OpenRouter embedding model |
| `OPENROUTER_BASE_URL` | OpenRouter API base URL |
| `OPENROUTER_APP_TITLE` | App title sent to OpenRouter |
| `OPENROUTER_HTTP_REFERER` | Referer sent to OpenRouter |
| `GEMINI_API_KEY` | Gemini API key |
| `GEMINI_CHAT_MODEL` | Gemini fallback chat model |
| `GEMINI_EMBEDDING_MODEL` | Gemini fallback embedding model |
| `GEMINI_BASE_URL` | Gemini API base URL |
| `MAX_UPLOAD_MB` | Upload size limit |
| `PRICE_PER_1K_TOKENS` | Cost estimation setting |
| `CLERK_JWKS_URL` | Clerk JWKS endpoint |
| `CLERK_ISSUER` | Clerk issuer |
| `AUTH_DISABLED` | Test/local bypass only |
| `DEV_ACCOUNT_ID` | Local fallback account ID |

### Frontend

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | Production backend API base URL |
| `VITE_API_URL` | Backward-compatible backend API base URL |
| `VITE_CLERK_PUBLISHABLE_KEY` | Clerk frontend publishable key |

Recommended production values:

```text
CORS_ORIGINS=https://ai-copilot-console.vercel.app
VITE_API_BASE_URL=https://ai-copilot-console.onrender.com
```

## 11. Deployment Architecture

### Frontend on Vercel

Expected configuration:

- Root directory: `frontend`
- Install command: `npm install`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variables:
  - `VITE_API_BASE_URL`
  - `VITE_CLERK_PUBLISHABLE_KEY`

### Backend on Render

Expected configuration:

- Runtime: Python/FastAPI
- Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 10000
```

Important Render environment variables:

- `CORS_ORIGINS=https://ai-copilot-console.vercel.app`
- `PUBLIC_API_URL=https://ai-copilot-console.onrender.com`
- Clerk JWT settings
- OpenRouter and/or Gemini provider settings
- Storage settings

## 12. Security Design

Security controls currently present:

- Clerk JWT required for protected routes.
- Account ID derived from token `sub`.
- Session ownership enforced by session ID prefix.
- CORS restricted through `CORS_ORIGINS`.
- Upload file extensions are restricted.
- Upload size is limited.
- Calculator agent tool avoids arbitrary `eval`.
- Backend never trusts frontend-provided account IDs for auth decisions.

Security areas to continue improving:

- Ensure all production routes that expose sensitive user data remain protected.
- Avoid `AUTH_DISABLED=true` outside test environments.
- Configure Clerk JWKS in production.
- Use HTTPS-only production URLs.
- Consider rate limiting.
- Consider per-user upload quotas.
- Consider virus scanning for uploaded files if accepting untrusted files.
- Consider persistent server-side cache invalidation if multiple backend instances are used.

## 13. Testing

### Backend Tests

Backend tests live in:

```text
backend/tests/
```

Covered areas include:

- Authentication
- Streaming API
- Retrieval quality
- Orchestrator behavior
- Metrics
- Memory
- LLM provider behavior
- Evaluation
- Chunking
- Agent behavior
- Suggestions

Run from the project root:

```bash
pytest backend/tests/
```

### Frontend Tests

Frontend tests use Vitest and Testing Library.

Run from `frontend/`:

```bash
npm test
```

The Vite test environment is configured with jsdom.

## 14. Strengths

- Clear backend service separation.
- Strong typed API contracts with Pydantic.
- Practical service container pattern.
- Clerk authentication is integrated into frontend and backend.
- RAG is more than basic vector search because it includes keyword candidates and reranking.
- Responses expose citations, metrics, traces, and agent steps.
- Supports streaming for better user experience.
- Supports both SQLite and PostgreSQL memory stores.
- Has an evaluation subsystem.
- Has both server-side and client-side caching.
- Uses provider fallback to reduce LLM outage risk.

## 15. Current Limitations and Risks

- Server-side cache is in-memory, so it is not shared across multiple backend instances.
- Metrics are in-memory, so they reset on process restart.
- ChromaDB is local persistent storage by default; cloud deployments need careful volume/storage configuration.
- Gemini streaming is simulated from a complete response rather than true token streaming.
- Agent planning is rule-based, not model-planned.
- There is a `db` tool placeholder, but no real database tool is configured for agent runs.
- Some README text references `frontend/src/api.js`, while the actual implementation uses `frontend/src/hooks/useApi.js` and `frontend/src/lib/apiClient.js`.
- If production uses PostgreSQL by default, `POSTGRES_DSN` must be configured or startup can fail.
- JWT verification depends on correct Clerk JWKS and issuer settings.

## 16. Suggested Future Improvements

High-value engineering improvements:

- Add rate limiting for authenticated API routes.
- Add structured logging with request IDs.
- Persist metrics to a database or observability platform.
- Add OpenTelemetry tracing end to end.
- Add pagination to sessions, documents, and history endpoints.
- Add file upload progress UI.
- Add background document ingestion for large files.
- Add richer document metadata and document-level permissions.
- Add integration tests for production CORS and Clerk-authenticated API calls.
- Add CI workflows for backend and frontend tests.
- Add linting and formatting scripts.
- Update README to reference the current frontend API files.
- Consider using a shared Redis cache for multi-instance deployment.

## 17. Conclusion

AI Copilot Console is a solid full-stack AI application with a production-oriented backend architecture and a practical frontend console experience. The backend is organized around composable services for auth, orchestration, retrieval, memory, metrics, caching, and LLM provider fallback. The frontend provides authenticated API access, streaming responses, local and persisted caching, session management, and a multi-panel response inspection experience.

The most important production requirements are correct environment configuration, especially Clerk JWT settings, CORS origins, backend API URL, and provider keys. With those configured, the system is well-positioned as a document-aware AI assistant that can support direct LLM answers, RAG workflows, and lightweight tool-using agent workflows.
