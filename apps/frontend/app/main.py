import os
import random
import time

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from observability_demo_shared.logging import configure_logging, current_trace_id, emit_logfmt
from observability_demo_shared.request_metrics import count_response_bytes, create_http_metrics, request_bytes
from observability_demo_shared.telemetry import configure_profiling, configure_tracing

SERVICE_NAME = os.getenv("SERVICE_NAME", "frontend")
REPLICA_ID = os.getenv("REPLICA_ID", "frontend-unknown")
BACKEND_URL = os.getenv("BACKEND_URL", "http://load-balancer/api").rstrip("/")
PUBLIC_GRAFANA_URL = os.getenv("PUBLIC_GRAFANA_URL", "http://localhost:3000").rstrip("/")

logger = configure_logging("frontend")
templates = Jinja2Templates(directory="app/templates")
session = requests.Session()

HTTP_METRICS = create_http_metrics(SERVICE_NAME, REPLICA_ID)
HTTP_REQUESTS = HTTP_METRICS.requests
HTTP_DURATION = HTTP_METRICS.duration
HTTP_REQUEST_BYTES = HTTP_METRICS.request_bytes
HTTP_RESPONSE_BYTES = HTTP_METRICS.response_bytes
BUILD_INFO = HTTP_METRICS.build_info

app = FastAPI(title="Observability Demo Frontend")
configure_tracing(app, default_service_name="frontend")
configure_profiling(default_service_name="frontend", logger_name="frontend")


def _trace_error(status_code: int, message: str, trace_id: str | None = None) -> JSONResponse:
    trace_id = trace_id or current_trace_id()
    return JSONResponse(
        {"error": message, "trace_id": trace_id},
        status_code=status_code,
        headers={"X-Trace-Id": trace_id},
    )


def _upstream_error_response(error: requests.HTTPError, message: str) -> JSONResponse:
    response = error.response
    status_code = response.status_code if response is not None else 502
    trace_id = response.headers.get("X-Trace-Id") if response is not None else None
    if response is not None:
        try:
            trace_id = response.json().get("trace_id") or trace_id
        except ValueError:
            pass
    return _trace_error(status_code, message, trace_id)


@app.middleware("http")
async def record_requests(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    response = None
    response_bytes = 0
    try:
        response = await call_next(request)
        response, response_bytes = await count_response_bytes(response)
        status = response.status_code
        return response
    finally:
        duration = time.perf_counter() - start
        route = getattr(request.scope.get("route"), "path", request.url.path)
        if request.url.path != "/metrics" and not request.url.path.startswith("/admin"):
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


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return _trace_error(500, "internal server error")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME, "replica": REPLICA_ID}


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "replica": REPLICA_ID,
            "backend_url": BACKEND_URL,
            "grafana_url": PUBLIC_GRAFANA_URL,
        },
    )


@app.get("/admin")
def admin(request: Request):
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "replica": REPLICA_ID,
        },
    )


@app.get("/shop")
def shop() -> JSONResponse:
    try:
        product_response = session.get(f"{BACKEND_URL}/products", timeout=5)
        product_response.raise_for_status()
        products = product_response.json()["products"]

        selected = random.choice(products)
        checkout_response = session.post(
            f"{BACKEND_URL}/checkout",
            json={"product_id": selected["id"]},
            timeout=5,
        )
        checkout_response.raise_for_status()
    except requests.HTTPError as exc:
        return _upstream_error_response(exc, "checkout flow failed")
    except requests.RequestException:
        return _trace_error(502, "backend unavailable")

    return JSONResponse(
        {
            "frontend_replica": REPLICA_ID,
            "backend_products_response": product_response.json(),
            "checkout_response": checkout_response.json(),
        }
    )
