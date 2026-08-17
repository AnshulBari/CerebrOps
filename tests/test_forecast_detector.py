"""
Test suite for the CerebrOps forecast-residual anomaly detector (Phase 5).
"""

import math
import unittest
from datetime import datetime, timedelta, timezone

import numpy as np

from forecast_detector import ForecastResidualDetector

T0 = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)  # a Monday


def _synthetic_forecast_rows(days, interval_h=1.0, base=50.0, season_amp=10.0,
                             noise=1.0, seed=1, spike_idx=None, spike_val=95.0):
    """Seasonal (daily) synthetic history with small noise - explicit test
    data, never a production fallback."""
    rng = np.random.default_rng(seed)
    n = int(days * 24.0 / interval_h)
    rows = []
    for i in range(n):
        ts = T0 + timedelta(hours=i * interval_h)
        hour = ts.hour
        val = base + season_amp * math.sin((hour / 24.0) * 2 * math.pi)
        val += rng.normal(0, noise)
        if spike_idx is not None and i == spike_idx:
            val = spike_val
        rows.append({
            'ts': ts.isoformat(),
            'cpu_usage': round(float(val), 4),
            'memory_usage': round(base + 20 + rng.normal(0, noise), 4),
            'disk_usage': round(base + 40 + rng.normal(0, noise), 4),
            'error_rate': round(0.5 + rng.normal(0, 0.1), 4),
            'request_count': round(100 + rng.normal(0, 5), 4),
            'response_time': round(0.3 + rng.normal(0, 0.05), 4),
        })
    return rows


class TestForecastResidualDetector(unittest.TestCase):

    def test_fit_requires_min_history_span(self):
        """A short history (3 days) must not fit - real-data gate."""
        det = ForecastResidualDetector(min_history_days=7, min_history_points=50)
        rows = _synthetic_forecast_rows(3)
        self.assertFalse(det.fit(rows))
        self.assertFalse(det.is_fitted)

    def test_fit_requires_min_points(self):
        """Too few points must not fit even when the span is long enough."""
        det = ForecastResidualDetector(min_history_days=1, min_history_points=1000)
        rows = _synthetic_forecast_rows(3)  # 72 points, span 3 days
        self.assertFalse(det.fit(rows))
        self.assertFalse(det.is_fitted)

    def test_fit_requires_timestamped_rows(self):
        det = ForecastResidualDetector(min_history_days=1, min_history_points=10)
        rows = [{'cpu_usage': 50.0} for _ in range(50)]  # no ts
        self.assertFalse(det.fit(rows))
        self.assertFalse(det.is_fitted)

    def test_fit_success_with_sufficient_history(self):
        det = ForecastResidualDetector(min_history_days=7, min_history_points=100)
        rows = _synthetic_forecast_rows(14, interval_h=0.5)  # 672 pts, 4 obs/bucket
        self.assertTrue(det.fit(rows))
        self.assertTrue(det.is_fitted)
        meta = det.fit_meta
        self.assertGreaterEqual(meta['history_days'], 13.9)
        self.assertGreaterEqual(meta['obs_per_bucket'], 4.0)
        self.assertIn('cpu_usage', meta['metrics'])

    def test_fit_requires_min_obs_per_bucket(self):
        """Sparse buckets (1 obs/bucket) must not fit - noisy forecast gate."""
        det = ForecastResidualDetector(min_history_days=7, min_history_points=100)
        rows = _synthetic_forecast_rows(14)  # 336 pts hourly = 2 obs/bucket
        self.assertFalse(det.fit(rows))
        self.assertFalse(det.is_fitted)

    def test_detect_normal_continuation(self):
        det = ForecastResidualDetector(min_history_days=7, min_history_points=100)
        train = _synthetic_forecast_rows(14, interval_h=0.5)
        self.assertTrue(det.fit(train))
        test = _synthetic_forecast_rows(1, interval_h=0.5, seed=2)  # 24h, no spike
        result = det.detect(test)
        self.assertEqual(result['status'], 'normal')
        self.assertEqual(result['method'], 'forecast-residual')
        self.assertEqual(result['anomaly_count'], 0)

    def test_detect_flags_strong_spike(self):
        det = ForecastResidualDetector(min_history_days=7, min_history_points=100)
        train = _synthetic_forecast_rows(14, interval_h=0.5)
        self.assertTrue(det.fit(train))
        test = _synthetic_forecast_rows(1, interval_h=0.5, seed=2,
                                        spike_idx=5, spike_val=95.0)
        result = det.detect(test)
        self.assertEqual(result['status'], 'anomaly')
        self.assertEqual(result['method'], 'forecast-residual')
        self.assertGreaterEqual(result['anomaly_count'], 1)
        self.assertGreater(result['anomaly_percentage'], 0)
        self.assertIn('cpu_usage', result['top_metric_contributions'])
        self.assertGreaterEqual(result['top_metric_contributions']['cpu_usage'], 4.0)
        # The anomalous point records the metric, forecast, residual, z-score.
        self.assertTrue(result['anomalous_data'])
        first_scores = result['anomalous_data'][0]['scores']
        self.assertTrue(any(s['metric'] == 'cpu_usage' and s['z_score'] >= 4.0
                            for s in first_scores))

    def test_detect_without_fit_reports_insufficient_data(self):
        det = ForecastResidualDetector()
        rows = _synthetic_forecast_rows(1)
        result = det.detect(rows)
        self.assertEqual(result['status'], 'insufficient_data')
        self.assertIn('not fitted', result['message'])

    def test_detect_too_few_points_reports_insufficient_data(self):
        det = ForecastResidualDetector(min_history_days=7, min_history_points=100)
        self.assertTrue(det.fit(_synthetic_forecast_rows(14, interval_h=0.5)))
        result = det.detect(_synthetic_forecast_rows(1, interval_h=0.5)[:5])
        self.assertEqual(result['status'], 'insufficient_data')

    def test_detect_empty_reports_no_data(self):
        det = ForecastResidualDetector(min_history_days=7, min_history_points=100)
        self.assertTrue(det.fit(_synthetic_forecast_rows(14, interval_h=0.5)))
        result = det.detect([])
        self.assertEqual(result['status'], 'no_data')

    def test_severity_scaling(self):
        self.assertEqual(ForecastResidualDetector._calculate_severity(0.0), 'low')
        self.assertEqual(ForecastResidualDetector._calculate_severity(8.0), 'medium')
        self.assertEqual(ForecastResidualDetector._calculate_severity(15.0), 'high')
        self.assertEqual(ForecastResidualDetector._calculate_severity(25.0), 'critical')

    # ------------------------------------------------------------------
    # Debounce (tail-of-noise filtering)
    # ------------------------------------------------------------------

    def _debounce_fixture(self):
        """Low-noise fixture; returns (detector, clean test window)."""
        det = ForecastResidualDetector(min_history_days=7, min_history_points=100)
        self.assertTrue(det.fit(_synthetic_forecast_rows(14, interval_h=0.5, noise=0.1)))
        test = _synthetic_forecast_rows(1, interval_h=0.5, noise=0.1, seed=2)
        return det, test

    @staticmethod
    def _set_z(det, row, z_target):
        """Set cpu_usage so the point's z-score equals z_target exactly."""
        from metrics_store import parse_ts
        p = det.profiles['cpu_usage']
        ts = parse_ts(row['ts'])
        b = ts.weekday() * 24 + ts.hour
        row['cpu_usage'] = round(
            float(p['bucket_mean'][b]) + p['resid_mean'] + z_target * p['resid_std'], 4
        )

    def test_debounce_isolated_borderline_not_flagged(self):
        """A single point between z_threshold and hard_z_threshold with clean
        neighbors is tail-of-noise - must NOT be flagged."""
        det, test = self._debounce_fixture()
        self._set_z(det, test[10], 4.2)
        result = det.detect(test)
        self.assertEqual(result['status'], 'normal')
        self.assertEqual(result['anomaly_count'], 0)

    def test_debounce_adjacent_pair_flagged(self):
        """Two adjacent borderline points (persistent deviation) ARE flagged."""
        det, test = self._debounce_fixture()
        self._set_z(det, test[10], 4.2)
        self._set_z(det, test[11], 4.2)
        result = det.detect(test)
        self.assertEqual(result['status'], 'anomaly')
        self.assertEqual(result['anomaly_count'], 2)

    def test_hard_threshold_flags_isolated_strong_point(self):
        """A single point above the hard threshold is flagged unconditionally."""
        det, test = self._debounce_fixture()
        self._set_z(det, test[10], 6.0)
        result = det.detect(test)
        self.assertEqual(result['status'], 'anomaly')
        self.assertEqual(result['anomaly_count'], 1)


if __name__ == '__main__':
    unittest.main()
