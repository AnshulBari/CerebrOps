"""
Test suite for CerebrOps Flask application
"""

import pytest
import json
from app import app


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


def test_dashboard(client):
    """Test the main dashboard endpoint"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'CerebrOps' in response.data


def test_metrics_endpoint(client):
    """Test the metrics API endpoint"""
    response = client.get('/metrics')
    assert response.status_code == 200
    data = json.loads(response.data)

    required_fields = ['timestamp', 'cpu_usage', 'memory_usage', 'disk_usage']
    for field in required_fields:
        assert field in data


def test_logs_endpoint(client):
    """Test the logs API endpoint"""
    response = client.get('/logs')
    assert response.status_code == 200
    data = json.loads(response.data)

    assert 'logs' in data
    assert isinstance(data['logs'], list)


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
    response = client.get('/simulate-error')
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'status' in data
    assert data['status'] == 'error simulated'
