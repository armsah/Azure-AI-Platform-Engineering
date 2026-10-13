"""Negative and positive tests for B8/B9 acceptance evidence."""

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_b8_b9_evidence import MANIFEST, REQUIRED, validate


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8-sig"))


def test_current_manifest_valid():
    assert validate(manifest()) == []


def test_all_ten_requirements_present():
    assert {item["id"] for item in manifest()["requirements"]} == REQUIRED


def test_complete_without_evidence_rejected():
    data = manifest()
    data["requirements"][0]["status"] = "COMPLETE"
    assert validate(data)


def test_unverified_evidence_rejected():
    data = manifest()
    data["requirements"][0].update(
        status="COMPLETE",
        live_evidence=[{"reference": "exercise-001", "verified": False}],
    )
    assert validate(data)


def test_blank_reference_rejected():
    data = manifest()
    data["requirements"][0].update(
        status="COMPLETE",
        live_evidence=[{"reference": " ", "verified": True}],
    )
    assert validate(data)


def test_duplicate_requirement_rejected():
    data = manifest()
    data["requirements"].append(copy.deepcopy(data["requirements"][0]))
    assert validate(data)


def test_missing_requirement_rejected():
    data = manifest()
    data["requirements"].pop()
    assert validate(data)


def test_invalid_status_rejected():
    data = manifest()
    data["requirements"][0]["status"] = "DONE"
    assert validate(data)


def test_complete_with_verified_reference_accepted():
    data = manifest()
    data["requirements"][0].update(
        status="COMPLETE",
        live_evidence=[{"reference": "approved-exercise-001", "verified": True}],
    )
    assert validate(data) == []
