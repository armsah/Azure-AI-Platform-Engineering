from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from platform_lifecycle import validate_preview


def audit_previews(previews: list, now: datetime) -> dict:
    results = []
    seen = set()

    for index, preview in enumerate(previews):
        if not isinstance(preview, dict):
            results.append({
                "index": index,
                "status": "INVALID",
                "errors": ["Preview must be a JSON object"],
            })
            continue

        name = preview.get("name")
        errors = validate_preview(preview, now=now)

        if not isinstance(name, str) or not name.strip():
            errors.append("Preview requires a name")
        elif name in seen:
            errors.append("Duplicate preview name")
        else:
            seen.add(name)

        expired = "Preview has expired" in errors

        results.append({
            "index": index,
            "name": name,
            "owner": preview.get("owner"),
            "status": (
                "EXPIRED" if expired else
                "INVALID" if errors else
                "VALID"
            ),
            "requiresRetirementReview": expired,
            "errors": errors,
        })

    return {
        "status": "ACTION_REQUIRED" if any(
            item["status"] != "VALID" for item in results
        ) else "PASS",
        "checkedAt": now.isoformat(),
        "total": len(results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline preview inventory audit; never provisions or deletes resources"
    )
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    try:
        inventory = json.loads(
            args.inventory.read_text(encoding="utf-8-sig")
        )

        if not isinstance(inventory, list):
            raise ValueError("Inventory must be a JSON array")

        report = audit_previews(inventory, datetime.now(timezone.utc))
        output = json.dumps(report, indent=2)
        print(output)

        if args.report:
            args.report.write_text(output + "\n", encoding="utf-8")

        return 2 if report["status"] == "ACTION_REQUIRED" else 0

    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
