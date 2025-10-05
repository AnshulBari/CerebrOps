"""
CerebrOps Slack Alerting Module
Sends alerts to Slack when anomalies are detected
"""

import json
import requests
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('alerts')


class SlackAlerter:
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack alerter

        Args:
            webhook_url: Slack webhook URL for sending messages
        """
        self.webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')

        if not self.webhook_url:
            logger.warning("No Slack webhook URL provided. Alerts will be logged only.")

    def send_slack_alert(self, message: str, severity: str = "medium",
                         anomaly_data: Dict[str, Any] = None) -> bool:
        """
        Send alert to Slack

        Args:
            message: Alert message
            severity: Severity level (low, medium, high, critical)
            anomaly_data: Additional data about the anomaly

        Returns:
            bool: True if alert sent successfully
        """
        try:
            # Create Slack message payload
            payload = self._create_slack_payload(message, severity, anomaly_data)

            # Log the alert locally
            logger.info(f"ALERT [{severity.upper()}]: {message}")

            # Send to Slack if webhook URL is available
            if self.webhook_url:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10
                )
                response.raise_for_status()
                logger.info("Alert sent to Slack successfully")
                return True
            else:
                logger.info("Alert logged locally (no Slack webhook configured)")
                return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return False

    def _create_slack_payload(self, message: str, severity: str,
                              anomaly_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create Slack message payload with rich formatting"""

        # Choose color based on severity
        color_map = {
            'low': '#36a64f',      # Green
            'medium': '#ff9500',   # Orange
            'high': '#ff6b35',     # Red-Orange
            'critical': '#ff0000'   # Red
        }

        color = color_map.get(severity.lower(), '#36a64f')

        # Choose emoji based on severity
        emoji_map = {
            'low': '🟡',
            'medium': '🟠',
            'high': '🔴',
            'critical': '🚨'
        }

        emoji = emoji_map.get(severity.lower(), '⚠️')

        # Base payload
        payload = {
            "username": "CerebrOps AI Monitor",
            "icon_emoji": ":brain:",
            "attachments": [
                {
                    "color": color,
                    "title": f"{emoji} CerebrOps Alert - {severity.upper()}",
                    "text": message,
                    "timestamp": int(datetime.now().timestamp()),
                    "footer": "CerebrOps AI-Powered Monitoring",
                    "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png"
                }
            ]
        }

        # Add anomaly data if available
        if anomaly_data:
            fields = []

            if 'anomaly_count' in anomaly_data:
                fields.append({
                    "title": "Anomalies Detected",
                    "value": f"{anomaly_data['anomaly_count']} out of {anomaly_data.get('total_data_points', 'N/A')} data points",
                    "short": True
                })

            if 'anomaly_percentage' in anomaly_data:
                fields.append({
                    "title": "Anomaly Rate",
                    "value": f"{anomaly_data['anomaly_percentage']}%",
                    "short": True
                })

            if 'recommendations' in anomaly_data and anomaly_data['recommendations']:
                recommendations_text = "\n".join([f"• {rec}" for rec in anomaly_data['recommendations']])
                fields.append({
                    "title": "Recommendations",
                    "value": recommendations_text,
                    "short": False
                })

            # Add anomalous metrics if available
            if 'anomalous_data' in anomaly_data and anomaly_data['anomalous_data']:
                anomalous_metrics = anomaly_data['anomalous_data'][0]  # Show first anomalous point
                metrics_text = ""
                for key, value in anomalous_metrics.items():
                    if key != 'timestamp' and isinstance(value, (int, float)):
                        metrics_text += f"• {key.replace('_', ' ').title()}: {value:.2f}\n"

                if metrics_text:
                    fields.append({
                        "title": "Anomalous Metrics",
                        "value": metrics_text,
                        "short": True
                    })

            payload["attachments"][0]["fields"] = fields

        return payload

    def send_anomaly_alert(self, anomaly_results: Dict[str, Any]) -> bool:
        """
        Send specific anomaly alert based on detection results

        Args:
            anomaly_results: Results from anomaly detection

        Returns:
            bool: True if alert sent successfully
        """
        if anomaly_results.get('status') == 'normal':
            return True  # No alert needed for normal status

        if anomaly_results.get('status') == 'error':
            message = f"⚠️ Anomaly Detection Error: {anomaly_results.get('message', 'Unknown error')}"
            return self.send_slack_alert(message, 'medium')

        if anomaly_results.get('status') == 'anomaly':
            severity = anomaly_results.get('severity', 'medium')
            anomaly_count = anomaly_results.get('anomaly_count', 0)
            anomaly_percentage = anomaly_results.get('anomaly_percentage', 0)

            message = f"🧠 CerebrOps detected {anomaly_count} anomalies ({anomaly_percentage}% of data points)"

            return self.send_slack_alert(message, severity, anomaly_results)

        return True

    def send_pipeline_alert(self, pipeline_status: str, pipeline_data: Dict[str, Any] = None) -> bool:
        """
        Send CI/CD pipeline alert

        Args:
            pipeline_status: Status of the pipeline (success, failed, etc.)
            pipeline_data: Additional pipeline information

        Returns:
            bool: True if alert sent successfully
        """
        status_emojis = {
            'success': '✅',
            'failed': '❌',
            'running': '🔄',
            'pending': '⏳'
        }

        emoji = status_emojis.get(pipeline_status.lower(), '⚠️')

        if pipeline_status.lower() == 'failed':
            severity = 'high'
            message = f"{emoji} CI/CD Pipeline Failed"
        elif pipeline_status.lower() == 'success':
            severity = 'low'
            message = f"{emoji} CI/CD Pipeline Completed Successfully"
        else:
            severity = 'medium'
            message = f"{emoji} CI/CD Pipeline Status: {pipeline_status}"

        # Add pipeline details if available
        if pipeline_data:
            details = []
            if 'pipeline_id' in pipeline_data:
                details.append(f"Pipeline ID: {pipeline_data['pipeline_id']}")
            if 'branch' in pipeline_data:
                details.append(f"Branch: {pipeline_data['branch']}")
            if 'duration' in pipeline_data:
                details.append(f"Duration: {pipeline_data['duration']}s")

            if details:
                message += f"\n{chr(10).join(details)}"

        return self.send_slack_alert(message, severity, pipeline_data)

    def send_health_alert(self, health_status: str, details: str = "") -> bool:
        """
        Send application health alert

        Args:
            health_status: Health status (healthy, unhealthy, degraded)
            details: Additional details about the health issue

        Returns:
            bool: True if alert sent successfully
        """
        if health_status.lower() == 'healthy':
            return True  # No alert needed for healthy status

        severity_map = {
            'unhealthy': 'critical',
            'degraded': 'medium',
            'warning': 'low'
        }

        severity = severity_map.get(health_status.lower(), 'medium')

        emoji_map = {
            'unhealthy': '🚨',
            'degraded': '⚠️',
            'warning': '🟡'
        }

        emoji = emoji_map.get(health_status.lower(), '⚠️')

        message = f"{emoji} Application Health Alert: {health_status.upper()}"
        if details:
            message += f"\nDetails: {details}"

        return self.send_slack_alert(message, severity)


def send_slack_alert(message: str, webhook_url: str = None, severity: str = "medium") -> bool:
    """
    Simple function to send a Slack alert (for backward compatibility)

    Args:
        message: Alert message
        webhook_url: Slack webhook URL
        severity: Severity level

    Returns:
        bool: True if successful
    """
    alerter = SlackAlerter(webhook_url)
    return alerter.send_slack_alert(message, severity)


def main():
    """Test the Slack alerting functionality"""
    alerter = SlackAlerter()

    # Test basic alert
    alerter.send_slack_alert("Test alert from CerebrOps", "low")

    # Test anomaly alert
    test_anomaly_data = {
        'status': 'anomaly',
        'anomaly_count': 3,
        'total_data_points': 20,
        'anomaly_percentage': 15.0,
        'severity': 'high',
        'recommendations': [
            'High CPU usage detected. Consider scaling up.',
            'Check for memory leaks.'
        ],
        'anomalous_data': [{
            'cpu_usage': 95.2,
            'memory_usage': 88.5,
            'error_rate': 12.3
        }]
    }

    alerter.send_anomaly_alert(test_anomaly_data)

    # Test pipeline alert
    test_pipeline_data = {
        'pipeline_id': 'pipeline-1234',
        'branch': 'main',
        'duration': 180
    }

    alerter.send_pipeline_alert('failed', test_pipeline_data)


if __name__ == "__main__":
    main()
