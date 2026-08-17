"""
CerebrOps Flask Application
AI-Powered CI/CD Monitoring System
"""

from flask import (Flask, jsonify, request, render_template, Response, g,
                   session, redirect, url_for)
from functools import wraps
import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
import psutil
import requests
from werkzeug.security import check_password_hash, generate_password_hash
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from logging_config import configure_logging, read_recent_logs
from metrics_store import MetricsStore

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
log_file = os.path.join(log_dir, 'app.log')
configure_logging(level=logging.INFO, log_dir=log_dir, log_file='app.log')

logger = logging.getLogger('cerebrops')

# ---------------------------------------------------------------------------
# Storage - single source of truth for historical telemetry
# ---------------------------------------------------------------------------
store = MetricsStore()

# API key for protecting sensitive endpoints. When set, /api/v1/* (except
# /api/v1/health) and legacy protected routes require X-API-Key (or ?api_key=).
API_KEY = os.getenv('CEREBROPS_API_KEY')

# Process start time for uptime calculation
PROCESS_START_TIME = time.time()

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
http_requests_total = Counter(
    'cerebrops_http_requests_total',
    'Total HTTP requests handled',
    ['method', 'route', 'status'],
)
http_request_duration_seconds = Histogram(
    'cerebrops_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'route'],
)
cpu_usage_gauge = Gauge('cerebrops_cpu_usage_percent', 'CPU usage percent')
memory_usage_gauge = Gauge('cerebrops_memory_usage_percent', 'Memory usage percent')
disk_usage_gauge = Gauge('cerebrops_disk_usage_percent', 'Disk usage percent')
metrics_rows_gauge = Gauge('cerebrops_metrics_rows_total', 'Total metric rows stored')

# Routes that should not be instrumented (metrics scrapes and self-reporting).
_UNINSTRUMENTED = {'/metrics-prom'}

# Metric fields exposed by the JSON/v1 APIs (percentages for error_rate).
METRIC_FIELDS = ['cpu_usage', 'memory_usage', 'disk_usage',
                 'error_rate', 'request_count', 'response_time']

app = Flask(__name__)

# Session signing for the dashboard login. Set CEREBROPS_SECRET_KEY in
# production; the fallback keeps local dev deterministic. Production refuses
# to start with the known dev key: sessions signed with a public key would be
# forgeable by anyone who reads the source.
_APP_ENV = (os.getenv('FLASK_ENV') or os.getenv('CEREBROPS_ENV') or 'development').lower()
_secret_key = os.getenv('CEREBROPS_SECRET_KEY')
if _secret_key:
    app.secret_key = _secret_key
elif _APP_ENV == 'production':
    raise RuntimeError(
        'CEREBROPS_SECRET_KEY must be set in production. Refusing to start '
        'with the public dev fallback. Generate one with: '
        'python -c "import secrets; print(secrets.token_hex(32))"'
    )
else:
    app.secret_key = 'cerebrops-dev-secret-change-me'
    logger.warning(
        'CEREBROPS_SECRET_KEY not set - using the DEV fallback. Set it before '
        'deploying anywhere non-local.')

# Login hardening: an email is locked out after this many failed attempts
# within the window, and a per-IP ceiling protects the login form from
# brute force in single-process deployments. (For multi-worker deploys the
# email lockout stays authoritative - it is SQLite-backed.)
LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_MINUTES = 15
LOGIN_MAX_PER_IP = 10
LOGIN_IP_WINDOW_SECONDS = 60
_login_ips = {}  # ip -> [timestamps] (best-effort, in-process)

# Dashboard auth. UI routes (/dashboard) require a login; the API surface
# (/api/v1/*, /metrics-prom, webhooks) stays key-based and open so scrapers
# and CI never need browser sessions. Tests set CEREBROPS_AUTH_DISABLED=1.
app.config['AUTH_DISABLED'] = os.getenv('CEREBROPS_AUTH_DISABLED') == '1'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True


# ---------------------------------------------------------------------------
# Request ID + API envelope helpers
# ---------------------------------------------------------------------------
@app.before_request
def _require_login():
    """Protect the dashboard shell; login/register/logout stay public."""
    if app.config.get('AUTH_DISABLED'):
        return
    if request.path.startswith('/dashboard') and 'user_id' not in session:
        return redirect(url_for('login', next='/dashboard'))


@app.before_request
def _set_request_id():
    g.request_id = request.headers.get('X-Request-Id') or str(uuid.uuid4())


@app.after_request
def _add_request_id_header(response):
    rid = getattr(g, 'request_id', None)
    if rid:
        response.headers['X-Request-Id'] = rid
    return response


def api_ok(data, status: int = 200):
    return jsonify({
        'status': 'success',
        'data': data,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'request_id': getattr(g, 'request_id', None),
    }), status


def api_error(code: str, message: str, status: int = 400, details=None):
    return jsonify({
        'status': 'error',
        'error': {'code': code, 'message': message, 'details': details},
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'request_id': getattr(g, 'request_id', None),
    }), status


def require_api_key(f):
    """Protect sensitive endpoints with API key authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if API_KEY:
            provided = request.headers.get('X-API-Key') or request.args.get('api_key')
            if provided != API_KEY:
                return api_error('UNAUTHORIZED', 'Missing or invalid API key', 401)
        return f(*args, **kwargs)
    return decorated


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _store_safe(fn, default=None):
    """Run a metrics-store read; on failure log and return `default`.

    Graceful degradation: the app keeps serving (dashboard/metrics return
    degraded data, v1 API routes return 503 STORE_UNAVAILABLE) instead of
    failing with a 500 when the SQLite store is down or locked.
    """
    try:
        return fn()
    except Exception:
        logger.exception("Metrics store unavailable; serving degraded response")
        return default


def _parse_iso(value: str, default: datetime) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return default


def _health_payload():
    """Run health checks; returns (checks, overall_healthy)."""
    checks = []
    overall_healthy = True

    checks.append({"name": "application", "status": "ok"})

    try:
        test_file = os.path.join(log_dir, '.health_check')
        with open(test_file, 'w') as f:
            f.write('ok')
        os.remove(test_file)
        checks.append({"name": "filesystem", "status": "ok"})
    except Exception as e:
        checks.append({"name": "filesystem", "status": "error", "detail": str(e)})
        overall_healthy = False

    try:
        store.count_metrics()
        checks.append({"name": "metrics_store", "status": "ok"})
    except Exception as e:
        checks.append({"name": "metrics_store", "status": "error", "detail": str(e)})
        overall_healthy = False

    return checks, overall_healthy


def _series_from_rows(rows, window_s: int):
    """Downsample metric rows into time-bucketed series (pure python)."""
    buckets = {}
    for r in rows:
        try:
            ts = _parse_iso(r.get('ts', ''), None)
        except Exception:
            continue
        if ts is None:
            continue
        b = int(ts.timestamp() // window_s) * window_s
        for m in METRIC_FIELDS:
            v = r.get(m)
            if isinstance(v, (int, float)):
                buckets.setdefault(b, {}).setdefault(m, []).append(float(v))

    series = {m: [] for m in METRIC_FIELDS}
    for b in sorted(buckets):
        t = datetime.fromtimestamp(b, tz=timezone.utc).isoformat()
        for m in METRIC_FIELDS:
            values = buckets[b].get(m)
            if values:
                series[m].append({'t': t, 'v': round(sum(values) / len(values), 4)})
    return series


# ---------------------------------------------------------------------------
# Request instrumentation (Prometheus counters/histograms + metric rows)
# ---------------------------------------------------------------------------
@app.before_request
def _record_request_start():
    g._cerebrops_start = time.perf_counter()


@app.after_request
def _instrument_request(response):
    if request.path in _UNINSTRUMENTED:
        return response

    method = request.method
    route = request.path
    status = str(response.status_code)
    http_requests_total.labels(method=method, route=route, status=status).inc()

    start = getattr(g, '_cerebrops_start', None)
    if start is not None:
        duration = time.perf_counter() - start
        http_request_duration_seconds.labels(method=method, route=route).observe(duration)

        try:
            store.record_metric(
                cpu_usage=psutil.cpu_percent(interval=None),
                memory_usage=psutil.virtual_memory().percent,
                disk_usage=psutil.disk_usage('/').percent,
                error_rate=1.0 if response.status_code >= 500 else 0.0,
                request_count=1,
                response_time=duration,
                extra={'method': method, 'route': route, 'status': response.status_code},
            )
        except Exception:
            logger.exception("Failed to record metric row")
    return response


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route('/')
def landing():
    """Public marketing landing page (no store access — stays fast)."""
    return render_template('landing.html')


@app.route('/experience')
def experience():
    """Immersive mobile-first Three.js product experience (no store access)."""
    return render_template('experience.html')


@app.route('/dashboard')
def dashboard():
    """Application shell with embedded initial data; the SPA refreshes
    everything through the v1 API afterwards."""
    logger.info("Dashboard accessed")

    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    summary = _store_safe(lambda: store.summary(since_hours=1))
    if summary is None:
        # Graceful degradation: zeroed summary so the dashboard stays coherent.
        summary = {'total': 0, 'error_rate_percent': 0.0,
                   'avg_response_time_seconds': 0.0, 'avg_response_time_ms': 0.0}
    anomalies = _store_safe(lambda: store.get_anomaly_runs(limit=10), [])
    alerts = _store_safe(lambda: store.get_alerts(limit=10), [])
    pipeline = _store_safe(lambda: store.get_pipeline_events(limit=10), [])

    recent_logs = read_recent_logs(log_file, limit=8)

    initial = {
        'system': {
            'cpu_usage': cpu_percent,
            'memory_usage': mem.percent,
            'disk_usage': disk.percent,
            'uptime': int(time.time() - PROCESS_START_TIME),
        },
        'summary': summary,
        'anomalies': anomalies,
        'alerts': alerts,
        'pipeline': pipeline,
        'api_key_configured': bool(API_KEY),
        'recent_logs': [
            f"{entry.get('ts', '')} {entry.get('level', '')} {entry.get('message', '')}"
            for entry in recent_logs
        ],
    }

    user_name = session.get('user_name') or 'operator'
    user_initials = ''.join(p[0] for p in user_name.split() if p)[:2].upper() or 'op'

    return render_template(
        'dashboard.html',
        initial_data=json.dumps(initial, default=str),
        api_key=API_KEY or '',
        user_name=user_name,
        user_initials=user_initials,
    )


# ---------------------------------------------------------------------------
# Auth — login / register / logout
# ---------------------------------------------------------------------------
def _client_ip() -> str:
    return request.headers.get('X-Forwarded-For', '').split(',')[0].strip() \
        or request.remote_addr or 'unknown'


def _login_locked(email: str, ip: str) -> Optional[str]:
    """Return a lockout message when the email or IP is throttled, else None."""
    failures = store.recent_failed_logins(email, LOGIN_LOCKOUT_MINUTES)
    if failures >= LOGIN_MAX_FAILURES:
        wait = LOGIN_LOCKOUT_MINUTES
        return (f'Too many failed attempts. Try again in {wait} minutes, '
                f'or reset your password.')
    now = time.time()
    stamps = [t for t in _login_ips.get(ip, []) if now - t < LOGIN_IP_WINDOW_SECONDS]
    _login_ips[ip] = stamps
    if len(stamps) >= LOGIN_MAX_PER_IP:
        return 'Too many attempts from this network. Try again in a minute.'
    return None


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Sign in to the dashboard; honors ?next= for post-login redirects."""
    if 'user_id' in session and not app.config.get('AUTH_DISABLED'):
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        ip = _client_ip()
        locked = _login_locked(email, ip)
        if locked:
            store.record_login_attempt(email, success=False, ip=ip)
            error = locked
        else:
            user = store.get_user_by_email(email) if email else None
            if user and check_password_hash(user.get('password_hash') or '', password):
                store.clear_login_attempts(email)
                session.clear()
                session['user_id'] = user['id']
                session['user_name'] = user.get('name') or user['email']
                session.permanent = True
                nxt = request.args.get('next') or '/dashboard'
                return redirect(nxt if nxt.startswith('/') else '/dashboard')
            store.record_login_attempt(email, success=False, ip=ip)
            error = 'Invalid email or password.'
    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Create an account and sign in immediately."""
    if 'user_id' in session and not app.config.get('AUTH_DISABLED'):
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        if not email or '@' not in email:
            error = 'Enter a valid email address.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif store.get_user_by_email(email):
            error = 'An account with that email already exists.'
        else:
            user_id = store.create_user(
                email=email,
                password_hash=generate_password_hash(password),
                name=name or None,
            )
            session.clear()
            session['user_id'] = user_id
            session['user_name'] = name or email
            session.permanent = True
            return redirect(url_for('dashboard'))
    return render_template('register.html', error=error)


@app.route('/logout')
def logout():
    """Clear the session and return to the landing page."""
    session.clear()
    return redirect(url_for('landing'))


def _hash_token(token: str) -> str:
    """SHA-256 of the raw token - the DB never stores the link itself."""
    return hashlib.sha256(token.encode()).hexdigest()


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request a password reset. Emails the link when an SMTP/webhook sender is
    configured (CEREBROPS_RESET_SENDER_URL); otherwise the link is logged to
    the server log and shown on the page in non-production environments."""
    if 'user_id' in session and not app.config.get('AUTH_DISABLED'):
        return redirect(url_for('dashboard'))
    message = None
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        user = store.get_user_by_email(email) if email else None
        # Always render the same message whether or not the account exists, so
        # the endpoint cannot be used to enumerate accounts.
        if user:
            raw = secrets.token_urlsafe(32)
            store.create_reset_token(
                email=email,
                token_hash=_hash_token(raw),
                expires_at=(datetime.now(timezone.utc)
                            + timedelta(minutes=30)).isoformat(),
            )
            link = url_for('reset_password', token=raw, _external=True)
            logger.warning('Password reset requested for %s: %s', email, link)
            sender = os.getenv('CEREBROPS_RESET_SENDER_URL')
            if sender:
                try:
                    requests.post(sender, json={'email': email, 'reset_link': link},
                                  timeout=10)
                except Exception as exc:  # never break the flow on sender errors
                    logger.error('Reset sender failed: %s', exc)
            if _APP_ENV != 'production':
                message = (f'Reset link (development only): {link}')
            else:
                message = 'If an account exists for that email, a reset link has been sent.'
        else:
            message = 'If an account exists for that email, a reset link has been sent.'
    return render_template('forgot_password.html', message=message)


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Set a new password using a single-use, expiring token."""
    if 'user_id' in session and not app.config.get('AUTH_DISABLED'):
        return redirect(url_for('dashboard'))
    token = (request.args.get('token') or '').strip()
    if not token:
        return redirect(url_for('forgot_password'))
    record = store.get_reset_token(_hash_token(token))
    expired = False
    error = None
    if not record or record.get('consumed'):
        error = 'This reset link is invalid or has already been used.'
    else:
        expires = record.get('expires_at') or ''
        try:
            expired = datetime.fromisoformat(expires) < datetime.now(timezone.utc)
        except ValueError:
            expired = True
        if expired:
            error = 'This reset link has expired. Request a new one.'
    if request.method == 'POST' and not error:
        password = request.form.get('password') or ''
        if len(password) < 8:
            error = 'Password must be at least 8 characters.'
        else:
            store.update_user_password(record['email'], generate_password_hash(password))
            store.consume_reset_token(_hash_token(token))
            session.clear()
            return redirect(url_for('login', reset='1'))
    return render_template('reset_password.html', error=error, token=token)


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for compatibility; prefer /api/v1/*)
# ---------------------------------------------------------------------------
@app.route('/health')
def health_check():
    """Health check endpoint for Kubernetes."""
    logger.info("Health check requested")
    checks, overall_healthy = _health_payload()
    status = "healthy" if overall_healthy else "unhealthy"
    return jsonify({"status": status, "checks": checks}), 200 if overall_healthy else 503


@app.route('/metrics')
def get_metrics():
    """Get real metrics in JSON format (legacy; prefer /api/v1/metrics)."""
    logger.info("Metrics requested")
    summary = _store_safe(lambda: store.summary(since_hours=1))
    degraded = summary is None
    if degraded:
        summary = {'total': 0, 'error_rate_percent': 0.0, 'avg_response_time_seconds': 0.0}
    payload = {
        'timestamp': _utc_now().isoformat(),
        'cpu_usage': psutil.cpu_percent(interval=0.1),
        'memory_usage': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
        'request_count': summary['total'],
        'error_rate': summary['error_rate_percent'],
        'response_time': summary['avg_response_time_seconds'],
    }
    if degraded:
        payload['degraded'] = True
    return jsonify(payload)


@app.route('/metrics-prom')
def prometheus_metrics():
    """Prometheus text-format metrics endpoint (scraped by Prometheus)."""
    cpu_usage_gauge.set(psutil.cpu_percent(interval=None))
    memory_usage_gauge.set(psutil.virtual_memory().percent)
    disk_usage_gauge.set(psutil.disk_usage('/').percent)
    # Degrades to the last known row count (gauge keeps its value) when the
    # store is unavailable; the scrape itself must never 500.
    metrics_rows_gauge.set(_store_safe(lambda: store.count_metrics(), 0))
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route('/logs')
@require_api_key
def get_logs():
    """Return real recent log entries from the application log file."""
    logger.info("Logs requested")

    try:
        limit = max(1, min(int(request.args.get('limit', 20)), 1000))
    except (TypeError, ValueError):
        limit = 20
    level = request.args.get('level')
    since = request.args.get('since')

    entries = read_recent_logs(log_file, limit=limit, level=level, since=since)

    logs = [
        {
            'timestamp': entry.get('ts', ''),
            'level': entry.get('level', ''),
            'message': entry.get('message', ''),
            'module': entry.get('logger', ''),
        }
        for entry in entries
    ]

    return jsonify({'logs': logs, 'total': len(logs), 'limit': limit})


@app.route('/simulate-error')
@require_api_key
def simulate_error():
    """Simulate an error for testing anomaly detection (records a real row)."""
    logger.error("Simulated error occurred")

    anomalous_metrics = {
        'timestamp': _utc_now().isoformat(),
        'cpu_usage': 99.9,
        'memory_usage': 95.5,
        'disk_usage': psutil.disk_usage('/').percent,
        'error_rate': 100.0,
    }

    # Inject the simulated anomaly into the time series. It is NOT counted as
    # a real request (the actual 500 response is recorded by the request
    # instrumentation with error_rate=1.0), so dashboard stats stay honest.
    store.record_metric(
        cpu_usage=anomalous_metrics['cpu_usage'],
        memory_usage=anomalous_metrics['memory_usage'],
        disk_usage=anomalous_metrics['disk_usage'],
        error_rate=0.0,
        request_count=0,
        response_time=3.0,
        extra={'simulated': True, 'route': '/simulate-error', 'status': 500},
    )

    return jsonify({'status': 'error simulated', 'metrics': anomalous_metrics}), 500


@app.route('/api/pipeline-status')
def pipeline_status():
    """Get CI/CD pipeline status (legacy; prefer GET /api/v1/pipeline)."""
    logger.info("Pipeline status requested")
    events = _store_safe(lambda: store.get_pipeline_events(limit=1), []) or []
    if events:
        e = events[0]
        data = {
            'pipeline_id': e['pipeline_id'],
            'status': e['status'],
            'stage': e['stage'] or 'unknown',
            'duration': e['duration'],
            'commit_hash': e['commit_hash'] or '',
            'branch': e['branch'] or '',
            'source': e['source'] or 'unknown',
            'recorded_at': e['ts'],
            'deprecated': True,
        }
    else:
        data = {
            'pipeline_id': None,
            'status': 'unknown',
            'stage': 'none',
            'duration': None,
            'commit_hash': '',
            'branch': '',
            'source': 'no pipeline events recorded yet',
            'deprecated': True,
        }
    return jsonify(data)


# ---------------------------------------------------------------------------
# v1 API
# ---------------------------------------------------------------------------
@app.route('/api/v1/health')
def api_v1_health():
    """Health status in the standard v1 envelope (no auth required)."""
    checks, overall_healthy = _health_payload()
    return api_ok({
        'status': 'healthy' if overall_healthy else 'unhealthy',
        'checks': checks,
    }, 200 if overall_healthy else 503)


@app.route('/api/v1/metrics')
@require_api_key
def api_v1_metrics():
    """Aggregated metric series + summary.

    Query params:
        from (ISO ts) - start of range (default: now-1h)
        to (ISO ts)   - end of range (default: now)
        window (s)    - bucket size for downsampling (default: 60)
    """
    now = _utc_now()
    to = _parse_iso(request.args.get('to', ''), now)
    from_dt = _parse_iso(request.args.get('from', ''), now - timedelta(hours=1))
    try:
        window_s = max(1, int(request.args.get('window', 60)))
    except (TypeError, ValueError):
        window_s = 60

    # None (not []) marks a store failure; an empty store legitimately
    # returns [] and stays a 200 with an empty series.
    rows = _store_safe(lambda: store.get_metrics(
        limit=50000,
        since=from_dt.isoformat(),
        until=to.isoformat(),
    ))
    if rows is None:
        return api_error('STORE_UNAVAILABLE', 'Metrics store is unavailable', 503)
    series = _series_from_rows(rows, window_s)
    summary = _store_safe(lambda: store.summary(since_hours=1))
    if summary is None:
        return api_error('STORE_UNAVAILABLE', 'Metrics store is unavailable', 503)

    return api_ok({
        'from': from_dt.isoformat(),
        'to': to.isoformat(),
        'window': window_s,
        'point_count': len(rows),
        'summary': summary,
        'series': series,
    })


@app.route('/api/v1/anomalies')
@require_api_key
def api_v1_anomalies():
    """Recent anomaly detection runs."""
    try:
        limit = max(1, min(int(request.args.get('limit', 50)), 500))
    except (TypeError, ValueError):
        limit = 50
    runs = _store_safe(lambda: store.get_anomaly_runs(limit=limit))
    if runs is None:
        return api_error('STORE_UNAVAILABLE', 'Metrics store is unavailable', 503)
    return api_ok({'anomalies': runs})


@app.route('/api/v1/alerts')
@require_api_key
def api_v1_alerts():
    """Recent alerts."""
    try:
        limit = max(1, min(int(request.args.get('limit', 50)), 500))
    except (TypeError, ValueError):
        limit = 50
    alerts = _store_safe(lambda: store.get_alerts(limit=limit))
    if alerts is None:
        return api_error('STORE_UNAVAILABLE', 'Metrics store is unavailable', 503)
    return api_ok({'alerts': alerts})


@app.route('/api/v1/pipeline', methods=['GET'])
@require_api_key
def api_v1_pipeline_get():
    """Recent CI/CD pipeline events."""
    try:
        limit = max(1, min(int(request.args.get('limit', 50)), 500))
    except (TypeError, ValueError):
        limit = 50
    events = _store_safe(lambda: store.get_pipeline_events(limit=limit))
    if events is None:
        return api_error('STORE_UNAVAILABLE', 'Metrics store is unavailable', 503)
    return api_ok({'events': events})


@app.route('/api/v1/pipeline/events', methods=['POST'])
@require_api_key
def api_v1_pipeline_events():
    """Ingest a CI/CD pipeline event (webhook from GitHub Actions etc.)."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return api_error('INVALID_REQUEST', 'Request body must be a JSON object', 400)

    status = str(payload.get('status', '')).lower()
    if status not in {'success', 'failed', 'running', 'pending', 'cancelled'}:
        return api_error(
            'INVALID_REQUEST',
            f"status must be one of success|failed|running|pending|cancelled, got {status!r}",
            400,
        )

    try:
        duration = float(payload['duration']) if payload.get('duration') is not None else None
    except (TypeError, ValueError):
        duration = None

    event_id = store.record_pipeline_event(
        status=status,
        pipeline_id=payload.get('pipeline_id'),
        stage=payload.get('stage'),
        duration=duration,
        branch=payload.get('branch'),
        commit_hash=payload.get('commit_hash'),
        source=payload.get('source') or 'webhook',
        payload=payload,
    )
    logger.info(f"Recorded pipeline event #{event_id}: {status}")

    return api_ok({'event_id': event_id, 'recorded': True, 'status': status}, 202)


if __name__ == '__main__':
    os.makedirs(log_dir, exist_ok=True)
    logger.info("Starting CerebrOps application")
    app.run(host='0.0.0.0', port=5000, debug=False)
