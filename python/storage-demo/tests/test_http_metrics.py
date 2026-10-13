from fastapi.testclient import TestClient

from app import app


def test_metrics_endpoint_exposes_prometheus_format():
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "storage_demo_http_requests_total" in response.text
    assert "storage_demo_http_request_duration_seconds" in response.text


def test_http_requests_are_counted_by_route():
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200

    metrics = client.get("/metrics").text

    assert 'method="GET",route="/health",status="200"' in metrics


def test_unknown_paths_use_bounded_label():
    client = TestClient(app)

    response = client.get("/nonexistent-observability-test")
    assert response.status_code == 404

    metrics = client.get("/metrics").text

    assert 'route="unmatched",status="404"' in metrics
    assert 'route="/nonexistent-observability-test"' not in metrics
