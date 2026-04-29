from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from app.services.errors import UnsupportedDocumentError


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}


async def extract_text_from_upload(
    file: UploadFile,
    *,
    max_bytes: int | None = None,
) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedDocumentError(f"Unsupported file type. Allowed: {allowed}.")

    if max_bytes is not None and max_bytes > 0:
        data = await file.read(max_bytes + 1)
        if len(data) > max_bytes:
            limit_mb = max_bytes / (1024 * 1024)
            raise UnsupportedDocumentError(
                f"Uploaded document exceeds the {limit_mb:.0f} MB limit."
            )
    else:
        data = await file.read()
    if not data:
        raise UnsupportedDocumentError("Uploaded document is empty.")

    if suffix in {".txt", ".md", ".markdown"}:
        return data.decode("utf-8", errors="replace")

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise UnsupportedDocumentError(
            "PDF parsing requires pypdf to be installed."
        ) from exc

    reader = PdfReader(BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(page.strip() for page in pages if page.strip())
    if not text:
        raise UnsupportedDocumentError("No extractable text was found in the PDF.")
    return text

