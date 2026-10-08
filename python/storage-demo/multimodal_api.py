from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Callable
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field

from multimodal_assets import (
    MAX_ASSET_BYTES,
    MultimodalAssetRegistry,
    MultimodalAssetError,
)

from multimodal_rag_answer import (
    MultimodalRAGAnswerService,
)

from request_context import RequestContext

from secure_image_processing import (
    ImageSecurityError,
    sanitize_image,
)

from tenant_boundary import (
    TenantAuthorizationError,
    TenantBoundary,
)

from multimodal_upload_workflow import (
    MultimodalUploadError,
    MultimodalUploadWorkflow,
)


class MultimodalAPIError(Exception):
    """Application-level multimodal workflow failure."""


class AuthenticationNotConfigured(MultimodalAPIError):
    """The production authentication dependency is missing."""


class ImageUploadResponse(BaseModel):
    asset_id: str
    version: int
    content_type: str
    source_sha256: str
    sanitized_sha256: str
    width: int
    height: int
    description: str | None = None
    search_id: str | None = None


class AnswerRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=4000,
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )


class CitationResponse(BaseModel):
    citation_id: str
    evidence_id: str
    modality: str
    resource_id: str
    resource_version: int


class AnswerResponse(BaseModel):
    answer: str
    snapshot_id: str | None
    citations: list[CitationResponse]
    abstained: bool


@dataclass(frozen=True)
class MultimodalAPIDependencies:
    boundary: TenantBoundary
    assets: MultimodalAssetRegistry
    answers: MultimodalRAGAnswerService
    upload_workflow: MultimodalUploadWorkflow | None = None


async def require_authenticated_context(
    request: Request,
) -> RequestContext:
    """
    Fail-closed default.

    Production wiring must replace this dependency with the
    existing A2 verified Entra JWT authentication dependency.

    Never construct RequestContext from unverified headers.
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is not configured",
    )


def create_multimodal_app(
    dependencies: MultimodalAPIDependencies,
) -> FastAPI:

    app = FastAPI(
        title="Azure AI Platform — Multimodal API",
        version="0.1.0",
    )

    def authorize(
        context: RequestContext,
    ) -> RequestContext:
        try:
            return dependencies.boundary.authorize(
                context=context,
                requested_tenant_id=context.tenant_id,
            )
        except TenantAuthorizationError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant access denied",
            )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "component": "multimodal-api",
        }

    @app.post(
        "/api/v1/multimodal/images",
        response_model=ImageUploadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_image(
        file: Annotated[UploadFile, File()],
        context: Annotated[
            RequestContext,
            Depends(require_authenticated_context),
        ],
    ):

        authorized = authorize(context)

        if file.content_type not in {
            "image/png",
            "image/jpeg",
            "image/webp",
        }:
            raise HTTPException(
                status_code=415,
                detail="Unsupported image content type",
            )

        # Read one byte beyond the limit so oversized uploads
        # can be rejected without reading an unbounded body.
        content = await file.read(
            MAX_ASSET_BYTES + 1
        )

        if len(content) > MAX_ASSET_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Image exceeds size limit",
            )

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Image is empty",
            )

        try:
            sanitized = sanitize_image(
                content_type=file.content_type,
                content=content,
            )

        except ImageSecurityError:
            raise HTTPException(
                status_code=422,
                detail="Invalid or unsafe image",
            )
        
        if dependencies.upload_workflow is not None:

            try:
                completed = dependencies.upload_workflow.upload(
                    context=authorized,
                    filename=file.filename or "image",
                    content_type=file.content_type,
                    content=content,
                )

            except TenantAuthorizationError:
                raise HTTPException(
                    status_code=403,
                    detail="Tenant access denied",
                )

            except MultimodalUploadError:
                raise HTTPException(
                    status_code=422,
                    detail="Image processing failed",
                )

            return ImageUploadResponse(
                asset_id=completed.asset.asset_id,
                version=completed.asset.version,
                content_type=completed.asset.content_type,
                source_sha256=completed.asset.content_sha256,
                sanitized_sha256=completed.sanitized.sanitized_sha256,
                width=completed.sanitized.width,
                height=completed.sanitized.height,
                description=completed.description,
                search_id=completed.search_id,
            )

        asset_id = str(uuid4())

        try:
            asset = dependencies.assets.register(
                tenant_id=authorized.tenant_id,
                asset_id=asset_id,
                filename=file.filename or "image",
                content_type=file.content_type,
                content=content,
                version=1,
            )

        except MultimodalAssetError:
            raise HTTPException(
                status_code=422,
                detail="Image registration failed",
            )

        return ImageUploadResponse(
            asset_id=asset.asset_id,
            version=asset.version,
            content_type=asset.content_type,
            source_sha256=asset.content_sha256,
            sanitized_sha256=sanitized.sanitized_sha256,
            width=sanitized.width,
            height=sanitized.height,
        )

    @app.post(
        "/api/v1/multimodal/answers",
        response_model=AnswerResponse,
    )
    def answer_question(
        payload: AnswerRequest,
        context: Annotated[
            RequestContext,
            Depends(require_authenticated_context),
        ],
    ):

        authorized = authorize(context)

        try:
            result = dependencies.answers.answer(
                context=authorized,
                question=payload.question,
                top_k=payload.top_k,
            )

        except TenantAuthorizationError:
            raise HTTPException(
                status_code=403,
                detail="Tenant access denied",
            )

        citations = [
            CitationResponse(
                citation_id=citation.citation_id,
                evidence_id=citation.evidence_id,
                modality=citation.kind.value,
                resource_id=citation.resource_id,
                resource_version=citation.resource_version,
            )
            for citation in result.citations
        ]

        return AnswerResponse(
            answer=result.answer,
            snapshot_id=result.snapshot_id,
            citations=citations,
            abstained=result.abstained,
        )

    return app