# CerebrOps Runbooks

Alert-to-action playbooks for the CerebrOps stack. For deeper architecture and
maintenance procedures, see `OPERATIONS_MANUAL.md` at the repo root.

## SLOs

| SLO | Target | Budget | Window |
|-----|--------|--------|--------|
| Availability | 99.9% | 0.1% of requests may 5xx | 30d rolling |
| Latency | p95 < 500ms | — | 5m/10m windows |
| Error rate (guardrail) | < 1% 5xx share | — | 5m window |

SLO and burn-rate alerts are defined in `monitoring/prometheus-rules.yml`.
Burn rate = actual error ratio / 0.001. A burn rate of **14.4** exhausts the
30d budget in ~2 hours (page); **3** exhausts it in ~10 hours (ticket).

## Severity matrix

| Severity | Meaning | Response time | Alerting |
|----------|---------|---------------|----------|
| `critical` | Service down, budget burning fast, disk filling | Immediately, page on-call | Slack + Prometheus page |
| `high` | Degraded UX, sustained error/latency spike | < 1h | Slack |
| `warning` | Trend that may become an incident | Same business day | Slack |
| `low` | Informational | Triage queue | Dashboard only |

## Escalation

1. **Tier 1 (L1)**: respond to alerts, run the matching runbook, gather
   evidence (timeline, metrics, logs, deploy correlation).
2. **Tier 2 (L2)**: if unresolved after 30 min (critical) / 4 h (high),
   escalate to the maintainer. L2 owns code-level fixes and rollbacks.
3. **Tier 3 (L3)**: vendor/platform issues (Slack outage, cloud provider,
   cluster control plane). Open support tickets and keep the timeline updated.

## Alert → runbook map

| Alert | Runbook |
|-------|---------|
| `CerebrOpsDown` | `service-down.md` |
| `CerebrOpsSLOFastBurn` / `CerebrOpsSLOSlowBurn` | `slo-burn.md` |
| `CerebrOpsHighErrorRate`, `CerebrOpsHighLatencyP95` | `anomaly-alert.md` + `slo-burn.md` |
| `CerebrOpsHighCPU`, `CerebrOpsDiskPressure` | `service-down.md` (capacity section) |
| Slack anomaly alert from `monitor.py` | `anomaly-alert.md` |

## Operational procedures

| Procedure | Runbook |
|-----------|---------|
| Restore SQLite store / models from backup | `restore.md` + `python scripts/restore_drill.py` |
| Evaluate v1 vs v2 detectors on real labeled data | `model-evaluation.md` + `python scripts/evaluate_models.py --self-check` |
| Prove app → Filebeat → ES → Kibana/Grafana e2e | `./scripts/verify-observability.sh` |

## Where to look first (in order)

1. **Slack anomaly alert payload** — includes `method`
   (`isolation-forest` vs `forecast-residual`), `top_metric_contributions`,
   and (when a deploy is correlated) a `root_cause` block with
   `deploy_correlation`, `metric_shifts`, and a plain-language `hypothesis`.
2. **Dashboard** — `/dashboard` (Flask app shell + `static/js/app.js`):
   Overview (stat tiles, recent pipelines, anomalies, activity, alerts),
   Pipelines (filterable list + run detail with stage rail and searchable
   logs), Deployments, Anomalies (with root-cause hypothesis), Alerts,
   Environments, Analytics, Settings. `⌘K` opens the command palette.
3. **Grafana** — `cerebrops-overview` (resources, request rate, error rate,
   p95) and `cerebrops-http` (by route/status).
4. **Kibana** — `cerebrops-logs-*` data view for the app's structured JSON
   logs.
5. **API** — `GET /api/v1/anomalies`, `/api/v1/alerts`, `/api/v1/pipeline`
   (all require `X-API-Key` when `CEREBROPS_API_KEY` is set).
