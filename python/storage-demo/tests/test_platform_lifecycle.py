from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "scripts/platform_lifecycle.py"

spec = importlib.util.spec_from_file_location("platform_lifecycle", PATH)
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


def test_no_drift():
    assert lifecycle.detect_drift({"replicas": 2}, {"replicas": 2}) == []


def test_changed_configuration_detected():
    assert lifecycle.detect_drift(
        {"replicas": 2}, {"replicas": 5}
    ) == ["Changed: replicas"]


def test_missing_configuration_detected():
    assert lifecycle.detect_drift(
        {"replicas": 2}, {}
    ) == ["Missing: replicas"]


def test_unexpected_configuration_detected():
    assert lifecycle.detect_drift(
        {}, {"debug": True}
    ) == ["Unexpected: debug"]


def valid_preview():
    now = datetime.now(timezone.utc)
    return {
        "approved": True,
        "costApproved": True,
        "isolatedNamespace": True,
        "owner": "platform-team",
        "createdAt": now.isoformat(),
        "expiresAt": (now + timedelta(hours=2)).isoformat(),
    }


def test_valid_preview():
    assert lifecycle.validate_preview(valid_preview()) == []


def test_preview_requires_approval():
    preview = valid_preview()
    preview["approved"] = False
    assert "Preview requires approval" in lifecycle.validate_preview(preview)


def test_preview_requires_cost_approval():
    preview = valid_preview()
    preview["costApproved"] = False
    assert "Preview requires approved cost estimate" in lifecycle.validate_preview(
        preview
    )


def test_preview_expiration():
    preview = valid_preview()
    preview["expiresAt"] = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()
    assert "Preview has expired" in lifecycle.validate_preview(preview)


def test_preview_lifetime_limit():
    preview = valid_preview()
    preview["expiresAt"] = (
        datetime.now(timezone.utc) + timedelta(hours=48)
    ).isoformat()
    assert "Preview lifetime must be at most 24 hours" in (
        lifecycle.validate_preview(preview)
    )


def test_portability_inventory():
    assert lifecycle.validate_portability(ROOT) == []
