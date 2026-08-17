"""
CerebrOps deploy-correlation root-cause analysis (Phase 5).

Attributes anomalies to recent CI/CD deployments using the pipeline_events
table fed by the Phase 3 webhook (GitHub Actions posts real run results).
For every anomaly, the monitor attaches a root-cause summary that lists
deploys in the lookback window and the metrics that shifted around them, plus
a plain-language hypothesis.

This works on real data: pipeline events come from the webhook, metric
shifts are computed from the metrics store. No fabricated inputs.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from metrics_store import MetricsStore, parse_ts

logger = logging.getLogger('cerebrops.root_cause')

METRIC_FIELDS = ['cpu_usage', 'memory_usage', 'disk_usage',
                 'error_rate', 'request_count', 'response_time']

# Deploy events we care about (build/deploy stages, both outcomes).
DEPLOY_STAGES = {'deploy', 'build'}
DEPLOY_STATUSES = {'success', 'failed'}
# A metric must shift by this much (relative %) to count as "shifted".
SHIFT_THRESHOLD_PCT = 20.0


def correlate_deploys(store: MetricsStore,
                      at_ts: Optional[datetime] = None,
                      lookback: timedelta = timedelta(hours=2)) -> List[Dict[str, Any]]:
    """
    List deploy/build pipeline events in the window before `at_ts`.

    Events are returned oldest-first with `minutes_before` (how long before
    the anomaly the deploy completed).
    """
    at = at_ts or datetime.now(timezone.utc)
    events = store.get_pipeline_events(limit=500)
    matches: List[Dict[str, Any]] = []
    for ev in events:
        if (ev.get('status') or '').lower() not in DEPLOY_STATUSES:
            continue
        if (ev.get('stage') or '').lower() not in DEPLOY_STAGES:
            continue
        ts = parse_ts(ev.get('ts') or ev.get('timestamp'))
        if ts is None:
            continue
        if ts < at - lookback or ts > at + timedelta(minutes=5):
            continue
        matches.append({
            'pipeline_id': ev.get('pipeline_id'),
            'status': ev.get('status'),
            'stage': ev.get('stage'),
            'branch': ev.get('branch'),
            'commit_hash': ev.get('commit_hash'),
            'ts': ev.get('ts'),
            'minutes_before': round((at - ts).total_seconds() / 60.0, 1),
        })
    matches.sort(key=lambda m: m['minutes_before'])
    return matches


def metric_shift_summary(store: MetricsStore,
                         at_ts: Optional[datetime] = None,
                         window: timedelta = timedelta(hours=2)) -> Dict[str, Any]:
    """
    Compare each metric's mean in the `window` before `at_ts` (after) with the
    preceding window (before). Reports relative shift and whether it exceeded
    SHIFT_THRESHOLD_PCT.
    """
    at = at_ts or datetime.now(timezone.utc)
    try:
        rows = store.get_metrics(limit=20000, since=(at - 2 * window).isoformat())
    except Exception as e:
        logger.warning(f"metric_shift_summary: could not fetch metrics: {e}")
        return {}

    before: Dict[str, List[float]] = {m: [] for m in METRIC_FIELDS}
    after: Dict[str, List[float]] = {m: [] for m in METRIC_FIELDS}
    for row in rows:
        ts = parse_ts(row.get('timestamp', row.get('ts')))
        if ts is None:
            continue
        bucket = after if ts >= at - window else before
        for m in METRIC_FIELDS:
            v = row.get(m)
            try:
                if v is not None:
                    bucket[m].append(float(v))
            except (TypeError, ValueError):
                pass

    shifts: Dict[str, Any] = {}
    for m in METRIC_FIELDS:
        if not before[m] or not after[m]:
            continue
        bm = float(np.mean(before[m]))
        am = float(np.mean(after[m]))
        pct = ((am - bm) / bm * 100.0) if abs(bm) > 1e-9 else None
        shifts[m] = {
            'before_mean': round(bm, 3),
            'after_mean': round(am, 3),
            'shift_pct': round(pct, 1) if pct is not None else None,
            'shifted': bool(pct is not None and abs(pct) > SHIFT_THRESHOLD_PCT),
        }
    return shifts


def analyze_root_cause(store: MetricsStore,
                       at_ts: Optional[datetime] = None,
                       lookback: timedelta = timedelta(hours=2)) -> Dict[str, Any]:
    """
    Full root-cause summary for an anomaly at `at_ts`:
    deploy correlation + metric shifts + a plain-language hypothesis.
    """
    deploys = correlate_deploys(store, at_ts, lookback)
    shifts = metric_shift_summary(store, at_ts, lookback)

    hypothesis: Optional[str] = None
    if deploys:
        latest = deploys[0]
        rev = f"{latest.get('branch')}@{latest.get('commit_hash')}" if latest.get('commit_hash') else latest.get('pipeline_id')
        if latest['status'] == 'success':
            hypothesis = (
                f"Possible deploy-related regression: {latest.get('pipeline_id')} "
                f"({rev}) completed {latest['minutes_before']}m before the anomaly."
            )
        else:
            hypothesis = (
                f"Deploy failure near the anomaly: {latest.get('pipeline_id')} "
                f"({rev}) failed {latest['minutes_before']}m before; the cluster may "
                "still be in a degraded state."
            )
        shifted = [m for m, s in shifts.items() if s.get('shifted')]
        if shifted:
            hypothesis += f" Metrics that shifted: {', '.join(sorted(shifted))}."

    return {
        'deploy_correlation': deploys,
        'metric_shifts': shifts,
        'hypothesis': hypothesis,
    }
