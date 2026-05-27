import asyncio
import os
import random
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from observability_demo_shared.logging import configure_logging, current_trace_id, emit_json, emit_logfmt
from observability_demo_shared.request_metrics import (
    count_response_bytes,
    create_http_metrics,
    headers_size,
    request_bytes,
)
from observability_demo_shared.telemetry import configure_profiling, configure_tracing

from . import db, faults

SERVICE_NAME = os.getenv("SERVICE_NAME", "backend")
REPLICA_ID = os.getenv("REPLICA_ID", "backend-unknown")

logger = configure_logging("backend")

HTTP_METRICS = create_http_metrics(SERVICE_NAME, REPLICA_ID)
HTTP_REQUESTS = HTTP_METRICS.requests
HTTP_DURATION = HTTP_METRICS.duration
HTTP_REQUEST_BYTES = HTTP_METRICS.request_bytes
HTTP_RESPONSE_BYTES = HTTP_METRICS.response_bytes
BUILD_INFO = HTTP_METRICS.build_info

app = FastAPI(title="Observability Demo Backend")
configure_tracing(app, default_service_name="backend", instrument_psycopg2=True)
configure_profiling(default_service_name="backend", logger_name="backend")


class CheckoutRequest(BaseModel):
    product_id: int = 1


class FaultConfigureRequest(BaseModel):
    scope: str = faults.DEFAULT_SCOPE
    latency_ms: int = 0
    jitter_ms: int = 0
    error_rate: int = 0
    error_status: int = 503
    cpu_ms: int = 0
    db_delay_ms: int = 0


def _error_event(event: str, **fields: Any) -> None:
    emit_json(
        logger,
        level="error",
        service=SERVICE_NAME,
        replica=REPLICA_ID,
        event=event,
        trace_id=current_trace_id(),
        **fields,
    )


def _error_response(status_code: int, message: str = "request failed") -> JSONResponse:
    trace_id = current_trace_id()
    return JSONResponse(
        {"error": message, "trace_id": trace_id},
        status_code=status_code,
        headers={"X-Trace-Id": trace_id},
    )


def _fault_summary() -> dict[str, object]:
    state = faults.snapshot()
    return {
        "backend_replica": REPLICA_ID,
        "scope": state.scope,
        "latency_ms": state.latency_ms,
        "jitter_ms": state.jitter_ms,
        "error_rate": state.error_rate,
        "error_status": state.error_status,
        "cpu_ms": state.cpu_ms,
        "db_delay_ms": state.db_delay_ms,
        "memory_mb": sum(len(block) for block in state.memory_blocks) // (1024 * 1024),
    }


def _burn_cpu(milliseconds: int) -> int:
    end = time.perf_counter() + (milliseconds / 1000)
    value = 17
    while time.perf_counter() < end:
        value = ((value * 31) + 7) % 1_000_003
    return value


def _apply_db_delay(path: str) -> None:
    state = faults.snapshot()
    if state.db_delay_ms > 0 and faults.applies_to_path(state, path):
        time.sleep(state.db_delay_ms / 1000)


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
        is_fault_target = faults.applies_to_path(state, path)

        if is_fault_target and state.latency_ms > 0:
            latency_ms = state.latency_ms
            if state.jitter_ms > 0:
                latency_ms += random.randint(0, state.jitter_ms)
            await asyncio.sleep(latency_ms / 1000)

        if is_fault_target and state.cpu_ms > 0:
            _burn_cpu(state.cpu_ms)

        if is_fault_target and state.error_rate > 0 and random.randint(1, 100) <= state.error_rate:
            status = state.error_status
            _error_event("request_error", path=path, status=status)
            response = _error_response(status, "service temporarily unavailable")
            response_bytes = len(response.body) + headers_size(response.headers)
            return response

        response = await call_next(request)
        response, response_bytes = await count_response_bytes(response)
        status = response.status_code
        return response
    finally:
        duration = time.perf_counter() - start
        route = getattr(request.scope.get("route"), "path", route)
        if request.url.path != "/metrics" and not request.url.path.startswith("/api/fault"):
            HTTP_REQUESTS.labels(SERVICE_NAME, REPLICA_ID, request.method, route, str(status)).inc()
            HTTP_DURATION.labels(SERVICE_NAME, REPLICA_ID, request.method, route, str(status)).observe(duration)
            HTTP_REQUEST_BYTES.labels(SERVICE_NAME, REPLICA_ID, request.method, route, str(status)).inc(
                request_bytes(request)
            )
            HTTP_RESPONSE_BYTES.labels(SERVICE_NAME, REPLICA_ID, request.method, route, str(status)).inc(
                response_bytes
            )
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
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    trace_id = current_trace_id()
    return JSONResponse(
        {"error": exc.detail, "trace_id": trace_id},
        status_code=exc.status_code,
        headers={"X-Trace-Id": trace_id},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _error_event("request_error", path=request.url.path, status=500, error=exc.__class__.__name__)
    return _error_response(500, "internal server error")


@app.get("/api/health")
def health() -> dict[str, object]:
    _apply_db_delay("/api/health")
    return {"status": "ok", "service": SERVICE_NAME, "replica": REPLICA_ID, "database": db.healthcheck()}


@app.get("/api/products")
def products() -> dict[str, object]:
    _apply_db_delay("/api/products")
    return {"backend_replica": REPLICA_ID, "products": db.get_products()}


@app.get("/api/orders")
def orders() -> dict[str, object]:
    _apply_db_delay("/api/orders")
    return {"backend_replica": REPLICA_ID, "orders": db.get_orders()}


@app.post("/api/checkout")
def checkout(payload: CheckoutRequest) -> dict[str, object]:
    try:
        _apply_db_delay("/api/checkout")
        order = db.create_order(payload.product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"backend_replica": REPLICA_ID, "order": order}


@app.get("/api/fault/status")
def fault_status() -> dict[str, object]:
    return _fault_summary()


@app.post("/api/fault/configure")
def fault_configure(payload: FaultConfigureRequest) -> dict[str, object]:
    faults.configure(
        scope=payload.scope,
        latency_ms=payload.latency_ms,
        jitter_ms=payload.jitter_ms,
        error_rate=payload.error_rate,
        error_status=payload.error_status,
        cpu_ms=payload.cpu_ms,
        db_delay_ms=payload.db_delay_ms,
    )
    return _fault_summary()


@app.get("/api/fault/latency")
def fault_latency(ms: int = 1000, jitter_ms: int = 0, scope: str = faults.DEFAULT_SCOPE) -> dict[str, object]:
    faults.set_latency(ms, jitter_ms=jitter_ms, scope=scope)
    return _fault_summary()


@app.get("/api/fault/errors")
def fault_errors(rate: int = 25, status: int = 503, scope: str = faults.DEFAULT_SCOPE) -> dict[str, object]:
    faults.set_error_rate(rate, status=status, scope=scope)
    return _fault_summary()


@app.get("/api/fault/memory")
def fault_memory(mb: int = 128) -> dict[str, object]:
    faults.grow_memory(mb)
    return _fault_summary()


@app.get("/api/fault/cpu")
def fault_cpu(seconds: int = 10) -> dict[str, object]:
    seconds = max(1, min(seconds, 60))
    value = _burn_cpu(seconds * 1000)
    return {"backend_replica": REPLICA_ID, "cpu_seconds": seconds, "checksum": value}


@app.get("/api/fault/db-slow")
def fault_db_slow(seconds: int = 3) -> dict[str, object]:
    seconds = max(1, min(seconds, 30))
    result = db.slow_query(seconds)
    return {"backend_replica": REPLICA_ID, "db": result}


@app.get("/api/fault/db-connections")
def fault_db_connections(count: int = 20, seconds: int = 30) -> dict[str, object]:
    started = db.hold_connections(count, seconds)
    return {"backend_replica": REPLICA_ID, "connections_started": started, "hold_seconds": seconds}


@app.get("/api/fault/reset")
def fault_reset() -> dict[str, object]:
    faults.reset()
    result = _fault_summary()
    result["reset"] = True
    return result
