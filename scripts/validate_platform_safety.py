from __future__ import annotations

from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load(relative_path: str):
    return yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors = []
    policy = load("platform/safety-policy.yaml")["spec"]
    helm = load("helm/storage-demo/values.yaml")

    deployment = policy["deployment"]
    previews = deployment["previewEnvironments"]
    finops = policy["finops"]
    capacity = policy["capacity"]
    chaos = policy["chaos"]

    if deployment["automaticProvisioning"]:
        errors.append("Automatic provisioning must remain disabled")
    if previews["enabled"]:
        errors.append("Preview environments require separate approval")
    if not previews["requireApproval"] or not previews["isolatedNamespace"]:
        errors.append("Preview isolation and approval are required")
    if not 0 < previews["maximumLifetimeHours"] <= 24:
        errors.append("Preview lifetime must not exceed 24 hours")

    if finops["allowAutomaticAzureProvisioning"]:
        errors.append("Automatic Azure provisioning is forbidden")
    if not finops["requireBudgetApproval"] or not finops["requireCostEstimateBeforeApply"]:
        errors.append("Budget approval and cost estimation are required")
    if finops["maximumUnapprovedMonthlyCostUsd"] != 0:
        errors.append("Unapproved monthly spending must be zero")

    autoscaling = helm["autoscaling"]
    if not autoscaling["enabled"]:
        errors.append("HPA must remain enabled")
    for policy_key, helm_key in (
        ("minimumReplicas", "minReplicas"),
        ("maximumReplicas", "maxReplicas"),
        ("cpuTargetPercent", "targetCPUUtilizationPercentage"),
    ):
        if capacity[policy_key] != autoscaling[helm_key]:
            errors.append(f"Capacity mismatch: {policy_key}")

    if capacity["minimumReplicas"] > capacity["maximumReplicas"]:
        errors.append("Invalid replica range")

    resources = helm["resources"]
    if capacity["requireResourceRequests"] and not resources.get("requests"):
        errors.append("Resource requests are required")
    if capacity["requireResourceLimits"] and not resources.get("limits"):
        errors.append("Resource limits are required")

    if chaos["liveFaultInjectionEnabled"]:
        errors.append("Live chaos experiments must remain disabled")
    if not chaos["requireExplicitApproval"]:
        errors.append("Chaos experiments require approval")

    performance = policy["performance"]
    if not 0 < performance["minimumSuccessRate"] <= 1:
        errors.append("Invalid success-rate threshold")
    if performance["maximumP95Milliseconds"] <= 0:
        errors.append("Invalid latency threshold")
    if performance["maximumConcurrentRequestsWithoutApproval"] < 1:
        errors.append("Invalid concurrency limit")

    return errors


if __name__ == "__main__":
    problems = validate()
    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        sys.exit(1)
    print("PASS: B8/B9 offline platform safety policy")
