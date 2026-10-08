import hashlib
import json
import threading
from dataclasses import dataclass

from chunk_provenance import (
    ExtractionManifest,
    sha256_text,
)
from document_provenance import (
    ProvenanceConflict,
    ProvenanceIntegrityError,
)


GRAPH_PROVENANCE_VERSION = "graph-provenance-v1"


@dataclass(frozen=True)
class GraphRelationshipProvenance:
    relationship_id: str
    tenant_id: str

    source_entity_id: str
    target_entity_id: str
    relationship_type: str

    document_id: str
    document_version: int

    extraction_version: str
    extraction_sha256: str

    evidence_start_char: int
    evidence_end_char: int
    evidence_sha256: str

    provenance_version: str


def _relationship_identity(
    *,
    tenant_id: str,
    source_entity_id: str,
    target_entity_id: str,
    relationship_type: str,
    document_id: str,
    document_version: int,
    extraction_version: str,
    extraction_sha256: str,
    evidence_start_char: int,
    evidence_end_char: int,
    evidence_sha256: str,
) -> str:

    payload = {
        "tenant_id": tenant_id,
        "source_entity_id": source_entity_id,
        "target_entity_id": target_entity_id,
        "relationship_type": relationship_type,
        "document_id": document_id,
        "document_version": document_version,
        "extraction_version": extraction_version,
        "extraction_sha256": extraction_sha256,
        "evidence_start_char": evidence_start_char,
        "evidence_end_char": evidence_end_char,
        "evidence_sha256": evidence_sha256,
        "provenance_version": GRAPH_PROVENANCE_VERSION,
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def create_relationship_provenance(
    *,
    extraction: ExtractionManifest,
    extracted_text: str,
    source_entity_id: str,
    target_entity_id: str,
    relationship_type: str,
    evidence_start_char: int,
    evidence_end_char: int,
) -> GraphRelationshipProvenance:

    if not all(
        isinstance(value, str) and value.strip()
        for value in (
            source_entity_id,
            target_entity_id,
            relationship_type,
        )
    ):
        raise ProvenanceIntegrityError(
            "Missing relationship fields"
        )

    if (
        evidence_start_char < 0
        or evidence_end_char <= evidence_start_char
        or evidence_end_char > len(extracted_text)
    ):
        raise ProvenanceIntegrityError(
            "Invalid relationship evidence span"
        )

    if (
        len(extracted_text)
        != extraction.extracted_text_length
    ):
        raise ProvenanceIntegrityError(
            "Extraction length mismatch"
        )

    if (
        sha256_text(extracted_text)
        != extraction.extracted_text_sha256
    ):
        raise ProvenanceIntegrityError(
            "Extraction digest mismatch"
        )

    evidence_text = extracted_text[
        evidence_start_char:evidence_end_char
    ]

    evidence_sha256 = sha256_text(
        evidence_text
    )

    relationship_id = _relationship_identity(
        tenant_id=extraction.tenant_id,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
        document_id=extraction.document_id,
        document_version=extraction.document_version,
        extraction_version=extraction.extraction_version,
        extraction_sha256=extraction.extracted_text_sha256,
        evidence_start_char=evidence_start_char,
        evidence_end_char=evidence_end_char,
        evidence_sha256=evidence_sha256,
    )

    return GraphRelationshipProvenance(
        relationship_id=relationship_id,
        tenant_id=extraction.tenant_id,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
        document_id=extraction.document_id,
        document_version=extraction.document_version,
        extraction_version=extraction.extraction_version,
        extraction_sha256=extraction.extracted_text_sha256,
        evidence_start_char=evidence_start_char,
        evidence_end_char=evidence_end_char,
        evidence_sha256=evidence_sha256,
        provenance_version=GRAPH_PROVENANCE_VERSION,
    )


class GraphRelationshipProvenanceRegistry:
    def __init__(self):
        self._lock = threading.RLock()

        self._relationships: dict[
            tuple[str, str],
            GraphRelationshipProvenance,
        ] = {}

        self._revoked: set[
            tuple[str, str]
        ] = set()

    def register(
        self,
        relationship: GraphRelationshipProvenance,
    ) -> None:

        key = (
            relationship.tenant_id,
            relationship.relationship_id,
        )

        with self._lock:
            if key in self._relationships:
                raise ProvenanceConflict(
                    "Relationship already registered"
                )

            self._relationships[key] = relationship

    def get(
        self,
        *,
        tenant_id: str,
        relationship_id: str,
    ) -> GraphRelationshipProvenance:

        key = (
            tenant_id,
            relationship_id,
        )

        with self._lock:
            relationship = self._relationships.get(key)

            if relationship is None:
                raise ProvenanceIntegrityError(
                    "Relationship not found"
                )

            if key in self._revoked:
                raise ProvenanceIntegrityError(
                    "Relationship revoked"
                )

            return relationship

    def revoke(
        self,
        *,
        tenant_id: str,
        relationship_id: str,
    ) -> None:

        key = (
            tenant_id,
            relationship_id,
        )

        with self._lock:
            if key not in self._relationships:
                raise ProvenanceIntegrityError(
                    "Cannot revoke missing relationship"
                )

            self._revoked.add(key)