"""Offline release policy and GitOps configuration validation."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
ENVIRONMENTS = ("dev", "staging", "prod")


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected YAML mapping")
    return data


def validate_release(root: Path = ROOT) -> list[str]:
    errors = []
    policy = load_yaml(root / "release/release-manifest.yaml")["spec"]
    base = load_yaml(root / "gitops/apps/storage-demo/helm/helmrelease.yaml")
    image = base["spec"]["values"]["image"]

    if image.get("repository") != policy["imageRepository"]:
        errors.append("Base HelmRelease image repository differs from release policy")

    base_digest = image.get("digest")
    if base_digest != "sha256:REPLACED_BY_CI" and not (
        isinstance(base_digest, str) and DIGEST.fullmatch(base_digest)
    ):
        errors.append("Base HelmRelease image digest is invalid")

    digests = {}

    for env in ENVIRONMENTS:
        directory = root / "gitops/environments" / env
        patch = load_yaml(directory / "values-patch.yaml")
        values = load_yaml(directory / "values.yaml")
        kustomization = load_yaml(directory / "kustomization.yaml")
        expected = policy["environments"][env]

        if patch.get("kind") != "HelmRelease":
            errors.append(f"{env}: patch must target HelmRelease")
            continue

        config = patch["spec"]["values"]
        digest = config.get("image", {}).get("digest")

        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            errors.append(f"{env}: invalid image digest")
        else:
            digests[env] = digest

        if config.get("environment") != env or values.get("environment") != env:
            errors.append(f"{env}: environment label mismatch")

        if kustomization.get("namespace") != expected["namespace"]:
            errors.append(f"{env}: namespace differs from release policy")

        if "../../apps/storage-demo" not in kustomization.get("resources", []):
            errors.append(f"{env}: missing application resource")

        patches = kustomization.get("patches", [])
        if not any(
            p.get("path") == "values-patch.yaml"
            and p.get("target", {}).get("kind") == "HelmRelease"
            for p in patches if isinstance(p, dict)
        ):
            errors.append(f"{env}: HelmRelease values patch not wired")

        for source_name, source in (("values", values), ("patch", config)):
            replicas = source.get("replicaCount")
            scaling = source.get("autoscaling", {})
            minimum = scaling.get("minReplicas")
            maximum = scaling.get("maxReplicas")

            if replicas != expected["minReplicas"]:
                errors.append(f"{env}: {source_name} replica count drift")

            if minimum != expected["minReplicas"]:
                errors.append(f"{env}: {source_name} minimum replica drift")

            if maximum != expected["maxReplicas"]:
                errors.append(f"{env}: {source_name} maximum replica drift")

    if digests.get("prod") and digests.get("staging"):
        if digests["prod"] != digests["staging"]:
            errors.append("prod: digest differs from staging; promotion not verified")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()

    errors = validate_release(args.root)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print("PASS: Offline release readiness and GitOps configuration checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
