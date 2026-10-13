from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def validate_security_controls(root: Path = ROOT) -> list[str]:
    errors = []

    values = yaml.safe_load(
        (root / "helm/storage-demo/values.yaml").read_text(encoding="utf-8")
    )

    templates = root / "helm/storage-demo/templates"

    required_templates = {
        "networkpolicy.yaml": "NetworkPolicy",
        "serviceaccount.yaml": "ServiceAccount",
        "pdb.yaml": "PodDisruptionBudget",
    }

    for filename, resource in required_templates.items():
        path = templates / filename

        if not path.is_file():
            errors.append(f"Missing Kubernetes security/reliability template: {filename}")
            continue

        if resource not in path.read_text(encoding="utf-8"):
            errors.append(f"Expected {resource} in {filename}")

    if not values.get("networkPolicy", {}).get("enabled"):
        errors.append("NetworkPolicy must be enabled")

    if not values.get("serviceAccount", {}).get("clientId"):
        errors.append("Workload identity client ID is required")

    if values.get("pdb", {}).get("minAvailable", 0) < 1:
        errors.append("Pod disruption protection is required")

    resources = values.get("resources", {})

    if not resources.get("requests") or not resources.get("limits"):
        errors.append("CPU and memory resource boundaries are required")

    deployment = (templates / "deployment.yaml").read_text(encoding="utf-8")

    if "serviceAccountName" not in deployment:
        errors.append("Deployment must specify a service account")

    if "resources:" not in deployment:
        errors.append("Deployment must configure resource boundaries")

    return errors


if __name__ == "__main__":
    problems = validate_security_controls()

    for problem in problems:
        print(f"FAIL: {problem}")

    if problems:
        raise SystemExit(1)

    print("PASS: B9.2 offline security configuration checks")
