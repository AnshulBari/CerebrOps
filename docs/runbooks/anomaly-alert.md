# Anomaly Alert

Fired by the monitor's Slack alert when the anomaly detector flags points.

## What the alert contains

```
🧠 CerebrOps detected 3 anomalies (9.1% of data points) [forecast-residual]
```

- `method` — how it was detected:
  - **`isolation-forest`** — outlier in rolling 15m/1h/24h feature space
    (model vN, drift-retrained).
  - **`forecast-residual`** — deviation from the learned hour-of-week
    seasonal forecast by > `FORECAST_Z_THRESHOLD` (default 4) robust stddevs.
    Only active once ≥ 7 days of real history exist. This method is *better*
    at catching slow, seasonal-context deviations; trust it.
- `top_metric_contributions` — which metric(s) deviated most (units: stddevs
  from the 1h expectation).
- `root_cause` (attached when a deploy is correlated) —
  - `deploy_correlation`: pipeline events (run id, branch, commit, minutes
    before the anomaly)
  - `metric_shifts`: per-metric mean before/after the deploy window, with
    `shifted: true/false`
  - `hypothesis`: plain-language "possible deploy-related regression".

## Triage

1. **Is it correlated to a deploy?** If `root_cause.hypothesis` is present,
   note the commit and minutes-before, then check the deploy's stage logs.
   A regression that shipped with a deploy is a **rollback candidate**.
2. **Is the metric deviation real or seasonal?** Look at the same hour on
   previous days in Grafana. A repeated daily pattern flagged by the forest
   (but not the forecast detector) usually means the baseline drifted and a
   retrain is due — the drift check handles this automatically.
3. **Check the dashboard + logs**: Overview tab stat cards, log tail, and
   `GET /api/v1/anomalies` for the full window with per-point scores.

## Responses

| Situation | Action |
|-----------|--------|
| Deploy regression (metrics shifted after deploy) | Roll back to previous digest (`kubectl rollout undo deployment/cerebrops-app` or ArgoCD sync to previous revision). File a bug on the commit. |
| Capacity (CPU/mem/disk high, latency up) | Scale out (HPA handles automatically) or investigate a leak; check `k8s/base/hpa.yaml` behavior. |
| Upstream / external dependency | Confirm with the provider; add a dashboard annotation; no code action. |
| One-off spike, no deploy, self-recovered | Log it; no action. Note it in the incident thread. |
| Persistent deviation without deploy | The metric distribution has shifted — drift-based retraining will fire (`max PSI > 0.25`); verify the new model card (`models/` dir) and that alerts remain sensible. |

## Do not

- **Do not** dismiss `forecast-residual` alerts as "new behavior" without
  checking the seasonal baseline — that is exactly what it models.
- **Do not** retrain the model manually to silence alerts; drift retraining is
  automatic and recorded in the model card.
- **Do not** deploy a fix during an active anomaly without a rollback plan.
