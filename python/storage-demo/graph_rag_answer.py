from graph_rag_evidence import GraphRAGEvidenceService
from rag_citation_validation import (
    VerifiedAnswer,
    validate_grounded_answer,
)
from rag_grounding import (
    GroundedModel,
    SYSTEM_INSTRUCTIONS,
    build_evidence_message,
)
from request_context import RequestContext


class GraphRAGAnswerService:
    def __init__(
        self,
        *,
        evidence_service: GraphRAGEvidenceService,
        model: GroundedModel,
    ):
        self.evidence_service = evidence_service
        self.model = model

    def answer(
        self,
        *,
        context: RequestContext,
        start_entity_id: str,
        question: str,
    ) -> VerifiedAnswer:

        evidence = self.evidence_service.retrieve_evidence(
            context=context,
            start_entity_id=start_entity_id,
        )

        if not evidence.context.chunks:
            return VerifiedAnswer(
                answer="Insufficient authorized evidence to answer.",
                citations=(),
                grounded=False,
            )

        draft = self.model.generate(
            system_instructions=SYSTEM_INSTRUCTIONS,
            user_message=build_evidence_message(
                question,
                evidence.context,
            ),
        )

        return validate_grounded_answer(
            draft,
            evidence.context,
        )