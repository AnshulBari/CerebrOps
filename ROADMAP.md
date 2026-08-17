# 🧠 CerebrOps Revamp Roadmap

> **Status**: Draft for review · **Last updated**: 2026-08-17
> This roadmap is based on a full audit of the repository (code, docs, CI/CD, k8s, ELK) as of the current state of `main`.

---

## 1. Executive Summary

CerebrOps is a well-documented CI/CD monitoring scaffold with a working skeleton: a Flask app, an IsolationForest-based anomaly detector, Slack alerting, Docker/Kubernetes manifests, an ELK stack, and a GitHub Actions pipeline. All 31 tests pass and the docs are extensive — **but many documented features are not actually functional end-to-end**. The core problem is that the system looks complete while the data paths that would make it real are missing or simulated:

1. **The AI anomaly detection is theater.** The model trains on *synthetic, seeded* data and then scores a *single live metric point*, making "anomaly percentage" (0% or 100%) meaningless. Retraining every 24h re-generates the same fake data. There is no time-series history, no model persistence, no evaluation.
2. **The telemetry pipeline is not wired.** Prometheus scrapes `/metrics` but the endpoint returns JSON (not the Prometheus text format). The ELK stack has security/auth misconfigurations that prevent it from starting or shipping logs as configured. The app never writes logs to the volume Logstash/Filebeat read.
3. **The dashboard and API return fabricated data** (hardcoded build status, test counts, log entries, pipeline status).
4. **The CI/CD deploy path is insecure** (`--insecure-skip-tls-verify`, 100-year service-account token) and the "anomaly detection" CI job cannot reach the app it pretends to monitor.

**Recommendation**: Do not "finish" the project by patching symptoms. Do a **phased revamp** that (a) makes the telemetry real, (b) makes anomaly detection real, (c) makes the dashboard real, and (d) hardens the delivery path — in that order. Phases are sized so the system remains deployable after each one.

---

## 2. Current State Assessment

### 2.1 What works today (verified)

| Area | Detail |
|---|---|
| Flask app | `/`, `/health`, `/metrics`, `/logs`, `/api/pipeline-status`, `/simulate-error` respond; health check does a real filesystem probe |
| Anomaly detector | `AnomalyDetector` trains an IsolationForest + StandardScaler and returns status/count/severity/recommendations |
| Alerts | `SlackAlerter` builds rich Slack payloads, severity color-coding, anomaly/pipeline/health alert types |
| Monitor | `CerebrOpsMonitor` orchestrates health check → metrics fetch → detection → alerting → periodic retrain; writes `logs/monitoring_results.jsonl` |
| Tests | 31 tests pass (`pytest tests/`), flake8 clean for the checked subset |
| Container/K8s | Multi-stage Dockerfile (non-root user, healthcheck, gunicorn), deployment+service+ingress, cronjobs, RBAC, PVCs |
| CI/CD | 6-job workflow: test → build → trivy scan → deploy → anomaly-detection → performance-test |
| Docs | 12+ markdown files (README, ops manual, deployment guide/checklist, API docs, quick guides) |

### 2.2 What is broken or non-functional

**Anomaly detection (the "AI" part)**
- `anomaly_detector.py::fetch_metrics_data()` returns `[response.json()]` — a **single point**. `detect_anomalies()` then reports an anomaly percentage of 0% or 100%, so severity thresholds (5/10/20%) never behave as intended.
- `train_model()` / `retrain_model()` train on `_generate_sample_data()` (seeded synthetic data, 100 normal + 10 anomalous rows). The model never learns from the system's real behavior; `monitor.py` even comments *"In production, pull historical data from a time-series DB"* — never implemented.
- Model is not persisted (no joblib/pickle), not versioned, and there is no way to evaluate accuracy, precision, or drift.
- `app.py` keeps a capped in-memory `metrics_data` list but the detector never reads it — the two halves of the system are disconnected.

**Telemetry & observability**
- `monitoring/prometheus.yml` scrapes `/metrics`, but `/metrics` returns JSON — Prometheus will reject the scrape (`INVALID`). Grafana is started in dev compose but has no datasource or dashboards provisioned.
- ELK stack as configured will not come up reliably: `xpack.security.enabled: true` in ES with `xpack.security.transport.ssl.enabled: false` (ES 8.x refuses this combination); Kibana config sets `xpack.security.enabled: false` and authenticates as `kibana_system` with `${ELASTIC_PASSWORD}` which is never provisioned; Logstash's ES output has no credentials.
- Logstash reads `/app/logs/*.log` from a named volume (`cerebrops_logs`) that the app (running in a *different* compose project / K8s) never writes to; Filebeat ships nothing meaningful. Dev compose has no Filebeat/Logstash at all.
- App logs are unstructured text; Logstash grok pattern expects JSON or a Flask-style timestamp the app doesn't emit (comma-milliseconds break `TIMESTAMP_ISO8601`).

**App & data**
- `docker-compose.dev.yml` mounts `./logging_config.py`, which does not exist → compose fails/creates a stray directory.
- `/logs` returns fabricated entries (always INFO); `/api/pipeline-status` and the dashboard's build status / test counts / recent logs are hardcoded.
- No persistence for metrics (in-memory only, capped at 100), no database despite `DATABASE_URL` in `.env.example`.
- Python `FileHandler` has no rotation → `logs/app.log` grows unbounded.

**CI/CD & security**
- Deploy job configures kubectl with `--insecure-skip-tls-verify=true` and a 100-year SA token stored in GitHub secrets. No OIDC/workload identity, no environment protection rules, no concurrency control.
- `anomaly-detection` job runs on a GitHub runner pointed at a URL it can't reach; on failure it **silently falls back to sample data** — the job always "passes" without monitoring anything.
- `performance-test` job pulls the stale `:latest` tag (runs on PRs too, where `latest` doesn't exist), installs k6 via apt on every run, and doesn't share the freshly built image.
- Image name `anshulbari/cerebrops` is hardcoded; tags are branch-sha only (no semver).
- No dependency-update automation (Dependabot/Renovate), no SBOM, no CodeQL on a schedule.

**Kubernetes**
- Docs claim auto-scaling, but there is no HPA manifest. No PodDisruptionBudget, no NetworkPolicy, no explicit `securityContext` on the deployment, no resource limits on the CronJob cleanup job.
- Ingress uses `cerebrops.local` + `letsencrypt-prod` cert-manager issuer, but cert-manager is never installed and the host isn't a real domain → TLS will never issue.

### 2.3 Docs claim vs. reality (summary)

| Documented feature | Reality |
|---|---|
| "AI anomaly detection with automatic retraining" | Trains/scored on synthetic data & single points; no real retraining |
| "Real-time metrics visualization dashboard" | Static HTML string with hardcoded values; no charts |
| "Complete ELK logging solution" | Config present but auth/volume wiring broken end-to-end |
| "Prometheus/Grafana monitoring" | Prometheus scrape invalid; no Grafana provisioning |
| "Auto-scaling support (HPA)" | No HPA manifest |
| "CI/CD pipeline with anomaly detection integration" | Detection job is unreachable theater |
| "Comprehensive test suite" | 31 unit tests, mostly mock-based; no end-to-end or infra tests |

---

## 3. Target Architecture (Revamp)

```
┌──────────────┐   ┌──────────────────┐   ┌─────────────────────┐
│ App (Flask)  │──▶│ /metrics (JSON)  │──▶│ Metric Repository   │
│ + worker     │   │ Prometheus /met  │   │ (SQLite dev /       │
│              │   │ structured JSON  │   │  Timescale prod)    │
└──────┬───────┘   │ logs to stdout   │   └──────────┬──────────┘
       │           └────────┬─────────┘              │
       │                    │                        ▼
       │              ┌─────▼──────┐        ┌──────────────────┐
       │              │ Filebeat   │        │ Anomaly Detector │
       │              │ (stdout)   │        │ (real history,   │
       │              └─────┬──────┘        │  persisted model,│
       │                    │               │  eval + drift)   │
       │                    ▼               └────────┬─────────┘
       │           ┌────────────────┐                │
       └──────────▶│ Grafana        │◀───────────────┘
                   │ (Prometheus +  │        ┌──────────────────┐
                   │  Loki/ES)      │        │ Slack Alerter    │
                   └────────────────┘        │ (+ dedupe,       │
                                             │  severity, ACK)  │
                                             └──────────────────┘
        Delivery: GitHub Actions (OIDC) → GHCR (semver) → GitOps/ArgoCD or kubectl (TLS verify)
        Ops: HPA, PDB, NetworkPolicy, securityContext, ExternalSecrets, runbooks
```

Design principles:
- **No fabricated data.** Every number on the dashboard must trace to a real measurement.
- **One source of truth for history**: a metric repository the app writes to and the detector reads from.
- **Ship logs as JSON to stdout** (12-factor) and let the collector (Filebeat) handle shipping — one compose project for app + observability so volumes/network actually connect.
- **Keep the ML stack simple and honest**: IsolationForest is fine to start; the win is real data + windows + persistence + evaluation, not a fancier model.
- **Secure-by-default delivery**: OIDC workload identity, TLS verification, short-lived credentials, GitOps-friendly.

---

## 4. Phased Roadmap

Each phase is independently shippable and leaves the system in a working state. Effort estimates assume one engineer.

### Phase 0 — Truth & Baseline (week 1)

**Goal**: Remove the fake data paths, add real metric capture and storage, and make the stack boot locally.

Tasks:
1. **Structured JSON logging**: replace `logging.basicConfig` in `app.py`/`monitor.py` with a JSON formatter (stdlib-only or `python-json-logger`) writing to stdout + rotating files (`RotatingFileHandler`). Ship `%s %s %s`-style messages as `{"ts","level","logger","msg","...context"}`.
2. **Metric repository**: introduce a `metrics_store.py` with a `MetricsStore` interface:
   - default SQLite implementation (zero-ops, works in dev and single-node prod);
   - schema: `metrics(id, ts, cpu, mem, disk, error_rate, req_count, resp_time, extra_json)` + `alerts` + `anomaly_runs` tables;
   - the Flask app records a row per request on `/metrics` and `/` (real request_count, response_time, error_rate from 5xx).
   - Keep the in-memory list only as a cache, or delete it.
3. **Real `/metrics`** (JSON API for humans/detector) **and** a Prometheus-native `/metrics-prom`** (text exposition via `prometheus_client`)**: counters for requests by route/status, histogram for latency, gauges for CPU/mem/disk. Update `monitoring/prometheus.yml` target accordingly.
4. **Delete dead wiring**: remove `./logging_config.py` mount from `docker-compose.dev.yml`; stop Logstash's file input (or fix volume sharing by making observability one compose project).
5. **ELK fix (dev-first)**: run the dev ELK profile with `xpack.security.enabled: false` (simplest correct config for local dev) and a single compose project that includes the app so logs actually flow; document the secured prod variant (below) separately.
6. **CI**: add a `concurrency` group; make the anomaly-detection job fail loudly instead of falling back to sample data (see Phase 4).

Deliverables: `metrics_store.py`, JSON logging, Prometheus endpoint, working dev compose with logs visible in Kibana, updated `.env.example`.
Acceptance criteria: `docker compose up` in one project brings up app + ES + Kibana + Filebeat; hitting `/` and `/metrics` produces real rows in SQLite and visible entries in Kibana; `promtool check metrics` passes on `/metrics-prom`.

### Phase 1 — Telemetry & Observability Pipeline (weeks 2–3)

**Goal**: Ship trustworthy metrics, logs, and dashboards end-to-end.

Tasks:
1. **Finish ELK for prod** (or swap): document + implement the secured path — ES with TLS certs generated via `elasticsearch-certutil`, passwords via `elasticsearch-setup-passwords`, CA mounted into Filebeat/Logstash/Kibana; or reduce footprint by replacing Logstash with Filebeat → ES directly (Logstash adds little here). Provide both a `compose.dev.yml` (insecure, fast) and `compose.prod.yml` (secure).
2. **Grafana provisioning**: datasources (Prometheus) and 3–4 dashboards (Overview, Resources, API Health, Anomalies) as JSON files in `monitoring/grafana/`, auto-loaded via provisioning dirs.
3. **Prometheus alerting rules**: `monitoring/alerts.yml` for SLO-ish alerts (error rate > threshold, p95 latency, pod down) routed to Slack via alertmanager (or keep Slack-only via app alerts; decide in Phase 6).
4. **Log-based anomaly features**: parse request logs into structured fields (route, status, latency) so the detector can consume per-route error rates from real data.
5. **Retention & rotation**: index lifecycle management (ILM) or curator/cron for ES; log rotation in app; retention config for SQLite.

Deliverables: working secured ELK or Filebeat→ES, provisioned Grafana dashboards, Prometheus alert rules.
Acceptance criteria: log a 500 via `/simulate-error` and see it in Kibana within 30s; Grafana shows real request/error/latency trends from live traffic; Prometheus alert rules evaluate without errors.

### Phase 2 — Real Anomaly Detection (weeks 3–5)

**Goal**: The detector becomes a genuinely useful, evaluated, persistent ML service.

Tasks:
1. **Windowed features**: detector reads the last N (e.g., 1,000) rows from `MetricsStore` instead of one live point; compute window features (rolling mean/std/slope, min/max, percentiles) per metric over multiple windows (15m, 1h, 24h).
2. **Real training pipeline**:
   - train on real history (≥ some minimum samples) with `train/test` split;
   - persist model + scaler with `joblib` to a versioned path (or SQLite BLOB), load at startup;
   - retrain trigger: time-based + drift-based (compare new window distribution to training distribution, e.g., PSI/KL divergence) — replacing the fixed 24h synthetic retrain;
   - `model_card` JSON: trained-at, n_samples, contamination, eval metrics (precision/recall on held-out labeled window), feature list.
3. **Detection semantics**: score the window, report anomaly *windows/points* with per-metric contribution (which feature drove the score); severity derived from score magnitude + number of anomalous metrics, not from a 1-point percentage.
4. **Alerting quality**: dedupe/cooldown in `SlackAlerter` (don't spam every 5-min cycle), aggregate into one digest per incident, add "resolve" notifications.
5. **Evaluation harness**: `scripts/evaluate_model.py` + a `tests/test_detector_integration.py` that injects known anomalies into the store and asserts detection; track precision/recall in CI.
6. **Optional stretch**: add a lightweight forecast baseline (e.g., EWMA or Holt-Winters; or `statsforecast` later) whose residual z-scores feed the IsolationForest — this gives *trend-aware* anomaly detection without deep learning.

Deliverables: `metrics_store`-backed training, persisted versioned models, drift-based retraining, deduped alerts, evaluation script.
Acceptance criteria: run monitor for 24h against real traffic; detector flags a deliberate injected anomaly (e.g., 95% CPU sustained 10 min) with severity ≥ high; no duplicate alerts for the same incident; precision/recall report generated in CI.

### Phase 3 — Product Dashboard & API (weeks 5–6)

**Goal**: The dashboard and API show real data and are usable by humans.

Tasks:
1. **Frontend**: shipped as a Flask-served SPA — `/` marketing landing (animated commit→production pipeline) + `/dashboard` app shell (sidebar, topbar, `⌘K` command palette, dark/light themes). Pages: Overview, Pipelines (filterable list + run detail with stage rail and searchable logs), Deployments, Anomalies (with deploy-correlated root cause), Alerts, Environments, Analytics (hand-rolled SVG charts), Settings. Real data via the v1 API; honest opt-in sample-data mode for empty stores.
2. **Real API v1**: `/api/v1/health`, `/api/v1/metrics?from&to&window`, `/api/v1/anomalies?limit`, `/api/v1/pipeline` (fed by a CI webhook or GH Actions status poll), with consistent error envelope and `X-Request-Id`. Mark old routes deprecated.
3. **Auth**: enforce `CEREBROPS_API_KEY` (already exists) across mutating/read endpoints behind a config flag; add basic UI login if deployed publicly.
4. **Pipeline integration**: add a `POST /api/v1/pipeline/events` webhook; GitHub Actions posts real run results (job, stage, status, duration, sha) after each deploy — replaces the hardcoded `pipeline-realtime` data.

Deliverables: real dashboard, v1 API, auth, pipeline event ingestion.
Acceptance criteria: dashboard charts reflect live metrics with 60s freshness; anomaly list matches `anomaly_runs` table; a CI run shows up on the Pipeline page; unauthenticated access to protected endpoints returns 401.

### Phase 4 — CI/CD & Kubernetes Hardening (weeks 6–8)

**Goal**: Secure, reproducible, GitOps-friendly delivery with real monitoring of the deployed system.

Tasks:
1. **OIDC + short-lived credentials**: replace `K8S_TOKEN` (100-year secret) with GitHub OIDC → cloud provider (AWS/GCP/Azure) or a short-lived token from a vault; remove `--insecure-skip-tls-verify`; pin cluster cert.
2. **CI workflow overhaul**:
   - semantic version tags (`type=semver`) + `latest` only on default branch;
   - pass image digest between jobs (artifact) instead of re-resolving `:latest`;
   - run k6 with a pinned version and against the just-built image; add threshold assertions;
   - anomaly-detection CI job: either delete it or make it a *real* canary check against the deployed env (with failure = red), never silent fallback;
   - add Dependabot/Renovate + scheduled CodeQL + SBOM (syft/trivy `--format spdx`) upload.
3. **GitOps option**: add `deploy/` manifests and ArgoCD app of apps (or keep kubectl with `kubectl diff` + approval gate). Keep `scripts/deploy.sh` as a fallback.
4. **K8s hardening**: HPA on CPU + custom metric, PodDisruptionBudget (minAvailable 1), NetworkPolicy (deny-by-default, allow ingress 80/5000 + egress ES), `securityContext` (runAsNonRoot, readOnlyRootFilesystem, capabilities drop), resource limits everywhere incl. cronjobs, `SealedSecret`/ExternalSecrets for slack webhook, cert-manager with a real domain + ClusterIssuer, remove the `cerebrops.local` placeholder.
5. **Environment protection**: branch protection, required status checks, environment rules (`main` = production with manual approval optional).

Deliverables: hardened workflow + manifests, GitOps app, secret management, HPA/PDB/NetworkPolicy.
Acceptance criteria: deploy runs entirely without long-lived secrets and verifies TLS; `kubectl apply` of the whole `deploy/` dir converges with no warnings; a rollback via ArgoCD (or `rollout undo`) is tested and documented; Trivy/SBOM reports uploaded per release.

### Phase 5 — Ops, Reliability & Advanced AI (weeks 8–12, ongoing)

> **Status**: all engineering items done ✅ — runbooks
> (`docs/runbooks/`, incl. restore + model evaluation), SLOs + burn alerts
> (`monitoring/prometheus-rules.yml`), forecast-residual detector
> (`forecast_detector.py`: median seasonal profile, small-sample scale
> correction, hard-threshold + neighbor debounce), deploy-correlated root
> cause (`root_cause.py`), backup automation (`scripts/backup.py` +
> `k8s/base/backup.yaml`), graceful degradation (store WAL/busy timeout +
> `_store_safe` route resilience), opt-in LLM summaries (`llm_summary.py`),
> multi-env promotion (`k8s/base` + `k8s/overlays/{dev,staging}` +
> `deploy/argocd-{dev,staging}.yaml` + `promote.yml` PR flow), and the
> evaluation harness (`scripts/evaluate_models.py`, v2: P/R/F1 1.0 on the
> labeled fixture). **Remaining (data-dependent)**: run the harness on
> ≥ 2 weeks of real production labels and record the report in the repo.

**Multi-env note**: manifests moved to `k8s/base/`; `k8s/` is now the prod
overlay (CI `kubectl apply -k k8s/` and ArgoCD `deploy/argocd.yaml` still
point at it). When ArgoCD takes over prod deploys, its `kustomize.images`
entry supersedes the CI digest rewrite — choose one delivery path per env.

**Goal**: Operate it for real; then push the AI further.

Tasks:
1. **Operations**: commit runbooks (`docs/runbooks/`) for incident response, rollback, restore from backup; automate backup of SQLite/ES; add on-call escalation to Slack; define SLOs and error budgets from Prometheus data.
2. **Reliability**: load test the collector path (k6 against app + ES ingestion); ensure the app degrades gracefully when ES/DB is down (circuit breaker, local buffer); add trace correlation (OpenTelemetry → Tempo/Jaeger) optional.
3. **Advanced AI (only after real data exists — otherwise it's more theater)**:
   - per-metric adaptive thresholds + seasonality (hour-of-day/weekday aware features already prepared in Phase 2);
   - forecast-residual detection (Prophet/StatsForecast or a small LSTM) once ≥ weeks of history exist;
   - root-cause suggestion: correlate anomaly with changed deploy (git SHA / config) — "this anomaly started after deploy X";
   - optional LLM-assisted summary of anomalies into Slack (only if the detection itself is trusted).
4. **Multi-environment**: dev/staging/prod namespaces with promoted image digests and per-env config.

Deliverables: runbooks, backup automation, SLOs, advanced model v2, multi-env promotion.
Acceptance criteria: incident drill executed from runbook < 30 min to mitigation; anomaly alerts include suspected deploy correlation; model v2 evaluated on ≥ 2 weeks real data with documented precision/recall vs. v1.

---

## 5. Quick Wins (can land immediately, low risk)

1. Remove the `./logging_config.py` mount from `docker-compose.dev.yml`.
2. Make `fetch_metrics_data()` return the *last N* points from a store (or at minimum batch multiple polls) and change `detect_anomalies` to require ≥ 2 windows — stops the 0%/100% silliness even before the store exists.
3. Delete the silent fallback to `_generate_sample_data()` in `fetch_metrics_data()` and fail loudly (log + alert).
4. Add `concurrency` + `permissions` to the workflow; make `performance-test` consume the built image digest.
5. Swap `log_levels[0]` fabrication in `/logs` for the last N real log lines.
6. Add `RotatingFileHandler` to app logging.
7. Add a `Makefile`/`task` with `make test`, `make lint`, `make up`, `make seed-demo` (a *labeled* demo dataset script, kept explicitly separate from real detection).

---

## 6. Decisions Needed (owner + input)

| # | Decision | Options | Suggested |
|---|---|---|---|
| D1 | History store | SQLite → TimescaleDB/Postgres; or read from Prometheus HTTP API | SQLite first; Timescale when multi-node |
| D2 | Log pipeline | Fix full ELK (ES+LS+KB+FB) vs. slim (Filebeat→ES or Loki+Grafana) | Dev: insecure ELK; prod: Filebeat→ES or Loki (lower ops) |
| D3 | Delivery model | kubectl from Actions vs. ArgoCD GitOps | GitOps (ArgoCD) for prod |
| D4 | Frontend | Server-rendered + Chart.js vs. React SPA | Server-rendered + Chart.js (no node build) |
| D5 | Advanced model timeline | IsolationForest-only vs. forecast-residual vs. deep learning | Forecast-residual (statsforecast) at Phase 5 |
| D6 | Public vs. private | Is dashboard internet-facing? determines auth & ingress strategy | Private + VPN/SSO if public |

---

## 7. Definition of Done / Success Metrics

- **No fabricated data anywhere**: every endpoint value traces to a measurement, a webhook, or an explicit `seed-demo` script.
- **Anomaly detection is evaluated**: precision/recall report generated from real data in CI; retraining is data-driven (time + drift), not synthetic.
- **Observability works end-to-end**: a 500 error appears in Grafana/Kibana within 30s of occurring; alert fires once per incident (deduped).
- **Delivery is secure**: zero long-lived secrets in CI; TLS verified; releases are semver-tagged with SBOM.
- **Recovery is practiced**: restore-from-backup drill executed and documented.
- **K8s is production-grade**: HPA, PDB, NetworkPolicy, securityContext, ExternalSecrets applied and validated by `kubeconform`/`polaris` in CI.
- **Test suite grows with reality**: ≥ 1 integration test per data path (store→detector→alerter), coverage enforced ≥ 80% on core modules.

---

## 8. Suggested Timeline

```
Week 1       Phase 0 — Truth & Baseline          (no fake data, logs flow, store exists)
Weeks 2–3    Phase 1 — Telemetry & Dashboards    (Grafana/Prometheus/ELK real)
Weeks 3–5    Phase 2 — Real Anomaly Detection    (windowed, persisted, evaluated)
Weeks 5–6    Phase 3 — Product Dashboard & API   (real UI + v1 API + auth)
Weeks 6–8    Phase 4 — CI/CD & K8s Hardening     (OIDC, GitOps, HPA/PDB/NetPol)
Weeks 8–12+  Phase 5 — Ops, Reliability, AI v2   (runbooks, SLOs, forecast-residual)
```

Phases 0–3 are the critical path to "the AI actually works." Phase 4 makes it safe to run for real. Phase 5 is where the project becomes genuinely differentiating — but only because the earlier phases made its inputs trustworthy.

---

## Appendix — Files most impacted by each phase

| Phase | Primary files |
|---|---|
| 0 | `app.py`, `monitor.py`, new `metrics_store.py`, `docker-compose.dev.yml`, `elk/*`, `monitoring/prometheus.yml`, `.github/workflows/ci-cd.yml` |
| 1 | `elk/*`, `monitoring/grafana/*`, `monitoring/alerts.yml`, `requirements.txt` |
| 2 | `anomaly_detector.py`, `monitor.py`, new `model_card`/eval scripts, `tests/test_detector_integration.py`, `alerts.py` |
| 3 | `app.py`, new `templates/` + `static/`, `API_DOCUMENTATION.md`, `k8s/deployment.yaml` (auth env) |
| 4 | `.github/workflows/ci-cd.yml`, `k8s/*`, `deploy/` (new), `scripts/deploy.sh`, `GITHUB_SETUP.md` |
| 5 | `docs/runbooks/*` (new), `monitor.py`, `anomaly_detector.py`, `k8s/` (multi-env) |
