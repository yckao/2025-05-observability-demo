import threading
from dataclasses import dataclass, field


@dataclass
class FaultState:
    latency_ms: int = 0
    error_rate: int = 0
    memory_blocks: list[bytearray] = field(default_factory=list)


_state = FaultState()
_lock = threading.Lock()


def snapshot() -> FaultState:
    with _lock:
        return FaultState(
            latency_ms=_state.latency_ms,
            error_rate=_state.error_rate,
            memory_blocks=_state.memory_blocks.copy(),
        )


def set_latency(ms: int) -> int:
    ms = max(0, min(ms, 30_000))
    with _lock:
        _state.latency_ms = ms
    return ms


def set_error_rate(rate: int) -> int:
    rate = max(0, min(rate, 100))
    with _lock:
        _state.error_rate = rate
    return rate


def grow_memory(mb: int) -> int:
    mb = max(1, min(mb, 1024))
    with _lock:
        _state.memory_blocks.append(bytearray(mb * 1024 * 1024))
        return sum(len(block) for block in _state.memory_blocks) // (1024 * 1024)


def reset() -> None:
    with _lock:
        _state.latency_ms = 0
        _state.error_rate = 0
        _state.memory_blocks.clear()
