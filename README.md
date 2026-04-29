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

> *(Add screenshots here for maximum impact)*

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
OPENROUTER_API_KEY=
OPENROUTER_CHAT_MODEL=
OPENROUTER_EMBEDDING_MODEL=
GEMINI_API_KEY=
PUBLIC_API_URL=
```

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

## 💼 Resume Description

**AI Copilot System (RAG + Agents)**

* Built a production-grade AI system using FastAPI with RAG-based retrieval and agent orchestration
* Implemented vector search using ChromaDB and multi-LLM fallback (OpenRouter + Gemini)
* Designed planner–executor agent pipeline with execution tracing
* Added observability (latency, tokens, cache) and evaluation pipeline
* Deployed full-stack system using Vercel (frontend) and Render (backend)

---

## 👤 Author

**Lalith Sai Kumar**

* AI / LLM Engineer
* Backend Systems + Production AI

---

## ⭐ If you like this project

Give it a star — it helps visibility!
