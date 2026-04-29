import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.models import DocumentRecord, QueryFilters, RetrievedChunk
from app.services.errors import RetrievalError


@dataclass
class IngestionResult:
    document_id: str
    chunks_indexed: int
    chunks_skipped: int


class TextChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str) -> list[str]:
        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if not current:
                current = paragraph
                continue

            candidate = f"{current}\n\n{paragraph}"
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                chunks.extend(self._split_oversized(current))
                current = paragraph

        if current:
            chunks.extend(self._split_oversized(current))

        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def _split_oversized(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = max(0, end - self.chunk_overlap)
        return chunks


class RetrievalService:
    def __init__(self, settings: Settings, embedder: Any):
        self.settings = settings
        self.embedder = embedder
        self.chunker = TextChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        try:
            import chromadb
        except ImportError as exc:
            raise RetrievalError("chromadb is required for the embedded vector store.") from exc

        self._client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        self._collections: dict[str, Any] = {}

    async def add_document(
        self,
        file_name: str,
        text: str,
        *,
        user_id: str,
        session_id: str | None = None,
    ) -> IngestionResult:
        document_id = str(uuid4())
        chunks = self.chunker.chunk(text)
        if not chunks:
            raise RetrievalError("Document produced no chunks.")

        sections = self._derive_sections(chunks)
        ids: list[str] = []
        metadatas: list[dict[str, str | int | float | bool]] = []
        documents: list[str] = []
        created_at = datetime.now(timezone.utc).isoformat()
        model_name = self.embedder.embedding_model_name

        skipped = 0
        collection = self._collection_for_user(user_id)
        for index, chunk in enumerate(chunks):
            chunk_hash = self._chunk_hash(chunk, model_name, document_id, session_id)
            chunk_id = f"chunk_{chunk_hash[:40]}"
            existing = collection.get(ids=[chunk_id])
            if existing.get("ids"):
                skipped += 1
                continue

            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(
                {
                    "user_id": user_id,
                    "document_id": document_id,
                    "file_name": file_name,
                    "chunk_index": index,
                    "chunk_hash": chunk_hash,
                    "embedding_model": model_name,
                    "session_id": session_id or "",
                    "section": sections[index],
                    "created_at": created_at,
                }
            )

        if documents:
            embeddings = await self.embedder.embed(documents)
            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )

        return IngestionResult(
            document_id=document_id,
            chunks_indexed=len(documents),
            chunks_skipped=skipped,
        )

    async def retrieve(
        self,
        query: str,
        top_k: int,
        *,
        user_id: str,
        session_id: str | None = None,
        filters: QueryFilters | dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        collection = self._collection_for_user(user_id)
        if collection.count() == 0:
            return []

        candidate_k = max(top_k * 4, 20)
        where = self._build_where(user_id=user_id, session_id=session_id, filters=filters)
        query_embedding = (await self.embedder.embed([query]))[0]
        query_kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(candidate_k, max(collection.count(), 1)),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where
        result = collection.query(**query_kwargs)

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        dense_chunks: dict[str, RetrievedChunk] = {}
        dense_scores: dict[str, float] = {}
        for chunk_id, document, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
            strict=False,
        ):
            metadata = metadata or {}
            score = 1 - float(distance) if distance is not None else None
            chunk = self._to_chunk(chunk_id, document or "", metadata, score)
            dense_chunks[chunk.id] = chunk
            dense_scores[chunk.id] = score or 0.0

        keyword_chunks = self._keyword_candidates(
            query,
            self.all_chunks(user_id=user_id, session_id=session_id, filters=filters),
            candidate_k,
        )
        keyword_scores = {chunk.id: float(chunk.score or 0.0) for chunk in keyword_chunks}

        dense_norm = self._normalize_scores(dense_scores)
        keyword_norm = self._normalize_scores(keyword_scores)
        merged: dict[str, RetrievedChunk] = {}
        for chunk in [*dense_chunks.values(), *keyword_chunks]:
            dense_score = dense_norm.get(chunk.id, 0.0)
            keyword_score = keyword_norm.get(chunk.id, 0.0)
            hybrid_score = (0.7 * dense_score) + (0.3 * keyword_score)
            metadata = dict(chunk.metadata)
            metadata.update(
                {
                    "dense_score": dense_score,
                    "keyword_score": keyword_score,
                    "hybrid_score": hybrid_score,
                }
            )
            merged[chunk.id] = RetrievedChunk(
                id=chunk.id,
                text=chunk.text,
                source=chunk.source,
                chunk_index=chunk.chunk_index,
                score=hybrid_score,
                metadata=metadata,
            )

        reranked = sorted(
            merged.values(),
            key=lambda chunk: self._rerank_score(query, chunk),
            reverse=True,
        )
        final_chunks = []
        for chunk in reranked[:top_k]:
            metadata = dict(chunk.metadata)
            metadata["rerank_score"] = self._rerank_score(query, chunk)
            final_chunks.append(
                RetrievedChunk(
                    id=chunk.id,
                    text=chunk.text,
                    source=chunk.source,
                    chunk_index=chunk.chunk_index,
                    score=metadata["rerank_score"],
                    metadata=metadata,
                )
            )
        return final_chunks

    def list_documents(
        self,
        *,
        user_id: str,
        session_id: str | None = None,
    ) -> list[DocumentRecord]:
        collection = self._collection_for_user(user_id)
        where = self._build_where(user_id=user_id, session_id=session_id, filters=None)
        get_kwargs: dict[str, Any] = {"include": ["metadatas"]}
        if where:
            get_kwargs["where"] = where
        result = collection.get(**get_kwargs)
        aggregate: dict[str, dict[str, Any]] = {}
        for metadata in result.get("metadatas") or []:
            if not metadata:
                continue
            document_id = str(metadata.get("document_id", "unknown"))
            record = aggregate.setdefault(
                document_id,
                {
                    "document_id": document_id,
                    "file_name": str(metadata.get("file_name", "unknown")),
                    "chunks": 0,
                    "updated_at": str(metadata.get("created_at", "")),
                },
            )
            record["chunks"] += 1
            record["updated_at"] = max(
                str(record["updated_at"]),
                str(metadata.get("created_at", "")),
            )

        return [
            DocumentRecord(
                document_id=value["document_id"],
                file_name=value["file_name"],
                chunks=value["chunks"],
                updated_at=value["updated_at"],
            )
            for value in sorted(
                aggregate.values(),
                key=lambda item: item["updated_at"],
                reverse=True,
            )
        ]

    def all_chunks(
        self,
        *,
        user_id: str,
        session_id: str | None = None,
        filters: QueryFilters | dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        collection = self._collection_for_user(user_id)
        where = self._build_where(user_id=user_id, session_id=session_id, filters=filters)
        get_kwargs: dict[str, Any] = {"include": ["documents", "metadatas"]}
        if where:
            get_kwargs["where"] = where
        result = collection.get(**get_kwargs)
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []

        chunks: list[RetrievedChunk] = []
        for chunk_id, document, metadata in zip(
            ids,
            documents,
            metadatas,
            strict=False,
        ):
            metadata = metadata or {}
            chunks.append(self._to_chunk(chunk_id, document or "", metadata, None))
        return chunks

    def revision(self, *, user_id: str) -> int:
        return int(self._collection_for_user(user_id).count())

    @staticmethod
    def _chunk_hash(
        chunk: str,
        model_name: str,
        document_id: str = "",
        session_id: str | None = None,
    ) -> str:
        payload = f"{model_name}\n{document_id}\n{session_id or ''}\n{chunk}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _to_chunk(
        chunk_id: str,
        document: str,
        metadata: dict[str, Any],
        score: float | None,
    ) -> RetrievedChunk:
        return RetrievedChunk(
            id=chunk_id,
            text=document,
            source=str(metadata.get("file_name", "unknown")),
            chunk_index=int(metadata.get("chunk_index", 0)),
            score=score,
            metadata=dict(metadata),
        )

    def _build_where(
        self,
        *,
        user_id: str,
        session_id: str | None,
        filters: QueryFilters | dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        clauses: list[dict[str, str]] = []
        clauses.append({"user_id": user_id})
        if session_id and self._session_has_chunks(user_id, session_id):
            clauses.append({"session_id": session_id})

        document_id = self._filter_value(filters, "document_id")
        section = self._filter_value(filters, "section")
        if document_id:
            clauses.append({"document_id": document_id})
        if section:
            clauses.append({"section": section})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _session_has_chunks(self, user_id: str, session_id: str) -> bool:
        try:
            result = self._collection_for_user(user_id).get(
                where={"$and": [{"session_id": session_id}, {"user_id": user_id}]},
                include=["metadatas"],
                limit=1,
            )
        except TypeError:
            result = self._collection_for_user(user_id).get(
                where={"$and": [{"session_id": session_id}, {"user_id": user_id}]},
                include=["metadatas"],
            )
        return bool(result.get("ids"))

    def _collection_for_user(self, user_id: str) -> Any:
        if not user_id:
            raise RetrievalError("user_id is required for retrieval operations.")
        existing = self._collections.get(user_id)
        if existing is not None:
            return existing
        name = f"{self.settings.chroma_collection}_{user_id}"
        collection = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine", "user_id": user_id},
        )
        self._collections[user_id] = collection
        return collection

    @staticmethod
    def _filter_value(
        filters: QueryFilters | dict[str, Any] | None,
        key: str,
    ) -> str | None:
        if not filters:
            return None
        if isinstance(filters, dict):
            value = filters.get(key)
        else:
            value = getattr(filters, key, None)
        return str(value) if value else None

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _keyword_candidates(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        candidate_k: int,
    ) -> list[RetrievedChunk]:
        query_terms = self._tokenize(query)
        if not query_terms or not chunks:
            return []

        chunk_tokens = [self._tokenize(chunk.text) for chunk in chunks]
        doc_count = len(chunks)
        doc_freq: Counter[str] = Counter()
        for tokens in chunk_tokens:
            doc_freq.update(set(tokens))

        avg_len = sum(len(tokens) for tokens in chunk_tokens) / max(doc_count, 1)
        k1 = 1.5
        b = 0.75
        scored: list[RetrievedChunk] = []
        for chunk, tokens in zip(chunks, chunk_tokens, strict=False):
            if not tokens:
                continue
            tf = Counter(tokens)
            score = 0.0
            length_norm = k1 * (1 - b + b * (len(tokens) / max(avg_len, 1)))
            for term in query_terms:
                if tf[term] == 0:
                    continue
                idf = math.log(1 + ((doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5)))
                score += idf * ((tf[term] * (k1 + 1)) / (tf[term] + length_norm))
            if score <= 0:
                continue
            scored.append(
                RetrievedChunk(
                    id=chunk.id,
                    text=chunk.text,
                    source=chunk.source,
                    chunk_index=chunk.chunk_index,
                    score=score,
                    metadata=dict(chunk.metadata),
                )
            )
        return sorted(scored, key=lambda chunk: chunk.score or 0.0, reverse=True)[:candidate_k]

    @staticmethod
    def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
        if not scores:
            return {}
        values = list(scores.values())
        minimum = min(values)
        maximum = max(values)
        if maximum == minimum:
            return {key: 1.0 for key in scores}
        return {
            key: (value - minimum) / (maximum - minimum)
            for key, value in scores.items()
        }

    def _rerank_score(self, query: str, chunk: RetrievedChunk) -> float:
        query_terms = set(self._tokenize(query))
        chunk_terms = set(self._tokenize(chunk.text))
        coverage = len(query_terms & chunk_terms) / len(query_terms) if query_terms else 0.0
        phrase_boost = 1.0 if query.lower().strip() in chunk.text.lower() else 0.0
        hybrid_score = float(chunk.metadata.get("hybrid_score") or chunk.score or 0.0)
        return hybrid_score + (0.2 * coverage) + (0.1 * phrase_boost)

    @staticmethod
    def _derive_sections(chunks: list[str]) -> list[str]:
        sections: list[str] = []
        current = "default"
        for chunk in chunks:
            section = current
            for raw_line in chunk.splitlines()[:8]:
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    section = line.lstrip("#").strip().lower() or "default"
                    break
                if len(line) <= 80 and not line.endswith((".", "!", "?")):
                    section = line.lower()
                    break
            current = section or current
            sections.append(current or "default")
        return sections


def chunks_to_citations(chunks: list[RetrievedChunk]) -> list:
    from app.models import Citation

    return [
        Citation(
            source=chunk.source,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            score=chunk.score,
            quote=chunk.text[:280],
        )
        for chunk in chunks
    ]
