import re

from app.models import RetrievedChunk


EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def is_email_lookup(query: str) -> bool:
    lowered = query.lower()
    markers = ["email", "e-mail", "mail id", "mailid", "mail", "contact"]
    return any(marker in lowered for marker in markers)


def is_document_field_lookup(query: str) -> bool:
    lowered = query.lower()
    markers = [
        "email",
        "e-mail",
        "mail id",
        "mailid",
        "mail",
        "contact",
        "phone",
        "mobile",
        "name",
        "profile",
        "resume",
        "cv",
    ]
    return any(marker in lowered for marker in markers)


def chunks_with_emails(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    return [chunk for chunk in chunks if EMAIL_PATTERN.search(chunk.text)]


def build_email_answer(chunks: list[RetrievedChunk]) -> str | None:
    seen: set[tuple[str, str]] = set()
    entries: list[tuple[str, str, int]] = []

    for chunk in chunks:
        for email in EMAIL_PATTERN.findall(chunk.text):
            key = (email.lower(), chunk.source)
            if key in seen:
                continue
            seen.add(key)
            entries.append((email, chunk.source, chunk.chunk_index))

    if not entries:
        return None

    if len(entries) == 1:
        email, source, chunk_index = entries[0]
        return (
            "I found this email in the uploaded document:\n\n"
            f"- {email} (source: {source}, chunk {chunk_index})"
        )

    lines = [
        f"- {email} (source: {source}, chunk {chunk_index})"
        for email, source, chunk_index in entries
    ]
    return "I found these emails in the uploaded documents:\n\n" + "\n".join(lines)

