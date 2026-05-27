import json
import logging
import sys
from typing import Any

try:
    from opentelemetry import trace
except Exception:  # pragma: no cover - local static tests may not install app dependencies
    trace = None


def configure_logging(logger_name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )
    return logging.getLogger(logger_name)


def current_trace_id() -> str:
    if trace is None:
        return "none"
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return "none"
    return f"{span_context.trace_id:032x}"


def format_logfmt(fields: dict[str, Any]) -> str:
    return " ".join(f"{key}={_format_value(value)}" for key, value in fields.items())


def _format_value(value: Any) -> str:
    text = str(value)
    if text == "" or any(char.isspace() or char in {'"', '='} for char in text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def emit_logfmt(logger: logging.Logger, **fields: Any) -> None:
    logger.info(format_logfmt(fields))


def emit_json(logger: logging.Logger, **fields: Any) -> None:
    logger.warning(json.dumps(fields, separators=(",", ":"), default=str))
