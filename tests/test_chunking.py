import pytest

from chunking import chunk_text
from chunking import chunk_sections


def test_chunking_with_overlap():
    text = " ".join(f"word{i}" for i in range(250))

    chunks = chunk_text(
        document_id="doc1",
        text=text,
        source="test.txt",
        chunk_size=100,
        overlap=20,
    )

    assert len(chunks) == 3
    assert chunks[0].chunk_id == "doc1-0"
    assert chunks[0].source == "test.txt"

    first = chunks[0].content.split()
    second = chunks[1].content.split()

    assert first[-20:] == second[:20]


def test_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_text(
            document_id="doc1",
            text="hello world",
            source="test.txt",
            chunk_size=20,
            overlap=20,
        )

def test_structure_aware_chunking():
    sections = {
        "Authentication": "Managed identity provides passwordless Azure authentication.",
        "Networking": "Private endpoints provide private connectivity through a VNet.",
    }

    chunks = chunk_sections(
        document_id="azure-guide",
        sections=sections,
        source="azure-guide.md",
    )

    assert len(chunks) == 2

    assert chunks[0].section == "Authentication"
    assert chunks[1].section == "Networking"

    assert chunks[0].chunk_id == "azure-guide-authentication-0"
