"""
Test that monitoring/prometheus-rules.yml stays in sync with the metrics the
app actually exposes. The rules file is YAML; we assert structurally here
(alert names + metric references) rather than requiring a YAML parser.
"""

import os
import re
import unittest

RULES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'monitoring', 'prometheus-rules.yml',
)

KNOWN_METRICS = {
    'cerebrops_http_requests_total',
    'cerebrops_http_request_duration_seconds',
    'cerebrops_cpu_usage_percent',
    'cerebrops_memory_usage_percent',
    'cerebrops_disk_usage_percent',
    'cerebrops_metrics_rows_total',
}

REQUIRED_ALERTS = {
    'CerebrOpsSLOFastBurn',
    'CerebrOpsSLOSlowBurn',
    'CerebrOpsDown',
    'CerebrOpsHighErrorRate',
    'CerebrOpsHighLatencyP95',
    'CerebrOpsHighCPU',
    'CerebrOpsDiskPressure',
}


class TestSLORules(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(RULES_PATH, encoding='utf-8') as f:
            cls.text = f.read()

    def test_rules_file_exists(self):
        self.assertTrue(os.path.exists(RULES_PATH))

    def test_required_alerts_defined(self):
        for alert in REQUIRED_ALERTS:
            self.assertIn(f'- alert: {alert}', self.text, f'missing alert {alert}')

    def test_error_budget_recording_rule_defined(self):
        self.assertIn('cerebrops:slo:error_budget_remaining:30d', self.text)

    def test_all_referenced_metrics_exist(self):
        """Every cerebrops_* name in the rules must be a real metric (after
        stripping prometheus series suffixes)."""
        names = set(re.findall(r'\bcerebrops_[a-z0-9_]+', self.text))
        normalized = set()
        for n in names:
            base = n
            for suffix in ('_bucket', '_sum', '_count'):
                if base.endswith(suffix):
                    base = base[: -len(suffix)]
            normalized.add(base)
        unknown = normalized - KNOWN_METRICS
        self.assertEqual(unknown, set(), f'unknown metrics referenced: {unknown}')

    def test_alerts_have_severity_labels(self):
        """Every alert block must carry a severity label."""
        # Split on alert declarations and check each chunk contains a severity.
        chunks = re.split(r'- alert: [A-Za-z0-9]+', self.text)[1:]
        self.assertGreaterEqual(len(chunks), len(REQUIRED_ALERTS))
        for chunk in chunks:
            self.assertIn('severity:', chunk)


if __name__ == '__main__':
    unittest.main()
