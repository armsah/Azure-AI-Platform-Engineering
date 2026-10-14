"""Offline B10 release decision and evidence validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_release import validate_release

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "release_configuration",
    "automated_tests",
    "security_review",
    "rollback_plan",
    "recovery_drill",
    "architecture_review",
}
VALID_STATUSES = {"PASS", "PENDING", "FAIL"}
PRODUCTION_APPROVALS = {
    "automated_tests",
    "security_review",
    "recovery_drill",
    "architecture_review",
}


def assess(root: Path = ROOT) -> tuple[str, list[str]]:
    errors = validate_release(root)
    manifest = json.loads(
        (root / "release/b10-evidence.json").read_text(encoding="utf-8")
    )

    checks = manifest.get("checks")
    if not isinstance(checks, list):
        return "NO-GO", errors + ["checks must be a list"]

    ids = [check.get("id") for check in checks if isinstance(check, dict)]
    if len(ids) != len(checks) or set(ids) != REQUIRED or len(ids) != len(REQUIRED):
        errors.append("B10 evidence must contain exactly the required checks")
        return "NO-GO", errors

    for check in checks:
        identifier = check["id"]
        status = check.get("status")
        evidence = check.get("evidence")

        if status not in VALID_STATUSES:
            errors.append(f"{identifier}: invalid status")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{identifier}: missing evidence")
            continue

        for reference in evidence:
            if not isinstance(reference, str) or not reference.strip():
                errors.append(f"{identifier}: invalid evidence reference")
            elif Path(reference).is_absolute() or ".." in Path(reference).parts:
                errors.append(f"{identifier}: unsafe evidence path")
            elif not (root / reference).is_file():
                errors.append(f"{identifier}: evidence file not found: {reference}")

        if status == "FAIL":
            errors.append(f"{identifier}: failed")

        # Production approvals require explicit verified evidence.
        if status == "PASS" and identifier in PRODUCTION_APPROVALS:
            if check.get("verified") is not True:
                errors.append(f"{identifier}: PASS requires verified evidence")
            if not isinstance(check.get("approved_by"), str) or not check["approved_by"].strip():
                errors.append(f"{identifier}: PASS requires an approver")
            if not isinstance(check.get("approved_at"), str) or not check["approved_at"].strip():
                errors.append(f"{identifier}: PASS requires an approval timestamp")

    if errors:
        return "NO-GO", errors

    if any(check["status"] != "PASS" for check in checks):
        return "NO-GO", ["Release evidence is incomplete"]

    return "GO", []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()

    decision, reasons = assess(args.root)
    print(f"B10 release decision: {decision}")
    for reason in reasons:
        print(f"- {reason}")

    # NO-GO is an expected safe outcome for an unapproved production release.
    # Only structural/configuration failures cause a nonzero exit.
    return 0 if reasons == ["Release evidence is incomplete"] or decision == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
