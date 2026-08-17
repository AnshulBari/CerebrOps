# Error Budget Burn

Fired by `CerebrOpsSLOFastBurn` (page) / `CerebrOpsSLOSlowBurn` (ticket).

## What it means

The 30-day availability SLO is 99.9% (0.1% of requests may fail). The alert
uses multi-window burn rates so we act *before* the budget is gone:

| Alert | Burn rate | Budget exhausts in |
|-------|-----------|--------------------|
| FastBurn (critical, pages) | ≥ 14.4 over 1h **and** 5m | ~2 hours |
| SlowBurn (warning, ticket) | ≥ 3 over 6h **and** 30m | ~10 hours |

Burn rate 1.0 = exactly on target. 14.4 means we are burning the budget 14.4×
faster than allowed.

## Triage

1. **Find the failure source.** Grafana `cerebrops-http`: error rate by
   **route** and by **status**. A single route failing 500s points at that
   feature; a flat 5xx across all routes points at infra (ingress, DB,
   deployment).
2. **Check for a deploy.** `GET /api/v1/pipeline` — if a deploy landed in the
   window, this is a regression (see `anomaly-alert.md` rollback path).
3. **Check the store/disk.** `CerebrOpsDiskPressure` alongside a burn usually
   means the SQLite store or logs are failing; act on capacity first.
4. **Quantify the damage.** `GET /api/v1/metrics?window=1h` and the
   `cerebrops:slo:error_budget_remaining:30d` recording rule tell you how much
   budget is left and how long to full exhaustion.

## Responses

| Situation | Action |
|-----------|--------|
| Route-specific 500s | Investigate that route's code + logs; roll back its deploy if correlated |
| All-route 5xx | Check ingress/network policies (`k8s/base/network-policy.yaml`), the web deployment rollout, and disk |
| Slow burn (ticket, < 1h to act) | Schedule a fix this shift; do not page-dance on a slow burn |
| Fast burn (page) | Declare incident, follow `incident-response.md` |

## Budget math reference

- Budget per day ≈ 0.001 × requests/day. A single 30-minute full outage of a
  1 rps service burns ~0.06% of the 30d budget — noise. A 1-hour outage of a
  100 rps service burns ~0.8% of the budget — meaningful. Use the burn-rate
  alert, not intuition, to decide severity.

## After the incident

- Record the budget consumed in the postmortem (`incident-response.md`).
- If this SLO was missed, revisit the SLO target and/or add
  `slo: availability` labels to the alert routing so it reaches the right
  on-call.
