from __future__ import annotations

import sys
from pathlib import Path

import yaml


def update_digest(path: Path, digest: str) -> None:
    if not digest.startswith("sha256:"):
        raise ValueError("Image digest must start with sha256:")

    document = yaml.safe_load(path.read_text(encoding="utf-8"))

    try:
        document["spec"]["values"]["image"]["digest"] = digest
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"{path} does not contain spec.values.image.digest"
        ) from exc

    path.write_text(
        yaml.safe_dump(document, sort_keys=False),
        encoding="utf-8",
    )


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: update_gitops_digest.py <values-patch.yaml> <sha256:digest>"
        )

    path = Path(sys.argv[1])
    digest = sys.argv[2]

    if not path.is_file():
        raise FileNotFoundError(path)

    update_digest(path, digest)
    print(f"Updated {path} -> {digest}")


if __name__ == "__main__":
    main()