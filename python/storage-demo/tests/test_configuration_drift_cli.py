import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_configuration_drift.py"


def run_detector(tmp_path, desired, actual, *, bom=False):
    desired_path = tmp_path / "desired.json"
    actual_path = tmp_path / "actual.json"

    encoding = "utf-8-sig" if bom else "utf-8"

    desired_path.write_text(json.dumps(desired), encoding=encoding)
    actual_path.write_text(json.dumps(actual), encoding=encoding)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--desired",
            str(desired_path),
            "--actual",
            str(actual_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    return result, json.loads(result.stdout)


@pytest.mark.parametrize("bom", [False, True])
def test_matching_snapshots(tmp_path, bom):
    result, report = run_detector(
        tmp_path,
        {"replicas": 2},
        {"replicas": 2},
        bom=bom,
    )

    assert result.returncode == 0
    assert report["status"] == "MATCH"
    assert report["differences"] == []


@pytest.mark.parametrize("bom", [False, True])
def test_detects_configuration_drift(tmp_path, bom):
    result, report = run_detector(
        tmp_path,
        {"replicas": 2},
        {"replicas": 3},
        bom=bom,
    )

    assert result.returncode == 2
    assert report["status"] == "DRIFT"
    assert report["differences"] == ["Changed: replicas"]


def test_rejects_non_object_snapshots(tmp_path):
    result, report = run_detector(
        tmp_path,
        ["invalid"],
        {"replicas": 2},
    )

    assert result.returncode == 1
    assert report["status"] == "ERROR"


def test_rejects_missing_snapshot(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--desired",
            str(tmp_path / "missing.json"),
            "--actual",
            str(tmp_path / "also-missing.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "ERROR"


def test_writes_drift_report(tmp_path):
    desired = tmp_path / "desired.json"
    actual = tmp_path / "actual.json"
    report_path = tmp_path / "report.json"

    desired.write_text('{"replicas":2}', encoding="utf-8")
    actual.write_text('{"replicas":3}', encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--desired",
            str(desired),
            "--actual",
            str(actual),
            "--report",
            str(report_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert report_path.exists()
    assert json.loads(report_path.read_text(encoding="utf-8"))["status"] == "DRIFT"
