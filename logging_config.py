"""
CerebrOps logging configuration.

Provides structured JSON logging to stdout plus a rotating file handler,
and a helper to read recent parsed log entries from a JSON log file.
"""

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import List, Optional

# Standard LogRecord attributes that should not be dumped into JSON extras.
_RESERVED_ATTRS = frozenset({
    'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
    'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
    'message', 'msg', 'name', 'pathname', 'process', 'processName',
    'relativeCreated', 'stack_info', 'thread', 'threadName', 'taskName',
})


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'ts': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)
        # Merge any attributes set via logging's `extra={...}` keyword.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith('_'):
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO,
                      log_dir: Optional[str] = None,
                      log_file: str = 'app.log',
                      max_bytes: int = 5 * 1024 * 1024,
                      backup_count: int = 5) -> None:
    """
    Configure the root logger with a JSON stdout handler and a rotating
    JSON file handler. Idempotent: calling again with the same targets does
    not duplicate handlers. When TESTING=true (test runs) no handlers are
    attached so pytest's own capture is not disturbed.
    """
    root = logging.getLogger()

    if os.getenv('TESTING') == 'true':
        root.setLevel(level)
        return

    root.setLevel(level)

    marked = [h for h in root.handlers if getattr(h, '_cerebrops_json', False)]
    if marked:
        # Already configured (or configured with a different file) - leave as-is.
        return

    stream = logging.StreamHandler()
    stream.setFormatter(JsonFormatter())
    stream._cerebrops_json = True
    root.addHandler(stream)

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
        )
        file_handler.setFormatter(JsonFormatter())
        file_handler._cerebrops_json = True
        root.addHandler(file_handler)


def read_recent_logs(log_path: str, limit: int = 20,
                     level: Optional[str] = None,
                     since: Optional[str] = None) -> List[dict]:
    """
    Return the last `limit` parsed JSON log entries from `log_path`.

    Args:
        log_path: Path to a JSON-lines log file.
        limit: Maximum number of entries to return.
        level: If given, only return entries with this exact level (case-insensitive).
        since: If given (ISO timestamp), only return entries with ts >= since.
    """
    if not log_path or not os.path.exists(log_path):
        return []

    entries: List[dict] = []
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except OSError:
        return []

    # Only scan the tail of the file - more than enough for the newest entries.
    for line in lines[-max(limit * 10, 200):]:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(entry, dict):
            continue
        if level and str(entry.get('level', '')).upper() != level.upper():
            continue
        if since and entry.get('ts', '') < since:
            continue
        entries.append(entry)

    return entries[-limit:]
