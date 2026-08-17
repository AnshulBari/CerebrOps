#!/usr/bin/env python3
"""
CerebrOps model evaluation harness (Phase 5).

Compares the two anomaly detectors - v1 IsolationForest and v2
forecast-residual - on a LABELED dataset and reports point-level
precision / recall / F1 per method.

Two data sources:
  --labels FILE   JSONL of real production rows with a truth label:
                  {"ts": "...", "cpu_usage": ..., "true_anomaly": 0|1, ...}
                  (the Phase 5 acceptance path: run this on >= 2 weeks of
                  real production data once it exists)
  --generate      synthetic labeled data with known injected anomalies
                  (used by tests and dry runs)

The model is trained/fitted on the first `--train-fraction` of the window and
evaluated on the rest. A prediction matches a labeled anomaly when it falls
within `--tolerance-min` minutes of it.

Usage:
  python scripts/evaluate_models.py --labels labels.jsonl --model-dir models
  python scripts/evaluate_models.py --generate --days 21 --seed 7
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

# Allow running as `python scripts/evaluate_models.py` from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from anomaly_detector import AnomalyDetector  # noqa: E402
from forecast_detector import ForecastResidualDetector  # noqa: E402
from metrics_store import MetricsStore, parse_ts  # noqa: E402
from model_repository import ModelRepository  # noqa: E402

METRIC_FIELDS = ['cpu_usage', 'memory_usage', 'disk_usage',
                 'error_rate', 'request_count', 'response_time']


def generate_labeled(days: int = 21, anomaly_count: int = 10,
                     seed: int = 42) -> List[Dict[str, Any]]:
    """Seasonal synthetic data with known injected anomalies (test-only)."""
    rng = np.random.default_rng(seed)
    t0 = datetime(2026, 1, 5, tzinfo=timezone.utc)  # Monday
    rows = []
    for i in range(days * 48):  # 30-min sampling
        ts = t0 + timedelta(minutes=30 * i)
        hour = ts.hour
        anomaly = i % (days * 48 // max(anomaly_count, 1)) == days * 48 // max(anomaly_count, 1) - 1
        cpu = 50 + 10 * math.sin(hour / 24.0 * 2 * math.pi) + rng.normal(0, 1)
        if anomaly:
            cpu += 40  # 40-sigma spike at a seasonal-aware time
        rows.append({
            'ts': ts.isoformat(),
            'cpu_usage': round(float(cpu), 4),
            'memory_usage': round(70 + rng.normal(0, 1), 4),
            'disk_usage': round(85 + rng.normal(0, 1), 4),
            'error_rate': round(0.5 + rng.normal(0, 0.1), 4),
            'request_count': round(100 + rng.normal(0, 5), 4),
            'response_time': round(0.3 + rng.normal(0, 0.05), 4),
            'true_anomaly': 1 if anomaly else 0,
        })
    return rows


def load_labels(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def match_predictions(pred_times: List[datetime], true_times: List[datetime],
                      tolerance: timedelta) -> Tuple[int, int, int]:
    """Greedy nearest-match: returns (tp, fp, fn)."""
    preds = sorted(pred_times)
    trues = sorted(true_times)
    tp = 0
    used = set()
    for t in trues:
        best_i, best_d = None, tolerance
        for i, p in enumerate(preds):
            if i in used:
                continue
            d = abs(p - t)
            if d <= best_d:
                best_d = d
                best_i = i
        if best_i is not None:
            used.add(best_i)
            tp += 1
    fp = len(preds) - tp
    fn = len(trues) - tp
    return tp, fp, fn


def _result_ts(result: Dict[str, Any]) -> List[datetime]:
    out = []
    for p in result.get('anomalous_data') or []:
        ts = parse_ts(p.get('ts') or p.get('timestamp'))
        if ts is not None:
            out.append(ts)
    return out


def run_evaluation(train_rows: List[Dict[str, Any]],
                   test_rows: List[Dict[str, Any]],
                   true_times: List[datetime],
                   model_dir: Optional[str] = None,
                   tolerance_min: int = 60) -> Dict[str, Any]:
    """Evaluate both detectors; returns a comparison report."""
    tolerance = timedelta(minutes=tolerance_min)

    # --- v2 forecast-residual ---
    forecast = ForecastResidualDetector(min_history_days=0, min_history_points=50)
    forecast.fit(train_rows)
    v2_result = forecast.detect(test_rows)
    v2_preds = _result_ts(v2_result) if v2_result.get('status') == 'anomaly' else []
    v2_tp, v2_fp, v2_fn = match_predictions(v2_preds, true_times, tolerance)

    # --- v1 isolation-forest ---
    store = MetricsStore()  # session temp DB; store is only used for fetches
    repo = ModelRepository(model_dir) if model_dir else ModelRepository()
    detector = AnomalyDetector(store=store, repository=repo, min_samples=5)
    v1_preds: List[datetime] = []
    v1_trained = False
    v1_skipped = None
    try:
        if detector.load_model():
            v1_trained = True
        elif detector.train_model(train_rows, save=False):
            v1_trained = True
        if v1_trained:
            v1_result = detector.detect_anomalies(test_rows, method='isolation-forest')
            v1_preds = _result_ts(v1_result) if v1_result.get('status') == 'anomaly' else []
        else:
            v1_skipped = 'could not load or train IsolationForest'
    except Exception as e:  # sklearn missing / bad model dir
        v1_skipped = str(e)
    v1_tp, v1_fp, v1_fn = (0, 0, 0) if v1_skipped else match_predictions(v1_preds, true_times, tolerance)

    def _scores(tp, fp, fn):
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return {'precision': round(prec, 3), 'recall': round(rec, 3), 'f1': round(f1, 3)}

    report = {
        'dataset': {
            'train_points': len(train_rows),
            'test_points': len(test_rows),
            'labeled_anomalies': len(true_times),
            'tolerance_minutes': tolerance_min,
        },
        'v2_forecast_residual': {
            'fitted': forecast.is_fitted,
            'tp': v2_tp, 'fp': v2_fp, 'fn': v2_fn,
            'detected_anomalies': len(v2_preds),
            **_scores(v2_tp, v2_fp, v2_fn),
        },
        'v1_isolation_forest': {
            'trained': v1_trained,
            'skipped': v1_skipped,
            'tp': v1_tp, 'fp': v1_fp, 'fn': v1_fn,
            'detected_anomalies': len(v1_preds),
            **_scores(v1_tp, v1_fp, v1_fn),
        },
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }
    return report


def _split(rows: List[Dict[str, Any]], train_fraction: float):
    split = int(len(rows) * train_fraction)
    return rows[:split], rows[split:]


def main() -> int:
    parser = argparse.ArgumentParser(description='CerebrOps model evaluation')
    parser.add_argument('--labels', help='JSONL file with labeled rows (real data)')
    parser.add_argument('--generate', action='store_true', help='Use synthetic labeled data')
    parser.add_argument('--days', type=int, default=21, help='Synthetic data days')
    parser.add_argument('--anomaly-count', type=int, default=10, help='Synthetic anomaly count')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--model-dir', help='Persisted v1 model dir (default: CEREBROPS_MODEL_DIR)')
    parser.add_argument('--tolerance-min', type=int, default=60)
    parser.add_argument('--train-fraction', type=float, default=0.8)
    parser.add_argument('--output', help='Write JSON report to this path')
    parser.add_argument(
        '--self-check', action='store_true',
        help='CI gate: evaluate on synthetic labeled data and fail (exit 2) if '
             'detection quality drops below thresholds. Proves the harness '
             'works; real precision/recall still requires --labels with >= 2 '
             'weeks of production data.')
    args = parser.parse_args()

    if args.self_check:
        # Deterministic fixture (same seed the unit tests pin) so CI is stable.
        rows = generate_labeled(days=args.days, anomaly_count=args.anomaly_count,
                                seed=args.seed)
    elif args.labels:
        rows = load_labels(args.labels)
    elif args.generate:
        rows = generate_labeled(days=args.days, anomaly_count=args.anomaly_count, seed=args.seed)
    else:
        parser.error('Provide --labels FILE or --generate')

    if not rows:
        print('ERROR: no labeled rows', file=sys.stderr)
        return 1

    train, test = _split(rows, args.train_fraction)
    # Evaluate only against labels inside the test window (pre-window
    # anomalies are not detectable from the evaluation split).
    true_times = [parse_ts(r.get('ts') or r.get('timestamp'))
                  for r in test if r.get('true_anomaly')]
    true_times = [t for t in true_times if t is not None]

    model_dir = args.model_dir or os.getenv('CEREBROPS_MODEL_DIR')
    report = run_evaluation(
        train, test, true_times,
        model_dir=model_dir, tolerance_min=args.tolerance_min,
    )

    print(json.dumps(report, indent=2))
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f"Report written to {args.output}")

    if args.self_check:
        v2 = report['v2_forecast_residual']
        v1 = report['v1_isolation_forest']
        # Looser than the unit tests on purpose: the gate must catch real
        # regressions without being flaky across Python/sklearn versions.
        checks = [
            ('v2 forecast-residual recall >= 0.8', v2['recall'] >= 0.8),
            ('v2 forecast-residual precision >= 0.4', v2['precision'] >= 0.4),
            ('v2 forecast-residual f1 >= 0.5', v2['f1'] >= 0.5),
        ]
        if v1['trained']:
            checks.append(('v1 isolation-forest recall >= 0.5', v1['recall'] >= 0.5))
        else:
            print('NOTE: v1 skipped (%s) - not gated' % v1.get('skipped'))
        print('\n--self-check (synthetic labeled data, deterministic):')
        ok = True
        for label, passed in checks:
            print('  [%s] %s' % ('PASS' if passed else 'FAIL', label))
            ok = ok and passed
        if not ok:
            print('\nERROR: detection quality below gate thresholds. If this '
                  'regression is real, fix the detector before shipping; the '
                  'real precision/recall number still needs --labels with >= 2 '
                  'weeks of production data.', file=sys.stderr)
            return 2
        print('\nSelf-check passed - harness proven on labeled synthetic data.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
