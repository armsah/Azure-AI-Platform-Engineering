import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
digest = sys.argv[2]

if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
    raise ValueError(f"Invalid SHA-256 digest: {digest}")

content = path.read_text(encoding="utf-8")

pattern = r'(\s+digest:\s*)"sha256:[^"]+"'
updated, count = re.subn(
    pattern,
    rf'\1"{digest}"',
    content,
    count=1,
)

if count != 1:
    raise RuntimeError(
        f"Expected exactly one image digest, found {count}"
    )

path.write_text(updated, encoding="utf-8")