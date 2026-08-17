"""
CerebrOps Metrics Store.

SQLite-backed persistence for metrics, alerts, and anomaly detection runs.
This is the single source of truth for historical telemetry: the Flask app
writes real request metrics here and the anomaly detector reads windows of
history from here (no synthetic data fallback).
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger('cerebrops.store')

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'data', 'cerebrops.db'
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    cpu_usage REAL,
    memory_usage REAL,
    disk_usage REAL,
    error_rate REAL,
    request_count INTEGER,
    response_time REAL,
    extra_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    severity TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS anomaly_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    status TEXT NOT NULL,
    anomaly_count INTEGER,
    total_data_points INTEGER,
    severity TEXT,
    results_json TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    pipeline_id TEXT,
    status TEXT NOT NULL,
    stage TEXT,
    duration REAL,
    branch TEXT,
    commit_hash TEXT,
    source TEXT,
    payload_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_ts ON pipeline_events(ts);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    ip TEXT,
    success INTEGER NOT NULL DEFAULT 0,
    ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_attempts_email_ts
    ON login_attempts(email, ts);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    consumed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_hash
    ON password_reset_tokens(token_hash);
"""

_METRIC_COLUMNS = (
    'cpu_usage', 'memory_usage', 'disk_usage',
    'error_rate', 'request_count', 'response_time',
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def parse_ts(value: Any) -> Optional[datetime]:
    """Parse a stored timestamp (ISO string or epoch seconds/millis) into an
    aware datetime, or None when unparseable. Shared by the detector, root
    cause, and evaluation modules."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if abs(float(value)) > 1e12 else float(value)
        try:
            return _EPOCH + timedelta(seconds=seconds)
        except (OverflowError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


class MetricsStore:
    """Thread-safe SQLite-backed store for CerebrOps telemetry."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv('CEREBROPS_DB_PATH') or DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(_SCHEMA)
                conn.commit()
                # WAL + NORMAL give the best concurrent behavior for the
                # multi-replica / cronjob layout on a shared (RWX) volume:
                # readers never block the writer and the busy timeout in
                # _connect() handles write contention.
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")
                except sqlite3.Error:
                    pass
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def record_metric(self, ts: Optional[str] = None,
                      cpu_usage: Optional[float] = None,
                      memory_usage: Optional[float] = None,
                      disk_usage: Optional[float] = None,
                      error_rate: Optional[float] = None,
                      request_count: Optional[int] = None,
                      response_time: Optional[float] = None,
                      extra: Optional[Dict[str, Any]] = None) -> int:
        """Insert a single metric row and return its id."""
        return self.record_metrics([{
            'ts': ts or _now(),
            'cpu_usage': cpu_usage,
            'memory_usage': memory_usage,
            'disk_usage': disk_usage,
            'error_rate': error_rate,
            'request_count': request_count,
            'response_time': response_time,
            'extra': extra,
        }])

    def record_metrics(self, rows: List[Dict[str, Any]]) -> int:
        """Insert multiple metric rows; returns number of rows inserted."""
        if not rows:
            return 0
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.executemany(
                    "INSERT INTO metrics (ts, cpu_usage, memory_usage, disk_usage,"
                    " error_rate, request_count, response_time, extra_json)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            row.get('ts') or _now(),
                            row.get('cpu_usage'),
                            row.get('memory_usage'),
                            row.get('disk_usage'),
                            row.get('error_rate'),
                            row.get('request_count'),
                            row.get('response_time'),
                            json.dumps(row.get('extra')) if row.get('extra') else None,
                        )
                        for row in rows
                    ],
                )
                conn.commit()
                return cur.rowcount
            finally:
                conn.close()

    def get_metrics(self, limit: int = 1000, since: Optional[str] = None,
                    until: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return the most recent metric rows (chronological order)."""
        conditions = []
        params: List[Any] = []
        if since:
            conditions.append("ts >= ?")
            params.append(since)
        if until:
            conditions.append("ts <= ?")
            params.append(until)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        query = ("SELECT * FROM (SELECT * FROM metrics"
                 f"{where} ORDER BY id DESC LIMIT ?) ORDER BY id ASC")
        params.append(limit)
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(query, params).fetchall()
            finally:
                conn.close()
        return [self._metric_row_to_dict(row) for row in rows]

    def count_metrics(self) -> int:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT COUNT(*) AS c FROM metrics").fetchone()
                return int(row['c']) if row else 0
            finally:
                conn.close()

    def summary(self, since_hours: int = 1) -> Dict[str, Any]:
        """Aggregate stats for real request metrics recorded in the last `since_hours`.

        Only rows with a request_count are counted as requests, so internal
        probe rows (if any) do not skew request/error/latency stats.
        """
        since_ts = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COALESCE(SUM(request_count), 0) AS total,"
                    " COALESCE(SUM(error_rate), 0) AS errors,"
                    " AVG(response_time) AS avg_rt"
                    " FROM metrics WHERE ts >= ?",
                    (since_ts,),
                ).fetchone()
            finally:
                conn.close()
        total = int(row['total']) if row else 0
        errors = float(row['errors']) if row else 0.0
        avg_rt = row['avg_rt'] if row is not None else None
        avg_rt = float(avg_rt) if avg_rt is not None else 0.0
        return {
            'since': since_ts,
            'total': total,
            'error_rate_percent': round(errors / total * 100, 2) if total else 0.0,
            'avg_response_time_seconds': round(avg_rt, 4),
            'avg_response_time_ms': round(avg_rt * 1000, 1),
        }

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def record_alert(self, severity: str, alert_type: str, message: str,
                     payload: Optional[Dict[str, Any]] = None) -> int:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO alerts (ts, severity, alert_type, message, payload_json)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (_now(), severity, alert_type, message,
                     json.dumps(payload, default=str) if payload else None),
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def get_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            finally:
                conn.close()
        alerts = []
        for row in rows:
            alert = dict(row)
            alert['payload'] = self._loads_json(alert.pop('payload_json'))
            alerts.append(alert)
        return alerts

    # ------------------------------------------------------------------
    # Anomaly runs
    # ------------------------------------------------------------------

    def record_anomaly_run(self, status: str,
                           anomaly_count: Optional[int] = None,
                           total_data_points: Optional[int] = None,
                           severity: Optional[str] = None,
                           results: Optional[Dict[str, Any]] = None) -> int:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO anomaly_runs (ts, status, anomaly_count,"
                    " total_data_points, severity, results_json)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (_now(), status, anomaly_count, total_data_points, severity,
                     json.dumps(results, default=str) if results else None),
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def get_anomaly_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM anomaly_runs ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            finally:
                conn.close()
        runs = []
        for row in rows:
            run = dict(row)
            run['results'] = self._loads_json(run.pop('results_json'))
            runs.append(run)
        return runs

    # ------------------------------------------------------------------
    # Pipeline events
    # ------------------------------------------------------------------

    def record_pipeline_event(self, status: str,
                              pipeline_id: Optional[str] = None,
                              stage: Optional[str] = None,
                              duration: Optional[float] = None,
                              branch: Optional[str] = None,
                              commit_hash: Optional[str] = None,
                              source: Optional[str] = None,
                              payload: Optional[Dict[str, Any]] = None) -> int:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO pipeline_events (ts, pipeline_id, status, stage,"
                    " duration, branch, commit_hash, source, payload_json)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (_now(), pipeline_id, status, stage, duration, branch,
                     commit_hash, source,
                     json.dumps(payload, default=str) if payload else None),
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def get_pipeline_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM pipeline_events ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            finally:
                conn.close()
        events = []
        for row in rows:
            event = dict(row)
            event['payload'] = self._loads_json(event.pop('payload_json'))
            events.append(event)
        return events

    # ------------------------------------------------------------------
    # Users (dashboard login)
    # ------------------------------------------------------------------

    def create_user(self, email: str, password_hash: str,
                    name: Optional[str] = None) -> int:
        """Create a user row and return its id."""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO users (email, password_hash, name, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (email, password_hash, name, _now()),
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Look up a user by (lowercased) email, or None."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM users WHERE email = ?", (email,)
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Login hardening (rate limiting / lockout)
    # ------------------------------------------------------------------

    def record_login_attempt(self, email: str, success: bool,
                             ip: Optional[str] = None) -> None:
        """Record a login attempt so failed attempts can be rate limited."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO login_attempts (email, ip, success, ts) "
                    "VALUES (?, ?, ?, ?)",
                    (email, ip, 1 if success else 0, _now()),
                )
                conn.commit()
            finally:
                conn.close()

    def recent_failed_logins(self, email: str,
                             since_minutes: int = 15) -> int:
        """Count failed attempts for an email within the last N minutes."""
        since = (datetime.now(timezone.utc)
                 - timedelta(minutes=since_minutes)).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM login_attempts "
                    "WHERE email = ? AND success = 0 AND ts > ?",
                    (email, since),
                ).fetchone()
                return int(row['n']) if row else 0
            finally:
                conn.close()

    def clear_login_attempts(self, email: str) -> None:
        """Reset the failure counter after a successful login."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Password reset tokens
    # ------------------------------------------------------------------

    def create_reset_token(self, email: str, token_hash: str,
                           expires_at: str) -> None:
        """Store a hashed password-reset token with an expiry."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO password_reset_tokens "
                    "(email, token_hash, expires_at, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (email, token_hash, expires_at, _now()),
                )
                conn.commit()
            finally:
                conn.close()

    def get_reset_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Look up a token by hash. Returns None when missing."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM password_reset_tokens WHERE token_hash = ?",
                    (token_hash,),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def update_user_password(self, email: str, password_hash: str) -> None:
        """Replace a user's password hash (password reset)."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE email = ?",
                    (password_hash, email),
                )
                conn.commit()
            finally:
                conn.close()

    def consume_reset_token(self, token_hash: str) -> None:
        """Mark a token consumed so it cannot be replayed."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE password_reset_tokens SET consumed = 1 "
                    "WHERE token_hash = ?", (token_hash,)
                )
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _loads_json(value: Optional[str]) -> Any:
        if not value:
            return None
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None

    @classmethod
    def _metric_row_to_dict(cls, row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data['extra'] = cls._loads_json(data.pop('extra_json'))
        return data
