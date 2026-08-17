# Incident Response

General workflow for any CerebrOps incident. Specific playbooks:

- `anomaly-alert.md` — ML-detected metric anomaly
- `slo-burn.md` — error budget burning
- `service-down.md` — app unreachable / capacity

## Roles

| Role | Responsibility |
|------|----------------|
| **Incident Commander (IC)** | One person owns the incident; triages, delegates, declares severity, communicates |
| **Scribe** | Keeps the timeline; every action + timestamp + evidence link |
| **Subject-matter experts** | App, infra, data — assigned specific hypotheses to verify |

For incidents with more than two people involved, assign the IC and scribe
explicitly. The IC does not fix things; they coordinate.

## Workflow

1. **Acknowledge.** Confirm the alert is real (not a stale scrape). Create a
   chat thread / incident channel and link it in the alert.
2. **Triage (first 5 minutes).**
   - Who/what is affected? (all users, API only, dashboard only)
   - When did it start? (first anomalous point in `GET /api/v1/anomalies`)
   - Did a deploy happen just before? (`GET /api/v1/pipeline` — the monitor's
     root-cause block answers this automatically)
3. **Mitigate before you root-cause.** If the cheapest mitigation is a
   rollback, roll back first. Restoring service is priority one; understanding
   the root cause comes second.
4. **Communicate.** Post a status update at least every 30 minutes to the
   incident channel. Include: current severity, what's being tried, who owns
   what.
5. **Resolve.** Verify the fix with a smoke test (`scripts/smoke-tests.sh`)
   and by watching error rate / latency return to baseline.
6. **Post-incident review (within 5 working days).** Write the blameless
   postmortem. File follow-ups for every action item.

## Timeline template

```
HH:MM UTC  Alert fired (CerebrOpsHighErrorRate, severity high)
HH:MM UTC  L1 acknowledged; opened incident channel
HH:MM UTC  Deploy correlation found: run-987 (main@deadbeef) 23m before
HH:MM UTC  Metric shift: error_rate 0.1% -> 8.2% after deploy
HH:MM UTC  Rolled back to previous image digest (rollout status OK)
HH:MM UTC  Error rate back to baseline; incident closed
```

## Blameless postmortem template

```markdown
# Incident {date}: {title}

- **Severity**: {critical|high|warning}
- **Duration**: {start} – {end}
- **Impact**: {users/endpoints affected, error budget consumed}
- **Trigger**: {alert(s) fired}
- **Root cause**: {what actually happened}
- **Detection**: {how we learned about it; seconds-to-detect}
- **Mitigation**: {rollback / config change / scale-out}
- **Follow-ups**:
  - [ ] {action, owner, due date}
  - [ ] {action, owner, due date}
```

## Principles

- **Blameless**: incidents are system design problems, not people problems.
- **Restore first**: mitigation beats investigation when the incident is live.
- **Write everything down**: the timeline is the raw material for the
  postmortem; without it, the review is guesswork.
