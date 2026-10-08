import hashlib
import json
from dataclasses import dataclass
from enum import Enum


class MultimodalCitationError(Exception):
    pass


class EvidenceKind(str, Enum):
    TEXT = "text"
    IMAGE = "image"


@dataclass(frozen=True)
class MultimodalCitation:
    citation_id: str
    evidence_id: str
    kind: EvidenceKind

    tenant_id: str
    resource_id: str
    resource_version: int
    source_sha256: str


@dataclass(frozen=True)
class MultimodalEvidenceSnapshot:
    snapshot_id: str
    tenant_id: str

    evidence: tuple
    citations: tuple[MultimodalCitation, ...]


def _digest(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def create_multimodal_snapshot(
    *,
    tenant_id: str,
    evidence: tuple,
) -> MultimodalEvidenceSnapshot:

    if not tenant_id.strip():
        raise MultimodalCitationError(
            "Missing tenant ID"
        )

    if not evidence:
        raise MultimodalCitationError(
            "Cannot snapshot empty evidence"
        )

    citations = []
    seen = set()

    for item in evidence:
        if item.tenant_id != tenant_id:
            raise MultimodalCitationError(
                "Cross-tenant evidence"
            )

        if item.evidence_id in seen:
            raise MultimodalCitationError(
                "Duplicate evidence ID"
            )

        seen.add(item.evidence_id)

        kind = EvidenceKind(
            item.modality.value
        )

        citation_id = _digest(
            {
                "tenant_id": tenant_id,
                "evidence_id": item.evidence_id,
                "kind": kind.value,
                "resource_id": item.resource_id,
                "resource_version": (
                    item.resource_version
                ),
                "source_sha256": (
                    item.source_sha256
                ),
            }
        )

        citations.append(
            MultimodalCitation(
                citation_id=citation_id,
                evidence_id=item.evidence_id,
                kind=kind,
                tenant_id=tenant_id,
                resource_id=item.resource_id,
                resource_version=(
                    item.resource_version
                ),
                source_sha256=(
                    item.source_sha256
                ),
            )
        )

    snapshot_id = _digest(
        {
            "tenant_id": tenant_id,
            "citations": [
                citation.citation_id
                for citation in citations
            ],
            "evidence": [
                {
                    "id": item.evidence_id,
                    "text": item.text,
                }
                for item in evidence
            ],
        }
    )

    return MultimodalEvidenceSnapshot(
        snapshot_id=snapshot_id,
        tenant_id=tenant_id,
        evidence=evidence,
        citations=tuple(citations),
    )


def validate_multimodal_citations(
    snapshot: MultimodalEvidenceSnapshot,
    citation_ids: tuple[str, ...],
) -> tuple[MultimodalCitation, ...]:

    if not citation_ids:
        raise MultimodalCitationError(
            "Answer has no citations"
        )

    if len(citation_ids) != len(set(citation_ids)):
        raise MultimodalCitationError(
            "Duplicate citations"
        )

    available = {
        citation.citation_id: citation
        for citation in snapshot.citations
    }

    verified = []

    for citation_id in citation_ids:
        citation = available.get(citation_id)

        if citation is None:
            raise MultimodalCitationError(
                "Fabricated or unknown citation"
            )

        verified.append(citation)

    return tuple(verified)