from __future__ import annotations

import io

import pytest
from PIL import Image

from multimodal_offline_environment import (
    create_offline_multimodal_environment,
)
from request_context import RequestContext
from multimodal_upload_workflow import MultimodalRollbackError


DIRECTORY = "directory-1"
TENANT = "tenant-a"
USER = "alice"


def make_context() -> RequestContext:
    return RequestContext(
        directory_tenant_id=DIRECTORY,
        tenant_id=TENANT,
        user_id=USER,
        groups=(),
        roles=("AI.User",),
    )


def make_png() -> bytes:
    image = Image.new(
        "RGB",
        (32, 32),
        color=(20, 80, 160),
    )

    output = io.BytesIO()
    image.save(output, format="PNG")

    return output.getvalue()


def make_environment():
    return create_offline_multimodal_environment(
        directory_tenant_id=DIRECTORY,
        tenant_id=TENANT,
        user_id=USER,
    )


def upload(environment):
    return environment.upload_workflow.upload(
        context=make_context(),
        filename="diagram.png",
        content_type="image/png",
        content=make_png(),
    )


def test_successful_upload_remains_searchable():
    environment = make_environment()

    result = upload(environment)

    assert result.asset.asset_id
    assert result.description
    assert result.search_id


def test_vision_failure_does_not_register_asset():
    environment = make_environment()

    class FailingVisionProvider:
        def describe(self, *, image, instruction: str):
            raise RuntimeError("Simulated vision failure")

    environment.upload_workflow.vision_provider = (
        FailingVisionProvider()
    )

    with pytest.raises(RuntimeError, match="vision failure"):
        upload(environment)

    assert len(environment.assets._assets) == 0


def test_indexing_failure_does_not_register_asset():
    environment = make_environment()

    original_indexing = environment.upload_workflow.indexing

    class FailingIndexingService:
        def __init__(self):
            
            self.index = original_indexing.index

        def index_image_description(self, description):
            raise RuntimeError("Simulated indexing failure")

    environment.upload_workflow.indexing = FailingIndexingService()

    with pytest.raises(RuntimeError, match="indexing failure"):
        upload(environment)

    assert len(environment.assets._assets) == 0
    assert len(environment.index._documents) == 0
    assert len(environment.image_sources._items) == 0
    assert len(environment.descriptions._records) == 0
    
def test_index_write_then_exception_leaves_no_search_document():
    environment = make_environment()

    original_indexing = environment.upload_workflow.indexing

    class WriteThenFailIndexingService:
        def __init__(self):
            self.index = original_indexing.index

        def index_image_description(self, description):
            original_indexing.index_image_description(description)
            raise RuntimeError("Simulated failure after index write")

    environment.upload_workflow.indexing = WriteThenFailIndexingService()

    with pytest.raises(RuntimeError, match="failure after index write"):
        upload(environment)

    assert len(environment.assets._assets) == 0
    assert len(environment.index._documents) == 0
    

def test_access_grant_failure_revokes_access():
    environment = make_environment()

    access_policy = environment.upload_workflow.asset_access

    original_grant = access_policy.grant
    captured_grants = []

    def grant_then_fail(grant):
        captured_grants.append(grant)

        # Simulate a grant that succeeds before an exception.
        original_grant(grant)

        raise RuntimeError(
            "Simulated failure after access grant"
        )

    access_policy.grant = grant_then_fail

    with pytest.raises(
        RuntimeError,
        match="failure after access grant",
    ):
        upload(environment)

    assert len(captured_grants) == 1

    failed_grant = captured_grants[0]

    # The access grant must have been revoked.
    assert not access_policy.can_read(
        context=make_context(),
        asset_id=failed_grant.asset_id,
    )

    # No partial ingestion records may remain.
    assert len(environment.assets._assets) == 0

    assert len(
        environment.upload_workflow.image_sources._items
    ) == 0

    assert len(
        environment.upload_workflow.descriptions._records
    ) == 0

    assert len(environment.index._documents) == 0
    
def test_cleanup_failure_does_not_skip_remaining_cleanup():
    environment = make_environment()

    workflow = environment.upload_workflow

    original_grant = workflow.asset_access.grant
    original_revoke = workflow.asset_access.revoke

    captured_grants = []

    def grant_then_fail(grant):
        captured_grants.append(grant)
        original_grant(grant)
        raise RuntimeError("Simulated grant failure")

    def revoke_then_fail(grant):
        original_revoke(grant)
        raise RuntimeError("Simulated revoke failure")

    workflow.asset_access.grant = grant_then_fail
    workflow.asset_access.revoke = revoke_then_fail

    with pytest.raises(
        MultimodalRollbackError,
        match="cleanup was incomplete",
    ):
        upload(environment)

    assert len(captured_grants) == 1

    assert not workflow.asset_access.can_read(
        context=make_context(),
        asset_id=captured_grants[0].asset_id,
    )

    # Cleanup must continue after revoke() raises.
    assert len(environment.assets._assets) == 0
    assert len(workflow.image_sources._items) == 0
    assert len(workflow.descriptions._records) == 0
    assert len(environment.index._documents) == 0