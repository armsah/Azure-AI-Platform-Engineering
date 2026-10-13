"""Fail closed when B8/B9 acceptance lacks operational evidence."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "operations" / "b8-b9-evidence.json"

REQUIRED = {
    "B8.1-portability",
    "B8.1-drift",
    "B8.1-preview",
    "B8.2-load",
    "B8.2-autoscaling",
    "B8.2-finops",
    "B9.1-chaos",
    "B9.1-incident",
    "B9.2-threat-model",
    "B9.2-runbooks",
}


def validate(data):
    errors = []
    if data.get("schema_version") != 1:
        errors.append("Unsupported schema_version")

    requirements = data.get("requirements")
    if not isinstance(requirements, list):
        return ["requirements must be a list"]

    ids = [item.get("id") for item in requirements if isinstance(item, dict)]
    if len(ids) != len(requirements) or len(ids) != len(set(ids)):
        errors.append("Duplicate or invalid requirement entries")

    if set(ids) != REQUIRED:
        errors.append("Requirement IDs do not match the B8/B9 acceptance matrix")

    for item in requirements:
        if not isinstance(item, dict):
            continue

        requirement_id = item.get("id", "<unknown>")
        status = item.get("status")
        evidence = item.get("live_evidence")

        if status not in {"PARTIAL", "COMPLETE"}:
            errors.append(f"{requirement_id}: invalid status")

        if not isinstance(evidence, list):
            errors.append(f"{requirement_id}: live_evidence must be a list")
            continue

        if status == "COMPLETE":
            if not evidence:
                errors.append(f"{requirement_id}: COMPLETE requires live evidence")
            elif any(
                not isinstance(entry, dict)
                or not isinstance(entry.get("reference"), str)
                or not entry["reference"].strip()
                or entry.get("verified") is not True
                for entry in evidence
            ):
                errors.append(f"{requirement_id}: evidence must be verified and referenced")

    return errors


def main():
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
        errors = validate(data)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    complete = sum(
        item["status"] == "COMPLETE" for item in data["requirements"]
    )
    print(f"PASS: B8/B9 evidence manifest valid; {complete}/10 COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
