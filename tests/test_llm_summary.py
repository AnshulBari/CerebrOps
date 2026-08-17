"""
Tests for the CerebrOps LLM anomaly summary module (Phase 5).
"""

import unittest
from unittest.mock import Mock, patch

from llm_summary import build_prompt, generate_llm_summary

SAMPLE_RESULTS = {
    'status': 'anomaly',
    'method': 'forecast-residual',
    'anomaly_count': 3,
    'total_data_points': 50,
    'anomaly_percentage': 6.0,
    'severity': 'high',
    'top_metric_contributions': {'cpu_usage': 42.3, 'response_time': 3.0},
    'anomalous_data': [
        {'ts': '2026-08-16T20:23:53+00:00',
         'scores': [{'metric': 'cpu_usage', 'value': 99.0, 'forecast': 54.3,
                     'residual': 44.8, 'z_score': 42.3}]},
    ],
}

SAMPLE_ROOT_CAUSE = {
    'deploy_correlation': [{
        'pipeline_id': 'run-987', 'status': 'success', 'stage': 'deploy',
        'branch': 'main', 'commit_hash': 'deadbeef', 'minutes_before': 1.1,
    }],
    'metric_shifts': {'cpu_usage': {'shifted': True}},
    'hypothesis': 'Possible deploy-related regression: run-987 (main@deadbeef) completed 1.1m before the anomaly.',
}


class TestLLMSummary(unittest.TestCase):

    def test_disabled_without_api_url(self):
        """No LLM_API_URL -> None, and no HTTP call is attempted."""
        with patch('llm_summary.requests.post') as mock_post:
            summary = generate_llm_summary(SAMPLE_RESULTS, SAMPLE_ROOT_CAUSE)
            self.assertIsNone(summary)
            mock_post.assert_not_called()

    def test_build_prompt_contains_key_facts(self):
        prompt = build_prompt(SAMPLE_RESULTS, SAMPLE_ROOT_CAUSE)
        self.assertIn('forecast-residual', prompt)
        self.assertIn('cpu_usage=42.30', prompt)
        self.assertIn('run-987', prompt)
        self.assertIn('Shifted metrics', prompt)
        self.assertIn('deadbeef', prompt)

    @patch('llm_summary.requests.post')
    def test_generate_returns_summary(self, mock_post):
        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            'choices': [{'message': {'content': '  The CPU spike correlates with deploy run-987.  '}}],
            'usage': {'completion_tokens': 42},
        }
        mock_post.return_value = mock_resp

        summary = generate_llm_summary(
            SAMPLE_RESULTS, SAMPLE_ROOT_CAUSE,
            api_url='https://llm.example/v1', api_key='k', model='test-model',
        )
        self.assertEqual(summary, 'The CPU spike correlates with deploy run-987.')
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        self.assertTrue(url.endswith('/chat/completions'))
        headers = mock_post.call_args[1]['headers']
        self.assertEqual(headers['Authorization'], 'Bearer k')

    @patch('llm_summary.requests.post')
    def test_generate_tolerates_api_failure(self, mock_post):
        mock_post.side_effect = Exception('connection refused')
        summary = generate_llm_summary(
            SAMPLE_RESULTS, SAMPLE_ROOT_CAUSE,
            api_url='https://llm.example/v1',
        )
        self.assertIsNone(summary)


if __name__ == '__main__':
    unittest.main()
