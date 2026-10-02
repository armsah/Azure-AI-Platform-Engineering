from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    ConsoleSpanExporter,
)
from contextlib import contextmanager

provider = TracerProvider()

provider.add_span_processor(
    SimpleSpanProcessor(ConsoleSpanExporter())
)

trace.set_tracer_provider(provider)

tracer = trace.get_tracer("storage-demo.ai")

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