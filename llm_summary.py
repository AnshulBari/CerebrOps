"""
CerebrOps LLM-assisted anomaly summaries (Phase 5).

Opt-in: enabled only when LLM_API_URL is set (any OpenAI-compatible
/chat/completions endpoint). The monitor attaches a one-paragraph plain-English
summary of the anomaly + root cause to the Slack alert. The detection and
alerting pipeline never depends on the LLM: any failure returns None and the
anomaly alert goes out unchanged.

Environment:
    LLM_API_URL   - e.g. https://api.openai.com/v1 (required to enable)
    LLM_API_KEY   - bearer token (optional for local models)
    LLM_MODEL     - model name (default: gpt-4o-mini)
    LLM_TIMEOUT_S - request timeout (default: 20)
    LLM_MODE=mock - deterministic local summary, no network. Proves the
                    end-to-end attach path (monitor -> summary -> alert)
                    without any external endpoint.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger('cerebrops.llm_summary')

DEFAULT_MODEL = 'gpt-4o-mini'
DEFAULT_TIMEOUT = 20


def _truncate(points: list, limit: int = 3) -> list:
    if not points:
        return []
    return points[:limit]


def build_prompt(results: Dict[str, Any], root_cause: Optional[Dict[str, Any]]) -> str:
    """Build a compact, self-contained prompt from the detection payload."""
    contribs = results.get('top_metric_contributions') or {}
    contrib_text = ', '.join(f"{k}={v:.2f}σ" for k, v in sorted(
        contribs.items(), key=lambda kv: kv[1], reverse=True
    )) or 'none'
    points = _truncate(results.get('anomalous_data') or [])
    points_text = json.dumps(points, default=str)[:1200] if points else '[]'

    rc = root_cause or {}
    hypothesis = rc.get('hypothesis') or 'no deploy correlation found'
    shifts = rc.get('metric_shifts') or {}
    shifted_metrics = ', '.join(sorted(
        m for m, s in shifts.items() if isinstance(s, dict) and s.get('shifted')
    )) or 'none'

    return (
        "You are the on-call engineer for CerebrOps, an internal metrics and "
        "anomaly-detection service. Write ONE concise paragraph (max 120 words) "
        "summarizing the anomaly alert below for a busy engineer. State the "
        "detection method, the top contributing metrics with their deviation "
        "strength, whether a recent deploy is implicated, which metrics shifted, "
        "and the single most useful next action. Be specific; do not invent data.\n\n"
        f"Method: {results.get('method', 'unknown')}\n"
        f"Anomaly count: {results.get('anomaly_count')}/{results.get('total_data_points')} "
        f"({results.get('anomaly_percentage')}%), severity {results.get('severity')}\n"
        f"Top metric contributions: {contrib_text}\n"
        f"Deploy hypothesis: {hypothesis}\n"
        f"Shifted metrics: {shifted_metrics}\n"
        f"Anomalous points (first {len(points)}): {points_text}"
    )


def _mock_summary(results: Dict[str, Any],
                  root_cause: Optional[Dict[str, Any]]) -> str:
    """Deterministic summary for LLM_MODE=mock: same shape a real model would
    produce, built purely from the payload so it can never drift from it."""
    contribs = results.get('top_metric_contributions') or {}
    top = max(contribs.items(), key=lambda kv: kv[1])[0] if contribs else 'metrics'
    rc = root_cause or {}
    if rc.get('deploy_correlation'):
        deploy = rc['deploy_correlation'][0]
        hypothesis = (f"The {top} spike correlates with deploy "
                      f"{deploy.get('pipeline_id')} ({deploy.get('commit_hash', '')[:7]})")
    else:
        hypothesis = f"The {top} spike has no correlated deploy"
    return (f"[mock] {results.get('method', 'unknown')} detected "
            f"{results.get('anomaly_count', '?')} anomalies driven by {top}. "
            f"{hypothesis}.")


def generate_llm_summary(results: Dict[str, Any],
                         root_cause: Optional[Dict[str, Any]] = None,
                         api_url: Optional[str] = None,
                         api_key: Optional[str] = None,
                         model: Optional[str] = None,
                         timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    """
    Ask an OpenAI-compatible chat endpoint for a one-paragraph summary.

    Returns None when disabled (no LLM_API_URL), on network/API errors, or on
    a malformed response - the alerting path never depends on this. Set
    LLM_MODE=mock to get a deterministic local summary without any endpoint.
    """
    if os.getenv('LLM_MODE') == 'mock':
        return _mock_summary(results, root_cause)
    base_url = (api_url or os.getenv('LLM_API_URL', '')).rstrip('/')
    if not base_url:
        return None
    key = api_key if api_key is not None else os.getenv('LLM_API_KEY')
    model_name = model or os.getenv('LLM_MODEL') or DEFAULT_MODEL

    try:
        payload = {
            'model': model_name,
            'messages': [{'role': 'user', 'content': build_prompt(results, root_cause)}],
            'max_tokens': 220,
            'temperature': 0.3,
        }
        headers = {'Content-Type': 'application/json'}
        if key:
            headers['Authorization'] = f'Bearer {key}'
        response = requests.post(
            f'{base_url}/chat/completions', json=payload, headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        summary = data['choices'][0]['message']['content'].strip()
        if not summary:
            raise ValueError('Empty LLM response')
        logger.info("LLM anomaly summary generated (%s tokens)", data.get('usage', {}).get('completion_tokens'))
        return summary
    except Exception as e:
        logger.warning(f"LLM summary unavailable, alert proceeds without it: {e}")
        return None
