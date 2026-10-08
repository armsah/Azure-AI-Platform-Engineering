from io import BytesIO

from pypdf import PdfReader


MAX_EXTRACTED_CHARACTERS = 1_000_000
MAX_PDF_PAGES = 100


class DocumentExtractionError(Exception):
    pass


def extract_text(
    content: bytes,
    content_type: str,
) -> str:

    if content_type in {
        "text/plain",
        "text/markdown",
    }:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentExtractionError(
                "Document must contain valid UTF-8 text"
            ) from exc

    elif content_type == "application/pdf":
        try:
            reader = PdfReader(BytesIO(content), strict=True)

            if reader.is_encrypted:
                raise DocumentExtractionError(
                    "Encrypted PDFs are not supported"
                )

            if len(reader.pages) > MAX_PDF_PAGES:
                raise DocumentExtractionError(
                    "PDF page limit exceeded"
                )

            extracted = []
            total_characters = 0

            for page in reader.pages:
                page_text = page.extract_text() or ""

                total_characters += len(page_text)

                if total_characters > MAX_EXTRACTED_CHARACTERS:
                    raise DocumentExtractionError(
                        "Extracted text exceeds limit"
                    )

                extracted.append(page_text)

            text = "\n".join(extracted)

        except DocumentExtractionError:
            raise
        except Exception as exc:
            raise DocumentExtractionError(
                "PDF extraction failed"
            ) from exc

    else:
        raise DocumentExtractionError(
            "Unsupported content type"
        )

    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise DocumentExtractionError(
            "Extracted text exceeds limit"
        )

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.strip()

    if not text:
        raise DocumentExtractionError(
            "Document contains no extractable text"
        )

    return text