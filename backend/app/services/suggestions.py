import re
from pathlib import Path

from app.services.extraction import EMAIL_PATTERN


PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3,5}\)?[\s.-]?)?\d{3,5}[\s.-]?\d{4}"
)


def suggest_queries_for_document(file_name: str, text: str) -> list[str]:
    label = _document_label(file_name)
    lowered = text.lower()
    suggestions: list[str] = []

    if EMAIL_PATTERN.search(text):
        suggestions.append(f"Find the email address in {label}")
    if PHONE_PATTERN.search(text):
        suggestions.append(f"Find the phone number in {label}")
    if any(term in lowered for term in ["experience", "employment", "work history"]):
        suggestions.append(f"Extract the work experience from {label}")
    if any(term in lowered for term in ["skill", "technologies", "tools"]):
        suggestions.append(f"List the key skills from {label}")
    if any(term in lowered for term in ["education", "degree", "university", "college"]):
        suggestions.append(f"Summarize the education details in {label}")
    if any(term in lowered for term in ["project", "portfolio", "case study"]):
        suggestions.append(f"Summarize the projects in {label}")

    suggestions.append(f"Summarize {label}")
    suggestions.append(f"Extract the key facts from {label}")
    suggestions.append(f"List important follow-up questions for {label}")

    return _first_unique(suggestions, limit=3)


def _document_label(file_name: str) -> str:
    stem = Path(file_name).stem.strip()
    return stem or "this document"


def _first_unique(values: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)
        if len(result) == limit:
            break
    return result

