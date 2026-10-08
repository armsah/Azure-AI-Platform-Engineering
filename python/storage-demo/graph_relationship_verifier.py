from dataclasses import dataclass

from chunk_provenance import (
    ExtractionManifest,
    sha256_text,
)
from document_provenance import (
    ProvenanceIntegrityError,
)
from graph_relationship_provenance import (
    GRAPH_PROVENANCE_VERSION,
    GraphRelationshipProvenance,
    GraphRelationshipProvenanceRegistry,
    create_relationship_provenance,
)
from provenance_authorization import (
    AuthorizedProvenanceService,
)
from request_context import RequestContext


@dataclass(frozen=True)
class VerifiedGraphRelationship:
    relationship_id: str
    tenant_id: str

    source_entity_id: str
    target_entity_id: str
    relationship_type: str

    document_id: str
    document_version: int

    evidence_text: str
    evidence_start_char: int
    evidence_end_char: int

    source_sha256: str


class GraphRelationshipVerifier:
    def __init__(
        self,
        *,
        registry: GraphRelationshipProvenanceRegistry,
        provenance_service: AuthorizedProvenanceService,
    ):
        self.registry = registry
        self.provenance_service = provenance_service

    def verify(
        self,
        *,
        context: RequestContext,
        relationship: GraphRelationshipProvenance,
        extraction: ExtractionManifest,
        source_bytes: bytes,
        extracted_text: str,
        require_current: bool = True,
    ) -> VerifiedGraphRelationship:

        if (
            relationship.tenant_id
            != context.tenant_id
            or extraction.tenant_id
            != context.tenant_id
        ):
            raise ProvenanceIntegrityError(
                "Cross-tenant relationship"
            )

        if (
            relationship.document_id
            != extraction.document_id
            or relationship.document_version
            != extraction.document_version
        ):
            raise ProvenanceIntegrityError(
                "Document lineage mismatch"
            )

        if (
            relationship.extraction_version
            != extraction.extraction_version
            or relationship.extraction_sha256
            != extraction.extracted_text_sha256
        ):
            raise ProvenanceIntegrityError(
                "Extraction lineage mismatch"
            )

        if (
            relationship.provenance_version
            != GRAPH_PROVENANCE_VERSION
        ):
            raise ProvenanceIntegrityError(
                "Unsupported graph provenance version"
            )

        verified_document = (
            self.provenance_service.verify_document(
                context=context,
                document_id=relationship.document_id,
                version=relationship.document_version,
                content=source_bytes,
                require_current=require_current,
            )
        )

        if (
            extraction.source_sha256
            != verified_document.manifest.content_sha256
        ):
            raise ProvenanceIntegrityError(
                "Source digest mismatch"
            )

        if (
            len(extracted_text)
            != extraction.extracted_text_length
            or sha256_text(extracted_text)
            != extraction.extracted_text_sha256
        ):
            raise ProvenanceIntegrityError(
                "Extraction integrity failure"
            )

        expected = create_relationship_provenance(
            extraction=extraction,
            extracted_text=extracted_text,
            source_entity_id=(
                relationship.source_entity_id
            ),
            target_entity_id=(
                relationship.target_entity_id
            ),
            relationship_type=(
                relationship.relationship_type
            ),
            evidence_start_char=(
                relationship.evidence_start_char
            ),
            evidence_end_char=(
                relationship.evidence_end_char
            ),
        )

        if expected != relationship:
            raise ProvenanceIntegrityError(
                "Relationship provenance mismatch"
            )

        stored = self.registry.get(
            tenant_id=context.tenant_id,
            relationship_id=relationship.relationship_id,
        )

        if stored != relationship:
            raise ProvenanceIntegrityError(
                "Registered relationship mismatch"
            )

        evidence_text = extracted_text[
            relationship.evidence_start_char:
            relationship.evidence_end_char
        ]

        return VerifiedGraphRelationship(
            relationship_id=relationship.relationship_id,
            tenant_id=context.tenant_id,
            source_entity_id=relationship.source_entity_id,
            target_entity_id=relationship.target_entity_id,
            relationship_type=relationship.relationship_type,
            document_id=relationship.document_id,
            document_version=relationship.document_version,
            evidence_text=evidence_text,
            evidence_start_char=(
                relationship.evidence_start_char
            ),
            evidence_end_char=(
                relationship.evidence_end_char
            ),
            source_sha256=(
                verified_document.manifest.content_sha256
            ),
        )