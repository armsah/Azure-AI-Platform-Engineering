from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_alert_rules_define_error_and_latency_conditions():
    text = (ROOT / "observability/alerts.yaml").read_text(encoding="utf-8")
    assert "StorageDemoHighErrorRate" in text
    assert "StorageDemoHighLatency" in text
    assert "storage_demo_http_requests_total" in text
    assert "storage_demo_http_request_duration_seconds_bucket" in text
    assert "for: 10m" in text


def test_slo_and_runbook_document_operations():
    slo = (ROOT / "observability/SLO.md").read_text(encoding="utf-8")
    runbook = (ROOT / "observability/RUNBOOK.md").read_text(encoding="utf-8")

    assert "99.9%" in slo
    assert "95%" in slo
    assert "GET /metrics" in runbook
    assert "Do not start AKS" in runbook
