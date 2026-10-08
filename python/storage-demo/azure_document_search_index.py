from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from document_search_index import (
    SearchDocument,
    SearchIndexError,
)


class AzureDocumentSearchIndex:
    def __init__(
        self,
        *,
        endpoint: str,
        index_name: str,
        api_key: str,
    ):
        self.client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(api_key),
        )

    def upsert(
        self,
        documents: list[SearchDocument],
    ) -> None:

        if not documents:
            return

        payload = [
            {
                "id": document.chunk_id,
                "tenant_id": document.tenant_id,
                "document_id": document.document_id,
                "content_hash": document.content_hash,
                "chunk_index": document.chunk_index,
                "content": document.content,
                "content_vector": list(document.vector),
            }
            for document in documents
        ]

        results = self.client.merge_or_upload_documents(
            documents=payload
        )

        failures = [
            result.key
            for result in results
            if not result.succeeded
        ]

        if failures:
            raise SearchIndexError(
                f"Azure Search rejected {len(failures)} documents"
            )