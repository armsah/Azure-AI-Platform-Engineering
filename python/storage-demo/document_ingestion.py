import hashlib
import re
import uuid

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


MAX_DOCUMENT_BYTES = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
}


class DocumentValidationError(Exception):
    pass


class IngestionStatus(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    STORED = "stored"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class ValidatedDocument:
    document_id: str
    tenant_id: str
    filename: str
    content_type: str
    content_hash: str
    size_bytes: int
    content: bytes


def sanitize_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name

    name = re.sub(
        r"[^a-zA-Z0-9._-]",
        "_",
        name,
    )

    if not name or name in {".", ".."}:
        raise DocumentValidationError(
            "Invalid filename"
        )

    return name[:255]


def validate_document(
    tenant_id: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> ValidatedDocument:

    if not tenant_id:
        raise DocumentValidationError(
            "Tenant identity required"
        )

    safe_filename = sanitize_filename(filename)

    extension = Path(safe_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError(
            "Unsupported document extension"
        )

    if not content:
        raise DocumentValidationError(
            "Empty documents are not allowed"
        )

    if len(content) > MAX_DOCUMENT_BYTES:
        raise DocumentValidationError(
            "Document exceeds maximum size"
        )

    allowed_content_types = {
        ".txt": {"text/plain"},
        ".md": {"text/markdown", "text/plain"},
        ".pdf": {"application/pdf"},
    }

    if content_type not in allowed_content_types[extension]:
        raise DocumentValidationError(
            "Content type does not match extension"
        )

    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise DocumentValidationError(
            "Invalid PDF signature"
        )

    content_hash = hashlib.sha256(content).hexdigest()

    return ValidatedDocument(
        document_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        filename=safe_filename,
        content_type=content_type,
        content_hash=content_hash,
        size_bytes=len(content),
        content=content,
    )