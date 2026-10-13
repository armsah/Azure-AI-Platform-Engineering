import json
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_threat_model import validate_threat_model


ROOT = Path(__file__).resolve().parents[3]


def test_repository_threat_model_complete():
    assert validate_threat_model(
        ROOT / "operations/b9-threat-model.json"
    ) == []


def test_missing_stride_category_rejected(tmp_path):
    source = ROOT / "operations/b9-threat-model.json"
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    data["threats"].pop()

    path = tmp_path / "threats.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    assert any(
        "Missing STRIDE category" in error
        for error in validate_threat_model(path)
    )


def test_missing_verification_rejected(tmp_path):
    source = ROOT / "operations/b9-threat-model.json"
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    data["threats"][0]["verification"] = ""

    path = tmp_path / "threats.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    assert any(
        "missing verification" in error
        for error in validate_threat_model(path)
    )
