"""
CerebrOps Forecast-Residual Anomaly Detector (Phase 5, AI v2).

Seasonal-naive forecast + residual z-scores, implemented in pure numpy (no
extra dependencies).

WHY: the IsolationForest path flags points that are outliers in rolling
feature space. The forecast-residual path instead models *expected
seasonality* (a per-metric hour-of-week profile) and flags points whose
deviation from expectation exceeds an adaptive threshold. It is the roadmap's
"AI v2" detector: it only activates once enough REAL history exists
(>= FORECAST_MIN_HISTORY_DAYS of stored metrics), otherwise detection reports
`insufficient_data` and the monitor falls back to the persisted IsolationForest
model. No synthetic data is ever used.
"""

import logging
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from metrics_store import parse_ts

logger = logging.getLogger('cerebrops.forecast_detector')

METRIC_FIELDS = ['cpu_usage', 'memory_usage', 'disk_usage',
                 'error_rate', 'request_count', 'response_time']

DEFAULT_MIN_HISTORY_DAYS = 7.0
DEFAULT_MIN_HISTORY_POINTS = 500
DEFAULT_MIN_OBS_PER_BUCKET = 3
DEFAULT_Z_THRESHOLD = 4.0
DEFAULT_HARD_Z_THRESHOLD = 5.0
DEFAULT_SEASON_BUCKETS = 168  # hour-of-week profile (24h x 7d)
DEFAULT_MIN_DETECT_POINTS = 10


class ForecastResidualDetector:
    """
    Detect anomalies as large deviations from a learned seasonal forecast.

    Fitting requires a minimum span of real history (`min_history_days`) and a
    minimum number of points. The forecast is a per-metric hour-of-week mean
    profile; a point is anomalous when its residual (actual - forecast) is more
    than `z_threshold` robust standard deviations from the training residual
    distribution.
    """

    def __init__(self,
                 min_history_days: Optional[float] = None,
                 min_history_points: Optional[int] = None,
                 min_obs_per_bucket: Optional[int] = None,
                 z_threshold: Optional[float] = None,
                 season_buckets: int = DEFAULT_SEASON_BUCKETS,
                 min_detect_points: int = DEFAULT_MIN_DETECT_POINTS):
        self.min_history_days = float(os.getenv(
            'FORECAST_MIN_HISTORY_DAYS',
            min_history_days if min_history_days is not None else DEFAULT_MIN_HISTORY_DAYS
        ))
        self.min_history_points = int(os.getenv(
            'FORECAST_MIN_HISTORY_POINTS',
            min_history_points if min_history_points is not None else DEFAULT_MIN_HISTORY_POINTS
        ))
        self.min_obs_per_bucket = int(os.getenv(
            'FORECAST_MIN_OBS_PER_BUCKET',
            min_obs_per_bucket if min_obs_per_bucket is not None else DEFAULT_MIN_OBS_PER_BUCKET
        ))
        self.z_threshold = float(os.getenv(
            'FORECAST_Z_THRESHOLD',
            z_threshold if z_threshold is not None else DEFAULT_Z_THRESHOLD
        ))
        # Hard threshold: points above this are anomalous unconditionally.
        # Points between z_threshold and hard_z_threshold count only when an
        # adjacent point also breaches z_threshold (debounce) - this filters
        # isolated tail-of-noise draws without losing strong single-point
        # spikes or sustained deviations.
        self.hard_z_threshold = float(os.getenv(
            'FORECAST_HARD_Z_THRESHOLD', DEFAULT_HARD_Z_THRESHOLD
        ))
        self.season_buckets = int(season_buckets)
        self.min_detect_points = int(min_detect_points)

        # metric -> {'bucket_mean': np.ndarray(season_buckets), 'bucket_obs': np.ndarray,
        #            'global_mean': float, 'resid_mean': float, 'resid_std': float}
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.is_fitted = False
        self.fit_meta: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    @staticmethod
    def _rows_to_arrays(rows: List[Dict]) -> Optional[Dict[str, np.ndarray]]:
        """Extract per-metric value arrays and hour-of-week indices."""
        ts_list: List[datetime] = []
        values: Dict[str, List[float]] = {m: [] for m in METRIC_FIELDS}
        for row in rows:
            ts = parse_ts(row.get('timestamp', row.get('ts')))
            if ts is None:
                continue
            ts_list.append(ts)
            for m in METRIC_FIELDS:
                v = row.get(m)
                try:
                    values[m].append(float(v) if v is not None else np.nan)
                except (TypeError, ValueError):
                    values[m].append(np.nan)
        if not ts_list:
            return None
        return {
            'ts': np.asarray(ts_list),
            'values': {m: np.asarray(vals, dtype=float) for m, vals in values.items()},
        }

    def fit(self, rows: List[Dict]) -> bool:
        """
        Fit the seasonal forecast on real store history.

        Returns True when enough history exists and the profile was built;
        False (and `is_fitted` stays False) otherwise.
        """
        data = self._rows_to_arrays(rows or [])
        if data is None or data['ts'].size == 0:
            logger.warning("Forecast fit skipped: no timestamped metric rows")
            return False

        span_days = (data['ts'][-1] - data['ts'][0]).total_seconds() / 86400.0
        n = int(data['ts'].size)
        # The forecast is only trustworthy when each hour-of-week bucket is
        # backed by enough observations; otherwise the bucket means are too
        # noisy and the residual scale collapses. This is the real-data gate:
        # with hourly sampling you need ~3 weeks, with 30-min sampling ~10 days.
        avg_obs_per_bucket = n / float(self.season_buckets)
        if (n < self.min_history_points or span_days < self.min_history_days
                or avg_obs_per_bucket < self.min_obs_per_bucket):
            logger.info(
                "Forecast fit skipped: need >= %s points spanning >= %.0f days with "
                ">= %s obs/bucket (have %s points spanning %.1f days, %.1f obs/bucket)",
                self.min_history_points, self.min_history_days,
                self.min_obs_per_bucket, n, span_days, avg_obs_per_bucket,
            )
            return False

        hour_of_week = np.asarray(
            [ts.weekday() * 24 + ts.hour for ts in data['ts']], dtype=int
        )

        profiles: Dict[str, Dict[str, Any]] = {}
        for metric, vals in data['values'].items():
            finite = np.isfinite(vals)
            if finite.sum() < max(self.min_history_points * 0.5, 100):
                continue
            bucket_mean = np.full(self.season_buckets, np.nan)
            bucket_obs = np.zeros(self.season_buckets, dtype=int)
            for b in range(self.season_buckets):
                mask = (hour_of_week == b) & finite
                obs = int(mask.sum())
                bucket_obs[b] = obs
                if obs > 0:
                    # Median, not mean: with a handful of observations per
                    # bucket, one training-set outlier (a real past incident)
                    # would otherwise shift the seasonal profile and create
                    # false alarms at that hour every following week.
                    bucket_mean[b] = float(np.median(vals[mask]))
            # Buckets without observations fall back to the global median so
            # the forecast never produces NaN.
            global_mean = float(np.median(vals[finite]))
            bucket_mean = np.where(np.isfinite(bucket_mean), bucket_mean, global_mean)

            # Residuals only from buckets we actually observed.
            trusted = finite & (bucket_obs[hour_of_week] > 0)
            residuals = vals[trusted] - bucket_mean[hour_of_week[trusted]]
            resid_median = float(np.median(residuals))
            # Robust dispersion (MAD) so a few training outliers do not blow
            # the threshold up; clipped to a floor so flat metrics stay testable.
            mad = float(np.median(np.abs(residuals - resid_median)))
            resid_std = max(1.4826 * mad, 1e-6)
            # Small-sample correction: the fitted bucket center (mean or
            # median) absorbs ~sigma/sqrt(n) of the noise, which biases the
            # residual scale LOW and causes false alarms at the 4-sigma edge.
            # Median sampling variance is ~(pi/2)*sigma^2/n; inflate the
            # residual std by the implied factor.
            avg_obs = float(finite.sum()) / self.season_buckets
            if avg_obs > 1e-9:
                resid_std *= 1.0 / math.sqrt(max(1.0 - (math.pi / 2.0) / avg_obs, 0.25))

            profiles[metric] = {
                'bucket_mean': bucket_mean,
                'bucket_obs': bucket_obs,
                'global_mean': global_mean,
                'resid_mean': resid_median,
                'resid_std': resid_std,
            }

        if not profiles:
            logger.warning("Forecast fit failed: no metric with enough finite values")
            return False

        self.profiles = profiles
        self.is_fitted = True
        self.fit_meta = {
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'n_samples': n,
            'history_days': round(span_days, 2),
            'obs_per_bucket': round(avg_obs_per_bucket, 2),
            'metrics': sorted(profiles.keys()),
            'z_threshold': self.z_threshold,
            'hard_z_threshold': self.hard_z_threshold,
            'season_buckets': self.season_buckets,
        }
        logger.info(
            "Forecast-residual detector fitted on %s points spanning %.1f days (%s metrics)",
            n, span_days, len(profiles),
        )
        return True

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _insufficient(self, message: str) -> Dict[str, Any]:
        return {'status': 'insufficient_data', 'message': message}

    def detect(self, rows: List[Dict]) -> Dict[str, Any]:
        """
        Score a window of metric rows against the seasonal forecast.

        Returns the same result shape as AnomalyDetector.detect_anomalies so
        the monitor, alerter, and dashboard treat it identically.
        """
        if not self.is_fitted:
            return self._insufficient(
                "Forecast detector not fitted: needs >= %s real history days and "
                ">= %s stored metric points." % (self.min_history_days, self.min_history_points)
            )
        if not rows:
            return {'status': 'no_data', 'message': 'No data to analyze'}
        if len(rows) < self.min_detect_points:
            return self._insufficient(
                f"Only {len(rows)} data points available; forecast detection needs "
                f"at least {self.min_detect_points}."
            )

        data = self._rows_to_arrays(rows)
        if data is None:
            return self._insufficient("No timestamped metric rows in window.")

        hour_of_week = np.asarray(
            [ts.weekday() * 24 + ts.hour for ts in data['ts']], dtype=int
        )

        point_scores_all: List[List[Dict[str, Any]]] = []
        point_max_abs: List[float] = []
        max_abs_z: Dict[str, float] = {}

        for i, ts in enumerate(data['ts']):
            b = int(hour_of_week[i])
            point_scores: List[Dict[str, Any]] = []
            for metric, prof in self.profiles.items():
                v = float(data['values'][metric][i])
                if not np.isfinite(v):
                    continue
                # Do not trust buckets the forecast never observed; skip
                # instead of firing on an unseen hour-of-week.
                if int(prof['bucket_obs'][b]) < self.min_obs_per_bucket:
                    continue
                forecast = float(prof['bucket_mean'][b])
                residual = v - forecast - prof['resid_mean']
                z = residual / prof['resid_std']
                prev = max_abs_z.get(metric, 0.0)
                max_abs_z[metric] = max(prev, abs(float(z)))
                point_scores.append({
                    'metric': metric, 'value': round(v, 4),
                    'forecast': round(forecast, 4),
                    'residual': round(float(residual), 4),
                    'z_score': round(float(z), 3),
                })
            point_scores_all.append(point_scores)
            point_max_abs.append(
                max((abs(s['z_score']) for s in point_scores), default=0.0)
            )

        # Debounce: a point between z_threshold and hard_z_threshold is only
        # anomalous when a neighbor breaches z_threshold too (persistent
        # deviation beats an isolated tail-of-noise draw).
        def _flagged(i: int) -> bool:
            m = point_max_abs[i]
            if m >= self.hard_z_threshold:
                return True
            if m >= self.z_threshold:
                prev = point_max_abs[i - 1] >= self.z_threshold if i > 0 else False
                nxt = point_max_abs[i + 1] >= self.z_threshold if i + 1 < len(point_max_abs) else False
                return prev or nxt
            return False

        anomalous_points = [
            {'ts': data['ts'][i].isoformat(), 'scores': point_scores_all[i]}
            for i in range(len(point_scores_all))
            if point_scores_all[i] and _flagged(i)
        ]

        total = len(data['ts'])
        anomaly_count = len(anomalous_points)
        anomaly_percentage = (anomaly_count / total) * 100.0

        return {
            'status': 'anomaly' if anomaly_count > 0 else 'normal',
            'method': 'forecast-residual',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'window_size': total,
            'total_data_points': total,
            'anomaly_count': anomaly_count,
            'anomaly_percentage': round(anomaly_percentage, 2),
            'anomalous_data': anomalous_points[:50],
            'severity': self._calculate_severity(anomaly_percentage),
            'top_metric_contributions': {
                m: round(abs(z), 3) for m, z in sorted(
                    max_abs_z.items(), key=lambda kv: kv[1], reverse=True
                )
            },
            'recommendations': self._get_recommendations(anomaly_percentage),
            'model_version': None,
        }

    @staticmethod
    def _calculate_severity(anomaly_percentage: float) -> str:
        """Severity from the share of anomalous points (mirrors the forest path)."""
        if anomaly_percentage > 20:
            return 'critical'
        if anomaly_percentage > 10:
            return 'high'
        if anomaly_percentage > 5:
            return 'medium'
        return 'low'

    @staticmethod
    def _get_recommendations(anomaly_percentage: float) -> List[str]:
        if anomaly_percentage == 0:
            return []
        recs = [f"{anomaly_percentage:.1f}% of points deviate from the seasonal forecast."]
        if anomaly_percentage > 20:
            recs.append("Large deviation share: investigate deploy correlation (see root_cause).")
        else:
            recs.append("Check the anomalous points' metrics and any recent deployments.")
        recs.append("If the deviation persists, the distribution may have shifted; retraining will follow drift detection.")
        return recs
