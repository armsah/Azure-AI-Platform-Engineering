from pathlib import Path
import importlib.util

import yaml


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/validate_security_controls.py"

spec = importlib.util.spec_from_file_location("security_controls", SCRIPT)
security = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security)


def test_security_controls_pass():
    assert security.validate_security_controls() == []


def test_network_policy_cannot_be_disabled(tmp_path):
    import shutil

    root = tmp_path / "repo"
    source = ROOT / "helm/storage-demo"
    destination = root / "helm/storage-demo"

    destination.parent.mkdir(parents=True)
    shutil.copytree(source, destination)

    values_path = destination / "values.yaml"
    values = yaml.safe_load(values_path.read_text(encoding="utf-8"))
    values["networkPolicy"]["enabled"] = False
    values_path.write_text(yaml.safe_dump(values), encoding="utf-8")

    errors = security.validate_security_controls(root)

    assert "NetworkPolicy must be enabled" in errors


def test_missing_service_account_detected(tmp_path):
    import shutil

    root = tmp_path / "repo"
    source = ROOT / "helm/storage-demo"
    destination = root / "helm/storage-demo"

    destination.parent.mkdir(parents=True)
    shutil.copytree(source, destination)

    (destination / "templates/serviceaccount.yaml").unlink()

    errors = security.validate_security_controls(root)

    assert any("serviceaccount.yaml" in error for error in errors)
