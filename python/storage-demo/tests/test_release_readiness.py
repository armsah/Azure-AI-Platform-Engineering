"""B8 offline release-readiness regression tests."""

import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "validate_release", ROOT / "scripts/validate_release.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture_repo(tmp_path):
    for directory in ("release", "gitops"):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    return tmp_path


def test_release_configuration_is_valid():
    assert MODULE.validate_release(ROOT) == []


def test_invalid_digest_is_rejected(tmp_path):
    root = fixture_repo(tmp_path)
    path = root / "gitops/environments/dev/values-patch.yaml"
    text = path.read_text(encoding="utf-8")
    import re
    text = re.sub(r"sha256:[0-9a-f]{64}", "sha256:invalid", text)
    path.write_text(text, encoding="utf-8")
    assert any("invalid image digest" in e for e in MODULE.validate_release(root))


def test_replica_configuration_drift_is_rejected(tmp_path):
    root = fixture_repo(tmp_path)
    path = root / "gitops/environments/prod/values.yaml"
    text = path.read_text(encoding="utf-8").replace(
        "replicaCount: 3", "replicaCount: 1"
    )
    path.write_text(text, encoding="utf-8")
    assert any("replica count drift" in e for e in MODULE.validate_release(root))


def test_unreviewed_production_digest_divergence_is_rejected(tmp_path):
    root = fixture_repo(tmp_path)
    path = root / "gitops/environments/prod/values-patch.yaml"
    text = path.read_text(encoding="utf-8")
    import re
    text = re.sub(r"sha256:[0-9a-f]{64}", "sha256:" + "0" * 64, text)
    path.write_text(text, encoding="utf-8")
    assert any("promotion not verified" in e for e in MODULE.validate_release(root))


def test_namespace_drift_is_rejected(tmp_path):
    root = fixture_repo(tmp_path)
    path = root / "gitops/environments/staging/kustomization.yaml"
    text = path.read_text(encoding="utf-8").replace(
        "namespace: storage-demo-staging", "namespace: unexpected"
    )
    path.write_text(text, encoding="utf-8")
    assert any("namespace differs" in e for e in MODULE.validate_release(root))


def test_recovery_runbook_documents_safety():
    text = (ROOT / "release/RECOVERY-RUNBOOK.md").read_text(encoding="utf-8")
    assert "VALIDATION_ONLY=true" in text
    assert "Do not start it" in text
    assert "last known-good" in text
