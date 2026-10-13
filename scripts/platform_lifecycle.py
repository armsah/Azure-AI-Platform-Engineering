from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


def detect_drift(desired: dict, actual: dict) -> list[str]:
    """Compare desired and observed configuration without changing resources."""
    differences = []

    def compare(expected, observed, location):
        if isinstance(expected, dict) and isinstance(observed, dict):
            for key in sorted(set(expected) | set(observed)):
                path = f"{location}.{key}" if location else key
                if key not in expected:
                    differences.append(f"Unexpected: {path}")
                elif key not in observed:
                    differences.append(f"Missing: {path}")
                else:
                    compare(expected[key], observed[key], path)
        elif expected != observed:
            differences.append(f"Changed: {location}")

    compare(desired, actual, "")
    return differences


def validate_preview(preview: dict, now: datetime | None = None) -> list[str]:
    """Validate preview metadata; never provision or delete infrastructure."""
    errors = []
    now = now or datetime.now(timezone.utc)

    if not preview.get("approved"):
        errors.append("Preview requires approval")

    if not preview.get("costApproved"):
        errors.append("Preview requires approved cost estimate")

    if not preview.get("isolatedNamespace"):
        errors.append("Preview requires namespace isolation")

    if not preview.get("owner"):
        errors.append("Preview requires an owner")

    try:
        created = datetime.fromisoformat(
            preview["createdAt"].replace("Z", "+00:00")
        )
        expires = datetime.fromisoformat(
            preview["expiresAt"].replace("Z", "+00:00")
        )

        if created.tzinfo is None or expires.tzinfo is None:
            errors.append("Preview timestamps must include timezone")
        else:
            lifetime = (expires - created).total_seconds()
            if not 0 < lifetime <= 24 * 3600:
                errors.append("Preview lifetime must be at most 24 hours")
            if expires <= now:
                errors.append("Preview has expired")
    except (KeyError, ValueError, TypeError):
        errors.append("Invalid preview timestamps")

    return errors


def validate_portability(repository_root: Path) -> list[str]:
    """Report portability limitations without claiming multi-cloud readiness."""
    errors = []

    versions = (
        repository_root / "infrastructure/terraform/versions.tf"
    ).read_text(encoding="utf-8")

    if 'source  = "hashicorp/azurerm"' not in versions:
        errors.append("Expected AzureRM provider declaration not found")

    if 'backend "azurerm"' not in versions:
        errors.append("Expected Azure backend declaration not found")

    helm = yaml.safe_load(
        (repository_root / "helm/storage-demo/values.yaml").read_text(
            encoding="utf-8"
        )
    )

    if not helm.get("image", {}).get("digest", "").startswith("sha256:"):
        errors.append("Container image must use immutable digest")

    return errors


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    problems = validate_portability(root)

    if problems:
        print(json.dumps({"status": "FAIL", "errors": problems}, indent=2))
        raise SystemExit(1)

    print("PASS: Offline portability inventory checks")
    print("NOTE: Secondary-cloud deployment remains unverified")
