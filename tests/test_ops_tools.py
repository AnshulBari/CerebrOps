"""
Tests for the Phase 5 ops tooling that closes the 'documented but unproven'
gaps: the restore drill, LLM mock mode, and the evaluation self-check gate.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_summary import generate_llm_summary  # noqa: E402
from scripts.restore_drill import run_drill  # noqa: E402

SAMPLE_RESULTS = {
    'status': 'anomaly',
    'method': 'forecast-residual',
    'anomaly_count': 3,
    'total_data_points': 50,
    'anomaly_percentage': 6.0,
    'severity': 'high',
    'top_metric_contributions': {'cpu_usage': 42.3, 'response_time': 3.0},
    'anomalous_data': [],
}
SAMPLE_ROOT_CAUSE = {
    'deploy_correlation': [{
        'pipeline_id': 'run-987', 'status': 'success', 'stage': 'deploy',
        'branch': 'main', 'commit_hash': 'deadbeef', 'minutes_before': 1.1,
    }],
    'metric_shifts': {'cpu_usage': {'shifted': True}},
    'hypothesis': 'Possible deploy-related regression: run-987 (main@deadbeef).',
}


class TestRestoreDrill(unittest.TestCase):

    def test_drill_passes_on_fixture_store(self):
        """The quarterly drill can run anywhere (no cluster, no live store)."""
        self.assertEqual(
            run_drill('missing.db', 'missing-models', use_fixture=True), 0)

    def test_drill_passes_on_real_store_layout(self):
        """Pointed at the real db path with an empty model dir it still works
        (the real store only has to be readable)."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        real_db = os.path.join(root, 'data', 'cerebrops.db')
        if not os.path.exists(real_db):
            self.skipTest('no real store in this checkout')
        self.assertEqual(run_drill(real_db, 'missing-models', use_fixture=False), 0)


class TestLLMMockMode(unittest.TestCase):

    @patch.dict(os.environ, {'LLM_MODE': 'mock'}, clear=False)
    @patch('llm_summary.requests.post')
    def test_mock_mode_is_deterministic_and_offline(self, mock_post):
        summary = generate_llm_summary(SAMPLE_RESULTS, SAMPLE_ROOT_CAUSE)
        self.assertIsNotNone(summary)
        self.assertIn('[mock]', summary)
        self.assertIn('forecast-residual', summary)
        self.assertIn('run-987', summary)
        self.assertIn('cpu_usage', summary)
        mock_post.assert_not_called()  # no network, ever

    @patch.dict(os.environ, {'LLM_MODE': 'mock'}, clear=False)
    def test_mock_mode_works_without_any_api_config(self):
        # No LLM_API_URL set: a real call would return None; mock still answers.
        for key in ('LLM_API_URL', 'LLM_API_KEY', 'LLM_MODEL'):
            os.environ.pop(key, None)
        self.assertIsNotNone(generate_llm_summary(SAMPLE_RESULTS, SAMPLE_ROOT_CAUSE))

    @patch.dict(os.environ, {'LLM_MODE': 'mock'}, clear=False)
    def test_mock_mode_mentions_deploy_when_correlated(self):
        summary = generate_llm_summary(SAMPLE_RESULTS, SAMPLE_ROOT_CAUSE)
        self.assertIn('deploy run-987', summary)


class TestEvalSelfCheckGate(unittest.TestCase):

    def test_self_check_exits_zero(self):
        """The CI gate runs on deterministic synthetic data and must pass."""
        import subprocess
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        py = sys.executable
        proc = subprocess.run(
            [py, os.path.join(root, 'scripts', 'evaluate_models.py'),
             '--self-check'],
            capture_output=True, text=True, timeout=300, cwd=root,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout[-1500:] + proc.stderr[-500:])
        self.assertIn('Self-check passed', proc.stdout)
