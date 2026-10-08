from rag_citation_validation import (
    VerifiedAnswer,
    validate_grounded_answer,
)
from rag_evidence_pipeline import RAGEvidencePipeline
from rag_grounding import (
    GroundedModel,
    SYSTEM_INSTRUCTIONS,
    build_evidence_message,
)
from request_context import RequestContext


class RAGAnswerService:
    def __init__(
        self,
        *,
        evidence_pipeline: RAGEvidencePipeline,
        model: GroundedModel,
    ):
        self.evidence_pipeline = evidence_pipeline
        self.model = model

    def answer(
        self,
        *,
        context: RequestContext,
        question: str,
    ) -> VerifiedAnswer:

        evidence = self.evidence_pipeline.retrieve_evidence(
            context=context,
            question=question,
        )

        if not evidence.context.chunks:
            return VerifiedAnswer(
                answer="Insufficient evidence to answer.",
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