"""
Test suite for CerebrOps Flask application
"""

import pytest
import json
import os
import re
from app import app, store, _login_ips, LOGIN_MAX_FAILURES


@pytest.fixture
def client():
    """Create a test client for the Flask app"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_check(client):
    """Test the health check endpoint"""
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'healthy'
    assert 'checks' in data
    assert isinstance(data['checks'], list)
    assert len(data['checks']) > 0


def test_landing_page(client):
    """The landing page renders without touching the store"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'CerebrOps' in response.data
    assert b'landing.css' in response.data
    assert b'hero-video' in response.data
    assert 'cloudfront.net' in response.data.decode('utf-8')


def test_dashboard_shell(client):
    """The application shell renders with embedded initial data"""
    response = client.get('/dashboard')
    assert response.status_code == 200
    body = response.data.decode('utf-8')
    assert b'CerebrOps' in response.data
    assert 'initial-data' in body
    assert 'api-key' in body
    assert 'app.js' in body


def test_experience_page(client):
    """The Three.js experience page renders with its vendored runtime"""
    response = client.get('/experience')
    assert response.status_code == 200
    body = response.data.decode('utf-8')
    assert b'CerebrOps' in response.data
    assert 'Early Access' in body
    assert 'Frequently' in body and 'asked' in body
    assert 'serif-it' in body
    assert 'three.min.js' in body
    assert 'experience.js' in body


def test_metrics_endpoint(client):
    """Test the metrics API endpoint"""
    response = client.get('/metrics')
    assert response.status_code == 200
    data = json.loads(response.data)

    required_fields = ['timestamp', 'cpu_usage', 'memory_usage', 'disk_usage']
    for field in required_fields:
        assert field in data


def test_prometheus_metrics_endpoint(client):
    """Test the Prometheus text-format metrics endpoint"""
    response = client.get('/metrics-prom')
    assert response.status_code == 200
    assert 'text/plain' in response.content_type
    body = response.data.decode('utf-8')
    assert 'cerebrops_http_requests_total' in body


def test_metrics_degrades_when_store_down(client, monkeypatch):
    """Graceful degradation: store failure must not 500 the JSON metrics."""
    from app import store

    def boom(*a, **k):
        raise RuntimeError('store unavailable')

    monkeypatch.setattr(store, 'summary', boom)
    response = client.get('/metrics')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['degraded'] is True
    assert data['request_count'] == 0


def test_metrics_prom_degrades_when_store_down(client, monkeypatch):
    """The Prometheus scrape must never fail because the store is down."""
    from app import store

    def boom(*a, **k):
        raise RuntimeError('store unavailable')

    monkeypatch.setattr(store, 'count_metrics', boom)
    response = client.get('/metrics-prom')
    assert response.status_code == 200
    assert 'text/plain' in response.content_type


def test_api_metrics_returns_503_when_store_down(client, monkeypatch):
    """v1 API surfaces store failure as an explicit 503 envelope."""
    from app import store

    def boom(*a, **k):
        raise RuntimeError('store unavailable')

    monkeypatch.setattr(store, 'get_metrics', boom)
    response = client.get('/api/v1/metrics')
    assert response.status_code == 503
    data = json.loads(response.data)
    assert data['status'] == 'error'
    assert data['error']['code'] == 'STORE_UNAVAILABLE'


def test_dashboard_renders_when_store_down(client, monkeypatch):
    """The dashboard shell still renders when the store fails."""
    from app import store

    def boom(*a, **k):
        raise RuntimeError('store unavailable')

    monkeypatch.setattr(store, 'summary', boom)
    monkeypatch.setattr(store, 'get_anomaly_runs', boom)
    monkeypatch.setattr(store, 'get_alerts', boom)
    monkeypatch.setattr(store, 'get_pipeline_events', boom)
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert b'CerebrOps' in response.data


def test_logs_endpoint_no_auth(client):
    """Test the logs endpoint without API key (should work when no key is set)"""
    # When CEREBROPS_API_KEY is not set, endpoint is accessible
    original_key = os.environ.get('CEREBROPS_API_KEY')
    if 'CEREBROPS_API_KEY' in os.environ:
        del os.environ['CEREBROPS_API_KEY']

    # Reimport to reset API_KEY
    import app as app_module
    app_module.API_KEY = None

    response = client.get('/logs')
    assert response.status_code == 200
    data = json.loads(response.data)

    assert 'logs' in data
    assert isinstance(data['logs'], list)

    # Restore
    if original_key:
        os.environ['CEREBROPS_API_KEY'] = original_key
        app_module.API_KEY = original_key


def test_pipeline_status_endpoint(client):
    """Test the pipeline status API endpoint"""
    response = client.get('/api/pipeline-status')
    assert response.status_code == 200
    data = json.loads(response.data)

    required_fields = ['pipeline_id', 'status', 'stage']
    for field in required_fields:
        assert field in data


def test_simulate_error(client):
    """Test the error simulation endpoint"""
    # Ensure no API key is required for tests
    import app as app_module
    app_module.API_KEY = None

    response = client.get('/simulate-error')
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'error simulated'


def test_landing_does_not_touch_store(client, monkeypatch):
    """The marketing page must stay fast: zero store reads."""
    from app import store

    def boom(*a, **k):
        raise RuntimeError('landing must not touch the store')

    monkeypatch.setattr(store, 'summary', boom)
    monkeypatch.setattr(store, 'get_anomaly_runs', boom)
    response = client.get('/')
    assert response.status_code == 200
    assert b'CerebrOps' in response.data


def test_experience_does_not_touch_store(client, monkeypatch):
    """The experience page must stay fast: zero store reads."""
    from app import store

    def boom(*a, **k):
        raise RuntimeError('experience must not touch the store')

    monkeypatch.setattr(store, 'summary', boom)
    monkeypatch.setattr(store, 'get_anomaly_runs', boom)
    response = client.get('/experience')
    assert response.status_code == 200
    assert b'CerebrOps' in response.data


def test_api_v1_health(client):
    """Test the v1 health endpoint (open, no auth)"""
    response = client.get('/api/v1/health')
    assert response.status_code == 200
    body = response.get_json()
    assert body['status'] == 'success'
    assert body['data']['status'] == 'healthy'
    assert 'checks' in body['data']
    assert response.headers.get('X-Request-Id')


def test_api_v1_metrics_series(client):
    """Test the v1 metrics endpoint returns series + summary"""
    response = client.get('/api/v1/metrics')
    assert response.status_code == 200
    data = response.get_json()['data']
    assert 'series' in data
    assert 'cpu_usage' in data['series']
    assert 'summary' in data
    assert data['window'] == 60


def test_api_v1_requires_api_key(client):
    """When CEREBROPS_API_KEY is set, /api/v1/* (except health) requires it"""
    import app as app_module
    original = app_module.API_KEY
    app_module.API_KEY = 'test-secret'
    try:
        response = client.get('/api/v1/metrics')
        assert response.status_code == 401
        assert response.get_json()['error']['code'] == 'UNAUTHORIZED'

        response = client.get('/api/v1/metrics', headers={'X-API-Key': 'test-secret'})
        assert response.status_code == 200
        assert response.get_json()['status'] == 'success'

        # health stays open
        response = client.get('/api/v1/health')
        assert response.status_code == 200
    finally:
        app_module.API_KEY = original


def test_pipeline_webhook_and_readback(client):
    """POST a pipeline event, then read it back via v1 and the legacy endpoint"""
    response = client.post('/api/v1/pipeline/events', json={
        'pipeline_id': 'run-123',
        'status': 'success',
        'stage': 'deploy',
        'duration': 42,
        'branch': 'main',
        'commit_hash': 'abc1234',
        'source': 'github-actions',
    })
    assert response.status_code == 202
    body = response.get_json()
    assert body['status'] == 'success'
    assert body['data']['event_id'] > 0

    response = client.get('/api/v1/pipeline')
    assert response.status_code == 200
    events = response.get_json()['data']['events']
    assert len(events) == 1
    assert events[0]['status'] == 'success'
    assert events[0]['pipeline_id'] == 'run-123'
    assert events[0]['commit_hash'] == 'abc1234'

    # Legacy endpoint now reflects real ingested data
    response = client.get('/api/pipeline-status')
    body = response.get_json()
    assert body['status'] == 'success'
    assert body['pipeline_id'] == 'run-123'
    assert body['deprecated'] is True


def test_pipeline_webhook_invalid_status(client):
    """Invalid webhook payloads are rejected with the error envelope"""
    response = client.post('/api/v1/pipeline/events', json={'status': 'exploded'})
    assert response.status_code == 400
    body = response.get_json()
    assert body['status'] == 'error'
    assert body['error']['code'] == 'INVALID_REQUEST'


def test_pipeline_webhook_invalid_body(client):
    """Non-JSON webhook bodies are rejected"""
    response = client.post('/api/v1/pipeline/events', data='not json',
                           content_type='text/plain')
    assert response.status_code == 400


def test_dashboard_embeds_api_key(client, monkeypatch):
    """The shell carries the configured API key for the SPA to use."""
    import app as app_module
    original = app_module.API_KEY
    app_module.API_KEY = 'shell-secret'
    try:
        response = client.get('/dashboard')
        assert response.status_code == 200
        assert b'shell-secret' in response.data
    finally:
        app_module.API_KEY = original


# ---------------------------------------------------------------------------
# Auth — login / register / logout
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_enabled():
    """Enable dashboard auth for one test, then restore the suite default."""
    was = app.config.get('AUTH_DISABLED')
    app.config['AUTH_DISABLED'] = False
    # The in-process per-IP limiter is shared across tests: reset it so a
    # previous test's login spam cannot trip this test's IP ceiling.
    _login_ips.clear()
    yield
    app.config['AUTH_DISABLED'] = was


def _register(client, email='dev@cerebrops.dev', password='correct-horse'):
    # Fresh account = fresh failure counter (the SQLite attempt log is shared
    # across tests in this suite).
    store.clear_login_attempts(email)
    return client.post('/register', data={
        'name': 'Dev', 'email': email, 'password': password,
    })


def test_dashboard_redirects_to_login_when_logged_out(auth_enabled, client):
    response = client.get('/dashboard')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_login_page_renders(auth_enabled, client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Welcome' in response.data
    assert b'auth.css' in response.data


def test_register_creates_user_and_opens_dashboard(auth_enabled, client):
    response = _register(client)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/dashboard')
    with client.session_transaction() as sess:
        assert sess.get('user_id') is not None
    assert client.get('/dashboard').status_code == 200


def test_login_accepts_valid_credentials(auth_enabled, client):
    _register(client)
    client.get('/logout')
    response = client.post('/login', data={
        'email': 'dev@cerebrops.dev', 'password': 'correct-horse',
    })
    assert response.status_code == 302
    assert client.get('/dashboard').status_code == 200


def test_login_rejects_bad_password(auth_enabled, client):
    _register(client)
    response = client.post('/login', data={
        'email': 'dev@cerebrops.dev', 'password': 'wrong-password',
    })
    assert response.status_code == 200
    assert b'Invalid email or password' in response.data


def test_register_rejects_duplicate_email(auth_enabled, client):
    _register(client)
    client.get('/logout')
    response = _register(client, email='dev@cerebrops.dev')
    assert response.status_code == 200
    assert b'already exists' in response.data


def test_logout_clears_session(auth_enabled, client):
    _register(client)
    response = client.get('/logout')
    assert response.status_code == 302
    # dashboard is protected again after logout
    assert client.get('/dashboard').status_code == 302


# Auth hardening — lockout + password reset
# ---------------------------------------------------------------------------

def test_login_locks_out_after_repeated_failures(auth_enabled, client):
    """After LOGIN_MAX_FAILURES failures the account is locked even with the
    correct password, until the failure window passes."""
    _register(client)
    client.get('/logout')
    for _ in range(LOGIN_MAX_FAILURES):
        client.post('/login', data={
            'email': 'dev@cerebrops.dev', 'password': 'wrong-pass',
        })
    response = client.post('/login', data={
        'email': 'dev@cerebrops.dev', 'password': 'correct-horse',
    })
    assert b'Too many failed attempts' in response.data
    # ...and the correct password is still refused while locked
    assert b'Invalid email or password' not in response.data


def test_failed_attempts_are_recorded_in_store(auth_enabled, client):
    _register(client)
    client.get('/logout')
    for _ in range(3):
        client.post('/login', data={
            'email': 'dev@cerebrops.dev', 'password': 'wrong-pass',
        })
    assert store.recent_failed_logins('dev@cerebrops.dev') == 3


def test_forgot_password_issues_link_in_dev(auth_enabled, client):
    """Non-production environments render the reset link so the flow is
    usable without email infrastructure."""
    _register(client)
    client.get('/logout')
    response = client.post('/forgot-password', data={'email': 'dev@cerebrops.dev'})
    assert response.status_code == 200
    assert b'Reset link (development only)' in response.data


def test_forgot_password_does_not_enumerate_accounts(auth_enabled, client):
    """Unknown emails get the same generic message as known ones."""
    response = client.post('/forgot-password', data={'email': 'nobody@example.com'})
    assert response.status_code == 200
    assert b'Reset link (development only)' not in response.data
    assert b'If an account exists' in response.data


def test_password_reset_flow_end_to_end(auth_enabled, client):
    """Request -> use token -> new password works, old one does not."""
    _register(client)
    client.get('/logout')
    response = client.post('/forgot-password', data={'email': 'dev@cerebrops.dev'})
    match = re.search(rb'/reset-password\?token=([A-Za-z0-9_-]+)', response.data)
    assert match is not None
    token = match.group(1).decode()

    response = client.post('/reset-password?token=' + token, data={'password': 'brand-new-pass'})
    assert response.status_code == 302  # -> login?reset=1

    # Old password rejected, new one accepted.
    response = client.post('/login', data={
        'email': 'dev@cerebrops.dev', 'password': 'correct-horse',
    })
    assert b'Invalid email or password' in response.data
    response = client.post('/login', data={
        'email': 'dev@cerebrops.dev', 'password': 'brand-new-pass',
    })
    assert response.status_code == 302
    assert client.get('/dashboard').status_code == 200


def test_reset_token_is_single_use_and_expires(auth_enabled, client):
    _register(client)
    client.get('/logout')
    response = client.post('/forgot-password', data={'email': 'dev@cerebrops.dev'})
    token = re.search(rb'/reset-password\?token=([A-Za-z0-9_-]+)', response.data).group(1).decode()
    client.post('/reset-password?token=' + token, data={'password': 'first-new-pass'})
    # Replaying the same token must fail.
    response = client.post('/reset-password?token=' + token, data={'password': 'second-new-pass'})
    assert b'invalid or has already been used' in response.data
    # The token row is marked consumed in the store.
    from hashlib import sha256
    record = store.get_reset_token(sha256(token.encode()).hexdigest())
    assert record is not None and record['consumed'] == 1
