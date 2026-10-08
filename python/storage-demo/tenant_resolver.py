class TenantResolutionError(Exception):
    pass


# Temporary implementation.
# Replace with persistent membership storage later.
MEMBERSHIPS = {
    # (Entra directory tenant ID, Entra object ID): application tenant
}


def resolve_application_tenant(
    directory_tenant_id: str,
    user_id: str,
) -> str:
    tenant_id = MEMBERSHIPS.get(
        (directory_tenant_id, user_id)
    )

    if tenant_id is None:
        raise TenantResolutionError(
            "User has no application tenant membership"
        )

    return tenant_id