from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    user_id: str
    groups: tuple[str, ...]
    
def build_request_context() -> RequestContext:
    return RequestContext(
        tenant_id="customer-a",
        user_id="user-001",
        groups=("platform-engineering",),
    )