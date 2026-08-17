"""
Test suite for the SQLite-backed MetricsStore
"""

import pytest

from metrics_store import MetricsStore


def test_record_and_get_metrics(tmp_path):
    """Test recording and fetching a single metric row."""
    store = MetricsStore(str(tmp_path / 'test.db'))
    row_id = store.record_metric(
        cpu_usage=1.0,
        memory_usage=2.0,
        disk_usage=3.0,
        error_rate=0.0,
        request_count=1,
        response_time=0.25,
        extra={'route': '/'},
    )
    assert row_id > 0

    rows = store.get_metrics()
    assert len(rows) == 1
    assert rows[0]['cpu_usage'] == 1.0
    assert rows[0]['memory_usage'] == 2.0
    assert rows[0]['error_rate'] == 0.0
    assert rows[0]['request_count'] == 1
    assert rows[0]['response_time'] == 0.25
    assert rows[0]['extra'] == {'route': '/'}


def test_get_metrics_limit_and_order(tmp_path):
    """Test that get_metrics returns the most recent rows chronologically."""
    store = MetricsStore(str(tmp_path / 'test.db'))
    store.record_metrics([
        {'cpu_usage': float(i), 'request_count': 1, 'response_time': 0.1}
        for i in range(10)
    ])

    rows = store.get_metrics(limit=3)
    assert len(rows) == 3
    assert [row['cpu_usage'] for row in rows] == [7.0, 8.0, 9.0]


def test_summary(tmp_path):
    """Test the summary aggregation."""
    store = MetricsStore(str(tmp_path / 'test.db'))
    store.record_metrics([
        {'error_rate': 0.0, 'response_time': 0.1, 'request_count': 1},
        {'error_rate': 1.0, 'response_time': 0.3, 'request_count': 1},
        {'error_rate': 0.0, 'response_time': 0.2, 'request_count': 1},
    ])

    summary = store.summary(since_hours=1)
    assert summary['total'] == 3
    assert summary['error_rate_percent'] == pytest.approx(33.33, abs=0.01)
    assert summary['avg_response_time_seconds'] == pytest.approx(0.2)
    assert summary['avg_response_time_ms'] == pytest.approx(200.0)


def test_summary_excludes_probe_rows(tmp_path):
    """Probe rows without request_count must not skew request/error stats."""
    store = MetricsStore(str(tmp_path / 'test.db'))
    store.record_metrics([
        {'error_rate': 1.0, 'request_count': 1, 'response_time': 0.5},
        {'error_rate': 0.0, 'request_count': 1, 'response_time': 0.1},
        {'extra': {'probe': 'health'}},  # no request_count -> not a request
    ])

    summary = store.summary(since_hours=1)
    assert summary['total'] == 2
    assert summary['error_rate_percent'] == pytest.approx(50.0)
    assert summary['avg_response_time_seconds'] == pytest.approx(0.3)

    # All rows are still stored/retrievable for the detector window.
    assert store.count_metrics() == 3


def test_alerts_roundtrip(tmp_path):
    """Test recording and fetching alerts."""
    store = MetricsStore(str(tmp_path / 'test.db'))
    alert_id = store.record_alert('high', 'anomaly', 'Detected anomalies', {'count': 3})
    assert alert_id > 0

    alerts = store.get_alerts()
    assert len(alerts) == 1
    assert alerts[0]['severity'] == 'high'
    assert alerts[0]['alert_type'] == 'anomaly'
    assert alerts[0]['payload'] == {'count': 3}


def test_anomaly_runs_roundtrip(tmp_path):
    """Test recording and fetching anomaly runs."""
    store = MetricsStore(str(tmp_path / 'test.db'))
    run_id = store.record_anomaly_run(
        status='anomaly',
        anomaly_count=2,
        total_data_points=50,
        severity='high',
        results={'status': 'anomaly'},
    )
    assert run_id > 0

    runs = store.get_anomaly_runs()
    assert len(runs) == 1
    assert runs[0]['status'] == 'anomaly'
    assert runs[0]['anomaly_count'] == 2
    assert runs[0]['total_data_points'] == 50
    assert runs[0]['severity'] == 'high'
    assert runs[0]['results'] == {'status': 'anomaly'}


def test_pipeline_events_roundtrip(tmp_path):
    """Test recording and fetching pipeline events."""
    store = MetricsStore(str(tmp_path / 'test.db'))
    event_id = store.record_pipeline_event(
        status='success', pipeline_id='run-1', stage='deploy',
        duration=42, branch='main', commit_hash='abc', source='github-actions',
        payload={'extra': 'info'},
    )
    assert event_id > 0

    events = store.get_pipeline_events()
    assert len(events) == 1
    assert events[0]['status'] == 'success'
    assert events[0]['pipeline_id'] == 'run-1'
    assert events[0]['commit_hash'] == 'abc'
    assert events[0]['payload'] == {'extra': 'info'}


def test_empty_store(tmp_path):
    """Test that a fresh store returns empty results."""
    store = MetricsStore(str(tmp_path / 'test.db'))
    assert store.get_metrics() == []
    assert store.count_metrics() == 0
    assert store.summary()['total'] == 0
    assert store.get_alerts() == []
    assert store.get_anomaly_runs() == []
