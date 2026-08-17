# CerebrOps — The Whole Project, Explained

> A beginner-friendly tour of **what problem we're solving**, **how we chose to solve it**, and **how every piece of the project actually works**.

If you just cloned this repository and feel overwhelmed, start here. By the end of this document you should be able to explain CerebrOps to someone else in plain English, and find your way around the codebase without a map.

---

## Table of contents

1. [The problem](#1-the-problem)
2. [Our approach](#2-our-approach)
3. [What CerebrOps is, in one sentence](#3-what-cerebrops-is-in-one-sentence)
4. [The big picture (architecture)](#4-the-big-picture-architecture)
5. [Technology stack](#5-technology-stack)
6. [The core workflow, step by step](#6-the-core-workflow-step-by-step)
7. [The two "AI" detectors](#7-the-two-ai-detectors)
8. [The web interface](#8-the-web-interface)
9. [The API](#9-the-api)
10. [Security](#10-security)
11. [Observing the observer (Prometheus, Grafana, ELK, SLOs)](#11-observing-the-observer)
12. [Deployment & CI/CD](#12-deployment--cicd)
13. [The roadmap: how the project was built in phases](#13-the-roadmap)
14. [Testing](#14-testing)
15. [Map of the repository](#15-map-of-the-repository)
16. [Running it locally](#16-running-it-locally)
17. [What is genuinely still left to do](#17-what-is-genuinely-still-left-to-do)
18. [Glossary for beginners](#18-glossary-for-beginners)

---

## 1. The problem

Software teams ship code through a **pipeline**: the code is checked out, built, tested, scanned for security issues, deployed, and finally lands in production. This is called **CI/CD** (Continuous Integration / Continuous Deployment).

Here's what goes wrong in the real world:

- **Pipelines fail and nobody notices for hours.** A build breaks at 3am and the team finds out from a customer complaint.
- **Deploys cause regressions.** New code ships, and suddenly error rates climb — but is the deploy the cause, or is something else going on? The data needed to answer that is scattered across five different tools.
- **Alerts are noise without context.** "CPU is high!" — high compared to *what*? Is this normal for a Tuesday morning, or genuinely wrong? Did anything just change?
- **Dashboards lie.** Many monitoring tools ship with fake/sample data baked in, or give you charts that look alive but have nothing to do with your actual system.
- **Detection is a blunt instrument.** A simple "is the value above 90%?" rule produces false alarms and misses the subtle problems — like a slow drift that only matters relative to *expected* seasonality.

The core problem CerebrOps targets is this: **teams need to know, in minutes, when a deploy or a code change broke something — with the context to fix it — using only their real data.**

---

## 2. Our approach

We made four deliberate design decisions that shape the entire project:

### 2.1 Real data only — no fabrication

Every number on the dashboard comes from one of two places:

1. **The webhook ingestion path** — your CI/CD system (GitHub Actions, Jenkins, etc.) POSTs pipeline run results to CerebrOps as they happen.
2. **The metrics store** — a SQLite database that holds every metric row the system has ever collected.

There is a *demo mode* (you can flip it on to explore the UI), but it is explicitly labeled **"sample data · local demo"** — and the AI detectors never train on it. If the store is empty, the UI honestly shows you empty states plus a "connect your pipeline" card with a copyable curl command, instead of pretending there's data.

### 2.2 AI that is honest about what it knows

Two anomaly detectors work side by side:

- **v1 — Isolation Forest**: an unsupervised machine-learning model that learns "what normal looks like" from rolling statistics (averages, trends, spread over 15 minutes / 1 hour / 24 hours) and flags points that don't fit.
- **v2 — Forecast-residual**: a simpler but often more accurate seasonal model that learns each metric's *expected* pattern by hour-of-week and flags deviations from that expectation (e.g., "this CPU spike is 42 standard deviations above what we'd expect at 8pm on a Wednesday").

v2 only activates after **at least 7 days of real stored history** — until then it honestly reports `insufficient_data` and falls back to v1. No synthetic training data, ever.

### 2.3 Alerts with a story, not just a number

When an anomaly is detected, CerebrOps doesn't just say "CPU is high." It:

1. Detects the anomaly (which method, how severe, which metrics contributed).
2. Checks whether any **recent deploy** lines up with the anomaly (root-cause correlation).
3. Optionally asks an LLM to write a one-paragraph plain-English summary.
4. Sends the whole package to Slack.

So the alert reads like: *"forecast-residual detected 3 anomalies driven by cpu_usage (42.3σ). This correlates with deploy run-987 (main@deadbeef) which completed 1.1m before the spike."*

### 2.4 Self-hosted and production-shaped from day one

CerebrOps is built to run **inside your own cluster**: Kubernetes manifests with kustomize overlays (dev/staging/prod), Horizontal Pod Autoscaling, Pod Disruption Budgets, NetworkPolicies, least-privilege security contexts, External Secrets, ArgoCD GitOps, OIDC short-lived credentials, SBOMs, backups, and runbooks. It also ships its own observability (Prometheus metrics, Grafana dashboards, and an ELK log pipeline) so you can watch CerebrOps watching your pipelines.

---

## 3. What CerebrOps is, in one sentence

> **CerebrOps is a self-hosted, AI-assisted CI/CD observability platform: your pipeline events and server metrics go in, and a live dashboard, honest anomaly detection, deploy-correlated root causes, and contextual Slack alerts come out — built only on your real data.**

---

## 4. The big picture (architecture)

Here is the whole system as a diagram you can read top to bottom:

```text
                            YOUR CI/CD SYSTEM (GitHub Actions, Jenkins, ...)
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │ pipeline run events (webhook) │  server metrics (CPU, memory…)  │
        ▼                               ▼                                ▼
┌───────────────────┐          ┌────────────────────┐          ┌──────────────────┐
│   /api/v1/        │          │  monitor.py        │          │  Prometheus      │
│   pipeline/events │          │  (periodic loop)   │          │  scrape of       │
│   (Flask webhook) │          │  collects + checks │          │  /metrics-prom   │
└─────────┬─────────┘          └─────────┬──────────┘          └────────┬─────────┘
          │                             │                               │
          ▼                             ▼                               ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                        metrics_store.py  (SQLite)                              │
│   metrics │ alerts │ anomaly_runs │ pipeline_events │ users │ login attempts  │
└───────┬───────────────────────────┬───────────────────────────┬───────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌──────────────┐          ┌──────────────────────┐     ┌──────────────────────┐
│ Flask app.py │          │  anomaly_detector.py │     │  root_cause.py       │
│ serves the   │          │  (Isolation Forest)  │     │  deploy correlation  │
│ dashboard +  │          │  forecast_detector.py│     │  + llm_summary.py    │
│ JSON API     │          │  (seasonal forecast) │     │  (optional summary)  │
└──────┬───────┘          └──────────┬───────────┘     └──────────┬───────────┘
       │                            │                             │
       │                            ▼                             ▼
       │                     ┌────────────────┐           ┌────────────────┐
       │                     │ alerts.py      │           │ Slack alert    │
       │                     │ SlackAlerter   │──────────▶│ (with context) │
       │                     └────────────────┘           └────────────────┘
       ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (Flask templates + vanilla JS, mobile-first)                        │
│  /          landing page (video hero, animations)                             │
│  /experience  cinematic Three.js product page                                  │
│  /dashboard   the SPA: Overview, Pipelines, Deploys, Anomalies, Alerts,        │
│               Environments, Analytics, Settings  (hash routing: #/pipelines)   │
│  /login /register /forgot-password /reset-password                             │
└───────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────────┐
│  DEPLOYMENT & OBSERVABILITY                                                   │
│  Dockerfile → GitHub Actions (tests, scan, SBOM, validate, deploy via OIDC)   │
│  k8s/base + overlays (dev/staging/prod) → ArgoCD, HPA, PDB, NetPol, backups   │
│  ELK: Filebeat → Logstash → Elasticsearch → Kibana   (structured JSON logs)   │
│  Grafana: cerebrops-overview + cerebrops-http dashboards on Prometheus        │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Technology stack

| Layer | Technology | Why it was chosen |
|---|---|---|
| Backend framework | **Flask** (Python) | Tiny, battle-tested, zero magic; the whole app is one readable `app.py` plus focused modules |
| Data store | **SQLite** (single file) | No database server to run; perfect for a self-hosted tool; online-backup API for safe snapshots |
| ML / data | **scikit-learn, numpy, pandas, joblib** | Isolation Forest, feature engineering, and model persistence that survives restarts |
| Metrics (Prometheus format) | **prometheus-client** | One line per metric; scraped by Prometheus for Grafana |
| Frontend | **Flask templates + vanilla JavaScript** | No build step, no framework churn; vendored **Chart.js** (charts) and **Three.js** (the cinematic product page) |
| Fonts / design | **Space Grotesk, Instrument Serif (italic), JetBrains Mono** | Technical-but-alive typography, editorial italic accents, mono for anything machine-ish |
| Logging | **Python `logging` → structured JSON, rotated** | Machine-readable logs that Filebeat can ship to Elasticsearch |
| Log pipeline | **Filebeat → Logstash → Elasticsearch → Kibana** (ELK 8.9) | End-to-end "find the log line for this request" capability |
| Metrics dashboards | **Prometheus + Grafana** (provisioned from JSON files) | Standard, self-hosted, declarative dashboards |
| Container | **Docker** (slim Python image, non-root) | Reproducible deploys |
| Orchestration | **Kubernetes + kustomize** (base/overlays) | One manifest set, three environments (dev/staging/prod) |
| CI/CD | **GitHub Actions** | Tests, image build, Trivy security scan, SBOM, kubeconform + polaris manifest validation, OIDC deploy, smoke tests |
| GitOps | **ArgoCD** (optional) | Declarative "the cluster converges to this repo" |
| Alerts | **Slack webhooks** | Where developers already are |

---

## 6. The core workflow, step by step

Let's follow one deploy through the whole system.

### Step 1 — The webhook lands a pipeline event

Your CI system (or you, manually) POSTs to:

```text
POST /api/v1/pipeline/events
Content-Type: application/json

{
  "pipeline_id": "run-1842",
  "status": "success",        // success | failed | running | cancelled
  "stage": "deploy",          // checkout | build | test | security | deploy
  "duration": 42,
  "branch": "main",
  "commit_hash": "9f8a2c1",
  "source": "github-actions"
}
```

`app.py` validates it, and `metrics_store.py` writes a row into the `pipeline_events` table. That's it — the dashboard now knows about the run.

### Step 2 — The dashboard shows it

The frontend (a single-page app in `static/js/app.js`) fetches the real data through the `/api/v1/*` endpoints and renders:

- **Overview** — a cinematic pipeline hero (an animated rail through Checkout → Build → Tests → Security → Deploy → ★Production) with status pills, plus stat tiles and panels for recent pipelines, anomalies, activity, and alerts.
- **Pipelines** — an editorial gallery of runs, each with a mini-rail preview, status/hash/duration pills, filters and search.
- **Pipeline detail** — the hero, a sticky run header, run facts, and a terminal-style log viewer.
- **Deployments, Anomalies (with root-cause hypotheses), Alerts, Environments, Analytics, Settings.**

Every page reads only from the store. Empty store → honest empty states with a connect card.

### Step 3 — The monitor watches

`monitor.py` runs on a schedule (default every 60 seconds). Each cycle it:

1. **Collects metrics** — CPU, memory, disk, error rate, request count, response time — and stores them (`metrics_store.record_metrics`).
2. **Checks application health** — hits the app's `/health` endpoint.
3. **Decides whether the model needs retraining** — using a drift metric (Population Stability Index) instead of a fixed timer.
4. **Runs anomaly detection** on the most recent window of stored metrics.
5. If anomalies are found → **root-cause correlation** (was there a deploy in the last N minutes? which metrics shifted?) → optional **LLM summary** → **Slack alert** with the full story.
6. Records the anomaly run and any alert in the store.

### Step 4 — Detection actually works

The detector reads a window of *real stored history* (15m / 1h / 24h rolling features for v1; hour-of-week seasonal profiles for v2). No synthetic data, ever. v2 explicitly reports `insufficient_data` until 7 days of history exist.

### Step 5 — The alert arrives with context

The Slack message includes the detection method, severity, top contributing metrics with their deviation strength, the correlated deploy (if any), the shifted metrics, and a plain-language hypothesis — exactly the "story, not a number" goal from §2.3.

### Step 6 — Everything is observable

- The app exposes Prometheus metrics at `/metrics-prom` (request counts, durations, CPU/memory gauges) → Grafana dashboards.
- Every request is logged as a structured JSON line with a request id → Filebeat → Elasticsearch → Kibana.
- SLOs (99.9% availability, p95 < 500ms) and burn-rate alerts are defined in `monitoring/prometheus-rules.yml`, with runbooks in `docs/runbooks/`.

---

## 7. The two "AI" detectors

### v1 — Isolation Forest (`anomaly_detector.py`)

- **What it is:** an unsupervised ensemble that isolates outliers instead of modeling the normal data — think "how easy is it to separate this point from everything else with random cuts."
- **Features:** for every metric, rolling **mean / std / slope / min / max** over **15m / 1h / 24h** windows. So the model doesn't look at raw values — it looks at *recent behavior and trends*.
- **Persistence:** trained models are saved with **joblib**, along with a **versioned model card** (JSON with training time, data range, feature list) and a `current_version` pointer. A failed or bad retrain can be rolled back.
- **Retraining:** **drift-based** — the monitor compares the live metric distribution to the training baseline (Population Stability Index) and retrains only when the world has genuinely changed. No more "retrain every 24h regardless."

### v2 — Forecast-residual (`forecast_detector.py`)

- **What it is:** a **seasonal-naive forecast**. For each metric it builds a per-hour-of-week expectation profile from real history, then scores each new point by how far it deviates (a z-score) from what's expected *at that moment of the week*.
- **Why:** "CPU at 70%" might be alarming at 3am and completely normal at 8pm. v2 catches *contextual* anomalies — and it's pure numpy, so it has no heavy dependencies.
- **Honesty rule:** requires `>= 7 days` of real stored metrics before it activates; otherwise it reports `insufficient_data` and the monitor falls back to the persisted v1 model.

### How they're evaluated (`scripts/evaluate_models.py`)

Both detectors are compared on **labeled data** with point-level **precision / recall / F1**. The harness ships with:

- `--generate` — a synthetic labeled dataset with known injected anomalies (used by tests and dry runs).
- `--self-check` — a CI gate: runs the harness on the deterministic synthetic set and fails the build if detection quality drops below thresholds (v2 recall ≥ 0.8, precision ≥ 0.4, f1 ≥ 0.5). This proves the harness itself never rots.
- `--labels file.jsonl` — the real acceptance path: point it at **≥ 2 weeks of real production data** with human-labeled anomalies. That number is the true measure of "does detection actually catch regressions."

---

## 8. The web interface

### Pages

| Route | What it is |
|---|---|
| `/` | **Landing page** — video hero background, animated pipeline card, scroll-triggered word animations, developer credit in the footer |
| `/experience` | **Cinematic product page** — a Three.js particle world behind three tabs (Pipeline / Detection / Observability), sticky Early Access banner with live countdown, FAQ accordion, bottom nav |
| `/dashboard` | **The product** — a single-page app with hash routing (`#/overview`, `#/pipelines`, `#/pipeline/42`, `#/deployments`, `#/anomalies`, `#/alerts`, `#/environments`, `#/analytics`, `#/settings`) |
| `/login`, `/register`, `/forgot-password`, `/reset-password` | **Auth pages** in the same design language |

### Design language

Dark, dimensional near-black surfaces; pill-shaped metadata and buttons; mono type for hashes/ids/timestamps; serif-italic accents on the voice moments ("Ship code without *the ceremony.*"); a cinematic pipeline hero whose rail animates through the six stages; a mobile bottom nav with a glowing gradient FAB; reveal-on-scroll animations that respect `prefers-reduced-motion`.

### The empty-state connect card

If the store has no pipeline events, the Overview hero shows a **webhook card** with the exact curl command to send, a copy button, and a "Load sample data" button. The product is never *silently* empty.

---

## 9. The API

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness/readiness for Kubernetes |
| `/metrics` | GET | Legacy JSON metrics summary |
| `/metrics-prom` | GET | Prometheus-format metrics (scrape target) |
| `/logs` | GET | Recent structured logs |
| `/api/v1/health` | GET | API health |
| `/api/v1/metrics` | GET | Stored metric series |
| `/api/v1/anomalies` | GET | Anomaly runs (with root-cause hypotheses) |
| `/api/v1/alerts` | GET | Alerts |
| `/api/v1/pipeline` | GET | Recent pipeline events |
| `/api/v1/pipeline/events` | POST | **Webhook ingestion** — the main data entry point |

The API surface is protected by an optional `X-API-Key` header (set `CEREBROPS_API_KEY`), so CI systems and scrapers never need a browser login.

---

## 10. Security

| Area | Implementation |
|---|---|
| Dashboard auth | Session-based: `/login`, `/register`, `/logout`, `/forgot-password`, `/reset-password` |
| Brute-force protection | Email lockout after **5 failed attempts / 15 minutes** (SQLite-backed) + a per-IP ceiling on the login form |
| Password reset | Single-use, **30-minute**, SHA-256-hashed tokens; account enumeration prevented (same message for known/unknown emails); link logged server-side and shown on-page in dev |
| Session signing | `CEREBROPS_SECRET_KEY` — the app **refuses to start in production** without it (no public dev fallback); k8s injects it from a secret created once and never rotated |
| Password hashing | `werkzeug` (PBKDF2) hashes |
| API security | Key-based (`X-API-Key`) for `/api/v1/*` and webhooks; CI/scrapers need no session |
| Container | Non-root user, read-only root filesystem, dropped capabilities |
| Cluster | NetworkPolicies (default-deny), Pod Disruption Budgets, least-privilege RBAC, security contexts on every workload, External Secrets + cert-manager (operator-gated) |

---

## 11. Observing the observer

- **Prometheus** (`monitoring/prometheus.yml`) scrapes `/metrics-prom`.
- **Grafana** (`monitoring/grafana/`) is provisioned from JSON: `cerebrops-overview` (resources, request rate, error rate, p95) and `cerebrops-http` (by route/status).
- **SLOs & burn rate** (`monitoring/prometheus-rules.yml`): 99.9% availability, p95 < 500ms, error-rate guardrail; burn-rate alerts mapped to runbooks.
- **ELK** (`elk/`): the app writes **structured JSON logs with rotation**; Filebeat ships them to Elasticsearch via Logstash; Kibana serves a `cerebrops-logs-*` data view. A dev profile runs with security disabled for local testing.
- **`scripts/verify-observability.sh`**: validates the compose files, and (when the Docker daemon is up) boots the stack and proves a request-id'd log line reaches Elasticsearch within 30 seconds.

---

## 12. Deployment & CI/CD

### The GitHub Actions pipeline (`.github/workflows/ci-cd.yml`)

```text
test ──────────────┐
build ─────────────┼──▶ deploy (main branch only, via OIDC)
security-scan ─────┼──▶   • ensure session secret exists
validate-manifests ┘      • kubectl apply -k k8s/
                          • rollout status + smoke tests
```

| Job | What it does |
|---|---|
| `test` | flake8 + pytest with coverage |
| `build` | Build + push the Docker image, cache with buildx, record the image digest |
| `security-scan` | Trivy vulnerability scan (SARIF), SBOM generation (SPDX), uploads to GitHub Security |
| `validate-manifests` | Renders all kustomize overlays → **kubeconform** strict schema check (k8s 1.29) → **polaris** security audit (fail on danger / score < 90) |
| `deploy` | OIDC short-lived AWS credentials (no long-lived tokens), sets the image digest, ensures the session secret exists (created once, never rotated), `kubectl apply -k`, smoke tests, reports a pipeline event back to the webhook + Slack |

### Kubernetes

- `k8s/base/` — namespace, deployment, cronjobs (anomaly detection, backup, log cleanup), backup Job, persistent volume, secrets, RBAC, HPA, PDB, NetworkPolicies; `cert-manager` and `external-secrets` are optional operator-gated resources.
- `k8s/overlays/{dev,staging}` — tuned copies of the base (namespace, replicas, ingress host, image tag).
- `deploy/` — ArgoCD applications (dev/staging/prod) for GitOps.
- Backups: `scripts/backup.py` takes consistent SQLite snapshots + copies persisted models with a manifest, prunes by retention; `scripts/restore_drill.py` proves the restore path quarterly (backup → restore to scratch → verify integrity, row counts, model loadability).

---

## 13. The roadmap

The project was built in phases; each one left the system genuinely more complete:

| Phase | Delivered |
|---|---|
| **0 — Foundation** | SQLite `MetricsStore`, structured JSON logging with rotation, Prometheus-format `/metrics-prom`, removed all fabricated data paths |
| **1 — Observability** | ELK stack boots and ships the JSON logs end-to-end (dev profile, Filebeat reading app stdout); Grafana datasources + dashboards provisioned from JSON |
| **2 — AI v2** | Windowed feature engineering (rolling mean/std/slope over 15m/1h/24h), joblib model persistence with versioned model cards, drift-based retraining replacing the fixed 24h timer |
| **3 — Product** | Real frontend dashboard, v1 API, auth, webhook ingestion replacing hardcoded status |
| **4 — CI/CD & K8s** | OIDC short-lived credentials, semver + SBOM, ArgoCD GitOps, HPA / PDB / NetworkPolicy / securityContext / ExternalSecrets |
| **5 — Ops & AI v2.5** | Runbooks, SLOs, forecast-residual detection, deploy-correlated root cause, backup automation, graceful degradation when ES is down, LLM-assisted summaries, multi-env promotion, precision/recall evaluation harness |

---

## 14. Testing

- **135 tests** (`tests/`) covering the app, auth (login/register/logout/lockout/reset), the store, both detectors, model repository, monitor, alerts, root cause, LLM summaries, forecast detector, backup, restore drill, evaluation harness, SLO rules, and the frontend routes.
- **CI gates**: flake8, pytest with coverage, Trivy, kubeconform, polaris, and the `--self-check` detection-quality gate.
- **Frontend checks**: `node --check` on all JS files; live browser verification of every page, the Three.js scenes, the countdown, accordions, reveals, and the auth flow.

---

## 15. Map of the repository

```text
CerebrOps/
├── app.py                 # Flask app: routes, auth, API, dashboard shell
├── metrics_store.py       # SQLite store (metrics, alerts, runs, events, users)
├── anomaly_detector.py    # v1: IsolationForest + features + drift retraining
├── forecast_detector.py   # v2: seasonal-naive forecast-residual (pure numpy)
├── model_repository.py    # joblib persistence + versioned model cards
├── monitor.py             # the periodic monitoring loop (collect → detect → alert)
├── root_cause.py          # deploy correlation for anomalies
├── llm_summary.py         # optional LLM summaries (mock mode for offline testing)
├── alerts.py              # SlackAlerter
├── logging_config.py      # structured JSON logs + rotation
├── templates/             # landing, experience, dashboard, auth pages
├── static/
│   ├── css/               # tokens, base, app, landing, experience, auth
│   ├── js/                # app.js (dashboard SPA), landing.js, experience.js
│   └── vendor/            # chart.umd.min.js, three.min.js (no build step)
├── scripts/
│   ├── backup.py          # consistent SQLite snapshot + models + manifest
│   ├── restore_drill.py   # quarterly restore verification
│   ├── evaluate_models.py # precision/recall/F1 harness + --self-check gate
│   ├── verify-observability.sh  # ELK/Grafana e2e verification
│   ├── deploy.sh, setup.sh, smoke-tests.sh, setup-cicd.ps1, github-setup.ps1
├── k8s/                   # base manifests + overlays (dev/staging/prod)
├── deploy/                # ArgoCD applications
├── elk/                   # Elasticsearch/Logstash/Kibana/Filebeat configs
├── monitoring/            # Prometheus + Grafana provisioning + SLO rules
├── docs/runbooks/         # incident-response, restore, model-eval, SLO burn…
├── tests/                 # 135 tests
├── .github/workflows/     # ci-cd.yml, codeql.yml, promote.yml, dependabot.yml
├── data/  logs/  models/  # runtime state (gitignored): store, logs, models
└── Dockerfile, docker-compose.dev.yml, requirements.txt
```

---

## 16. Running it locally

```bash
# 1. Create a virtualenv and install dependencies
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

# 2. Run the app (dev fallback secret is fine locally)
.venv/Scripts/python -c "from app import app; app.run(host='127.0.0.1', port=5001)"

# 3. Open http://127.0.0.1:5001  → landing page
#    http://127.0.0.1:5001/register → create an account
#    http://127.0.0.1:5001/dashboard → the product

# 4. Feed it a real pipeline event:
curl -s -X POST http://127.0.0.1:5001/api/v1/pipeline/events \
  -H 'Content-Type: application/json' \
  -d '{"pipeline_id":"run-1","status":"success","stage":"deploy","branch":"main"}'

# 5. Watch the monitor run detection:
.venv/Scripts/python -m monitor --app-url http://127.0.0.1:5001

# 6. Run the checks:
.venv/Scripts/python -m pytest tests/ -q
.venv/Scripts/python -m flake8 app.py metrics_store.py monitor.py alerts.py anomaly_detector.py forecast_detector.py root_cause.py llm_summary.py logging_config.py model_repository.py
node --check static/js/app.js
```

---

## 17. What is genuinely still left to do

Being honest about it — these are the gaps between "build complete" and "production-proven":

1. **Precision/recall on real data** — the harness is proven (`--self-check`), but the meaningful number requires **≥ 2 weeks of real production traffic** with human-labeled anomalies. Only time in production provides that.
2. **Live cluster apply** — manifests pass kubeconform + polaris, but nobody has applied them to a real cluster with real operators (cert-manager, External Secrets, ArgoCD) yet. A real apply is the final proof.
3. **Live ELK/Grafana e2e** — configs are complete and `verify-observability.sh` is ready, but the "log line appears in Kibana within 30s" test still needs a running Docker daemon / stack.
4. **LLM against a real endpoint** — the attach path is proven with a deterministic mock; a real OpenAI-compatible endpoint hasn't been exercised.
5. **Auth hardening beyond basics** — lockout + reset exist; password reset via a real email/webhook sender and Argon2 hashing are natural next steps.

---

## 18. Glossary for beginners

| Term | Meaning |
|---|---|
| **CI/CD** | Automatically building, testing, and deploying code whenever it changes |
| **Pipeline** | The sequence of stages code passes through: checkout → build → test → security → deploy → production |
| **Webhook** | An HTTP POST your CI system sends to tell CerebrOps "a run just finished" |
| **Metric** | A number measured over time (CPU %, error rate, response time) |
| **Anomaly** | A data point that doesn't fit what history says is normal |
| **Isolation Forest** | An ML algorithm that finds outliers by how easily they can be separated |
| **Forecast-residual** | Detecting anomalies by comparing reality against an expected seasonal forecast |
| **Feature engineering** | Turning raw values into more useful signals (rolling averages, trends, spread) |
| **Drift** | When the live data's distribution stops matching the training data's — a signal it's time to retrain |
| **Model card** | A JSON file describing a trained model: when, on what data, with what features |
| **Precision / Recall / F1** | Precision = "of what we flagged, how much was real?" Recall = "of the real problems, how many did we catch?" F1 = their harmonic mean |
| **SBOM** | Software Bill of Materials — a list of every dependency and version in the image |
| **OIDC** | OpenID Connect — short-lived cloud credentials from the CI platform, no long-lived tokens |
| **Kustomize** | Kubernetes manifest templating: a base + per-environment overlays |
| **HPA / PDB / NetworkPolicy** | Auto-scaling / availability guarantees / network access control in Kubernetes |
| **GitOps (ArgoCD)** | The cluster continuously converges to match the manifests in your git repo |
| **SLO / burn rate** | Service Level Objective (e.g. 99.9% availability) and how fast you're spending its error budget |
| **Structured JSON logs** | Logs as JSON objects with fields (level, request_id, route) — machine-queryable |

---

*That's the whole story: a self-hosted, AI-assisted CI/CD observability platform that only ever speaks from real data — with an honest, production-shaped design so the gap between "demo" and "running in your cluster" is as small as possible.*
