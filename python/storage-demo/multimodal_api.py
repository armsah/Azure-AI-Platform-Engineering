from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated
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

from entra_auth import get_request_context

from multimodal_assets import (
    MAX_ASSET_BYTES,
    MultimodalAssetRegistry,
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
    MultimodalRollbackError,
    MultimodalUploadError,
    MultimodalUploadWorkflow,
)


logger = logging.getLogger("multimodal.api")

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
    *,
    enable_entra_auth: bool = True,
) -> FastAPI:

    app = FastAPI(
        title="Azure AI Platform — Multimodal API",
        version="0.1.0",
    )

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        request_id = str(uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception:
            logger.error(
                "multimodal_request_failed",
                extra={
                    "request_id": request_id,
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "failure_category": "unexpected_error",
                },
            )
            raise

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "multimodal_request_completed",
            extra={
                "request_id": request_id,
                "http_method": request.method,
                "http_path": request.url.path,
                "http_status_code": response.status_code,
            },
        )

        return response

    if enable_entra_auth:
        app.dependency_overrides[
            require_authenticated_context
        ] = get_request_context

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
        request: Request,
        file: Annotated[UploadFile, File()],
        context: Annotated[
            RequestContext,
            Depends(require_authenticated_context),
        ],
    ):
        authorized = authorize(context)

        allowed_types = {
            "image/png",
            "image/jpeg",
            "image/webp",
        }

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=415,
                detail="Unsupported image content type",
            )

        content = await file.read(MAX_ASSET_BYTES + 1)

        if len(content) > MAX_ASSET_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Image exceeds maximum allowed size",
            )

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Image is empty",
            )

        try:
            sanitize_image(
                content_type=file.content_type,
                content=content,
            )

        except ImageSecurityError as exc:
            raise HTTPException(
                status_code=422,
                detail="Invalid or unsafe image",
            ) from exc

        if dependencies.upload_workflow is None:
            raise HTTPException(
                status_code=503,
                detail="Image ingestion service is unavailable",
            )

        try:
            completed = dependencies.upload_workflow.upload(
                context=authorized,
                filename=file.filename or "image",
                content_type=file.content_type,
                content=content,
            )

        except TenantAuthorizationError as exc:
            raise HTTPException(
                status_code=403,
                detail="Tenant access denied",
            ) from exc

        except MultimodalUploadError as exc:
            rollback_incomplete = isinstance(
                exc,
                MultimodalRollbackError,
            )

            logger.error(
                "multimodal_ingestion_failed",
                extra={
                    "request_id": getattr(
                        request.state,
                        "request_id",
                        None,
                    ),
                    "failure_category": (
                        "rollback_incomplete"
                        if rollback_incomplete
                        else "ingestion_failure"
                    ),
                    "rollback_incomplete": rollback_incomplete,
                },
            )

            raise HTTPException(
                status_code=503,
                detail="Image ingestion service is unavailable",
            ) from exc

        except (TimeoutError, ConnectionError) as exc:
            logger.error(
                "multimodal_ingestion_dependency_unavailable",
                extra={
                    "request_id": getattr(
                        request.state,
                        "request_id",
                        None,
                    ),
                    "failure_category": "dependency_unavailable",
                },
            )

            raise HTTPException(
                status_code=503,
                detail="Image ingestion service is unavailable",
            ) from exc

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

        except TenantAuthorizationError as exc:
            raise HTTPException(
                status_code=403,
                detail="Tenant access denied",
            ) from exc

        except (TimeoutError, ConnectionError) as exc:
            raise HTTPException(
                status_code=503,
                detail="Answer generation service is unavailable",
            ) from exc

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