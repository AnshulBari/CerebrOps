#!/usr/bin/env python3
"""
CerebrOps Main Monitoring Script
Orchestrates anomaly detection and alerting
"""

import time
import logging
import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional

from anomaly_detector import AnomalyDetector
from alerts import SlackAlerter
from logging_config import configure_logging
from metrics_store import MetricsStore

# Configure logging - resolve paths dynamically
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

configure_logging(level=logging.INFO, log_dir=log_dir, log_file='monitoring.log')

logger = logging.getLogger('cerebrops.monitor')


class CerebrOpsMonitor:
    def __init__(self, app_url: str = "http://localhost:5000",
                 slack_webhook: Optional[str] = None,
                 check_interval: int = 300,
                 store: Optional[MetricsStore] = None):
        """
        Initialize CerebrOps monitoring system

        Args:
            app_url: URL of the Flask application
            slack_webhook: Slack webhook URL for alerts
            check_interval: Monitoring interval in seconds
            store: MetricsStore for history; created from env if None
        """
        self.app_url = app_url
        self.check_interval = check_interval
        self.store = store or MetricsStore()

        self.anomaly_detector = AnomalyDetector(app_url=app_url, store=self.store)
        self.slack_alerter = SlackAlerter(slack_webhook)

        self.is_running = False
        self.last_training_time = None

        logger.info("CerebrOps Monitor initialized")

    def initialize(self) -> bool:
        """Initialize the monitoring system (tolerant of missing training data)."""
        try:
            logger.info("Initializing anomaly detection model...")

            # Prefer the persisted model so a restart does not force a retrain.
            if self.anomaly_detector.load_model():
                card = self.anomaly_detector.model_card or {}
                trained_at = card.get('trained_at')
                if trained_at:
                    try:
                        parsed = datetime.fromisoformat(trained_at)
                        # Cards store UTC-aware ISO; normalize to naive so the
                        # naive `datetime.now()` arithmetic in
                        # should_retrain_model() never mixes tz-aware/naive.
                        self.last_training_time = (
                            parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
                        )
                    except ValueError:
                        self.last_training_time = None
                logger.info(
                    "Loaded persisted anomaly model "
                    f"(version {self.anomaly_detector.current_version})"
                )
            elif self.anomaly_detector.train_model():
                self.last_training_time = datetime.now()
                logger.info("Anomaly detection model trained and persisted successfully")
            else:
                logger.warning(
                    "Anomaly model not trained yet (insufficient real history in the store). "
                    "Detection will report 'insufficient_data' until enough metrics are collected."
                )

            # Phase 5: fit the forecast-residual detector from real history.
            # It activates only once enough history exists (>= 7 days).
            self.anomaly_detector.fit_forecast()

            logger.info("Monitoring system initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize monitoring system: {e}")
            return False

    def should_retrain_model(self) -> bool:
        """
        Decide whether the model should be retrained.

        Retrains when: no model yet, max retrain interval elapsed (safety net),
        or the live metric distribution drifted from the training baseline
        (PSI above threshold). A minimum interval prevents thrashing.
        """
        detector = self.anomaly_detector

        if not self.last_training_time:
            return True

        time_since_training = datetime.now() - self.last_training_time
        if time_since_training < detector.min_retrain_interval:
            return False
        if time_since_training > detector.max_retrain_interval:
            logger.info("Max retrain interval reached; retraining.")
            return True

        # Drift check against the training baseline (PSI).
        recent = detector.fetch_metrics_data(limit=500)
        drift = detector.compute_drift(recent) if recent else {'needs_retrain': False}
        if drift.get('needs_retrain'):
            logger.info(
                f"Drift detected (max PSI {drift.get('max_psi', 0):.3f} "
                f"> threshold {drift.get('threshold', detector.drift_threshold)}); retraining."
            )
            return True
        return False

    def retrain_model(self) -> bool:
        """Retrain the anomaly detection model on real history and persist it."""
        try:
            logger.info("Retraining anomaly detection model...")

            if self.anomaly_detector.train_model():
                self.last_training_time = datetime.now()
                logger.info(
                    "Model retrained and persisted "
                    f"(version {self.anomaly_detector.current_version})"
                )
                return True
            else:
                logger.error("Model retraining failed")
                return False

        except Exception as e:
            logger.error(f"Model retraining failed: {e}")
            return False

    def check_application_health(self) -> Dict[str, Any]:
        """Check application health status"""
        try:
            import requests
            response = requests.get(f"{self.app_url}/health", timeout=10)
            response.raise_for_status()

            health_data = response.json()
            health_status = health_data.get('status', 'unknown')

            return {
                'status': 'healthy' if health_status == 'healthy' else 'unhealthy',
                'details': health_data,
                'response_time': response.elapsed.total_seconds()
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'details': {'error': str(e)},
                'response_time': None
            }

    def run_monitoring_cycle(self) -> Dict[str, Any]:
        """Run a single monitoring cycle"""
        cycle_results = {
            'timestamp': datetime.now().isoformat(),
            'health_check': None,
            'anomaly_detection': None,
            'alerts_sent': []
        }

        try:
            # 1. Check application health
            logger.info("Running health check...")
            health_result = self.check_application_health()
            cycle_results['health_check'] = health_result

            # Send health alert if needed
            if health_result['status'] == 'unhealthy':
                health_details = health_result.get('details', {})
                error_msg = health_details.get('error', 'Unknown health issue')

                if self.slack_alerter.send_health_alert('unhealthy', error_msg):
                    cycle_results['alerts_sent'].append('health_alert')
                    self._record_alert('critical', 'health',
                                       f"Application unhealthy: {error_msg}")

            # 2. Fetch current metrics window from the store
            logger.info("Fetching application metrics...")
            current_metrics = self.anomaly_detector.fetch_metrics_data()

            if not current_metrics:
                logger.warning("No metrics data available in the store yet")
                self.store.record_anomaly_run(status='no_data', results=cycle_results)
                return cycle_results

            # 3. Run anomaly detection
            logger.info("Running anomaly detection...")
            anomaly_results = self.anomaly_detector.detect_anomalies(current_metrics)

            # Phase 5: attach deploy-correlated root-cause analysis when an
            # anomaly is found (uses real pipeline webhook events + metric
            # shifts from the store), then an optional LLM summary.
            if anomaly_results.get('status') == 'anomaly':
                try:
                    from root_cause import analyze_root_cause
                    anomaly_results['root_cause'] = analyze_root_cause(self.store)
                except Exception as e:
                    logger.warning(f"Root-cause analysis failed: {e}")
                try:
                    from llm_summary import generate_llm_summary
                    summary = generate_llm_summary(
                        anomaly_results, anomaly_results.get('root_cause')
                    )
                    if summary:
                        anomaly_results['llm_summary'] = summary
                except Exception as e:
                    logger.warning(f"LLM summary failed: {e}")

            cycle_results['anomaly_detection'] = anomaly_results

            # Persist the anomaly run for the dashboard and later analysis
            try:
                self.store.record_anomaly_run(
                    status=anomaly_results.get('status', 'unknown'),
                    anomaly_count=anomaly_results.get('anomaly_count'),
                    total_data_points=anomaly_results.get('total_data_points'),
                    severity=anomaly_results.get('severity'),
                    results=anomaly_results,
                )
            except Exception as e:
                logger.error(f"Failed to record anomaly run: {e}")

            # 4. Send alerts if anomalies detected
            if anomaly_results.get('status') == 'anomaly':
                logger.warning(f"Anomalies detected: {anomaly_results}")

                if self.slack_alerter.send_anomaly_alert(anomaly_results):
                    cycle_results['alerts_sent'].append('anomaly_alert')
                    self._record_alert(
                        anomaly_results.get('severity', 'medium'),
                        'anomaly',
                        f"Detected {anomaly_results.get('anomaly_count')} anomalies "
                        f"({anomaly_results.get('anomaly_percentage')}% of points)",
                        anomaly_results,
                    )

            elif anomaly_results.get('status') == 'error':
                logger.error(f"Anomaly detection error: {anomaly_results}")

                if self.slack_alerter.send_slack_alert(
                    f"Anomaly detection failed: {anomaly_results.get('message', 'Unknown error')}",
                    'high'
                ):
                    cycle_results['alerts_sent'].append('error_alert')
                    self._record_alert('high', 'anomaly_error',
                                       anomaly_results.get('message', 'Unknown error'),
                                       anomaly_results)

            elif anomaly_results.get('status') == 'insufficient_data':
                logger.info(
                    f"Anomaly detection skipped: {anomaly_results.get('message', 'insufficient data')}"
                )

            else:
                logger.info("No anomalies detected - system operating normally")

            # 5. Check if model needs retraining
            if self.should_retrain_model():
                logger.info("Triggering model retraining...")
                self.retrain_model()

            return cycle_results

        except Exception as e:
            logger.error(f"Monitoring cycle failed: {e}")
            cycle_results['error'] = str(e)

            # Send error alert
            if self.slack_alerter.send_slack_alert(
                f"Monitoring cycle failed: {str(e)}",
                'critical'
            ):
                cycle_results['alerts_sent'].append('critical_error_alert')

            return cycle_results

    def start_monitoring(self) -> None:
        """Start continuous monitoring"""
        if not self.initialize():
            logger.error("Failed to initialize monitoring system")
            sys.exit(1)

        self.is_running = True
        logger.info(f"Starting continuous monitoring (interval: {self.check_interval}s)")

        # Send startup notification
        self.slack_alerter.send_slack_alert(
            "🧠 CerebrOps monitoring system started successfully",
            'low'
        )

        try:
            while self.is_running:
                cycle_start = datetime.now()

                # Run monitoring cycle
                results = self.run_monitoring_cycle()

                # Log cycle results
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                logger.info(f"Monitoring cycle completed in {cycle_duration:.2f}s")

                # Save results to file for analysis
                self._save_cycle_results(results)

                # Wait for next cycle
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Monitoring loop failed: {e}")
            self.slack_alerter.send_slack_alert(
                f"🚨 CerebrOps monitoring system crashed: {str(e)}",
                'critical'
            )
        finally:
            self.is_running = False
            self.slack_alerter.send_slack_alert(
                "⚠️ CerebrOps monitoring system stopped",
                'medium'
            )

    def stop_monitoring(self) -> None:
        """Stop monitoring"""
        logger.info("Stopping monitoring...")
        self.is_running = False

    def run_single_check(self) -> Dict[str, Any]:
        """Run a single monitoring check (for testing or cron jobs)"""
        if not self.initialize():
            return {'error': 'Failed to initialize monitoring system'}

        return self.run_monitoring_cycle()

    def _record_alert(self, severity: str, alert_type: str, message: str,
                      payload: Optional[Dict[str, Any]] = None) -> None:
        """Persist an alert to the metrics store."""
        try:
            self.store.record_alert(severity=severity, alert_type=alert_type,
                                    message=message, payload=payload)
        except Exception as e:
            logger.error(f"Failed to record alert: {e}")

    def _save_cycle_results(self, results: Dict[str, Any]) -> None:
        """Save monitoring cycle results to file"""
        try:
            results_file = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 'logs', 'monitoring_results.jsonl'
            )

            # Ensure directory exists
            os.makedirs(os.path.dirname(results_file), exist_ok=True)

            with open(results_file, 'a') as f:
                f.write(json.dumps(results) + '\n')

        except Exception as e:
            logger.error(f"Failed to save cycle results: {e}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='CerebrOps AI-Powered Monitoring System')
    parser.add_argument('--app-url', default=os.getenv('APP_URL', 'http://localhost:5000'),
                        help='URL of the application to monitor')
    parser.add_argument('--slack-webhook', default=os.getenv('SLACK_WEBHOOK_URL'),
                        help='Slack webhook URL for alerts')
    parser.add_argument('--interval', type=int, default=300,
                        help='Monitoring interval in seconds')
    parser.add_argument('--single-check', action='store_true',
                        help='Run a single check instead of continuous monitoring')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create monitor
    monitor = CerebrOpsMonitor(
        app_url=args.app_url,
        slack_webhook=args.slack_webhook,
        check_interval=args.interval
    )

    if args.single_check:
        # Run single check
        logger.info("Running single monitoring check...")
        results = monitor.run_single_check()
        print(json.dumps(results, indent=2))
    else:
        # Start continuous monitoring
        monitor.start_monitoring()


if __name__ == "__main__":
    main()
