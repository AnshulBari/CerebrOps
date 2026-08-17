"""
Test suite for the CerebrOps deploy-correlation root-cause module (Phase 5).
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from metrics_store import MetricsStore
from root_cause import analyze_root_cause, correlate_deploys, metric_shift_summary


class TestRootCause(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp.close()
        self._db = tmp.name
        self.store = MetricsStore(self._db)

    def tearDown(self):
        try:
            os.remove(self._db)
        except OSError:
            pass

    def _add_metrics(self, when_offsets_min, cpu=50.0, mem=60.0):
        for offset in when_offsets_min:
            ts = (datetime.now(timezone.utc) - timedelta(minutes=offset)).isoformat()
            self.store.record_metric(
                ts=ts, cpu_usage=cpu, memory_usage=mem,
                disk_usage=70.0, error_rate=0.5,
                request_count=100, response_time=0.3,
            )

    def test_correlate_finds_recent_deploy(self):
        self.store.record_pipeline_event(
            status='success', pipeline_id='run-987', stage='deploy',
            branch='main', commit_hash='deadbeef', source='github-actions',
        )
        matches = correlate_deploys(self.store)
        self.assertEqual(len(matches), 1)
        m = matches[0]
        self.assertEqual(m['pipeline_id'], 'run-987')
        self.assertEqual(m['commit_hash'], 'deadbeef')
        self.assertLessEqual(m['minutes_before'], 1.0)

    def test_correlate_filters_non_deploy_stages(self):
        self.store.record_pipeline_event(status='success', pipeline_id='run-1',
                                         stage='test', source='github-actions')
        self.store.record_pipeline_event(status='success', pipeline_id='run-2',
                                         stage='deploy', source='github-actions')
        matches = correlate_deploys(self.store)
        self.assertEqual([m['pipeline_id'] for m in matches], ['run-2'])

    def test_correlate_empty_store(self):
        self.assertEqual(correlate_deploys(self.store), [])

    def test_metric_shift_detected(self):
        # 2h before the window vs inside the window -> cpu doubles.
        self._add_metrics([240, 239, 238], cpu=30.0)
        self._add_metrics([30, 29, 28], cpu=75.0)
        shifts = metric_shift_summary(self.store)
        self.assertIn('cpu_usage', shifts)
        self.assertTrue(shifts['cpu_usage']['shifted'])
        self.assertGreater(shifts['cpu_usage']['shift_pct'], 100.0)

    def test_metric_shift_stable(self):
        self._add_metrics([240, 239], cpu=50.0)
        self._add_metrics([30, 29], cpu=51.0)
        shifts = metric_shift_summary(self.store)
        self.assertFalse(shifts['cpu_usage']['shifted'])

    def test_analyze_root_cause_hypothesis(self):
        self.store.record_pipeline_event(
            status='success', pipeline_id='run-42', stage='deploy',
            branch='main', commit_hash='c0ffee', source='github-actions',
        )
        self._add_metrics([240, 239], cpu=30.0)
        self._add_metrics([30, 29], cpu=80.0)
        rc = analyze_root_cause(self.store)
        self.assertEqual(len(rc['deploy_correlation']), 1)
        self.assertTrue(rc['metric_shifts']['cpu_usage']['shifted'])
        self.assertIsNotNone(rc['hypothesis'])
        self.assertIn('run-42', rc['hypothesis'])
        self.assertIn('deploy', rc['hypothesis'])

    def test_analyze_root_cause_no_deploy_no_hypothesis(self):
        self._add_metrics([240, 239], cpu=50.0)
        self._add_metrics([30, 29], cpu=50.0)
        rc = analyze_root_cause(self.store)
        self.assertEqual(rc['deploy_correlation'], [])
        self.assertIsNone(rc['hypothesis'])


if __name__ == '__main__':
    unittest.main()
