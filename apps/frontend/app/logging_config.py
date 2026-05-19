import logging
import sys
from typing import Any

from opentelemetry import trace


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )
    return logging.getLogger("frontend")


def current_trace_id() -> str:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return "none"
    return f"{span_context.trace_id:032x}"


def _format_value(value: Any) -> str:
    text = str(value)
    if text == "" or any(char.isspace() or char in {'"', '='} for char in text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def emit_logfmt(logger: logging.Logger, **fields: Any) -> None:
    logger.info(" ".join(f"{key}={_format_value(value)}" for key, value in fields.items()))
