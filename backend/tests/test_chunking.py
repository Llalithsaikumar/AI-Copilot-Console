from app.services.retrieval import TextChunker


def test_chunker_splits_large_text_with_overlap():
    chunker = TextChunker(chunk_size=20, chunk_overlap=5)
    chunks = chunker.chunk("abcdefghijklmnopqrstuvwxyz")

    assert len(chunks) > 1
    assert chunks[0].endswith("t")
    assert chunks[1].startswith("p")


def test_chunker_preserves_paragraph_boundaries_when_possible():
    chunker = TextChunker(chunk_size=80, chunk_overlap=10)
    chunks = chunker.chunk("First paragraph.\n\nSecond paragraph.")

    assert chunks == ["First paragraph.\n\nSecond paragraph."]

