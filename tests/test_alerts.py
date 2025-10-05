"""
Test suite for CerebrOps Slack alerting module
"""

import unittest
from unittest.mock import Mock, patch
from alerts import SlackAlerter


class TestSlackAlerter(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        self.alerter = SlackAlerter("https://hooks.slack.com/services/TEST/WEBHOOK/URL")

    def test_alerter_initialization(self):
        """Test alerter initialization"""
        self.assertEqual(self.alerter.webhook_url, "https://hooks.slack.com/services/TEST/WEBHOOK/URL")

    def test_alerter_initialization_no_webhook(self):
        """Test alerter initialization without webhook URL"""
        alerter = SlackAlerter()
        self.assertIsNone(alerter.webhook_url)

    def test_create_slack_payload(self):
        """Test Slack payload creation"""
        payload = self.alerter._create_slack_payload("Test message", "medium")

        self.assertIn("username", payload)
        self.assertIn("attachments", payload)
        self.assertIsInstance(payload["attachments"], list)
        self.assertGreater(len(payload["attachments"]), 0)

        attachment = payload["attachments"][0]
        self.assertIn("color", attachment)
        self.assertIn("title", attachment)
        self.assertIn("text", attachment)

    def test_create_slack_payload_with_data(self):
        """Test Slack payload creation with anomaly data"""
        anomaly_data = {
            'anomaly_count': 5,
            'total_data_points': 100,
            'anomaly_percentage': 5.0,
            'recommendations': ['Check CPU usage', 'Monitor memory']
        }

        payload = self.alerter._create_slack_payload("Test alert", "high", anomaly_data)

        attachment = payload["attachments"][0]
        self.assertIn("fields", attachment)
        self.assertIsInstance(attachment["fields"], list)
        self.assertGreater(len(attachment["fields"]), 0)

    @patch('requests.post')
    def test_send_slack_alert_success(self, mock_post):
        """Test successful Slack alert sending"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = self.alerter.send_slack_alert("Test alert", "low")

        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_send_slack_alert_failure(self, mock_post):
        """Test Slack alert sending failure"""
        mock_post.side_effect = Exception("Connection error")

        result = self.alerter.send_slack_alert("Test alert", "low")

        self.assertFalse(result)

    def test_send_slack_alert_no_webhook(self):
        """Test alert sending without webhook URL"""
        alerter = SlackAlerter()
        result = alerter.send_slack_alert("Test alert", "low")

        # Should return True but only log locally
        self.assertTrue(result)

    def test_send_anomaly_alert_normal(self):
        """Test anomaly alert with normal status"""
        anomaly_results = {'status': 'normal'}
        result = self.alerter.send_anomaly_alert(anomaly_results)

        self.assertTrue(result)

    def test_send_anomaly_alert_error(self):
        """Test anomaly alert with error status"""
        anomaly_results = {
            'status': 'error',
            'message': 'Test error'
        }

        with patch.object(self.alerter, 'send_slack_alert', return_value=True) as mock_send:
            result = self.alerter.send_anomaly_alert(anomaly_results)

            self.assertTrue(result)
            mock_send.assert_called_once()

    def test_send_anomaly_alert_anomaly(self):
        """Test anomaly alert with anomaly status"""
        anomaly_results = {
            'status': 'anomaly',
            'severity': 'high',
            'anomaly_count': 3,
            'anomaly_percentage': 15.0
        }

        with patch.object(self.alerter, 'send_slack_alert', return_value=True) as mock_send:
            result = self.alerter.send_anomaly_alert(anomaly_results)

            self.assertTrue(result)
            mock_send.assert_called_once()

    def test_send_pipeline_alert_success(self):
        """Test pipeline alert with success status"""
        pipeline_data = {
            'pipeline_id': 'test-123',
            'branch': 'main',
            'duration': 180
        }

        with patch.object(self.alerter, 'send_slack_alert', return_value=True) as mock_send:
            result = self.alerter.send_pipeline_alert('success', pipeline_data)

            self.assertTrue(result)
            mock_send.assert_called_once()

    def test_send_pipeline_alert_failed(self):
        """Test pipeline alert with failed status"""
        with patch.object(self.alerter, 'send_slack_alert', return_value=True) as mock_send:
            result = self.alerter.send_pipeline_alert('failed')

            self.assertTrue(result)
            mock_send.assert_called_once()

    def test_send_health_alert_healthy(self):
        """Test health alert with healthy status"""
        result = self.alerter.send_health_alert('healthy')

        # No alert should be sent for healthy status
        self.assertTrue(result)

    def test_send_health_alert_unhealthy(self):
        """Test health alert with unhealthy status"""
        with patch.object(self.alerter, 'send_slack_alert', return_value=True) as mock_send:
            result = self.alerter.send_health_alert('unhealthy', 'Database connection failed')

            self.assertTrue(result)
            mock_send.assert_called_once()


if __name__ == '__main__':
    unittest.main()
