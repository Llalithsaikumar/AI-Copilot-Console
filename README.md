# 🚀 AI Copilot Console

**Production-Grade RAG + Agent AI System (FastAPI + React + Vercel + Render)**

---

## 🔗 Live Demo

* 🌐 Frontend: https://ai-copilot-console.vercel.app/
* ⚙️ Backend API: https://your-link.onrender.com

---

## 🧠 Overview

AI Copilot Console is a **full-stack, production-style AI system** that combines:

* 📚 **Retrieval-Augmented Generation (RAG)**
* 🤖 **Agent-based reasoning (planner–executor)**
* ⚡ **Real-time streaming responses**
* 📊 **Observability + evaluation pipeline**

The system can ingest documents, retrieve context-aware knowledge, execute multi-step reasoning, and return **traceable, measurable outputs**.

---

## ✨ Key Features

* 🔎 **Document RAG** — semantic search with ChromaDB
* 🤖 **Agent Pipeline** — planner–executor with tool usage
* 🔌 **Multi-LLM Support** — OpenRouter (primary) + Gemini fallback
* 🧠 **Session Memory** — persistent conversation tracking
* ⚡ **Streaming Responses** — real-time token output
* 📊 **Metrics & Observability** — latency, tokens, cache, errors
* 🧪 **Evaluation System** — dataset-based scoring + report generation
* 🗂️ **Source Citations** — transparent retrieval outputs

---

## 🏗️ Architecture

```
User (Browser)
     ↓
Frontend (React + Vite on Vercel)
     ↓
FastAPI Backend (Render)
     ↓
---------------------------------
| Orchestrator Layer            |
| - Routing (LLM / RAG / Agent) |
| - Caching                     |
| - Metrics                     |
---------------------------------
     ↓
RAG Pipeline → ChromaDB (Vector Search)
     ↓
LLM Providers → OpenRouter + Gemini
     ↓
Response (Answer + Trace + Metrics)
```

---

## 🔁 Query Flow

```
User Query
   ↓
Route Selection (LLM / RAG / Agent)
   ↓
Cache Check
   ↓
Retrieval (if needed)
   ↓
Agent Execution (multi-step reasoning)
   ↓
LLM Response
   ↓
Metrics + Memory + Cache
   ↓
Return Answer + Trace
```

---

## 🧱 Tech Stack

### Backend

* **FastAPI**, Uvicorn
* **ChromaDB** (vector store)
* **SQLite / PostgreSQL-ready** (memory)
* **OpenRouter + Gemini** (LLMs)
* Docker (deployment-ready)

### Frontend

* **React 18 + Vite**
* Fetch API (backend integration)
* Minimal UI + metrics display

### Deployment

* **Vercel** (frontend)
* **Render** (backend)

---

## 📊 Example Response

```json
{
  "answer": "The document highlights financial and compliance risks...",
  "trace": [
    "retrieved 3 relevant chunks",
    "summarized content",
    "extracted risks"
  ],
  "metrics": {
    "latency_ms": 120,
    "tokens": 450,
    "cache_hit": false
  }
}
```

---

## 🧪 Evaluation System

Built-in evaluation framework to measure:

* ✔ Answer relevance
* ✔ Retrieval accuracy
* ✔ Consistency

Output:

```json
{
  "avg_score": 0.78,
  "total_cases": 50
}
```

---

## 📸 Screenshots

> <img width="1916" height="897" alt="image" src="https://github.com/user-attachments/assets/12f168ab-1bed-4687-bf21-f633cb4d00de" />


* Chat UI
* Agent trace
* Metrics panel

---

## ⚙️ Local Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload
```

Backend now requires PostgreSQL. Set `POSTGRES_DSN` before starting the API.

---

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 🔐 Environment Variables

```
POSTGRES_DSN=
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXP_HOURS=24
AUTH_COOKIE_NAME=copilot_token
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_DOMAIN=
OPENROUTER_API_KEY=
OPENROUTER_CHAT_MODEL=
OPENROUTER_EMBEDDING_MODEL=
GEMINI_API_KEY=
PUBLIC_API_URL=
```

For cross-site deployments (Vercel + Render), set `AUTH_COOKIE_SECURE=true` and
`AUTH_COOKIE_SAMESITE=none` so the browser will send the auth cookie.

## 🔐 Auth + Sessions

Flow:

1. `POST /auth/register` or `POST /auth/login`
2. `POST /v1/sessions` to create a session_id
3. Use `session_id` on query + upload requests

All core endpoints are protected; only `/health` is public.

---

## 🚀 Deployment

### Backend (Render)

* Build: `pip install -r requirements.txt`
* Start:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 10000
```

### Frontend (Vercel)

* Root: `frontend/`
* Build: `npm run build`
* Env:

```
VITE_API_URL=https://your-link.onrender.com
```

---

## ⚠️ Known Limitations

* Render free tier → cold starts
* Local storage (Chroma + SQLite) → non-persistent
* Free LLM models → variable latency

---

## 🔮 Future Improvements

* PostgreSQL + Redis (production storage)
* Hybrid retrieval + reranking
* Auth + multi-user isolation
* Cost tracking dashboard

---

## 👤 Author

**Lalith Sai Kumar**

* AI / LLM Engineer
* Backend Systems + Production AI

---

## ⭐ If you like this project

Give it a star — it helps visibility!
