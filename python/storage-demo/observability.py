import os
from contextlib import contextmanager
import logging

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

provider = TracerProvider(resource=resource)

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
        except Exception as exc:
            span.record_exception(exc)
            span.set_attribute("operation.success", False)
            raise
        else:
            span.set_attribute("operation.success", True)
            
def configure_logging():
    handler = logging.StreamHandler()
    handler.addFilter(TraceContextFilter())

    handler.setFormatter(logging.Formatter(
        '{"timestamp":"%(asctime)s",'
        '"level":"%(levelname)s",'
        '"logger":"%(name)s",'
        '"message":"%(message)s",'
        '"trace_id":"%(trace_id)s",'
        '"span_id":"%(span_id)s"}'
    ))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    
def configure_otel_logging():
    provider = LoggerProvider()
    set_logger_provider(provider)

    exporter = OTLPLogExporter(
        endpoint="http://localhost:4318/v1/logs"
    )

    provider.add_log_record_processor(
        BatchLogRecordProcessor(exporter)
    )

    handler = LoggingHandler(
        level=logging.INFO,
        logger_provider=provider,
    )

    logging.getLogger().addHandler(handler)