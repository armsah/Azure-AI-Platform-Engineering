import pytest

from document_ingestion import (
    DocumentValidationError,
    MAX_DOCUMENT_BYTES,
    sanitize_filename,
    validate_document,
)


def test_valid_text_document():
    document = validate_document(
        tenant_id="customer-a",
        filename="architecture.txt",
        content=b"Azure platform architecture",
        content_type="text/plain",
    )

    assert document.tenant_id == "customer-a"
    assert document.size_bytes == 27
    assert len(document.content_hash) == 64


def test_valid_markdown_document():
    document = validate_document(
        tenant_id="customer-a",
        filename="README.md",
        content=b"# Architecture",
        content_type="text/markdown",
    )

    assert document.filename == "README.md"


def test_valid_pdf_signature():
    document = validate_document(
        tenant_id="customer-a",
        filename="design.pdf",
        content=b"%PDF-1.7\nsample",
        content_type="application/pdf",
    )

    assert document.content_type == "application/pdf"


def test_rejects_unsupported_extension():
    with pytest.raises(DocumentValidationError):
        validate_document(
            "customer-a",
            "malware.exe",
            b"binary",
            "application/octet-stream",
        )


def test_rejects_empty_document():
    with pytest.raises(DocumentValidationError):
        validate_document(
            "customer-a",
            "empty.txt",
            b"",
            "text/plain",
        )


def test_rejects_oversized_document():
    with pytest.raises(DocumentValidationError):
        validate_document(
            "customer-a",
            "large.txt",
            b"x" * (MAX_DOCUMENT_BYTES + 1),
            "text/plain",
        )


def test_rejects_mime_mismatch():
    with pytest.raises(DocumentValidationError):
        validate_document(
            "customer-a",
            "notes.pdf",
            b"%PDF-1.7",
            "text/plain",
        )


def test_rejects_invalid_pdf_signature():
    with pytest.raises(DocumentValidationError):
        validate_document(
            "customer-a",
            "fake.pdf",
            b"not a pdf",
            "application/pdf",
        )


def test_sanitizes_path_traversal():
    filename = sanitize_filename(
        "../../private/secrets.txt"
    )

    assert filename == "secrets.txt"


def test_rejects_missing_tenant():
    with pytest.raises(DocumentValidationError):
        validate_document(
            "",
            "notes.txt",
            b"hello",
            "text/plain",
        )