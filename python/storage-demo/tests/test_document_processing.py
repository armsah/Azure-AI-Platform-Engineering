import hashlib

import pytest

from document_chunking import (
    DocumentChunk,
    ChunkingError,
    chunk_document,
)
from document_embeddings import (
    EmbeddingError,
    embed_chunks,
)
from document_extraction import (
    DocumentExtractionError,
    extract_text,
)


class FakeEmbeddingProvider:
    def embed(self, texts):
        return [
            [0.1, 0.2, 0.3]
            for _ in texts
        ]


def make_chunk(tenant_id="customer-a"):
    return DocumentChunk(
        chunk_id="chunk-1",
        tenant_id=tenant_id,
        document_id="doc-1",
        content_hash="hash-1",
        chunk_index=0,
        text="Azure platform architecture",
    )


def test_extract_text():
    result = extract_text(
        b"Hello Azure",
        "text/plain",
    )

    assert result == "Hello Azure"


def test_extract_markdown():
    result = extract_text(
        b"# Platform\n\nArchitecture",
        "text/markdown",
    )

    assert "Architecture" in result


def test_reject_invalid_utf8():
    with pytest.raises(DocumentExtractionError):
        extract_text(
            b"\xff\xfe",
            "text/plain",
        )


def test_reject_empty_extraction():
    with pytest.raises(DocumentExtractionError):
        extract_text(
            b"  \n ",
            "text/plain",
        )


def test_reject_unsupported_content_type():
    with pytest.raises(DocumentExtractionError):
        extract_text(
            b"binary",
            "application/octet-stream",
        )


def test_chunking_is_deterministic():
    args = dict(
        tenant_id="customer-a",
        document_id="doc-1",
        content_hash=hashlib.sha256(b"hello").hexdigest(),
        text="A" * 2500,
        chunk_size=1000,
        overlap=100,
    )

    first = chunk_document(**args)
    second = chunk_document(**args)

    assert [c.chunk_id for c in first] == [
        c.chunk_id for c in second
    ]


def test_chunking_preserves_tenant():
    chunks = chunk_document(
        tenant_id="customer-a",
        document_id="doc-1",
        content_hash="hash-1",
        text="Azure AI architecture",
    )

    assert all(
        chunk.tenant_id == "customer-a"
        for chunk in chunks
    )


def test_chunking_overlap():
    chunks = chunk_document(
        tenant_id="customer-a",
        document_id="doc-1",
        content_hash="hash-1",
        text="0123456789",
        chunk_size=6,
        overlap=2,
    )

    assert chunks[0].text == "012345"
    assert chunks[1].text.startswith("45")


def test_reject_invalid_chunk_parameters():
    with pytest.raises(ChunkingError):
        chunk_document(
            tenant_id="customer-a",
            document_id="doc-1",
            content_hash="hash-1",
            text="Hello",
            chunk_size=100,
            overlap=100,
        )


def test_embedding_preserves_provenance():
    result = embed_chunks(
        [make_chunk()],
        FakeEmbeddingProvider(),
        expected_dimensions=3,
    )

    assert result[0].chunk.tenant_id == "customer-a"
    assert result[0].vector == (0.1, 0.2, 0.3)


def test_reject_cross_tenant_embedding_batch():
    with pytest.raises(EmbeddingError):
        embed_chunks(
            [
                make_chunk("customer-a"),
                make_chunk("customer-b"),
            ],
            FakeEmbeddingProvider(),
            expected_dimensions=3,
        )


def test_reject_wrong_embedding_dimensions():
    with pytest.raises(EmbeddingError):
        embed_chunks(
            [make_chunk()],
            FakeEmbeddingProvider(),
            expected_dimensions=5,
        )