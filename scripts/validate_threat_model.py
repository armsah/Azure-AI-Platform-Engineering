from __future__ import annotations

import json
from pathlib import Path

REQUIRED = {
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information disclosure",
    "Denial of service",
    "Elevation of privilege",
}


def validate_threat_model(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    threats = data.get("threats")

    if not isinstance(threats, list):
        return ["Threats must be a list"]

    errors = []
    categories = set()

    for index, threat in enumerate(threats):
        if not isinstance(threat, dict):
            errors.append(f"Threat {index} must be an object")
            continue

        category = threat.get("category")
        if not isinstance(category, str) or category not in REQUIRED:
            errors.append(f"Invalid category at index {index}")
            continue

        if category in categories:
            errors.append(f"Duplicate category: {category}")

        categories.add(category)

        for field in ("mitigation", "verification"):
            value = threat.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{category}: missing {field}")

    for category in sorted(REQUIRED - categories):
        errors.append(f"Missing STRIDE category: {category}")

    return errors


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    errors = validate_threat_model(root / "operations/b9-threat-model.json")

    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        raise SystemExit(1)

    print("PASS: STRIDE threat-model completeness")
    print("NOTE: Mitigation effectiveness requires separate verification")
