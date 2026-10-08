from multimodal_evidence_gate import (
    TextEvidenceSource,
)


class InMemoryImageEvidenceStore:
    def __init__(self):
        self._items = {}

    def put(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        asset_version: int,
        content: bytes,
    ) -> None:

        key = (
            tenant_id,
            asset_id,
            asset_version,
        )

        self._items[key] = content

    def get(
        self,
        *,
        tenant_id: str,
        asset_id: str,
        asset_version: int,
    ) -> bytes:

        key = (
            tenant_id,
            asset_id,
            asset_version,
        )

        return self._items[key]


class InMemoryTextEvidenceStore:
    def __init__(self):
        self._items = {}

    def put(
        self,
        *,
        tenant_id: str,
        document_id: str,
        document_version: int,
        search_id: str,
        source: TextEvidenceSource,
    ) -> None:

        key = (
            tenant_id,
            document_id,
            document_version,
            search_id,
        )

        self._items[key] = source

    def get(
        self,
        *,
        tenant_id: str,
        document_id: str,
        document_version: int,
        search_id: str,
    ) -> TextEvidenceSource:

        key = (
            tenant_id,
            document_id,
            document_version,
            search_id,
        )

        return self._items[key]