import pytest
import logging
import observability
from unittest.mock import Mock, patch

from observability import traced_operation
from fastapi.testclient import TestClient


def test_traced_operation_returns_span():
    with traced_operation(
        "test.operation",
        component="unit-test",
    ) as span:
        assert span is not None


def test_traced_operation_preserves_exception():
    with pytest.raises(RuntimeError):
        with traced_operation("test.failure"):
            raise RuntimeError("boom")

def test_shutdown_telemetry_closes_providers():
    mock_trace_provider = Mock()
    mock_log_provider = Mock()

    with patch.object(
        observability,
        "provider",
        mock_trace_provider,
    ):
        with patch.object(
            observability,
            "_otel_logger_provider",
            mock_log_provider,
        ):
            observability.shutdown_telemetry()

    mock_trace_provider.shutdown.assert_called_once_with()
    mock_log_provider.shutdown.assert_called_once_with()

def test_otel_logging_disabled_by_environment(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setattr(
        observability,
        "_otel_logger_provider",
        None,
    )

    result = observability.configure_otel_logging()

    assert result is None


def test_otel_logging_requires_export_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.delenv(
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
        raising=False,
    )
    monkeypatch.delenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        raising=False,
    )

    monkeypatch.setattr(
        observability,
        "_otel_logger_provider",
        None,
    )

    result = observability.configure_otel_logging()

    assert result is None

def test_configure_logging_preserves_existing_handlers():
    root = logging.getLogger()

    existing_handler = logging.NullHandler()
    root.addHandler(existing_handler)

    try:
        configured_handler = observability.configure_logging()

        assert existing_handler in root.handlers
        assert configured_handler in root.handlers

    finally:
        root.removeHandler(existing_handler)

        if configured_handler is not None:
            root.removeHandler(configured_handler)
            configured_handler.close()

def test_configure_logging_is_idempotent():
    root = logging.getLogger()

    first_handler = observability.configure_logging()
    second_handler = observability.configure_logging()

    assert first_handler is second_handler

    matching_handlers = [
        handler
        for handler in root.handlers
        if getattr(
            handler,
            "_storage_demo_structured_handler",
            False,
        )
    ]

    assert len(matching_handlers) == 1

def test_configure_logging_preserves_existing_handlers():
    root = logging.getLogger()

    existing_handler = logging.NullHandler()
    root.addHandler(existing_handler)

    try:
        configured_handler = observability.configure_logging()

        assert existing_handler in root.handlers
        assert configured_handler in root.handlers

    finally:
        root.removeHandler(existing_handler)

def test_traced_operation_does_not_record_sensitive_exception():
    mock_span = Mock()

    mock_tracer = Mock()
    mock_tracer.start_as_current_span.return_value.__enter__ = (
        Mock(return_value=mock_span)
    )
    mock_tracer.start_as_current_span.return_value.__exit__ = (
        Mock(return_value=False)
    )

    with patch.object(
        observability,
        "tracer",
        mock_tracer,
    ):
        with pytest.raises(
            RuntimeError,
            match="SECRET_INTERNAL_CONNECTION_STRING",
        ):
            with observability.traced_operation(
                "test.sensitive_failure"
            ):
                raise RuntimeError(
                    "SECRET_INTERNAL_CONNECTION_STRING"
                )

    mock_span.record_exception.assert_not_called()

    mock_span.set_attribute.assert_any_call(
        "operation.success",
        False,
    )

    mock_span.set_attribute.assert_any_call(
        "operation.failure_category",
        "unexpected_error",
    )

def test_otel_logging_uses_configured_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
        "http://collector.example:4318/v1/logs",
    )

    monkeypatch.setattr(
        observability,
        "_otel_logger_provider",
        None,
    )

    mock_provider = Mock()
    mock_exporter = Mock()
    mock_processor = Mock()
    mock_handler = logging.NullHandler()

    with (
        patch.object(
            observability,
            "LoggerProvider",
            return_value=mock_provider,
        ),
        patch.object(
            observability,
            "OTLPLogExporter",
            return_value=mock_exporter,
        ) as exporter_factory,
        patch.object(
            observability,
            "BatchLogRecordProcessor",
            return_value=mock_processor,
        ),
        patch.object(
            observability,
            "LoggingHandler",
            return_value=mock_handler,
        ),
        patch.object(
            observability,
            "set_logger_provider",
        ),
    ):
        try:
            result = observability.configure_otel_logging()

            assert result is mock_provider

            exporter_factory.assert_called_once_with(
                endpoint="http://collector.example:4318/v1/logs"
            )

            mock_provider.add_log_record_processor.assert_called_once_with(
                mock_processor
            )

            assert mock_handler in logging.getLogger().handlers

        finally:
            logging.getLogger().removeHandler(mock_handler)

def test_repeated_app_lifespans_do_not_shutdown_telemetry():
    from app import app

    with patch("observability.provider.shutdown") as trace_shutdown:
        with patch(
            "observability.shutdown_telemetry"
        ) as telemetry_shutdown:
            with TestClient(app):
                pass

            with TestClient(app):
                pass

    trace_shutdown.assert_not_called()
    telemetry_shutdown.assert_not_called()