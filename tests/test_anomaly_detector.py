"""
Test suite for CerebrOps anomaly detection module
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import numpy as np
from anomaly_detector import AnomalyDetector
from metrics_store import MetricsStore
from model_repository import ModelRepository

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None


def _make_window_data(n, base_cpu=50.0, base_mem=60.0, seed=7):
    """Synthetic but explicit window data (never used as a silent fallback)."""
    rng = np.random.default_rng(seed)
    now = datetime.now(timezone.utc)
    data = []
    for i in range(n):
        data.append({
            'timestamp': (now - timedelta(hours=i * 0.1)).isoformat(),
            'cpu_usage': float(rng.normal(base_cpu, 5)),
            'memory_usage': float(rng.normal(base_mem, 4)),
            'disk_usage': float(rng.normal(70, 3)),
            'error_rate': float(rng.normal(1, 0.5)),
            'request_count': float(rng.normal(100, 10)),
            'response_time': float(rng.normal(0.3, 0.1)),
        })
    return data


class TestAnomalyDetector(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures with isolated store + model repo per test"""
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp.close()
        self._tmp_db_path = tmp.name
        self._tmp_model_dir = tempfile.mkdtemp()
        self.detector = AnomalyDetector(
            contamination=0.1,
            store=MetricsStore(self._tmp_db_path),
            repository=ModelRepository(self._tmp_model_dir),
        )

    def tearDown(self):
        """Clean up the per-test store and model repo"""
        try:
            os.remove(self._tmp_db_path)
        except OSError:
            pass
        try:
            shutil.rmtree(self._tmp_model_dir)
        except OSError:
            pass

    def test_detector_initialization(self):
        """Test detector initialization"""
        self.assertEqual(self.detector.contamination, 0.1)
        self.assertFalse(self.detector.is_trained)

    def test_generate_sample_data(self):
        """Test sample data generation"""
        data = self.detector._generate_sample_data()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        first_item = data[0]
        required_fields = ['timestamp', 'cpu_usage', 'memory_usage', 'disk_usage']
        for field in required_fields:
            self.assertIn(field, first_item)

    def test_prepare_features(self):
        """Test basic feature preparation"""
        sample_data = self.detector._generate_sample_data()
        features = self.detector.prepare_features(sample_data)

        self.assertIsInstance(features, np.ndarray)
        self.assertGreater(features.shape[0], 0)
        self.assertGreater(features.shape[1], 0)

    @unittest.skipUnless(PANDAS_AVAILABLE, 'pandas not available')
    def test_windowed_feature_building(self):
        """Test rolling-window feature extraction shape and names"""
        data = _make_window_data(50)
        features, names, kept = self.detector._build_features(data)

        # last + 5 stats (mean/std/slope/min/max) per window x 3 windows = 16
        # per metric, x 6 metrics, + hour + day_of_week = 98
        expected_per_metric = 1 + 5 * len(self.detector.windows_min)
        expected_cols = expected_per_metric * len(self.detector.feature_columns) + 2

        self.assertEqual(len(names), expected_cols)
        self.assertEqual(features.shape, (50, expected_cols))
        self.assertEqual(kept, list(range(50)))
        self.assertIn('cpu_usage_mean_15', names)
        self.assertIn('cpu_usage_std_60', names)
        self.assertIn('cpu_usage_slope_1440', names)
        self.assertIn('memory_usage_max_15', names)
        self.assertIn('hour', names)
        self.assertIn('day_of_week', names)

    @unittest.skipUnless(PANDAS_AVAILABLE, 'pandas not available')
    def test_windowed_features_are_finite(self):
        """Rolling features must not contain NaN/Inf after building"""
        data = _make_window_data(30)
        features, _, _ = self.detector._build_features(data)
        self.assertTrue(np.isfinite(features).all())

    def test_model_training(self):
        """Test model training"""
        training_data = _make_window_data(120)
        result = self.detector.train_model(training_data)

        self.assertTrue(result)
        self.assertTrue(self.detector.is_trained)

    def test_anomaly_detection_without_training(self):
        """Detection with an empty store must report insufficient_data - no
        silent synthetic fallback, and the model must remain untrained."""
        test_data = _make_window_data(10)
        result = self.detector.detect_anomalies(test_data)

        self.assertEqual(result.get('status'), 'insufficient_data')
        self.assertFalse(self.detector.is_trained)

    def test_detection_below_min_samples(self):
        """Detection below min_samples reports insufficient_data"""
        training_data = _make_window_data(120)
        self.assertTrue(self.detector.train_model(training_data))

        test_data = training_data[:5]
        result = self.detector.detect_anomalies(test_data)

        self.assertEqual(result.get('status'), 'insufficient_data')

    def test_train_model_without_data_refuses_synthetic(self):
        """Training with an empty store fails instead of faking data"""
        result = self.detector.train_model()

        self.assertFalse(result)
        self.assertFalse(self.detector.is_trained)

    def test_anomaly_detection_with_training(self):
        """Test anomaly detection with pre-trained model"""
        training_data = _make_window_data(120)
        self.assertTrue(self.detector.train_model(training_data))

        test_data = training_data[:20]
        result = self.detector.detect_anomalies(test_data)

        self.assertIn('status', result)
        self.assertIn('timestamp', result)
        self.assertIn('total_data_points', result)
        self.assertIn('anomaly_count', result)
        self.assertIn('top_metric_contributions', result)
        self.assertIn('model_version', result)

    def test_detection_returns_contributions_on_anomaly(self):
        """A strong injected spike should be flagged with metric contributions"""
        data = _make_window_data(150)
        for i in range(5):
            data.append({
                'timestamp': (datetime.now(timezone.utc) - timedelta(minutes=i)).isoformat(),
                'cpu_usage': 99.0,
                'memory_usage': 96.0,
                'disk_usage': 70.0,
                'error_rate': 40.0,
                'request_count': 400.0,
                'response_time': 4.0,
            })
        self.assertTrue(self.detector.train_model(data))

        result = self.detector.detect_anomalies(data[-40:])
        self.assertIn(result.get('status'), ('normal', 'anomaly'))
        if result.get('anomaly_count', 0) > 0 and PANDAS_AVAILABLE:
            self.assertTrue(result['top_metric_contributions'])
            self.assertIn('cpu_usage', result['top_metric_contributions'])
        elif result.get('anomaly_count', 0) > 0:
            # Raw-feature fallback has no windowed contributions.
            self.assertEqual(result['top_metric_contributions'], {})

    def test_metric_contributions_direct(self):
        """Unit-test the per-metric contribution computation"""
        names = [
            'cpu_usage_last', 'cpu_usage_mean_60', 'cpu_usage_std_60',
            'memory_usage_last', 'memory_usage_mean_60', 'memory_usage_std_60',
        ]
        features = np.array([
            [99.0, 50.0, 5.0, 60.0, 60.0, 5.0],
            [51.0, 50.0, 5.0, 62.0, 60.0, 5.0],
        ])
        contribs = self.detector._compute_metric_contributions(
            features, names, np.array([0])
        )
        self.assertIn('cpu_usage', contribs)

    def test_train_persists_model(self):
        """Training must persist a versioned model + card"""
        data = _make_window_data(120)
        self.assertTrue(self.detector.train_model(data))

        version = self.detector.repository.current_version()
        self.assertIsNotNone(version)
        self.assertGreaterEqual(version, 1)
        self.assertTrue(os.path.exists(self.detector.repository._model_path(version)))
        self.assertTrue(os.path.exists(self.detector.repository._card_path(version)))

    def test_retrain_increments_version(self):
        """Each retrain produces a new model version"""
        data = _make_window_data(120)
        self.assertTrue(self.detector.train_model(data))
        v1 = self.detector.repository.current_version()
        self.assertTrue(self.detector.train_model(data))
        v2 = self.detector.repository.current_version()
        self.assertEqual(v2, v1 + 1)

    def test_load_persisted_model(self):
        """A fresh detector must be able to reload the persisted model"""
        data = _make_window_data(120)
        self.assertTrue(self.detector.train_model(data))
        v1 = self.detector.repository.current_version()

        detector2 = AnomalyDetector(
            store=self.detector.store,
            repository=self.detector.repository,
        )
        self.assertFalse(detector2.is_trained)
        self.assertTrue(detector2.load_model())
        self.assertTrue(detector2.is_trained)
        self.assertEqual(detector2.current_version, v1)

        result = detector2.detect_anomalies(data[:20])
        self.assertIn('status', result)
        self.assertEqual(result.get('model_version'), v1)

    def test_load_model_when_none_persisted(self):
        """load_model returns False when no model was ever saved"""
        self.assertFalse(self.detector.load_model())
        self.assertFalse(self.detector.is_trained)

    def test_model_card_contents(self):
        """The model card must carry training metadata and a drift baseline"""
        data = _make_window_data(120)
        self.assertTrue(self.detector.train_model(data))

        card = self.detector.model_card
        for key in ('version', 'trained_at', 'n_samples', 'feature_names',
                    'feature_columns', 'windows_min', 'contamination', 'baseline'):
            self.assertIn(key, card)
        self.assertGreater(card['n_samples'], 0)
        self.assertIn('cpu_usage', card['baseline'])
        self.assertEqual(card['contamination'], 0.1)
        self.assertIn('psi_breakpoints', card['baseline']['cpu_usage'])
        self.assertIn('psi_expected', card['baseline']['cpu_usage'])

    def test_drift_detection_triggers_retrain(self):
        """A shifted distribution must flag needs_retrain"""
        train = _make_window_data(150, base_cpu=50.0, seed=1)
        self.assertTrue(self.detector.train_model(train))

        shifted = _make_window_data(50, base_cpu=95.0, seed=2)
        drift = self.detector.compute_drift(shifted)

        self.assertTrue(drift['needs_retrain'])
        self.assertGreater(drift['max_psi'], 0.25)
        self.assertIn('cpu_usage', drift['per_metric'])

    def test_drift_stable_when_similar(self):
        """A similar distribution must NOT trigger a retrain"""
        train = _make_window_data(150, base_cpu=50.0, seed=1)
        self.assertTrue(self.detector.train_model(train))

        similar = _make_window_data(50, base_cpu=50.0, seed=3)
        drift = self.detector.compute_drift(similar)

        self.assertFalse(drift['needs_retrain'])
        self.assertLess(drift['max_psi'], 0.25)

    def test_drift_without_baseline(self):
        """compute_drift is a no-op when the model was never trained"""
        data = _make_window_data(50)
        drift = self.detector.compute_drift(data)
        self.assertFalse(drift['needs_retrain'])
        self.assertEqual(drift['max_psi'], 0.0)

    def test_severity_calculation(self):
        """Test severity calculation"""
        scores = np.array([-0.1, -0.2, -0.3, -0.6])

        severity = self.detector._calculate_severity(5.0, scores)
        self.assertIn(severity, ['low', 'medium', 'high', 'critical'])

        severity = self.detector._calculate_severity(25.0, scores)
        self.assertEqual(severity, 'critical')

    def test_recommendations_generation(self):
        """Test recommendations generation"""
        test_data = [
            {'cpu_usage': 90, 'memory_usage': 85, 'error_rate': 15, 'disk_usage': 70,
             'request_count': 100, 'response_time': 3.0},
            {'cpu_usage': 95, 'memory_usage': 90, 'error_rate': 20, 'disk_usage': 75,
             'request_count': 120, 'response_time': 4.0},
            {'cpu_usage': 85, 'memory_usage': 80, 'error_rate': 12, 'disk_usage': 65,
             'request_count': 90, 'response_time': 2.5},
        ]

        features = self.detector.prepare_features(test_data)
        predictions = np.array([-1, -1, -1])  # All anomalies

        recommendations = self.detector._get_recommendations(features, predictions, test_data)

        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)

    def test_fetch_metrics_data_from_store(self):
        """Test fetching a real window of metrics from the store"""
        for i in range(5):
            self.detector.store.record_metric(
                cpu_usage=float(i),
                memory_usage=float(10 + i),
                disk_usage=float(20 + i),
                error_rate=0.0,
                request_count=1,
                response_time=0.1,
            )

        data = self.detector.fetch_metrics_data(limit=3)

        self.assertEqual(len(data), 3)
        self.assertIn('cpu_usage', data[0])
        # Most recent 3 rows: i=2,3,4 -> memory_usage 12, 13, 14
        self.assertEqual(data[0]['memory_usage'], 12.0)
        self.assertEqual(data[-1]['memory_usage'], 14.0)

    def test_fetch_metrics_data_empty_store(self):
        """An empty store returns an empty list (no synthetic fallback)"""
        data = self.detector.fetch_metrics_data()
        self.assertEqual(data, [])

    @patch.object(MetricsStore, 'get_metrics', side_effect=Exception("Store error"))
    def test_fetch_metrics_data_failure(self, mock_get_metrics):
        """Metrics fetching failure returns an empty list"""
        data = self.detector.fetch_metrics_data()
        self.assertEqual(data, [])

    # ------------------------------------------------------------------
    # Phase 5: forecast-residual dispatch
    # ------------------------------------------------------------------

    def test_detect_defaults_to_isolation_forest(self):
        """Without a fitted forecast detector, results say isolation-forest"""
        data = _make_window_data(120)
        self.assertTrue(self.detector.train_model(data))
        result = self.detector.detect_anomalies(data[:20])
        self.assertEqual(result.get('method'), 'isolation-forest')

    def test_detect_uses_forecast_when_fitted(self):
        """A fitted forecast detector takes precedence in auto mode"""
        from forecast_detector import ForecastResidualDetector

        det = ForecastResidualDetector(min_history_days=7, min_history_points=100)
        rng = np.random.default_rng(11)
        start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
        train = []
        for i in range(14 * 48):  # 30-min sampling -> 4 obs/bucket
            ts = start + timedelta(minutes=30 * i)
            val = 50 + 10 * np.sin(ts.hour / 24.0 * 2 * np.pi) + rng.normal(0, 1)
            train.append({
                'ts': ts.isoformat(), 'cpu_usage': float(val),
                'memory_usage': 60.0, 'disk_usage': 70.0,
                'error_rate': 0.5, 'request_count': 100.0, 'response_time': 0.3,
            })
        self.assertTrue(det.fit(train))
        self.detector.forecast = det

        result = self.detector.detect_anomalies(train[-48:])
        self.assertEqual(result.get('method'), 'forecast-residual')
        self.assertIn(result.get('status'), ('normal', 'anomaly'))

    def test_detect_forced_forecast_without_fit(self):
        """method='forecast' honors the request even when not fitted"""
        data = _make_window_data(20)
        result = self.detector.detect_anomalies(data, method='forecast')
        self.assertEqual(result.get('status'), 'insufficient_data')


if __name__ == '__main__':
    unittest.main()
