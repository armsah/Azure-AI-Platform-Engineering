import hashlib
import json
from dataclasses import dataclass

from evidence_eligibility import (
    EligibleEvidence,
    EvidenceEligibilityError,
)


@dataclass(frozen=True)
class CitationLineage:
    citation_id: str
    evidence_id: str
    evidence_kind: str
    tenant_id: str
    document_id: str
    document_version: int
    source_sha256: str


@dataclass(frozen=True)
class EvidenceSnapshot:
    snapshot_id: str
    tenant_id: str
    evidence: tuple[EligibleEvidence, ...]
    citations: tuple[CitationLineage, ...]


def _citation_id(
    evidence: EligibleEvidence,
) -> str:

    payload = {
        "evidence_id": evidence.evidence_id,
        "kind": evidence.kind,
        "tenant_id": evidence.tenant_id,
        "document_id": evidence.document_id,
        "document_version": evidence.document_version,
        "source_sha256": evidence.source_sha256,
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def create_evidence_snapshot(
    *,
    tenant_id: str,
    evidence: tuple[EligibleEvidence, ...],
) -> EvidenceSnapshot:

    if not tenant_id.strip():
        raise EvidenceEligibilityError(
            "Missing tenant ID"
        )

    if not evidence:
        raise EvidenceEligibilityError(
            "Cannot create empty evidence snapshot"
        )

    evidence_ids = [
        (item.kind, item.evidence_id)
        for item in evidence
    ]

    if len(evidence_ids) != len(set(evidence_ids)):
        raise EvidenceEligibilityError(
            "Duplicate evidence identifiers"
        )

    if any(
        item.tenant_id != tenant_id
        for item in evidence
    ):
        raise EvidenceEligibilityError(
            "Cross-tenant evidence snapshot"
        )

    citations = tuple(
        CitationLineage(
            citation_id=_citation_id(item),
            evidence_id=item.evidence_id,
            evidence_kind=item.kind,
            tenant_id=item.tenant_id,
            document_id=item.document_id,
            document_version=item.document_version,
            source_sha256=item.source_sha256,
        )
        for item in evidence
    )

    if len(
        {citation.citation_id for citation in citations}
    ) != len(citations):
        raise EvidenceEligibilityError(
            "Duplicate citation identifiers"
        )

    snapshot_payload = {
        "tenant_id": tenant_id,
        "citations": [
            citation.__dict__
            for citation in citations
        ],
        "evidence_text_sha256": [
            hashlib.sha256(
                item.text.encode("utf-8")
            ).hexdigest()
            for item in evidence
        ],
    }

    canonical = json.dumps(
        snapshot_payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    snapshot_id = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    return EvidenceSnapshot(
        snapshot_id=snapshot_id,
        tenant_id=tenant_id,
        evidence=evidence,
        citations=citations,
    )


def validate_snapshot_citations(
    *,
    snapshot: EvidenceSnapshot,
    citation_ids: tuple[str, ...],
) -> tuple[CitationLineage, ...]:

    known = {
        citation.citation_id: citation
        for citation in snapshot.citations
    }

    if len(citation_ids) != len(set(citation_ids)):
        raise EvidenceEligibilityError(
            "Duplicate citations in answer"
        )

    if not citation_ids:
        raise EvidenceEligibilityError(
            "Answer must cite eligible evidence"
        )

    verified = []

    for citation_id in citation_ids:
        citation = known.get(citation_id)

        if citation is None:
            raise EvidenceEligibilityError(
                "Unknown or fabricated citation"
            )

        verified.append(citation)

    return tuple(verified)