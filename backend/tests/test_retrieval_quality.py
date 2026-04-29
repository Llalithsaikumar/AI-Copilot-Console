import asyncio

from app.models import QueryFilters
from app.services.retrieval import RetrievalService


class FakeEmbedder:
    embedding_model_name = "fake"

    async def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class FakeCollection:
    def __init__(self, items):
        self.items = items

    def count(self):
        return len(self.items)

    def query(self, query_embeddings, n_results, include, where=None):
        rows = [item for item in self.items if self._matches(item["metadata"], where)]
        rows = sorted(rows, key=lambda item: item["distance"])[:n_results]
        return {
            "ids": [[item["id"] for item in rows]],
            "documents": [[item["text"] for item in rows]],
            "metadatas": [[item["metadata"] for item in rows]],
            "distances": [[item["distance"] for item in rows]],
        }

    def get(self, include=None, where=None, limit=None):
        rows = [item for item in self.items if self._matches(item["metadata"], where)]
        if limit is not None:
            rows = rows[:limit]
        return {
            "ids": [item["id"] for item in rows],
            "documents": [item["text"] for item in rows],
            "metadatas": [item["metadata"] for item in rows],
        }

    def _matches(self, metadata, where):
        if not where:
            return True
        if "$and" in where:
            return all(self._matches(metadata, clause) for clause in where["$and"])
        return all(metadata.get(key) == value for key, value in where.items())


def build_service(items):
    service = RetrievalService.__new__(RetrievalService)
    service.embedder = FakeEmbedder()
    service._collections = {"user-1": FakeCollection(items)}
    service._collection_for_user = lambda user_id: service._collections[user_id]
    return service


def item(chunk_id, text, document_id, section, session_id, distance):
    return {
        "id": chunk_id,
        "text": text,
        "distance": distance,
        "metadata": {
            "user_id": "user-1",
            "file_name": f"{document_id}.md",
            "document_id": document_id,
            "section": section,
            "session_id": session_id,
            "chunk_index": int(chunk_id[-1]),
        },
    }


def test_hybrid_retrieval_reranks_keyword_relevant_chunk():
    service = build_service(
        [
            item("chunk-1", "general launch overview", "doc1", "intro", "s1", 0.05),
            item("chunk-2", "compliance risk and financial exposure", "doc1", "risks", "s1", 0.10),
            item("chunk-3", "timeline notes", "doc1", "plan", "s1", 0.15),
        ]
    )

    chunks = asyncio.run(
        service.retrieve("compliance risk", top_k=1, user_id="user-1", session_id="s1")
    )

    assert chunks[0].id == "chunk-2"
    assert chunks[0].metadata["keyword_score"] > 0
    assert "rerank_score" in chunks[0].metadata


def test_retrieval_filters_by_document_section_and_session():
    service = build_service(
        [
            item("chunk-1", "risk in session one", "doc1", "risks", "s1", 0.1),
            item("chunk-2", "risk in session two", "doc1", "risks", "s2", 0.1),
            item("chunk-3", "risk in another document", "doc2", "risks", "s1", 0.1),
            item("chunk-4", "summary section", "doc1", "summary", "s1", 0.1),
        ]
    )

    chunks = asyncio.run(
        service.retrieve(
            "risk",
            top_k=10,
            user_id="user-1",
            session_id="s1",
            filters=QueryFilters(document_id="doc1", section="risks"),
        )
    )

    assert [chunk.id for chunk in chunks] == ["chunk-1"]
