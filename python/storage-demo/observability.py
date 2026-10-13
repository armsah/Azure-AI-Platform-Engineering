import os
from contextlib import contextmanager
import logging
import json

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

resource = Resource.create({
    "service.name": os.getenv("OTEL_SERVICE_NAME", "storage-demo-python"),
})

provider = TracerProvider(
    resource=resource,
    shutdown_on_exit=True,
)

if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter())
    )
else:
    provider.add_span_processor(
        SimpleSpanProcessor(ConsoleSpanExporter())
    )

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("storage-demo.ai")

class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "trace_id": getattr(record, "trace_id", ""),
                "span_id": getattr(record, "span_id", ""),
            },
            ensure_ascii=False,
        )


class TraceContextFilter(logging.Filter):
    def filter(self, record):
        span = trace.get_current_span()
        context = span.get_span_context()

        record.trace_id = (
            format(context.trace_id, "032x")
            if context.is_valid else ""
        )
        record.span_id = (
            format(context.span_id, "016x")
            if context.is_valid else ""
        )
        return True

@contextmanager
def traced_operation(name: str, **attributes):
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)

        try:
            yield span
        except Exception:
            span.set_attribute("operation.success", False)
            span.set_attribute(
                "operation.failure_category",
                "unexpected_error",
            )
            raise
        else:
            span.set_attribute("operation.success", True)

def configure_logging():
    root = logging.getLogger()

    for existing_handler in root.handlers:
        if getattr(
            existing_handler,
            "_storage_demo_structured_handler",
            False,
        ):
            return existing_handler

    handler = logging.StreamHandler()

    handler._storage_demo_structured_handler = True

    handler.addFilter(TraceContextFilter())

    handler.setFormatter(JsonLogFormatter())

    root.addHandler(handler)
    root.setLevel(logging.INFO)

    return handler

_otel_logger_provider = None

def configure_otel_logging():
    global _otel_logger_provider

    if _otel_logger_provider is not None:
        return _otel_logger_provider

    if os.getenv("OTEL_SDK_DISABLED", "").lower() == "true":
        return None

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT")

    if not endpoint:
        base_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if base_endpoint:
            endpoint = base_endpoint.rstrip("/") + "/v1/logs"

    if not endpoint:
        return None

    logger_provider = LoggerProvider(
        resource=resource,
        shutdown_on_exit=True,
    )

    exporter = OTLPLogExporter(endpoint=endpoint)

    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(exporter)
    )

    handler = LoggingHandler(
        level=logging.INFO,
        logger_provider=logger_provider,
    )

    set_logger_provider(logger_provider)
    logging.getLogger().addHandler(handler)

    _otel_logger_provider = logger_provider

    return logger_provider

def shutdown_telemetry():
    global _otel_logger_provider

    if _otel_logger_provider is not None:
        _otel_logger_provider.shutdown()
        _otel_logger_provider = None

    provider.shutdown()
