import threading
from dataclasses import dataclass, field

DEFAULT_SCOPE = "/api/"


@dataclass
class FaultState:
    scope: str = DEFAULT_SCOPE
    latency_ms: int = 0
    jitter_ms: int = 0
    error_rate: int = 0
    error_status: int = 503
    cpu_ms: int = 0
    db_delay_ms: int = 0
    memory_blocks: list[bytearray] = field(default_factory=list)


_state = FaultState()
_lock = threading.Lock()


def _normalize_scope(scope: str | None) -> str:
    allowed = {"/api/", "/api/products", "/api/checkout", "/api/orders", "/api/health"}
    if scope in allowed:
        return scope
    return DEFAULT_SCOPE


def snapshot() -> FaultState:
    with _lock:
        return FaultState(
            scope=_state.scope,
            latency_ms=_state.latency_ms,
            jitter_ms=_state.jitter_ms,
            error_rate=_state.error_rate,
            error_status=_state.error_status,
            cpu_ms=_state.cpu_ms,
            db_delay_ms=_state.db_delay_ms,
            memory_blocks=_state.memory_blocks.copy(),
        )


def applies_to_path(state: FaultState, path: str) -> bool:
    if path.startswith("/api/fault"):
        return False
    if state.scope == DEFAULT_SCOPE:
        return path.startswith("/api/")
    return path == state.scope


def configure(
    *,
    scope: str | None = None,
    latency_ms: int | None = None,
    jitter_ms: int | None = None,
    error_rate: int | None = None,
    error_status: int | None = None,
    cpu_ms: int | None = None,
    db_delay_ms: int | None = None,
) -> FaultState:
    with _lock:
        if scope is not None:
            _state.scope = _normalize_scope(scope)
        if latency_ms is not None:
            _state.latency_ms = max(0, min(latency_ms, 30_000))
        if jitter_ms is not None:
            _state.jitter_ms = max(0, min(jitter_ms, 30_000))
        if error_rate is not None:
            _state.error_rate = max(0, min(error_rate, 100))
        if error_status is not None:
            _state.error_status = max(400, min(error_status, 599))
        if cpu_ms is not None:
            _state.cpu_ms = max(0, min(cpu_ms, 10_000))
        if db_delay_ms is not None:
            _state.db_delay_ms = max(0, min(db_delay_ms, 30_000))
    return snapshot()


def set_latency(ms: int, jitter_ms: int = 0, scope: str | None = None) -> int:
    return configure(scope=scope, latency_ms=ms, jitter_ms=jitter_ms).latency_ms


def set_error_rate(rate: int, status: int = 503, scope: str | None = None) -> int:
    return configure(scope=scope, error_rate=rate, error_status=status).error_rate


def grow_memory(mb: int) -> int:
    mb = max(1, min(mb, 1024))
    with _lock:
        _state.memory_blocks.append(bytearray(mb * 1024 * 1024))
        return sum(len(block) for block in _state.memory_blocks) // (1024 * 1024)


def reset() -> None:
    with _lock:
        _state.scope = DEFAULT_SCOPE
        _state.latency_ms = 0
        _state.jitter_ms = 0
        _state.error_rate = 0
        _state.error_status = 503
        _state.cpu_ms = 0
        _state.db_delay_ms = 0
        _state.memory_blocks.clear()
