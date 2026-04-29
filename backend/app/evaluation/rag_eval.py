from app.models import RetrievedChunk


def _chunk_id(chunk: str | RetrievedChunk) -> str:
    if isinstance(chunk, RetrievedChunk):
        return chunk.id
    return str(chunk)


def retrieval_score(
    retrieved_chunks: list[str | RetrievedChunk],
    expected_chunks: list[str],
) -> float:
    if not expected_chunks:
        return 1.0
    retrieved_ids = {_chunk_id(chunk) for chunk in retrieved_chunks}
    expected_ids = set(expected_chunks)
    overlap = len(retrieved_ids & expected_ids)
    return overlap / len(expected_ids)
