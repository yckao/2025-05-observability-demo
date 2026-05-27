import os
import random
import time

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from .logging_config import configure_logging, current_trace_id, emit_logfmt
from .telemetry import configure_profiling, configure_tracing

SERVICE_NAME = os.getenv("SERVICE_NAME", "frontend")
REPLICA_ID = os.getenv("REPLICA_ID", "frontend-unknown")
BACKEND_URL = os.getenv("BACKEND_URL", "http://load-balancer/api").rstrip("/")
PUBLIC_GRAFANA_URL = os.getenv("PUBLIC_GRAFANA_URL", "http://localhost:3000").rstrip("/")

logger = configure_logging()
templates = Jinja2Templates(directory="app/templates")
session = requests.Session()

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
BUILD_INFO = Gauge(
    "demo_build_info",
    "Build and replica information for demo services.",
    ["service", "replica"],
)
BUILD_INFO.labels(SERVICE_NAME, REPLICA_ID).set(1)

app = FastAPI(title="Observability Demo Frontend")
configure_tracing(app)
configure_profiling()


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
        response, response_bytes = await _count_response_bytes(response)
        status = response.status_code
        return response
    finally:
        duration = time.perf_counter() - start
        route = getattr(request.scope.get("route"), "path", request.url.path)
        if request.url.path != "/metrics" and not request.url.path.startswith("/admin"):
            HTTP_REQUESTS.labels(SERVICE_NAME, REPLICA_ID, request.method, route, str(status)).inc()
            HTTP_DURATION.labels(SERVICE_NAME, REPLICA_ID, request.method, route, str(status)).observe(duration)
            HTTP_REQUEST_BYTES.labels(SERVICE_NAME, REPLICA_ID, request.method, route, str(status)).inc(
                _request_bytes(request)
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
