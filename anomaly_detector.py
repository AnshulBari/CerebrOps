"""
CerebrOps Anomaly Detection Module
Uses machine learning to detect anomalies in system metrics and logs.

Phase 2 capabilities:
- Windowed feature engineering: for every metric, rolling mean / std / slope /
  min / max over 15m, 1h and 24h windows (time-based rolling).
- Persistence: trained models are saved (joblib) with versioned model cards
  and reloaded across restarts.
- Drift-based retraining: the model is retrained when the live metric
  distribution drifts from the training baseline (Population Stability Index)
  rather than on a fixed schedule.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from metrics_store import MetricsStore
from model_repository import ModelRepository
from forecast_detector import ForecastResidualDetector

logger = logging.getLogger('cerebrops.anomaly_detector')

# Windows (minutes) used for rolling feature extraction.
DEFAULT_WINDOWS_MIN = (15, 60, 1440)
# Population Stability Index thresholds (industry convention):
#   < 0.1 no shift, 0.1-0.25 moderate, > 0.25 significant shift.
DEFAULT_DRIFT_THRESHOLD = 0.25
# Safety nets around drift-based retraining.
DEFAULT_MIN_RETRAIN_INTERVAL = timedelta(hours=1)
DEFAULT_MAX_RETRAIN_INTERVAL = timedelta(days=7)

_WINDOW_STATS = ('mean', 'std', 'slope', 'min', 'max')


class AnomalyDetector:
    def __init__(self, contamination: float = 0.1,
                 app_url: str = "http://localhost:5000",
                 store: Optional[MetricsStore] = None,
                 repository: Optional[ModelRepository] = None,
                 window_size: int = 200,
                 min_samples: int = 10,
                 windows_min: Tuple[int, ...] = DEFAULT_WINDOWS_MIN,
                 drift_threshold: Optional[float] = None,
                 min_retrain_interval: Optional[timedelta] = None,
                 max_retrain_interval: Optional[timedelta] = None):
        """
        Initialize the anomaly detector.

        Args:
            contamination: Expected proportion of anomalies in the data.
            app_url: URL of the Flask application (used for log fetching).
            store: Metrics history store; created from env if None.
            repository: Versioned model persistence; created from env if None.
            window_size: Number of recent metric points fetched per run.
            min_samples: Minimum points required before detection runs.
            windows_min: Rolling windows (minutes) for feature engineering.
            drift_threshold: PSI threshold above which retraining triggers.
            min_retrain_interval: Minimum time between retrains (anti-thrash).
            max_retrain_interval: Maximum time between retrains (safety net).
        """
        self.contamination = contamination
        self.app_url = app_url
        self.store = store or MetricsStore()
        self.repository = repository or ModelRepository()
        self.window_size = window_size
        self.min_samples = min_samples
        self.windows_min = windows_min
        self.drift_threshold = float(
            os.getenv('ANOMALY_DRIFT_THRESHOLD', drift_threshold if drift_threshold is not None else DEFAULT_DRIFT_THRESHOLD)
        )
        self.min_retrain_interval = min_retrain_interval or _timedelta_from_env(
            'RETRAIN_MIN_INTERVAL', DEFAULT_MIN_RETRAIN_INTERVAL
        )
        self.max_retrain_interval = max_retrain_interval or _timedelta_from_env(
            'RETRAIN_MAX_INTERVAL', DEFAULT_MAX_RETRAIN_INTERVAL
        )

        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.current_version: Optional[int] = None
        self.model_card: Optional[Dict[str, Any]] = None
        self.feature_names: List[str] = []
        # Phase 5: forecast-residual detector (AI v2). Fitted from real store
        # history; only used once enough history exists.
        self.forecast = ForecastResidualDetector()
        self.feature_columns = [
            'cpu_usage', 'memory_usage', 'disk_usage',
            'error_rate', 'request_count', 'response_time'
        ]

    # ------------------------------------------------------------------
    # Data fetching (real store history only - no synthetic fallback)
    # ------------------------------------------------------------------

    def fetch_metrics_data(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch a window of recent metrics from the metrics store."""
        try:
            rows = self.store.get_metrics(limit=limit or self.window_size)
            if not rows:
                logger.warning("No metrics history available in the store yet")
            return rows
        except Exception as e:
            logger.error(f"Failed to fetch metrics from store: {e}")
            return []

    def fetch_training_data(self, limit: int = 5000) -> List[Dict]:
        """Fetch historical metrics from the store for model training."""
        try:
            return self.store.get_metrics(limit=limit)
        except Exception as e:
            logger.error(f"Failed to fetch training data from store: {e}")
            return []

    def fetch_logs_data(self) -> List[Dict]:
        """Fetch recent logs from the Flask application."""
        try:
            import requests
            response = requests.get(f"{self.app_url}/logs", timeout=10)
            response.raise_for_status()
            return response.json().get('logs', [])
        except Exception as e:
            logger.error(f"Failed to fetch logs: {e}")
            return []

    def _generate_sample_data(self) -> List[Dict]:
        """Generate sample data for training and testing (explicit use only)."""
        np.random.seed(42)
        data = []

        # Generate normal data
        for i in range(100):
            data.append({
                'timestamp': (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(),
                'cpu_usage': np.random.normal(50, 10),
                'memory_usage': np.random.normal(60, 8),
                'disk_usage': np.random.normal(70, 5),
                'error_rate': np.random.normal(2, 1),
                'request_count': np.random.normal(100, 20),
                'response_time': np.random.normal(0.5, 0.2)
            })

        # Generate some anomalous data
        for i in range(10):
            data.append({
                'timestamp': (datetime.now(timezone.utc) - timedelta(hours=i * 5)).isoformat(),
                'cpu_usage': np.random.normal(90, 5),  # High CPU
                'memory_usage': np.random.normal(85, 5),  # High memory
                'disk_usage': np.random.normal(95, 2),  # High disk
                'error_rate': np.random.normal(15, 3),  # High error rate
                'request_count': np.random.normal(200, 30),  # High requests
                'response_time': np.random.normal(2.0, 0.5)  # Slow response
            })

        return data

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    def prepare_features(self, data: List[Dict]) -> np.ndarray:
        """Basic raw + time features (kept for compatibility and fallback)."""
        if PANDAS_AVAILABLE:
            df = pd.DataFrame(data)

            for col in self.feature_columns:
                if col not in df.columns:
                    df[col] = 0

            df[self.feature_columns] = df[self.feature_columns].fillna(0)

            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
                df['hour'] = df['timestamp'].dt.hour
                df['day_of_week'] = df['timestamp'].dt.dayofweek
                feature_cols = self.feature_columns + ['hour', 'day_of_week']
            else:
                feature_cols = self.feature_columns

            return df[feature_cols].fillna(0).values

        # Numpy fallback (no pandas): raw features + simple time features.
        feature_matrix = []
        for item in data:
            row = []
            for col in self.feature_columns:
                value = item.get(col, 0)
                if value is None or (isinstance(value, str) and not value.replace('.', '').isdigit()):
                    value = 0
                row.append(float(value))
            if 'timestamp' in item:
                try:
                    dt = datetime.fromisoformat(str(item['timestamp']).replace('Z', '+00:00'))
                    row.append(dt.hour)
                    row.append(dt.weekday())
                except (ValueError, AttributeError, TypeError):
                    row.extend([12, 1])
            feature_matrix.append(row)
        return np.array(feature_matrix)

    def _build_features(self, data: List[Dict]) -> Tuple[np.ndarray, List[str], List[int]]:
        """
        Build the feature matrix for `data`.

        Uses rolling-window features when pandas is available (the standard
        path); falls back to raw + time features otherwise.

        Returns (feature_matrix, feature_names, kept_indices) where
        kept_indices maps each feature row back to its position in `data`.
        """
        if PANDAS_AVAILABLE:
            return self._build_windowed_features(data)

        matrix = self.prepare_features(data)
        has_time = any('timestamp' in d or 'ts' in d for d in data)
        names = self.feature_columns + (['hour', 'day_of_week'] if has_time else [])
        return matrix, names, list(range(len(data)))

    def _build_windowed_features(self, data: List[Dict]) -> Tuple[np.ndarray, List[str], List[int]]:
        """
        Rolling-window features over 15m/1h/24h for every metric:
        mean, std, least-squares slope, min, max - plus the raw last value,
        hour of day and day of week.
        """
        if not data:
            return np.empty((0, 0)), [], []

        df = pd.DataFrame(data)

        for col in self.feature_columns:
            if col not in df.columns:
                df[col] = np.nan

        ts_col = 'timestamp' if 'timestamp' in df.columns else ('ts' if 'ts' in df.columns else None)
        if ts_col:
            df['_ts'] = pd.to_datetime(df[ts_col], errors='coerce', utc=True)
        else:
            df['_ts'] = pd.Timestamp.now(tz=timezone.utc)

        kept_indices = df.index[df['_ts'].notna()].tolist()
        df = df.dropna(subset=['_ts']).sort_values('_ts').set_index('_ts')
        if df.empty:
            return np.empty((0, 0)), [], []

        df['hour'] = df.index.hour
        df['day_of_week'] = df.index.dayofweek

        epoch_s = df.index.astype('int64') // 10 ** 9
        t_hours = pd.Series((epoch_s - epoch_s[0]) / 3600.0, index=df.index, dtype=float)

        feature_cols: List[str] = []
        for m in self.feature_columns:
            s = pd.to_numeric(df[m], errors='coerce').fillna(0.0)

            feature_cols.append(f'{m}_last')
            df[f'{m}_last'] = s

            for w in self.windows_min:
                window = f'{w}min'
                mean = s.rolling(window, min_periods=1).mean()
                std = s.rolling(window, min_periods=2).std().fillna(0.0)
                mn = s.rolling(window, min_periods=2).min()
                mx = s.rolling(window, min_periods=2).max()

                # Least-squares slope of the metric over the window, computed
                # efficiently from rolling sums (slope in units per hour).
                cnt = s.rolling(window, min_periods=2).count()
                sum_x = s.rolling(window, min_periods=2).sum()
                sum_t = t_hours.rolling(window, min_periods=2).sum()
                sum_xt = (s * t_hours).rolling(window, min_periods=2).sum()
                sum_t2 = (t_hours * t_hours).rolling(window, min_periods=2).sum()
                denom = cnt * sum_t2 - sum_t * sum_t
                slope = ((cnt * sum_xt - sum_x * sum_t) / denom.replace(0.0, np.nan)).fillna(0.0)

                for name, series in (('mean', mean), ('std', std),
                                     ('slope', slope), ('min', mn), ('max', mx)):
                    col = f'{m}_{name}_{w}'
                    df[col] = series.fillna(0.0)
                    feature_cols.append(col)

        feature_cols += ['hour', 'day_of_week']
        matrix = df[feature_cols].fillna(0.0).values
        self.feature_names = feature_cols
        return matrix, feature_cols, kept_indices

    # ------------------------------------------------------------------
    # Training & persistence
    # ------------------------------------------------------------------

    def train_model(self, training_data: Optional[List[Dict]] = None,
                    save: bool = True) -> bool:
        """
        Train the anomaly detection model on real history.

        If `training_data` is None, history is pulled from the metrics store.
        On success the model is persisted (versioned) unless save=False.
        """
        try:
            if training_data is None:
                training_data = self.fetch_training_data()
                if not training_data:
                    logger.error(
                        "No training data available in the metrics store; "
                        "refusing to train on synthetic data."
                    )
                    return False

            if len(training_data) < self.min_samples:
                logger.error(
                    f"Not enough training data ({len(training_data)} points; "
                    f"need at least {self.min_samples})."
                )
                return False

            logger.info(f"Training model with {len(training_data)} data points")

            features, feature_names, _ = self._build_features(training_data)
            if features.size == 0:
                logger.error("No valid features found in training data")
                return False

            start = datetime.now()
            self.feature_names = feature_names
            features_scaled = self.scaler.fit_transform(features)
            self.model.fit(features_scaled)
            self.is_trained = True

            self.model_card = self._build_model_card(training_data, feature_names, features)
            if save:
                self._save_model()

            logger.info(
                f"Model training completed in {(datetime.now() - start).total_seconds():.2f}s"
            )
            return True

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return False

    def _build_model_card(self, training_data: List[Dict],
                          feature_names: List[str],
                          features: np.ndarray) -> Dict[str, Any]:
        """Metadata + drift baseline for the trained model."""
        values_by_metric: Dict[str, List[float]] = {m: [] for m in self.feature_columns}
        for row in training_data:
            for m in self.feature_columns:
                value = row.get(m)
                if value is None:
                    continue
                try:
                    fv = float(value)
                except (TypeError, ValueError):
                    continue
                if np.isfinite(fv):
                    values_by_metric[m].append(fv)

        baseline = {}
        for m, values in values_by_metric.items():
            info = self._baseline_for(np.asarray(values, dtype=float))
            if info:
                baseline[m] = info

        # IsolationForest's own inlier/outlier split on training data.
        try:
            preds = self.model.predict(self.scaler.transform(features))
            training_anomaly_rate = round(float(np.mean(preds == -1)) * 100, 2)
        except Exception:
            training_anomaly_rate = None

        recent = self.store.get_metrics(limit=1)
        return {
            'version': self.current_version,
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'n_samples': len(training_data),
            'feature_count': int(features.shape[1]),
            'feature_names': feature_names,
            'feature_columns': list(self.feature_columns),
            'windows_min': list(self.windows_min),
            'contamination': self.contamination,
            'min_samples': self.min_samples,
            'training_anomaly_rate': training_anomaly_rate,
            'baseline': baseline,
            'store_fingerprint': {
                'rows': self.store.count_metrics(),
                'last_ts': recent[0].get('timestamp') or recent[0].get('ts') if recent else None,
            },
        }

    def _save_model(self) -> int:
        """Persist the current model as the next version and point at it."""
        if self.model_card is None:
            raise RuntimeError("Cannot save model without a model card")
        version = self.repository.next_version()
        self.current_version = version
        self.model_card['version'] = version
        self.repository.save(version, self.model, self.scaler, self.model_card)
        self.repository.set_current(version)
        return version

    def load_model(self) -> bool:
        """Load the current persisted model (if any)."""
        version = self.repository.current_version()
        if version is None:
            logger.info("No persisted model found")
            return False
        payload = self.repository.load(version)
        if payload is None:
            logger.warning(f"Persisted model v{version} is incomplete; ignoring")
            return False
        self.model = payload['model']
        self.scaler = payload['scaler']
        self.model_card = payload['card']
        self.current_version = version
        self.feature_names = list(self.model_card.get('feature_names', []))
        self.is_trained = True
        logger.info(f"Loaded persisted model v{version}")
        return True

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def fit_forecast(self, training_data: Optional[List[Dict]] = None) -> bool:
        """
        Fit the forecast-residual detector on real store history.

        Returns True when enough real history exists; the detector then runs
        in front of the IsolationForest path. Otherwise False and the forest
        model remains the active method.
        """
        data = training_data if training_data is not None else self.fetch_training_data(limit=10000)
        fitted = self.forecast.fit(data)
        if fitted:
            logger.info(
                "Forecast-residual detector ready "
                f"({self.forecast.fit_meta.get('n_samples')} points, "
                f"{self.forecast.fit_meta.get('history_days')} days)"
            )
        else:
            logger.info(
                "Forecast-residual detector not fitted yet "
                "(needs >= %s days of real history); IsolationForest remains active",
                self.forecast.min_history_days,
            )
        return fitted

    def detect_anomalies(self, data: List[Dict],
                         method: str = 'auto') -> Dict[str, Any]:
        """
        Detect anomalies in the provided data window.

        `method`:
          - 'auto' (default): use the forecast-residual detector when fitted
            (sufficient real history), else the IsolationForest model.
          - 'forecast': force the forecast-residual path.
          - 'isolation-forest': force the forest path.

        Reports the anomaly status, count, percentage, severity, the anomalous
        points, recommendations, per-metric contributions, and the model
        version that produced the result.
        """
        if method == 'forecast':
            return self.forecast.detect(data)

        if method == 'auto' and self.forecast.is_fitted:
            result = self.forecast.detect(data)
            if result.get('status') != 'insufficient_data':
                return result
            logger.info(
                "Forecast detector has insufficient data in window; "
                "falling back to IsolationForest"
            )

        if not data:
            logger.warning("No data provided for anomaly detection")
            return {'status': 'no_data', 'message': 'No data to analyze'}

        if len(data) < self.min_samples:
            logger.warning(
                f"Only {len(data)} data points available; need at least {self.min_samples} "
                "to run anomaly detection."
            )
            return {
                'status': 'insufficient_data',
                'message': f"Only {len(data)} data points available; need at least {self.min_samples}.",
            }

        if not self.is_trained:
            logger.info("Model not loaded; attempting to load persisted model")
            if not self.load_model():
                logger.warning("No persisted model; attempting to train on real store history")
                if not self.train_model():
                    return {
                        'status': 'insufficient_data',
                        'message': 'Model not trained: not enough real metrics history in the store yet.',
                    }

        try:
            features, feature_names, kept_indices = self._build_features(data)
            if features.size == 0:
                return {'status': 'error', 'message': 'No valid features found'}

            features_scaled = self.scaler.transform(features)
            predictions = self.model.predict(features_scaled)
            anomaly_scores = self.model.decision_function(features_scaled)

            anomaly_count = int(np.sum(predictions == -1))
            total_count = len(predictions)
            anomaly_percentage = (anomaly_count / total_count) * 100

            anomalous_positions = np.where(predictions == -1)[0]
            anomalous_kept = [kept_indices[int(i)] for i in anomalous_positions]
            anomalous_data = [data[i] for i in anomalous_kept]

            result = {
                'status': 'anomaly' if anomaly_count > 0 else 'normal',
                'method': 'isolation-forest',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'window_size': len(data),
                'total_data_points': total_count,
                'anomaly_count': anomaly_count,
                'anomaly_percentage': round(anomaly_percentage, 2),
                'anomalous_data': anomalous_data,
                'severity': self._calculate_severity(anomaly_percentage, anomaly_scores),
                'recommendations': self._get_recommendations(features, predictions, data),
                'top_metric_contributions': self._compute_metric_contributions(
                    features, feature_names, anomalous_positions
                ),
                'model_version': self.current_version,
            }

            logger.info(
                f"Anomaly detection completed (model v{self.current_version}): "
                f"{result['status']} - {anomaly_count}/{total_count} points"
            )
            return result

        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def _calculate_severity(self, anomaly_percentage: float, scores: np.ndarray) -> str:
        """Calculate severity level based on anomaly percentage and scores."""
        min_score = np.min(scores) if scores.size else 0.0

        if anomaly_percentage > 20 or min_score < -0.5:
            return 'critical'
        elif anomaly_percentage > 10 or min_score < -0.3:
            return 'high'
        elif anomaly_percentage > 5 or min_score < -0.1:
            return 'medium'
        else:
            return 'low'

    def _get_recommendations(self, features: np.ndarray, predictions: np.ndarray,
                             data: List[Dict]) -> List[str]:
        """Get recommendations based on detected anomalies."""
        recommendations = []
        anomaly_positions = np.where(predictions == -1)[0]

        if anomaly_positions.size:
            anomalous = [data[int(i)] for i in anomaly_positions if int(i) < len(data)]

            if PANDAS_AVAILABLE:
                df = pd.DataFrame(anomalous)
                cpu = df['cpu_usage'].mean() if 'cpu_usage' in df.columns else 0
                mem = df['memory_usage'].mean() if 'memory_usage' in df.columns else 0
                err = df['error_rate'].mean() if 'error_rate' in df.columns else 0
                resp = df['response_time'].mean() if 'response_time' in df.columns else 0
            else:
                cpu = np.mean([r.get('cpu_usage', 0) for r in anomalous]) or 0
                mem = np.mean([r.get('memory_usage', 0) for r in anomalous]) or 0
                err = np.mean([r.get('error_rate', 0) for r in anomalous]) or 0
                resp = np.mean([r.get('response_time', 0) for r in anomalous]) or 0

            if cpu > 80:
                recommendations.append("High CPU usage detected. Consider scaling up or optimizing processes.")
            if mem > 80:
                recommendations.append("High memory usage detected. Check for memory leaks or increase memory allocation.")
            if err > 10:
                recommendations.append("High error rate detected. Review application logs and fix critical issues.")
            if resp > 2.0:
                recommendations.append("Slow response times detected. Optimize database queries and API calls.")

        if not recommendations:
            recommendations.append("System appears to be operating normally.")

        return recommendations

    def _compute_metric_contributions(self, features: np.ndarray, feature_names: List[str],
                                      anomalous_positions: np.ndarray) -> Dict[str, float]:
        """
        For each flagged point, how far each metric deviates from its 1h
        window mean (in window std units); averaged across the flagged points.
        """
        if anomalous_positions.size == 0:
            return {}

        name_to_idx = {name: i for i, name in enumerate(feature_names)}
        contribs: Dict[str, float] = {}
        for m in self.feature_columns:
            last_i = name_to_idx.get(f'{m}_last')
            mean_i = name_to_idx.get(f'{m}_mean_60')
            std_i = name_to_idx.get(f'{m}_std_60')
            if last_i is None or mean_i is None or std_i is None:
                continue
            zs = []
            for pos in anomalous_positions:
                std = abs(float(features[int(pos), std_i]))
                if std < 1e-9:
                    continue
                z = abs((float(features[int(pos), last_i]) - float(features[int(pos), mean_i])) / std)
                zs.append(z)
            if zs:
                contribs[m] = round(float(np.mean(zs)), 2)

        top = sorted(contribs.items(), key=lambda kv: kv[1], reverse=True)[:3]
        return dict(top)

    # ------------------------------------------------------------------
    # Drift detection (PSI vs training baseline)
    # ------------------------------------------------------------------

    def compute_drift(self, recent_data: List[Dict],
                      threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Compare the recent metric distribution to the training baseline using
        the Population Stability Index. Returns per-metric PSI, the max PSI,
        and whether a retrain is warranted.
        """
        threshold = threshold if threshold is not None else self.drift_threshold

        if not self.model_card or not recent_data:
            return {
                'max_psi': 0.0,
                'per_metric': {},
                'needs_retrain': False,
                'threshold': threshold,
                'reason': 'no baseline or no recent data',
            }

        baseline = self.model_card.get('baseline', {})
        per_metric: Dict[str, float] = {}
        for m in self.feature_columns:
            info = baseline.get(m)
            if not info:
                continue
            values = [
                float(r[m]) for r in recent_data
                if r.get(m) is not None and np.isfinite(float(r[m]))
            ]
            if len(values) < 10:
                continue
            psi = self._psi_from_buckets(values, info['psi_breakpoints'], info['psi_expected'])
            per_metric[m] = round(psi, 4)

        max_psi = max(per_metric.values()) if per_metric else 0.0
        needs_retrain = max_psi > threshold
        return {
            'max_psi': round(max_psi, 4),
            'per_metric': per_metric,
            'needs_retrain': needs_retrain,
            'threshold': threshold,
            'reason': 'drift' if needs_retrain else 'stable',
        }

    @staticmethod
    def _baseline_for(values: np.ndarray, buckets: int = 5) -> Optional[Dict[str, Any]]:
        """Training-time distribution summary used for drift comparison."""
        values = values[np.isfinite(values)]
        if values.size < 20:
            return None
        breakpoints = np.nanpercentile(values, np.linspace(0, 100, buckets + 1)[1:-1])
        bins = np.concatenate([[-np.inf], breakpoints, [np.inf]])
        counts, _ = np.histogram(values, bins=bins)
        expected = counts / counts.sum()
        return {
            'mean': round(float(values.mean()), 4),
            'std': round(float(values.std()), 4),
            'psi_breakpoints': [float(b) for b in breakpoints],
            'psi_expected': [float(e) for e in expected],
        }

    @staticmethod
    def _psi_from_buckets(actual_values: List[float], breakpoints: List[float],
                          expected_shares: List[float]) -> float:
        """Population Stability Index of `actual_values` vs stored baseline buckets."""
        bins = np.concatenate([[-np.inf], np.asarray(breakpoints, dtype=float), [np.inf]])
        counts, _ = np.histogram(actual_values, bins=bins)
        actual_share = counts / counts.sum()
        expected = np.clip(np.asarray(expected_shares, dtype=float), 1e-6, None)
        actual = np.clip(actual_share, 1e-6, None)
        return float(np.sum((actual - expected) * np.log(actual / expected)))


def _timedelta_from_env(name: str, default: timedelta) -> timedelta:
    """Parse a seconds-based env var into a timedelta."""
    try:
        return timedelta(seconds=int(os.getenv(name, '')))
    except (TypeError, ValueError):
        return default


def main():
    """Main function to run anomaly detection."""
    from logging_config import configure_logging

    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    configure_logging(level=logging.INFO, log_dir=log_dir, log_file='anomaly.log')

    detector = AnomalyDetector()

    # Load a persisted model, otherwise train on real store history
    if not detector.load_model():
        logger.info("No persisted model; training on real store history")
        if not detector.train_model():
            logger.error(
                "Failed to train model: no real metrics history available. "
                "Collect metrics first (run the app and monitor.py)."
            )
            return {'status': 'error', 'message': 'No training data available in metrics store.'}

    current_metrics = detector.fetch_metrics_data()
    results = detector.detect_anomalies(current_metrics)
    print(json.dumps(results, indent=2, default=str))
    return results


if __name__ == "__main__":
    main()
