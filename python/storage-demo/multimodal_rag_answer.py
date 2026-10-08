from dataclasses import dataclass
from typing import Protocol

from document_provenance import ProvenanceError

from multimodal_assets import (
    AssetIntegrityError,
    AssetNotFound,
)

from multimodal_citation_lineage import (
    MultimodalCitation,
    create_multimodal_snapshot,
    validate_multimodal_citations,
)

from multimodal_evidence import (
    MultimodalEvidenceError,
)

from multimodal_evidence_gate import (
    MultimodalEvidenceGateError,
)

from multimodal_retrieval import (
    MultimodalRetrievalService,
)

from request_context import RequestContext

from secure_image_processing import ImageSecurityError

from tenant_boundary import (
    TenantAuthorizationError,
)

from multimodal_evidence_gate import (
    MultimodalEvidenceGate,
    MultimodalEvidenceGateError,
    VerifiedMultimodalEvidence,
)


class MultimodalRAGError(Exception):
    pass


@dataclass(frozen=True)
class MultimodalDraft:
    answer: str
    citation_ids: tuple[str, ...]


class MultimodalRAGModel(Protocol):
    def generate(
        self,
        *,
        question: str,
        evidence: tuple[VerifiedMultimodalEvidence, ...],
        citation_ids: tuple[str, ...],
    ) -> MultimodalDraft:
        ...


@dataclass(frozen=True)
class MultimodalRAGAnswer:
    answer: str
    snapshot_id: str | None
    citations: tuple[MultimodalCitation, ...]
    abstained: bool

EXPECTED_EVIDENCE_FAILURES = (
    MultimodalEvidenceGateError,
    MultimodalEvidenceError,
    ImageSecurityError,
    AssetNotFound,
    AssetIntegrityError,
    ProvenanceError,
    PermissionError,
    KeyError,
)


class MultimodalRAGAnswerService:
    def __init__(
        self,
        *,
        retrieval: MultimodalRetrievalService,
        evidence_gate: MultimodalEvidenceGate,
        model: MultimodalRAGModel,
    ):
        self.retrieval = retrieval
        self.evidence_gate = evidence_gate
        self.model = model

    def answer(
        self,
        *,
        context: RequestContext,
        question: str,
        top_k: int = 5,
    ) -> MultimodalRAGAnswer:

        hits = self.retrieval.search(
            context=context,
            question=question,
            top_k=top_k,
        )

        verified = []

        for hit in hits:
            try:
                item = self.evidence_gate.verify(
                    context=context,
                    hit=hit,
                )

            except TenantAuthorizationError:
                raise

            except EXPECTED_EVIDENCE_FAILURES:
                continue

            verified.append(item)

        if not verified:
            return MultimodalRAGAnswer(
                answer=(
                    "I do not have verified evidence "
                    "to answer that question."
                ),
                snapshot_id=None,
                citations=(),
                abstained=True,
            )

        snapshot = create_multimodal_snapshot(
            tenant_id=context.tenant_id,
            evidence=tuple(verified),
        )

        available_citations = tuple(
            citation.citation_id
            for citation in snapshot.citations
        )

        draft = self.model.generate(
            question=question,
            evidence=tuple(verified),
            citation_ids=available_citations,
        )

        if not isinstance(draft.answer, str):
            raise MultimodalRAGError(
                "Model answer must be text"
            )

        if not draft.answer.strip():
            raise MultimodalRAGError(
                "Model returned an empty answer"
            )

        verified_citations = (
            validate_multimodal_citations(
                snapshot,
                draft.citation_ids,
            )
        )

        return MultimodalRAGAnswer(
            answer=draft.answer.strip(),
            snapshot_id=snapshot.snapshot_id,
            citations=verified_citations,
            abstained=False,
        )