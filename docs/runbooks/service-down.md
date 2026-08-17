# Service Down / Capacity

Fired by `CerebrOpsDown`, `CerebrOpsHighCPU`, `CerebrOpsDiskPressure`.

## App unreachable (`CerebrOpsDown`)

Prometheus cannot scrape `/metrics-prom` for 1 minute.

1. **Is it a scrape or the app?**
   ```bash
   curl -sf http://localhost:5000/health          # local dev
   kubectl get pods -n cerebrops -l app=cerebrops
   kubectl rollout status deployment/cerebrops-app -n cerebrops
   ```
2. **Check the deployment**: `kubectl describe deployment cerebrops-app -n
   cerebrops` — look for `CrashLoopBackOff`, image pull errors, OOMKilled
   (limit is 512Mi), or a bad digest.
3. **Logs**:
   ```bash
   kubectl logs deployment/cerebrops-app -n cerebrops --tail=200 --previous
   ```
4. **Rollback** if a recent deploy is the cause:
   ```bash
   kubectl rollout undo deployment/cerebrops-app -n cerebrops
   # or with ArgoCD: sync the Application to the previous revision
   ```
5. **Restore the scrape**: confirm `/metrics-prom` answers, then watch
   `CerebrOpsDown` clear.

## High CPU / memory

1. **Is it the app or the host?** The gauge `cerebrops_cpu_usage_percent` is
   the *host*; check pod-level usage too:
   ```bash
   kubectl top pods -n cerebrops
   ```
2. **Scale out**: HPA (2–6 replicas, CPU 70%) should act on its own; verify
   `kubectl get hpa cerebrops-hpa -n cerebrops`.
3. **Memory**: a sustained climb points at a leak in the Flask app or the
   SQLite connection handling; check `logs/app.log` for repeated errors and
   the anomaly alert for `memory_usage` contributions.

## Disk pressure (`CerebrOpsDiskPressure`)

The SQLite store (`data/cerebrops.db`) and logs share this volume. It filling
**will** cause 5xx and silent metric loss — treat as critical.

1. Check usage and top consumers:
   ```bash
   kubectl get pvc -n cerebrops
   kubectl exec deploy/cerebrops-app -n cerebrops -- du -sh /app/data /app/logs
   ```
2. Log rotation is automatic (5MB × 5 files). The `cerebrops-log-cleanup`
   CronJob deletes `*.log` older than 7 days; if it failed, run it manually.
3. If the DB is large, offload history: the store keeps everything by design
   for the 7-day forecast baseline + 30d SLO window. Add a retention/archive
   job (Phase 5 follow-up) or expand the PVC (`kubectl edit pvc
   cerebrops-data-pvc`).

## Recovery checklist

- [ ] `/health` returns `healthy` and the store check passes
- [ ] Prometheus scrape is green (`up{job="cerebrops"} == 1`)
- [ ] Error rate and p95 back to baseline in Grafana
- [ ] Anomaly detector still has a fitted model (`GET /api/v1/anomalies`
      shows a run with `method`)
- [ ] No pending `CerebrOpsDown`/`DiskPressure` alerts
