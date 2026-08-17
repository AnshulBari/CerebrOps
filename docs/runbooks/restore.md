# Restore from Backup

Backups are created daily at 01:00 UTC by the `cerebrops-backup` CronJob
(`k8s/base/backup.yaml`) into the `cerebrops-backup-pvc` volume. Each backup is a
directory `backup-YYYYMMDD-HHMMSS/` containing:

- `cerebrops.db` — consistent SQLite snapshot (online backup API; safe to
  restore even if the app was writing during the backup)
- `cerebrops_v{N}.joblib` + `cerebrops_v{N}_card.json` + `current_version`
  — persisted anomaly models
- `manifest.json` — creation time, included files, pruned backups

## When to restore

- The `data/cerebrops.db` file is corrupt or the PVC was deleted.
- A bad migration/retrain destroyed model history and you need the last good
  model version.
- The metrics store was accidentally overwritten (e.g., by a `--reset`).

## Restore procedure

1. **Stop the writer** so the restore is not overwritten mid-copy:

   ```bash
   kubectl scale deployment cerebrops-app -n cerebrops --replicas=0
   ```

2. **Pick the backup** (usually the newest):

   ```bash
   kubectl exec -n cerebrops deploy/cerebrops-app -- ls -t /backup
   # (backup PVC is mounted at /backup in the backup CronJob; use a
   # temporary pod if the deployment is scaled to 0)
   ```

   With a temp pod:

   ```bash
   kubectl run restore-tmp --image=busybox:1.35 -n cerebrops --rm -it --restart=Never \
     --overrides='{"spec":{"volumes":[{"name":"b","persistentVolumeClaim":{"claimName":"cerebrops-backup-pvc"}},{"name":"d","persistentVolumeClaim":{"claimName":"cerebrops-data-pvc"}}],"containers":[{"name":"restore-tmp","image":"busybox:1.35","command":["sh"],"stdin":true,"tty":true,"volumeMounts":[{"name":"b","mountPath":"/backup"},{"name":"d","mountPath":"/data"}]}]}}'
   ```

3. **Copy the database + models** (backup `backup-20260817-010000` shown):

   ```sh
   cp /backup/backup-20260817-010000/cerebrops.db /data/cerebrops.db
   mkdir -p /data/models
   cp /backup/backup-20260817-010000/cerebrops_v*.joblib /data/models/
   cp /backup/backup-20260817-010000/cerebrops_v*_card.json /data/models/
   cp /backup/backup-20260817-010000/current_version /data/models/ 2>/dev/null || true
   ```

4. **Restart the app and verify**:

   ```bash
   kubectl scale deployment cerebrops-app -n cerebrops --replicas=2
   kubectl rollout status deployment/cerebrops-app -n cerebrops --timeout=300s
   curl -sf https://YOUR_HOST/health
   curl -sf https://YOUR_HOST/api/v1/metrics  # rows present again
   ```

5. **Confirm the anomaly detector reloads**: the next monitoring cycle logs
   `Loaded persisted anomaly model (version N)`; `GET /api/v1/anomalies`
   shows runs with `model_version` back at the restored version.

## Testing restore (mandatory, quarterly)

Restore into a **scratch PVC** (never the live one) and diff
`count_metrics()` before/after. Run this drill with the runbook open; target
time-to-restore is under 30 minutes.

An executable version of the drill ships in the repo:

```bash
python scripts/restore_drill.py            # uses the real store (read-only) + scratch restore
python scripts/restore_drill.py --fixture  # CI-safe: generates a fixture store
```

It backs up, restores into a scratch directory, and verifies sqlite
integrity, row-count parity across all core tables, and that persisted
models still load with joblib. Exit 0 = verified restore. Run it in CI on a
schedule (it needs no cluster) so the drill can never silently rot.

Last executed locally against the real store on 2026-08-17: PASS.

## Offsite durability

The backup PVC is on the same cluster as the data. For real durability:

- Sync `cerebrops-backup-pvc` to object storage (S3/EFS/azure blob) with a
  tool like `restic` or `velero` in a second CronJob, or
- Point the backup CronJob at a `restic` sidecar.

Do not consider the cluster restored until you have verified an offsite copy.
