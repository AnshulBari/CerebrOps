"""
Tests for the CerebrOps model evaluation harness (Phase 5).

The harness itself is the acceptance path for "model v2 evaluated on real
data" - these tests verify the machinery on a labeled synthetic fixture so it
is ready to run on >= 2 weeks of real production data once it exists.
"""

import unittest
from datetime import datetime

from scripts.evaluate_models import generate_labeled, run_evaluation


class TestEvaluationHarness(unittest.TestCase):

    def test_generate_labeled_has_expected_anomalies(self):
        rows = generate_labeled(days=21, anomaly_count=10, seed=7)
        self.assertEqual(len(rows), 21 * 48)
        self.assertEqual(sum(r['true_anomaly'] for r in rows), 10)
        self.assertIn('cpu_usage', rows[0])
        self.assertIn('ts', rows[0])

    def test_run_evaluation_reports_scores(self):
        rows = generate_labeled(days=21, anomaly_count=10, seed=7)
        train, test = rows[:800], rows[800:]
        true_times = [
            datetime.fromisoformat(r['ts']) for r in test if r['true_anomaly']
        ]
        report = run_evaluation(train, test, true_times, tolerance_min=90)

        self.assertEqual(report['dataset']['labeled_anomalies'], len(true_times))
        self.assertGreater(report['dataset']['test_points'], 0)

        v2 = report['v2_forecast_residual']
        self.assertTrue(v2['fitted'])
        # Strong seasonal-context spikes must be caught with high recall.
        self.assertGreaterEqual(v2['recall'], 0.9)
        self.assertGreaterEqual(v2['precision'], 0.5)
        self.assertIn('f1', v2)
        self.assertEqual(v2['tp'] + v2['fp'], v2['detected_anomalies'])

        v1 = report['v1_isolation_forest']
        self.assertTrue(v1['trained'])
        for key in ('tp', 'fp', 'fn', 'precision', 'recall', 'f1'):
            self.assertIn(key, v1)

    def test_empty_labels_never_match(self):
        rows = generate_labeled(days=14, anomaly_count=4, seed=3)
        train, test = rows[:500], rows[500:]
        report = run_evaluation(train, test, [], tolerance_min=60)
        v2 = report['v2_forecast_residual']
        # No labeled anomalies -> any detection is a false positive.
        self.assertEqual(v2['tp'], 0)
        self.assertEqual(v2['recall'], 0.0)


if __name__ == '__main__':
    unittest.main()
