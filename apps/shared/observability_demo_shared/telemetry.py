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


def configure_tracing(
    app: FastAPI,
    *,
    default_service_name: str,
    instrument_psycopg2: bool = False,
) -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://alloy:4317")
    service_name = os.getenv("SERVICE_NAME", default_service_name)
    replica_id = os.getenv("REPLICA_ID", f"{default_service_name}-unknown")

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.instance.id": replica_id,
            "deployment.environment": "local",
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls="/metrics")
    RequestsInstrumentor().instrument()

    if instrument_psycopg2:
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

        Psycopg2Instrumentor().instrument()


def configure_profiling(*, default_service_name: str, logger_name: str) -> None:
    server_address = os.getenv("PYROSCOPE_SERVER_ADDRESS")
    if not server_address:
        return

    try:
        import pyroscope

        pyroscope.configure(
            application_name=f"{os.getenv('SERVICE_NAME', default_service_name)}.{os.getenv('REPLICA_ID', 'unknown')}",
            server_address=server_address,
            tags={
                "service": os.getenv("SERVICE_NAME", default_service_name),
                "replica": os.getenv("REPLICA_ID", "unknown"),
                "environment": "local",
            },
        )
    except Exception as exc:  # pragma: no cover - profiling should not break the app
        logging.getLogger(logger_name).warning("profiling_setup_failed error=%s", exc)
