import asyncio
import os
import random
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel

from . import db, faults
from .logging_config import configure_logging, current_trace_id, emit_json, emit_logfmt
from .telemetry import configure_profiling, configure_tracing

SERVICE_NAME = os.getenv("SERVICE_NAME", "backend")
REPLICA_ID = os.getenv("REPLICA_ID", "backend-unknown")

logger = configure_logging()

HTTP_REQUESTS = Counter(
    "demo_http_requests_total",
    "HTTP requests handled by demo services.",
    ["service", "replica", "method", "route", "status"],
)
HTTP_DURATION = Histogram(
    "demo_http_request_duration_seconds",
    "HTTP request duration for demo services.",
    ["service", "replica", "method", "route", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
HTTP_REQUEST_BYTES = Counter(
    "demo_http_request_bytes_total",
    "Approximate HTTP request bytes received by demo services.",
    ["service", "replica", "method", "route", "status"],
)
HTTP_RESPONSE_BYTES = Counter(
    "demo_http_response_bytes_total",
    "Approximate HTTP response bytes sent by demo services.",
    ["service", "replica", "method", "route", "status"],
)
FAULT_STATE = Gauge(
    "demo_fault_state",
    "Active fault settings. Latency is milliseconds, error_rate is percent, memory_mb is retained megabytes.",
    ["service", "replica", "fault"],
)
BUILD_INFO = Gauge(
    "demo_build_info",
    "Build and replica information for demo services.",
    ["service", "replica"],
)
BUILD_INFO.labels(SERVICE_NAME, REPLICA_ID).set(1)

app = FastAPI(title="Observability Demo Backend")
configure_tracing(app)
configure_profiling()


class CheckoutRequest(BaseModel):
    product_id: int = 1


def _fault_metrics() -> None:
    state = faults.snapshot()
    FAULT_STATE.labels(SERVICE_NAME, REPLICA_ID, "latency_ms").set(state.latency_ms)
    FAULT_STATE.labels(SERVICE_NAME, REPLICA_ID, "error_rate").set(state.error_rate)
    memory_mb = sum(len(block) for block in state.memory_blocks) // (1024 * 1024)
    FAULT_STATE.labels(SERVICE_NAME, REPLICA_ID, "memory_mb").set(memory_mb)


def _fault_event(event: str, **fields) -> None:
    emit_json(
        logger,
        level="warning",
        service=SERVICE_NAME,
        replica=REPLICA_ID,
        event=event,
        trace_id=current_trace_id(),
        **fields,
    )


def _header_int(headers, name: str) -> int:
    try:
        return max(0, int(headers.get(name, "0") or 0))
    except ValueError:
        return 0


def _headers_size(headers) -> int:
    return sum(len(key) + len(value) + 4 for key, value in headers.items())


def _request_bytes(request: Request) -> int:
    return len(request.method) + len(str(request.url)) + _headers_size(request.headers) + _header_int(
        request.headers, "content-length"
    )


async def _count_response_bytes(response: Response) -> tuple[Response, int]:
    body = getattr(response, "body", None)
    if body is None:
        chunks = [chunk async for chunk in response.body_iterator]
        body = b"".join(chunks)
        headers = dict(response.headers)
        headers.pop("transfer-encoding", None)
        headers["content-length"] = str(len(body))
        response = Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )
    return response, len(body) + _headers_size(response.headers)


@app.middleware("http")
async def record_requests_and_apply_faults(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    route = request.url.path
    response = None
    response_bytes = 0
    try:
        state = faults.snapshot()
        path = request.url.path
        is_fault_target = path.startswith("/api/") and not path.startswith("/api/fault")

        if is_fault_target and state.latency_ms > 0:
            await asyncio.sleep(state.latency_ms / 1000)

        if is_fault_target and state.error_rate > 0 and random.randint(1, 100) <= state.error_rate:
            status = 503
            _fault_event("fault_error_injected", path=path, error_rate=state.error_rate)
            response = JSONResponse(
                {
                    "error": "injected backend failure",
                    "backend_replica": REPLICA_ID,
                    "error_rate": state.error_rate,
                },
                status_code=status,
            )
            response_bytes = len(response.body) + _headers_size(response.headers)
            return response

        response = await call_next(request)
        response, response_bytes = await _count_response_bytes(response)
        status = response.status_code
        return response
    finally:
        duration = time.perf_counter() - start
        route = getattr(request.scope.get("route"), "path", route)
        if request.url.path != "/metrics":
            HTTP_REQUESTS.labels(SERVICE_NAME, REPLICA_ID, request.method, route, str(status)).inc()
            HTTP_DURATION.labels(SERVICE_NAME, REPLICA_ID, request.method, route, str(status)).observe(duration)
            HTTP_REQUEST_BYTES.labels(SERVICE_NAME, REPLICA_ID, request.method, route, str(status)).inc(
                _request_bytes(request)
            )
            HTTP_RESPONSE_BYTES.labels(SERVICE_NAME, REPLICA_ID, request.method, route, str(status)).inc(
                response_bytes
            )
            _fault_metrics()
            emit_logfmt(
                logger,
                level="info",
                service=SERVICE_NAME,
                replica=REPLICA_ID,
                method=request.method,
                path=request.url.path,
                route=route,
                status=status,
                duration_ms=int(duration * 1000),
                trace_id=current_trace_id(),
            )


@app.get("/metrics")
def metrics() -> Response:
    _fault_metrics()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "service": SERVICE_NAME, "replica": REPLICA_ID, "database": db.healthcheck()}


@app.get("/api/products")
def products() -> dict[str, object]:
    return {"backend_replica": REPLICA_ID, "products": db.get_products()}


@app.get("/api/orders")
def orders() -> dict[str, object]:
    return {"backend_replica": REPLICA_ID, "orders": db.get_orders()}


@app.post("/api/checkout")
def checkout(payload: CheckoutRequest) -> dict[str, object]:
    try:
        order = db.create_order(payload.product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"backend_replica": REPLICA_ID, "order": order}


@app.get("/api/fault/status")
def fault_status() -> dict[str, object]:
    state = faults.snapshot()
    return {
        "backend_replica": REPLICA_ID,
        "latency_ms": state.latency_ms,
        "error_rate": state.error_rate,
        "memory_mb": sum(len(block) for block in state.memory_blocks) // (1024 * 1024),
    }


@app.get("/api/fault/latency")
def fault_latency(ms: int = 1000) -> dict[str, object]:
    enabled = faults.set_latency(ms)
    _fault_event("fault_latency_enabled", latency_ms=enabled)
    return {"backend_replica": REPLICA_ID, "latency_ms": enabled}


@app.get("/api/fault/errors")
def fault_errors(rate: int = 25) -> dict[str, object]:
    enabled = faults.set_error_rate(rate)
    _fault_event("fault_errors_enabled", error_rate=enabled)
    return {"backend_replica": REPLICA_ID, "error_rate": enabled}


@app.get("/api/fault/memory")
def fault_memory(mb: int = 128) -> dict[str, object]:
    total_mb = faults.grow_memory(mb)
    _fault_event("fault_memory_grew", added_mb=mb, total_mb=total_mb)
    return {"backend_replica": REPLICA_ID, "memory_mb": total_mb}


@app.get("/api/fault/cpu")
def fault_cpu(seconds: int = 10) -> dict[str, object]:
    seconds = max(1, min(seconds, 60))
    _fault_event("fault_cpu_started", seconds=seconds)
    end = time.perf_counter() + seconds
    value = 17
    while time.perf_counter() < end:
        value = ((value * 31) + 7) % 1_000_003
    _fault_event("fault_cpu_finished", seconds=seconds, checksum=value)
    return {"backend_replica": REPLICA_ID, "cpu_seconds": seconds, "checksum": value}


@app.get("/api/fault/db-slow")
def fault_db_slow(seconds: int = 3) -> dict[str, object]:
    seconds = max(1, min(seconds, 30))
    _fault_event("fault_db_slow_started", seconds=seconds)
    result = db.slow_query(seconds)
    _fault_event("fault_db_slow_finished", **result)
    return {"backend_replica": REPLICA_ID, "db": result}


@app.get("/api/fault/db-connections")
def fault_db_connections(count: int = 20, seconds: int = 30) -> dict[str, object]:
    started = db.hold_connections(count, seconds)
    _fault_event("fault_db_connections_started", count=started, seconds=seconds)
    return {"backend_replica": REPLICA_ID, "connections_started": started, "hold_seconds": seconds}


@app.get("/api/fault/reset")
def fault_reset() -> dict[str, object]:
    faults.reset()
    _fault_metrics()
    _fault_event("faults_reset")
    return {"backend_replica": REPLICA_ID, "reset": True}
