/* ============================================================
   CerebrOps Demo — API Override
   Intercepts fetch calls and returns mock data for static demo.
   ============================================================ */
(function() {
  'use strict';

  // Demo data that the dashboard expects
  var DEMO_DATA = {
    metrics: {
      request_count: generateSeries(120, 40, 36, true),
      error_rate: generateSeries(0.8, 0.5, 36, false, 28, 14),
      response_time: generateSeries(0.14, 0.04, 36, false),
      cpu_usage: generateSeries(34, 12, 36, false),
      memory_usage: generateSeries(58, 6, 36, false),
      disk_usage: generateSeries(41, 2, 36, false)
    },
    summary: { total: 4812, error_rate_percent: 1.7, avg_response_time_seconds: 0.143, avg_response_time_ms: 143, anomaly_count: 3, deploy_count: 9 },
    anomalies: [
      { id: 6, ts: new Date(Date.now() - 9 * 60000).toISOString(), status: 'detected', severity: 'page', anomaly_count: 3, total_data_points: 672, results: { method: 'forecast-residual', top_metric_contributions: { error_rate: 42.3, response_time: 12.1 }, root_cause: { run_id: 'run-1836', minutes_before: 1.1, branch: 'main', commit: '3a08f77', hypothesis: 'Possible deploy-related regression: run-1836 (main@3a08f77) 1.1m before the anomaly.' } } },
      { id: 5, ts: new Date(Date.now() - 5 * 3600000).toISOString(), status: 'detected', severity: 'ticket', anomaly_count: 1, total_data_points: 672, results: { method: 'isolation-forest', top_metric_contributions: { cpu_usage: 9.2 } } },
      { id: 4, ts: new Date(Date.now() - 13 * 3600000).toISOString(), status: 'detected', severity: 'ticket', anomaly_count: 2, total_data_points: 670, results: { method: 'forecast-residual', top_metric_contributions: { memory_usage: 17.7, error_rate: 6.4 } } },
      { id: 3, ts: new Date(Date.now() - 26 * 3600000).toISOString(), status: 'detected', severity: 'info', anomaly_count: 1, total_data_points: 668, results: { method: 'isolation-forest', top_metric_contributions: { disk_usage: 4.1 } } }
    ],
    alerts: [
      { id: 8, ts: new Date(Date.now() - 9 * 60000).toISOString(), severity: 'page', alert_type: 'anomaly', message: 'error_rate spike — forecast-residual flagged 3 points', payload: { channel: 'slack' } },
      { id: 7, ts: new Date(Date.now() - 5 * 3600000).toISOString(), severity: 'ticket', alert_type: 'anomaly', message: 'cpu_usage deviating from weekly profile', payload: { channel: 'slack' } },
      { id: 6, ts: new Date(Date.now() - 11 * 3600000).toISOString(), severity: 'ticket', alert_type: 'slo', message: 'FastBurn: error budget consumed 18.2x in the last hour', payload: { channel: 'opsgenie' } },
      { id: 5, ts: new Date(Date.now() - 22 * 3600000).toISOString(), severity: 'info', alert_type: 'pipeline', message: 'run-1827 passed · deploy to production', payload: { channel: 'slack' } }
    ],
    pipeline: generatePipeline(),
    deployments: [
      { id: 1841, env: 'Production', status: 'success', ts: new Date(Date.now() - 3 * 3600000).toISOString(), branch: 'main', commit: '7d2f9a1', duration: 142, url: 'app.cerebrops.dev' },
      { id: 1839, env: 'Staging', status: 'success', ts: new Date(Date.now() - 8 * 3600000).toISOString(), branch: 'main', commit: '9c41be2', duration: 118, url: 'staging.cerebrops.dev' },
      { id: 1838, env: 'Production', status: 'failed', ts: new Date(Date.now() - 21 * 3600000).toISOString(), branch: 'main', commit: '3a08f77', duration: 96, url: 'app.cerebrops.dev' },
      { id: 1835, env: 'Staging', status: 'success', ts: new Date(Date.now() - 30 * 3600000).toISOString(), branch: 'main', commit: 'e5d90b4', duration: 121, url: 'staging.cerebrops.dev' }
    ],
    health: 'healthy',
    degraded: false,
    demo: true
  };

  function generateSeries(base, amp, count, isInt, spikeIdx, spikeMult) {
    var pts = [];
    var now = Date.now();
    for (var i = 0; i <= count; i++) {
      var v = base + (Math.sin(i * 0.3) * amp * 0.5) + ((Math.random() - 0.5) * amp);
      if (spikeIdx && i === spikeIdx) v = base + amp * (spikeMult || 4);
      v = Math.max(0, v);
      pts.push({
        t: new Date(now - (count - i) * 10 * 60000).toISOString(),
        v: isInt ? Math.round(v) : Math.round(v * 10) / 10
      });
    }
    return pts;
  }

  function generatePipeline() {
    var commits = [
      ['7d2f9a1', 'fix: backpressure on webhook ingress', 'maya'],
      ['9c41be2', 'feat: forecast-residual detection v2', 'devon'],
      ['3a08f77', 'chore: pin trivy-action to 0.35.0', 'alex'],
      ['e5d90b4', 'feat: deploy-correlated root cause', 'maya'],
      ['b21a6c8', 'perf: batch metric inserts', 'devon'],
      ['f04e3d9', 'fix: WAL checkpoint on rotate', 'alex']
    ];
    var projects = ['cerebrops-core', 'gateway', 'web-dashboard'];
    var statuses = ['success', 'success', 'success', 'failed', 'success', 'running'];
    var pipeline = [];
    var now = Date.now();
    for (var i = 0; i < 10; i++) {
      var c = commits[i % commits.length];
      pipeline.push({
        id: i + 1,
        pipeline_id: 'run-' + (1842 - i),
        status: statuses[i % statuses.length],
        stage: statuses[i % statuses.length] === 'failed' ? 'test' : 'production',
        duration: 30 + Math.floor(Math.random() * 80),
        branch: i === 9 ? 'pr-127' : 'main',
        commit_hash: c[0],
        source: 'github-actions',
        ts: new Date(now - (i + 1) * (40 + Math.floor(Math.random() * 100)) * 60000).toISOString(),
        payload: { project: projects[i % 3], repo: 'cerebrops/' + projects[i % 3], author: c[2], message: c[1] }
      });
    }
    return pipeline;
  }

  // Map API paths to demo data
  var API_MAP = {
    '/api/v1/metrics': function(url) {
      return { status: 'success', data: { series: DEMO_DATA.metrics, summary: DEMO_DATA.summary }, timestamp: new Date().toISOString() };
    },
    '/api/v1/anomalies': function(url) {
      return { status: 'success', data: { anomalies: DEMO_DATA.anomalies }, timestamp: new Date().toISOString() };
    },
    '/api/v1/alerts': function(url) {
      return { status: 'success', data: { alerts: DEMO_DATA.alerts }, timestamp: new Date().toISOString() };
    },
    '/api/v1/pipeline': function(url) {
      return { status: 'success', data: { events: DEMO_DATA.pipeline }, timestamp: new Date().toISOString() };
    },
    '/health': function(url) {
      return { status: 'healthy', version: '1.0.0-demo', uptime: 86400 };
    },
    '/api/v1/health': function(url) {
      return { status: 'healthy', version: '1.0.0-demo' };
    }
  };

  // Override fetch
  var originalFetch = window.fetch;
  window.fetch = function(url, opts) {
    var path = typeof url === 'string' ? url.split('?')[0] : (url.url || '').split('?')[0];

    // Check if we have demo data for this path
    for (var key in API_MAP) {
      if (path === key || path.endsWith(key)) {
        var data = API_MAP[key](url);
        return Promise.resolve({
          ok: true,
          status: 200,
          json: function() { return Promise.resolve(data); }
        });
      }
    }

    // For all other requests, return a 404 or empty response
    return Promise.resolve({
      ok: false,
      status: 404,
      json: function() { return Promise.resolve({}); }
    });
  };

  console.log('[CerebrOps Demo] API override active — all data is simulated.');
})();
