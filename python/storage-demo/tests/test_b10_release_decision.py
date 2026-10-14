"""B10 offline release decision regression tests."""

import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "validate_b10", ROOT / "scripts/validate_b10.py"
)

import sys
sys.path.insert(0, str(ROOT / "scripts"))

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture_repo(tmp_path):
    for directory in ("release", "gitops", "operations", "python"):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    shutil.copy(ROOT / "README.md", tmp_path / "README.md")
    return tmp_path


def test_production_release_is_no_go():
    decision, reasons = MODULE.assess(ROOT)
    assert decision == "NO-GO"
    assert "Release evidence is incomplete" in reasons


def test_missing_evidence_blocks_release(tmp_path):
    root = fixture_repo(tmp_path)
    path = root / "release/b10-evidence.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["checks"][0]["evidence"] = ["missing-evidence.txt"]
    path.write_text(json.dumps(data), encoding="utf-8")
    decision, reasons = MODULE.assess(root)
    assert decision == "NO-GO"
    assert any("evidence file not found" in reason for reason in reasons)


def test_duplicate_check_blocks_release(tmp_path):
    root = fixture_repo(tmp_path)
    path = root / "release/b10-evidence.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["checks"].append(data["checks"][0])
    path.write_text(json.dumps(data), encoding="utf-8")
    decision, reasons = MODULE.assess(root)
    assert decision == "NO-GO"
    assert any("exactly the required checks" in reason for reason in reasons)


def test_failed_security_review_blocks_release(tmp_path):
    root = fixture_repo(tmp_path)
    path = root / "release/b10-evidence.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    next(
        check for check in data["checks"]
        if check["id"] == "security_review"
    )["status"] = "FAIL"
    path.write_text(json.dumps(data), encoding="utf-8")
    decision, reasons = MODULE.assess(root)
    assert decision == "NO-GO"
    assert any("security_review: failed" in reason for reason in reasons)


def test_unverified_approval_blocks_release(tmp_path):
    root = fixture_repo(tmp_path)
    path = root / "release/b10-evidence.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    security = next(
        check for check in data["checks"]
        if check["id"] == "security_review"
    )
    security["status"] = "PASS"

    path.write_text(json.dumps(data), encoding="utf-8")

    decision, reasons = MODULE.assess(root)
    assert decision == "NO-GO"
    assert any(
        "security_review: PASS requires verified evidence" in reason
        for reason in reasons
    )
