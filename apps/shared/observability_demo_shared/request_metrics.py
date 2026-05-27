from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import Response
from prometheus_client import Counter, Gauge, Histogram


@dataclass(frozen=True)
class HttpMetrics:
    requests: Counter
    duration: Histogram
    request_bytes: Counter
    response_bytes: Counter
    build_info: Gauge


def create_http_metrics(service_name: str, replica_id: str) -> HttpMetrics:
    metrics = HttpMetrics(
        requests=Counter(
            "demo_http_requests_total",
            "HTTP requests handled by demo services.",
            ["service", "replica", "method", "route", "status"],
        ),
        duration=Histogram(
            "demo_http_request_duration_seconds",
            "HTTP request duration for demo services.",
            ["service", "replica", "method", "route", "status"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        ),
        request_bytes=Counter(
            "demo_http_request_bytes_total",
            "Approximate HTTP request bytes received by demo services.",
            ["service", "replica", "method", "route", "status"],
        ),
        response_bytes=Counter(
            "demo_http_response_bytes_total",
            "Approximate HTTP response bytes sent by demo services.",
            ["service", "replica", "method", "route", "status"],
        ),
        build_info=Gauge(
            "demo_build_info",
            "Build and replica information for demo services.",
            ["service", "replica"],
        ),
    )
    metrics.build_info.labels(service_name, replica_id).set(1)
    return metrics


def header_int(headers, name: str) -> int:
    try:
        return max(0, int(headers.get(name, "0") or 0))
    except ValueError:
        return 0


def headers_size(headers) -> int:
    return sum(len(key) + len(value) + 4 for key, value in headers.items())


def request_bytes(request: Request) -> int:
    return len(request.method) + len(str(request.url)) + headers_size(request.headers) + header_int(
        request.headers, "content-length"
    )


async def count_response_bytes(response: Response) -> tuple[Response, int]:
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
    return response, len(body) + headers_size(response.headers)
