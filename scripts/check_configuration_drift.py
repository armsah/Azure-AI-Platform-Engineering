from __future__ import annotations

import argparse
import json
from pathlib import Path

from platform_lifecycle import detect_drift


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only comparison of desired and observed JSON snapshots"
    )
    parser.add_argument("--desired", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    try:
        desired = json.loads(args.desired.read_text(encoding="utf-8-sig"))
        actual = json.loads(args.actual.read_text(encoding="utf-8-sig"))

        if not isinstance(desired, dict) or not isinstance(actual, dict):
            raise ValueError("Both snapshots must contain JSON objects")

        differences = detect_drift(desired, actual)

        result = {
            "status": "DRIFT" if differences else "MATCH",
            "desired": str(args.desired),
            "actual": str(args.actual),
            "differences": differences,
        }

        output = json.dumps(result, indent=2)
        print(output)

        if args.report:
            args.report.write_text(output + "\n", encoding="utf-8")

        return 2 if differences else 0

    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
