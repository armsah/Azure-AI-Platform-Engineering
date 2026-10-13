import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "audit_preview_lifecycle.py"
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("audit_preview_lifecycle", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

NOW = datetime(2026, 10, 14, tzinfo=timezone.utc)


def preview(**changes):
    item = {
        "name": "preview-test",
        "owner": "platform-team",
        "approved": True,
        "costApproved": True,
        "isolatedNamespace": True,
        "createdAt": "2026-10-14T00:00:00Z",
        "expiresAt": "2026-10-14T12:00:00Z",
    }
    item.update(changes)
    return item


def test_valid_preview():
    report = module.audit_previews([preview()], NOW)
    assert report["status"] == "PASS"
    assert report["results"][0]["status"] == "VALID"


def test_expired_preview_requires_review():
    report = module.audit_previews(
        [preview(expiresAt="2026-10-13T12:00:00Z")], NOW
    )
    assert report["status"] == "ACTION_REQUIRED"
    assert report["results"][0]["status"] == "EXPIRED"
    assert report["results"][0]["requiresRetirementReview"] is True


@pytest.mark.parametrize("change", [
    {"approved": False},
    {"costApproved": False},
    {"isolatedNamespace": False},
    {"owner": ""},
    {"name": ""},
    {"expiresAt": "2026-10-16T00:00:00Z"},
])
def test_invalid_preview(change):
    report = module.audit_previews([preview(**change)], NOW)
    assert report["status"] == "ACTION_REQUIRED"
    assert report["results"][0]["status"] == "INVALID"


def test_duplicate_names():
    report = module.audit_previews([preview(), preview()], NOW)
    assert report["results"][1]["status"] == "INVALID"
    assert "Duplicate preview name" in report["results"][1]["errors"]


def test_non_object_preview():
    report = module.audit_previews(["invalid"], NOW)
    assert report["results"][0]["status"] == "INVALID"


def test_cli_expired_inventory(tmp_path):
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps([preview(expiresAt="2026-10-01T00:00:00Z")]),
        encoding="utf-8-sig",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--inventory", str(inventory)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "ACTION_REQUIRED"
