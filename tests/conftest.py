"""
Test configuration and fixtures for CerebrOps
"""

import pytest
import os
import sys
import tempfile
from unittest.mock import Mock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Isolate telemetry into per-process temp DB + model dir so tests never touch
# the real data/cerebrops.db or models/, and keep logging handlers out of
# pytest's capture.
os.environ['TESTING'] = 'true'
# Dashboard auth is off for the general suite (see test_app.py auth tests
# which flip AUTH_DISABLED on a per-test basis). Must be set before app.py
# is imported, because the flag is read at module load.
os.environ['CEREBROPS_AUTH_DISABLED'] = '1'
os.environ['CEREBROPS_DB_PATH'] = os.path.join(
    tempfile.gettempdir(), f'cerebrops_test_{os.getpid()}.db'
)
os.environ['CEREBROPS_MODEL_DIR'] = os.path.join(
    tempfile.gettempdir(), f'cerebrops_models_{os.getpid()}'
)


def pytest_sessionfinish(session, exitstatus):
    """Remove the temp test database and model dir after the session."""
    import shutil
    db_path = os.environ.get('CEREBROPS_DB_PATH')
    if db_path and os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass
    model_dir = os.environ.get('CEREBROPS_MODEL_DIR')
    if model_dir and os.path.isdir(model_dir):
        try:
            shutil.rmtree(model_dir)
        except OSError:
            pass


# Check for pandas availability
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None


@pytest.fixture
def mock_pandas_dataframe():
    """Mock pandas DataFrame for tests when pandas is not available"""
    if PANDAS_AVAILABLE:
        return pd.DataFrame

    # Create a mock DataFrame class
    class MockDataFrame:
        def __init__(self, data=None):
            self.data = data or []
            self.columns = []
            if data and len(data) > 0:
                if isinstance(data[0], dict):
                    self.columns = list(data[0].keys())

        def __getitem__(self, key):
            return MockDataFrame([row[key] for row in self.data if key in row])

        def mean(self):
            return 50.0  # Mock mean value

        def empty(self):
            return len(self.data) == 0

    return MockDataFrame


@pytest.fixture
def sample_test_data():
    """Sample data for testing"""
    return [
        {
            'timestamp': '2023-01-01T00:00:00',
            'cpu_usage': 45.0,
            'memory_usage': 60.0,
            'disk_usage': 70.0,
            'error_rate': 2.0
        },
        {
            'timestamp': '2023-01-01T00:01:00',
            'cpu_usage': 50.0,
            'memory_usage': 65.0,
            'disk_usage': 75.0,
            'error_rate': 1.5
        }
    ]


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment"""
    # Ensure logs directory exists for app.py tests
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    # Set test environment variables
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['TESTING'] = 'true'

    yield

    # Cleanup
    if 'FLASK_ENV' in os.environ:
        del os.environ['FLASK_ENV']
    if 'TESTING' in os.environ:
        del os.environ['TESTING']


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "requires_pandas: mark test as requiring pandas"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to skip pandas-dependent tests when pandas is not available"""
    if not PANDAS_AVAILABLE:
        skip_pandas = pytest.mark.skip(reason="pandas not available")
        for item in items:
            if "anomaly_detector" in str(item.fspath) and "pandas" in str(item.function.__name__):
                item.add_marker(skip_pandas)
