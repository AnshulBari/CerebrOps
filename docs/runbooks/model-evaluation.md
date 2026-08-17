# Model Evaluation (v1 vs v2)

The Phase 5 acceptance criterion is a documented precision/recall comparison
of the two detectors on **≥ 2 weeks of real production data**. The harness is
`scripts/evaluate_models.py`; it is tested on a labeled synthetic fixture in
`tests/test_evaluation.py`, so it is ready the moment real data exists.

## How the harness works

1. Split labeled rows 80/20 (train / evaluation window).
2. **v2 (forecast-residual)** is fitted on the train split and scores the
   evaluation window.
3. **v1 (isolation-forest)** loads the persisted model from
   `--model-dir` (or `CEREBROPS_MODEL_DIR`), or trains on the train split.
4. A predicted anomaly is a **true positive** if it falls within
   `--tolerance-min` (default 60) minutes of a labeled anomaly, using greedy
   nearest matching. Precision / recall / F1 are reported per method, and a
   JSON report is written with `--output`.

## Labeling real data

The store has everything needed except the truth label. Produce a JSONL file,
one row per metric point, with `true_anomaly` set by a human reviewer:

```bash
python - <<'EOF'
import sys, json
sys.path.insert(0, '.')
from metrics_store import MetricsStore
rows = MetricsStore().get_metrics(limit=50000)
# Reviewer sets true_anomaly=1 on points that were genuine incidents
# (cross-reference Slack alerts, deploy events, and the postmortems).
for r in rows:
    r['true_anomaly'] = 0   # ...edit by hand or via a labeling script
    print(json.dumps(r, default=str))
EOF
```

Practical labeling shortcuts:

- **Deploy-correlated incidents**: the `root_cause.deploy_correlation` block
  already marks anomaly timestamps near deploys — label those windows 1 if the
  incident was real.
- **Known outages**: label every point in the incident timeline (from the
  postmortem) 1, everything else 0.
- **Semi-automated**: export the anomaly runs + alerts from
  `GET /api/v1/anomalies` and have a reviewer confirm or reject each run
  before generating labels.

Aim for at least 20–50 labeled incidents across the two weeks; fewer than 10
makes precision/recall statistically meaningless.

## Running the evaluation

```bash
python scripts/evaluate_models.py \
  --labels labels.jsonl \
  --model-dir models \
  --tolerance-min 60 \
  --output evaluation_report.json
```

Interpret the report:

| Signal | Meaning |
|--------|---------|
| v2 recall < v1 recall | Forecast detector misses anomalies the forest catches — check `FORECAST_Z_THRESHOLD` (lower) or bucket coverage |
| v2 precision < 0.5 | Too many false alarms — raise `FORECAST_Z_THRESHOLD` or require 2+ consecutive anomalous points |
| v1 recall low | Retraining cadence or contamination is off; check the drift baseline |
| Both low | Labels are noisy or the metric set doesn't capture the incident |

## Ship criteria

Keep the report in the repo (`evaluation_report.json`) and record the model
version + dates in the commit message. Promotion of a tuned detector to
production requires:

- v2 precision ≥ 0.7 **and** recall ≥ 0.8 on the real labeled window, or
- v2 within 10 points of v1 on both metrics **and** strictly better on the
  metric you care about (recall for catching incidents, precision for alert
  fatigue).
