import hashlib
from dataclasses import dataclass

from graph_document_access import DocumentAccessPolicy
from graph_traversal import (
    GraphPath,
    GraphTraversalService,
)
from rag_context_selection import (
    ContextSelectionPolicy,
    SelectedContext,
    select_context,
)
from rag_reranking import RankedChunk
from rag_retrieval import RetrievedChunk
from request_context import RequestContext


@dataclass(frozen=True)
class GraphEvidenceResult:
    context: SelectedContext
    authorized_paths: int
    rejected_paths: int
    truncated: bool


def _path_document_ids(
    path: GraphPath,
) -> frozenset[str]:
    return frozenset(
        [
            *(
                entity.source_document_id
                for entity in path.entities
            ),
            *(
                relationship.source_document_id
                for relationship in path.relationships
            ),
        ]
    )


def _path_citation_id(
    tenant_id: str,
    path: GraphPath,
) -> str:
    parts = [
        tenant_id,
        *(
            entity.entity_id
            for entity in path.entities
        ),
        *(
            relationship.relationship_id
            for relationship in path.relationships
        ),
    ]

    digest = hashlib.sha256(
        "\x1f".join(parts).encode("utf-8")
    ).hexdigest()

    return f"graph:{digest}"


def _path_text(path: GraphPath) -> str:
    lines = []

    for index, relationship in enumerate(
        path.relationships
    ):
        source = path.entities[index]
        target = path.entities[index + 1]

        lines.append(
            f"{source.name} "
            f"--{relationship.relationship_type}--> "
            f"{target.name} "
            f"[source document: "
            f"{relationship.source_document_id}]"
        )

    return "\n".join(lines)


class GraphRAGEvidenceService:
    def __init__(
        self,
        *,
        traversal: GraphTraversalService,
        document_access: DocumentAccessPolicy,
        context_policy: ContextSelectionPolicy | None = None,
    ):
        self.traversal = traversal
        self.document_access = document_access

        self.context_policy = (
            context_policy
            or ContextSelectionPolicy(
                max_context_tokens=1500,
                max_chunks=5,
                min_relevance_score=0.0,
            )
        )

    def retrieve_evidence(
        self,
        *,
        context: RequestContext,
        start_entity_id: str,
    ) -> GraphEvidenceResult:

        traversal = self.traversal.traverse(
            context=context,
            start_entity_id=start_entity_id,
        )

        authorized: list[GraphPath] = []
        rejected = 0

        for path in traversal.paths:
            documents = _path_document_ids(path)

            if all(
                self.document_access.can_read(
                    context=context,
                    document_id=document_id,
                )
                for document_id in documents
            ):
                authorized.append(path)
            else:
                rejected += 1

        ranked_chunks: list[RankedChunk] = []

        for path in authorized:
            content = _path_text(path)

            chunk = RetrievedChunk(
                chunk_id=_path_citation_id(
                    context.tenant_id,
                    path,
                ),
                tenant_id=context.tenant_id,
                document_id=(
                    path.relationships[-1]
                    .source_document_id
                ),
                content=content,
                score=1.0,
                source="knowledge-graph",
            )

            ranked_chunks.append(
                RankedChunk(
                    chunk=chunk,
                    relevance_score=1.0,
                )
            )

        selected = select_context(
            tenant_id=context.tenant_id,
            ranked_chunks=ranked_chunks,
            policy=self.context_policy,
        )

        return GraphEvidenceResult(
            context=selected,
            authorized_paths=len(authorized),
            rejected_paths=rejected,
            truncated=traversal.truncated,
        )