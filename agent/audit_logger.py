import json
import os
import re
import threading

from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

AUDIT_LOG_PATH = Path(
    os.getenv("AUDIT_LOG_PATH", "logs/agent_audit.jsonl")
)

_current_session = ContextVar(
    "audit_session_id",
    default="unknown",
)

_file_lock = threading.Lock()


def set_audit_session(session_id: str):
    """Set the session ID for events in the current execution context."""
    return _current_session.set(session_id)


def reset_audit_session(token):
    """Restore the previous session ID."""
    _current_session.reset(token)


def sanitize(value):
    """Redact common secrets and limit the size of logged values."""
    text = str(value)

    patterns = [
        (
            r"(?i)(api[_-]?key|password|secret|access[_-]?token)"
            r"(\s*[:=]\s*)[^\s,;]+",
            r"\1\2[REDACTED]",
        ),
        (
            r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+",
            r"\1[REDACTED]",
        ),
    ]

    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)

    return text[:2000]


def summarize_result(result):
    """Capture a bounded preview, not an unlimited raw tool result."""
    if isinstance(result, dict):
        if "error" in result:
            return {"error": sanitize(result["error"])}

        data = result.get("data", result)

        if isinstance(data, list):
            return {
                "row_or_item_count": len(data),
                "preview": sanitize(
                    json.dumps(data[:2], default=str)
                )[:800],
            }

        return {
            "preview": sanitize(
                json.dumps(data, default=str)
            )[:800]
        }

    if isinstance(result, list):
        return {
            "row_or_item_count": len(result),
            "preview": sanitize(
                json.dumps(result[:2], default=str)
            )[:800],
        }

    return {"preview": sanitize(result)[:800]}


def audit_event(
    event_type: str,
    status: str = "info",
    **details,
):
    """Append one structured event to the audit log."""
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": _current_session.get(),
        "event_type": event_type,
        "status": status,
        "details": details,
    }

    # Sanitize detail values before writing to disk.
    safe_event = json.loads(
        json.dumps(event, default=str)
    )

    for key, value in safe_event["details"].items():
        safe_event["details"][key] = sanitize(value)

    line = json.dumps(safe_event, ensure_ascii=False)

    AUDIT_LOG_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with _file_lock:
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(line + "\n")