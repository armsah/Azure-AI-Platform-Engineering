from dataclasses import dataclass


@dataclass
class Chunk:
    document_id: str
    chunk_id: str
    content: str
    source: str
    section: str


def chunk_text(
    document_id: str,
    text: str,
    source: str,
    section: str = "default",
    chunk_size: int = 120,
    overlap: int = 20,
) -> list[Chunk]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = text.split()
    chunks = []

    start = 0
    index = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))

        chunks.append(
            Chunk(
                document_id=document_id,
                chunk_id=f"{document_id}-{index}",
                content=" ".join(words[start:end]),
                source=source,
                section=section,
            )
        )

        if end == len(words):
            break

        start = end - overlap
        index += 1

    return chunks

def chunk_sections(
    document_id: str,
    sections: dict[str, str],
    source: str,
    chunk_size: int = 120,
    overlap: int = 20,
) -> list[Chunk]:
    chunks = []

    for section, text in sections.items():
        section_chunks = chunk_text(
            document_id=document_id,
            text=text,
            source=source,
            section=section,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        for index, chunk in enumerate(section_chunks):
            chunk.chunk_id = f"{document_id}-{section.lower().replace(' ', '-')}-{index}"

        chunks.extend(section_chunks)

    return chunks