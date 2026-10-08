from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    directory_tenant_id: str
    tenant_id: str
    user_id: str
    groups: tuple[str, ...]
    roles: tuple[str, ...] = ()
    correlation_id: str | None = None
    