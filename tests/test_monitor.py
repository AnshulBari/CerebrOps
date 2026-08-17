"""
Regression tests for the CerebrOps monitor (Phase 5 fixes).
"""

import unittest
from datetime import datetime, timedelta, timezone

from monitor import CerebrOpsMonitor


class TestMonitorRetrain(unittest.TestCase):

    def setUp(self):
        # Uses the session-isolated temp DB/model dir from conftest.
        self.mon = CerebrOpsMonitor()

    def test_loaded_card_training_time_is_naive(self):
        """A persisted-card timestamp (aware ISO) must not break retrain math.

        Regression: `datetime.now() - aware_dt` raised TypeError, which made
        every monitoring cycle after a model reload fail.
        """
        trained_at = datetime.now(timezone.utc).isoformat()
        parsed = datetime.fromisoformat(trained_at)
        normalized = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        self.mon.last_training_time = normalized
        # Just-trained model: below min interval, must return False (no raise).
        self.assertFalse(self.mon.should_retrain_model())

    def test_should_retrain_after_max_interval(self):
        """Past the max interval the safety-net retrain must trigger."""
        self.mon.last_training_time = datetime.now() - timedelta(days=8)
        self.assertTrue(self.mon.should_retrain_model())


if __name__ == '__main__':
    unittest.main()
