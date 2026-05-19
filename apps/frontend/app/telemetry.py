import logging
import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_tracing(app: FastAPI) -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://alloy:4317")
    service_name = os.getenv("SERVICE_NAME", "frontend")
    replica_id = os.getenv("REPLICA_ID", "frontend-unknown")

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.instance.id": replica_id,
            "deployment.environment": "local",
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls="/metrics")
    RequestsInstrumentor().instrument()


def configure_profiling() -> None:
    server_address = os.getenv("PYROSCOPE_SERVER_ADDRESS")
    if not server_address:
        return

    try:
        import pyroscope

        pyroscope.configure(
            application_name=f"{os.getenv('SERVICE_NAME', 'frontend')}.{os.getenv('REPLICA_ID', 'unknown')}",
            server_address=server_address,
            tags={
                "service": os.getenv("SERVICE_NAME", "frontend"),
                "replica": os.getenv("REPLICA_ID", "unknown"),
                "environment": "local",
            },
        )
    except Exception as exc:  # pragma: no cover - profiling should not break the app
        logging.getLogger("frontend").warning("profiling_setup_failed error=%s", exc)
