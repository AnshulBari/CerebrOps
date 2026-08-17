/* ============================================================
   CerebrOps — application shell
   Real data from the v1 API, honest demo mode when the store
   is empty, and a command palette for everything else.
   ============================================================ */
(function () {
  'use strict';

  /* ================= utilities ================= */

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function fmtNum(n) {
    if (n == null) return '—';
    n = Number(n);
    if (!isFinite(n)) return '—';
    if (Math.abs(n) >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + 'k';
    return String(Math.round(n));
  }
  function fmt1(n) { return (n == null || !isFinite(n)) ? '—' : Number(n).toFixed(1); }
  function fmtPct(n) { return (n == null || !isFinite(n)) ? '—' : Number(n).toFixed(1) + '%'; }

  function fmtDur(sec) {
    if (sec == null) return '—';
    sec = Number(sec);
    if (sec < 60) return Math.round(sec) + 's';
    if (sec < 3600) return Math.floor(sec / 60) + 'm ' + Math.round(sec % 60) + 's';
    return Math.floor(sec / 3600) + 'h ' + Math.floor((sec % 3600) / 60) + 'm';
  }

  function fmtAgo(ts) {
    if (!ts) return '—';
    var d = new Date(ts);
    if (isNaN(d)) return '—';
    var s = Math.max(0, (Date.now() - d.getTime()) / 1000);
    if (s < 10) return 'just now';
    if (s < 60) return Math.floor(s) + 's ago';
    if (s < 3600) return Math.floor(s / 60) + 'm ago';
    if (s < 86400) return Math.floor(s / 3600) + 'h ago';
    return Math.floor(s / 86400) + 'd ago';
  }
  function fmtTime(ts) {
    if (!ts) return '—';
    var d = new Date(ts);
    if (isNaN(d)) return '—';
    var p = function (x) { return String(x).padStart(2, '0'); };
    var now = new Date();
    var sameDay = d.toDateString() === now.toDateString();
    return (sameDay ? '' : p(d.getMonth() + 1) + '/' + p(d.getDate()) + ' ') + p(d.getHours()) + ':' + p(d.getMinutes());
  }
  function fmtShortHash(h) { return h ? String(h).slice(0, 7) : ''; }

  /* ================= icons ================= */

  var ICONS = {
    play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5z"/></svg>',
    stop: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="1.5"/></svg>',
    refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 11-2.6-6.4M21 3v6h-6"/></svg>',
    copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 012-2h10"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>',
    x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>',
    search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>',
    bolt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
    bell: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 01-3.4 0"/></svg>',
    eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7.5 11-7.5S23 12 23 12s-4 7.5-11 7.5S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>',
    eyeOff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17.9 17.9A10.6 10.6 0 0112 19.5C5 19.5 1 12 1 12a20 20 0 014.1-5.9M9.9 4.2A9.9 9.9 0 0112 4.5c7 0 11 7.5 11 7.5a19.4 19.4 0 01-3.4 4M1 1l22 22"/></svg>',
    expand: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 00-2 2v3M16 3h3a2 2 0 012 2v3M8 21H5a2 2 0 01-2-2v-3M16 21h3a2 2 0 002-2v-3"/></svg>',
    wrap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h9a3 3 0 013 3 3 3 0 01-3 3H8"/><path d="M12 15l-4 3 4 3"/></svg>',
    download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"/></svg>',
    arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>',
    spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v4m0 10v4M3 12h4m10 0h4M6 6l2.5 2.5m7 7L18 18M18 6l-2.5 2.5m-7 7L6 18"/></svg>',
    doc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M9 13h6M9 17h6"/></svg>',
  };

  var STATUS_MAP = {
    success: { label: 'passed', cls: 'badge-success', dot: 'dot-success' },
    passed: { label: 'passed', cls: 'badge-success', dot: 'dot-success' },
    failed: { label: 'failed', cls: 'badge-fail', dot: 'dot-fail' },
    running: { label: 'running', cls: 'badge-run', dot: 'dot-run' },
    pending: { label: 'pending', cls: 'badge-muted', dot: 'dot-muted' },
    queued: { label: 'queued', cls: 'badge-muted', dot: 'dot-muted' },
    cancelled: { label: 'cancelled', cls: 'badge-muted', dot: 'dot-muted' },
    warning: { label: 'warning', cls: 'badge-warn', dot: 'dot-warn' },
    info: { label: 'info', cls: 'badge-accent', dot: 'dot-muted' },
    page: { label: 'page', cls: 'badge-fail', dot: 'dot-fail' },
    ticket: { label: 'ticket', cls: 'badge-warn', dot: 'dot-warn' },
  };

  function statusBadge(status, opts) {
    opts = opts || {};
    var m = STATUS_MAP[String(status).toLowerCase()] || { label: status, cls: 'badge-muted', dot: 'dot-muted' };
    var live = String(status).toLowerCase() === 'running';
    var dot = opts.noDot ? '' : '<span class="dot ' + m.dot + '"></span>';
    return '<span class="badge ' + m.cls + '">' + dot + esc(m.label) + '</span>';
  }

  var METRIC_LABELS = {
    cpu_usage: 'CPU usage', memory_usage: 'Memory usage', disk_usage: 'Disk usage',
    error_rate: 'Error rate', request_count: 'Request count', response_time: 'Response time',
  };

  /* ================= theme ================= */

  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('cb-theme', t); } catch (e) { /* noop */ }
  }
  function toggleTheme() {
    var cur = document.documentElement.getAttribute('data-theme') || 'dark';
    applyTheme(cur === 'dark' ? 'light' : 'dark');
    toast('Theme switched', cur === 'dark' ? 'Light mode on' : 'Dark mode on');
  }

  /* ================= state & data ================= */

  var state = {
    data: null,
    demo: (function () { try { return localStorage.getItem('cb-demo') === '1'; } catch (e) { return false; } })(),
    view: 'overview',
    params: {},
    notifRead: (function () {
      try { return JSON.parse(localStorage.getItem('cb-notif-read') || '[]'); } catch (e) { return []; }
    })(),
  };

  var API_KEY = ($('meta[name="api-key"]') || {}).content || '';

  function api(path) {
    var headers = { 'Accept': 'application/json' };
    if (API_KEY) headers['X-API-Key'] = API_KEY;
    return fetch(path, { headers: headers })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (body) { return { ok: r.ok, status: r.status, body: body }; }); })
      .catch(function () { return { ok: false, status: 0, body: null }; });
  }

  function loadData() {
    return Promise.all([
      api('/api/v1/metrics?window=300'),
      api('/api/v1/anomalies?limit=20'),
      api('/api/v1/alerts?limit=20'),
      api('/api/v1/pipeline?limit=30'),
      api('/health'),
    ]).then(function (rs) {
      var d = rs[0].body && rs[0].body.data, an = rs[1].body && rs[1].body.data,
          al = rs[2].body && rs[2].body.data, pl = rs[3].body && rs[3].body.data,
          h = rs[4].body || {};
      state.data = {
        metrics: d && d.series ? d.series : {},
        summary: (d && d.summary) || {},
        anomalies: (an && an.anomalies) || [],
        alerts: (al && al.alerts) || [],
        pipeline: (pl && pl.events) || [],
        health: h.status || 'unknown',
        degraded: rs.some(function (r) { return r.status === 503; }),
      };
      if (state.demo) state.data = mergeDemo(state.data);
      updateChrome();
      return state.data;
    });
  }

  function refresh(andRender) {
    loadData().then(function () {
      if (andRender && state.view) render();
    });
  }

  /* ================= demo data ================= */

  function mulberry(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  var PROJECTS = [
    { id: 'core', name: 'cerebrops-core', repo: 'cerebrops/core' },
    { id: 'gw', name: 'gateway', repo: 'cerebrops/gateway' },
    { id: 'web', name: 'web-dashboard', repo: 'cerebrops/web-dashboard' },
  ];
  var COMMITS = [
    ['7d2f9a1', 'fix: backpressure on webhook ingress', 'maya'],
    ['9c41be2', 'feat: forecast-residual detection v2', 'devon'],
    ['3a08f77', 'chore: pin trivy-action to 0.35.0', 'alex'],
    ['e5d90b4', 'feat: deploy-correlated root cause', 'maya'],
    ['b21a6c8', 'perf: batch metric inserts', 'devon'],
    ['f04e3d9', 'fix: WAL checkpoint on rotate', 'alex'],
    ['c887120', 'feat: promote workflow with PR', 'maya'],
    ['51abf0e', 'test: forecast detector debounce', 'devon'],
  ];
  var STAGES = [
    { key: 'checkout', label: 'Checkout', icon: 'git' },
    { key: 'build', label: 'Build', icon: 'b' },
    { key: 'test', label: 'Tests', icon: 't' },
    { key: 'security', label: 'Security', icon: 's' },
    { key: 'deploy', label: 'Deploy', icon: 'd' },
    { key: 'production', label: 'Production', icon: '★' },
  ];
  var ENVS = [
    { name: 'Production', sub: 'prod · us-east-1', status: 'success', branch: 'main', url: 'app.cerebrops.dev' },
    { name: 'Staging', sub: 'staging · us-east-1', status: 'success', branch: 'main', url: 'staging.cerebrops.dev' },
    { name: 'Development', sub: 'dev · cluster-local', status: 'success', branch: 'develop', url: 'dev.cerebrops.dev' },
    { name: 'Preview', sub: 'per-PR · ephemeral', status: 'running', branch: 'pr-127', url: 'pr-127.preview.cerebrops.dev' },
  ];

  function seriesPointCount(series) {
    var s = series || {};
    return Object.keys(s).reduce(function (n, k) { return n + (s[k] || []).length; }, 0);
  }

  function mergeDemo(real) {
    var demo = demoData();
    // Real store wins once it has substance (100+ points and 2h of the
    // request series); sparse early data gives way so the demo showcases.
    var realSubstantial = seriesPointCount(real.metrics) >= 100 &&
      (real.metrics.request_count || []).length >= 24;
    var out = {
      summary: real.summary && (real.summary.total || real.summary.total === 0) ? real.summary : demo.summary,
      metrics: realSubstantial ? real.metrics : demo.metrics,
      anomalies: (real.anomalies || []).length ? real.anomalies : demo.anomalies,
      alerts: (real.alerts || []).length ? real.alerts : demo.alerts,
      pipeline: (real.pipeline || []).length ? real.pipeline : demo.pipeline,
      deployments: demo.deployments,
      health: real.health,
      degraded: real.degraded,
      demo: true,
    };
    return out;
  }

  function demoData() {
    var rng = mulberry(20260105);
    var now = Date.now();
    var pick = function (arr) { return arr[Math.floor(rng() * arr.length)]; };

    var pipeline = [];
    var statuses = ['success', 'success', 'success', 'success', 'failed', 'success', 'success', 'running'];
    for (var i = 0; i < 14; i++) {
      var proj = pick(PROJECTS);
      var c = COMMITS[(i * 3 + Math.floor(rng() * 2)) % COMMITS.length];
      var st = i < 3 ? statuses[i % statuses.length] : (rng() < 0.72 ? 'success' : (rng() < 0.5 ? 'failed' : 'cancelled'));
      if (i === 0) st = 'success';
      if (i === 5) st = 'failed';
      if (i === 13) st = 'running';
      var dur = st === 'success' ? 38 + Math.floor(rng() * 90) : 20 + Math.floor(rng() * 60);
      pipeline.push({
        id: i + 1,
        pipeline_id: 'run-' + (1840 - i),
        status: st,
        stage: st === 'failed' ? 'test' : (st === 'running' ? 'deploy' : 'production'),
        duration: dur,
        branch: proj.id === 'web' && i === 13 ? 'pr-127' : 'main',
        commit_hash: c[0],
        source: pick(['github-actions', 'github-actions', 'gitlab-ci']),
        ts: new Date(now - (i + 1) * (42 + Math.floor(rng() * 110)) * 60000).toISOString(),
        payload: { project: proj.name, repo: proj.repo, author: c[2], message: c[1], url: 'https://github.com/' + proj.repo + '/actions/runs/' + (1840 - i) },
      });
    }

    var anomalies = [
      { id: 6, ts: new Date(now - 9 * 60000).toISOString(), status: 'detected', severity: 'page', anomaly_count: 3, total_data_points: 672, results: { method: 'forecast-residual', top_metric_contributions: { error_rate: 42.3, response_time: 12.1 }, root_cause: { run_id: 'run-1836', minutes_before: 1.1, branch: 'main', commit: '3a08f77', hypothesis: 'Possible deploy-related regression: run-1836 (main@3a08f77) 1.1m before the anomaly.' } } },
      { id: 5, ts: new Date(now - 5 * 3600000).toISOString(), status: 'detected', severity: 'ticket', anomaly_count: 1, total_data_points: 672, results: { method: 'isolation-forest', top_metric_contributions: { cpu_usage: 9.2 } } },
      { id: 4, ts: new Date(now - 13 * 3600000).toISOString(), status: 'detected', severity: 'ticket', anomaly_count: 2, total_data_points: 670, results: { method: 'forecast-residual', top_metric_contributions: { memory_usage: 17.7, error_rate: 6.4 } } },
      { id: 3, ts: new Date(now - 26 * 3600000).toISOString(), status: 'detected', severity: 'info', anomaly_count: 1, total_data_points: 668, results: { method: 'isolation-forest', top_metric_contributions: { disk_usage: 4.1 } } },
      { id: 2, ts: new Date(now - 40 * 3600000).toISOString(), status: 'ok', severity: null, anomaly_count: 0, total_data_points: 664, results: { method: 'forecast-residual' } },
      { id: 1, ts: new Date(now - 52 * 3600000).toISOString(), status: 'ok', severity: null, anomaly_count: 0, total_data_points: 660, results: { method: 'isolation-forest' } },
    ];

    var alerts = [
      { id: 8, ts: new Date(now - 9 * 60000).toISOString(), severity: 'page', alert_type: 'anomaly', message: 'error_rate spike — forecast-residual flagged 3 points', payload: { channel: 'slack' } },
      { id: 7, ts: new Date(now - 5 * 3600000).toISOString(), severity: 'ticket', alert_type: 'anomaly', message: 'cpu_usage deviating from weekly profile', payload: { channel: 'slack' } },
      { id: 6, ts: new Date(now - 11 * 3600000).toISOString(), severity: 'ticket', alert_type: 'slo', message: 'FastBurn: error budget consumed 18.2× in the last hour', payload: { channel: 'opsgenie' } },
      { id: 5, ts: new Date(now - 22 * 3600000).toISOString(), severity: 'info', alert_type: 'pipeline', message: 'run-1827 passed · deploy to production', payload: { channel: 'slack' } },
      { id: 4, ts: new Date(now - 30 * 3600000).toISOString(), severity: 'info', alert_type: 'pipeline', message: 'run-1825 failed · tests in gateway', payload: { channel: 'slack' } },
      { id: 3, ts: new Date(now - 44 * 3600000).toISOString(), severity: 'info', alert_type: 'health', message: 'Health checks passing · all systems nominal', payload: { channel: 'statuspage' } },
    ];

    var mkSeries = function (base, amp, opts) {
      opts = opts || {};
      var pts = [], t = now - 6 * 3600000;
      for (var i = 0; i <= 36; i++) {
        var v = base + (rng() - 0.5) * 2 * amp;
        if (opts.spike && i === 28) v = base + amp * (opts.spike === 'big' ? 14 : 4);
        pts.push({ t: new Date(t).toISOString(), v: Math.max(0, Math.round(v * (opts.int ? 1 : 10)) / (opts.int ? 1 : 10)) });
        t += 10 * 60000;
      }
      return pts;
    };

    var metrics = {
      request_count: mkSeries(120, 40, { int: true }),
      error_rate: mkSeries(0.8, 0.5, { spike: 'big' }),
      response_time: mkSeries(0.14, 0.04),
      cpu_usage: mkSeries(34, 12),
      memory_usage: mkSeries(58, 6),
      disk_usage: mkSeries(41, 2),
    };

    var summary = { total: 4812, error_rate_percent: 1.7, avg_response_time_seconds: 0.143, avg_response_time_ms: 143, anomaly_count: 3, deploy_count: 9 };

    var deployments = [
      { id: 1841, env: 'Production', status: 'success', ts: new Date(now - 3 * 3600000).toISOString(), branch: 'main', commit: '7d2f9a1', duration: 142, url: 'app.cerebrops.dev' },
      { id: 1839, env: 'Staging', status: 'success', ts: new Date(now - 8 * 3600000).toISOString(), branch: 'main', commit: '9c41be2', duration: 118, url: 'staging.cerebrops.dev' },
      { id: 1838, env: 'Production', status: 'failed', ts: new Date(now - 21 * 3600000).toISOString(), branch: 'main', commit: '3a08f77', duration: 96, url: 'app.cerebrops.dev' },
      { id: 1835, env: 'Staging', status: 'success', ts: new Date(now - 30 * 3600000).toISOString(), branch: 'main', commit: 'e5d90b4', duration: 121, url: 'staging.cerebrops.dev' },
      { id: 1832, env: 'Production', status: 'success', ts: new Date(now - 47 * 3600000).toISOString(), branch: 'main', commit: 'b21a6c8', duration: 139, url: 'app.cerebrops.dev' },
      { id: 1830, env: 'Preview', status: 'success', ts: new Date(now - 52 * 3600000).toISOString(), branch: 'pr-127', commit: '51abf0e', duration: 84, url: 'pr-127.preview.cerebrops.dev' },
    ];

    return { summary: summary, metrics: metrics, anomalies: anomalies, alerts: alerts, pipeline: pipeline, deployments: deployments, demo: true };
  }

  /* ================= charts (hand-rolled SVG) ================= */

  function sparkline(points, opts) {
    opts = opts || {};
    var w = opts.w || 72, h = opts.h || 28;
    var vals = (points || []).map(function (p) { return typeof p === 'number' ? p : p.v; }).filter(function (v) { return v != null; });
    if (vals.length < 2) return '';
    var min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
    if (max === min) { max = min + 1; }
    var px = function (i) { return (i / (vals.length - 1)) * w; };
    var py = function (v) { return h - ((v - min) / (max - min)) * (h - 2) - 1; };
    var d = vals.map(function (v, i) { return (i ? 'L' : 'M') + px(i).toFixed(1) + ' ' + py(v).toFixed(1); }).join('');
    var color = opts.color || 'var(--accent)';
    return '<svg class="stat-spark" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none" aria-hidden="true">' +
      '<path d="' + d + ' L ' + w + ' ' + h + ' L 0 ' + h + ' Z" fill="' + color + '" opacity="0.12"/>' +
      '<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>';
  }

  function areaChart(el, series, opts) {
    opts = opts || {};
    var W = 720, H = 200, pad = { l: 40, r: 12, t: 12, b: 22 };
    var iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;

    // Drop points with unparseable timestamps or non-numeric values so a
    // weird store row can never produce NaN coordinates.
    series = series.map(function (s) {
      return { points: (s.points || []).filter(function (p) {
        var t = new Date(p.t).getTime();
        return !isNaN(t) && isFinite(Number(p.v));
      }), color: s.color, cls: s.cls };
    });
    var all = [];
    series.forEach(function (s) { all = all.concat(s.points || []); });
    var ts = all.map(function (p) { return new Date(p.t).getTime(); });
    if (!ts.length) { el.innerHTML = '<div class="empty"><p>No data yet — start recording metrics.</p></div>'; return; }
    var t0 = Math.min.apply(null, ts);
    var t1 = Math.max.apply(null, ts);
    if (t1 - t0 < 1) t1 = t0 + 1;

    var maxV = 0;
    series.forEach(function (s) { (s.points || []).forEach(function (p) { if (p.v > maxV) maxV = p.v; }); });
    maxV = Math.max(1, Math.ceil(maxV * 1.15));

    function X(t) { return pad.l + ((t - t0) / (t1 - t0)) * iw; }
    function Y(v) { return pad.t + ih - (v / maxV) * ih; }

    var grid = '';
    var ticks = 4;
    for (var i = 0; i <= ticks; i++) {
      var gy = pad.t + (ih / ticks) * i;
      grid += '<line class="grid-line" x1="' + pad.l + '" y1="' + gy + '" x2="' + (W - pad.r) + '" y2="' + gy + '"/>';
      var val = maxV - (maxV / ticks) * i;
      grid += '<text x="' + (pad.l - 8) + '" y="' + (gy + 3) + '" text-anchor="end">' + (opts.int ? fmtNum(val) : fmt1(val)) + '</text>';
    }
    var gx = t0 + (t1 - t0) * 0.5;
    grid += '<text x="' + X(gx) + '" y="' + (H - 6) + '" text-anchor="middle">' + fmtTime(new Date(gx).toISOString()) + '</text>';
    grid += '<text x="' + X(t0) + '" y="' + (H - 6) + '" text-anchor="start">' + fmtTime(new Date(t0).toISOString()) + '</text>';

    var layers = '', hoverPts = '';
    series.forEach(function (s) {
      var pts = s.points || [];
      if (pts.length < 2) return;
      var d = pts.map(function (p, j) {
        var x = X(new Date(p.t).getTime()), y = Y(p.v);
        return (j ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
      }).join('');
      var color = s.color || 'var(--accent)';
      layers += '<path d="' + d + ' L ' + X(new Date(pts[pts.length - 1].t).getTime()).toFixed(1) + ' ' + (pad.t + ih) + ' L ' + X(new Date(pts[0].t).getTime()).toFixed(1) + ' ' + (pad.t + ih) + ' Z" fill="' + color + '" opacity="0.1"/>';
      layers += '<path class="line' + (s.cls ? ' ' + s.cls : '') + '" d="' + d + '"/>';
    });

    el.innerHTML = '<svg class="chart-svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" role="img">' +
      '<defs><linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="var(--accent)" stop-opacity="0.22"/><stop offset="100%" stop-color="var(--accent)" stop-opacity="0"/></linearGradient></defs>' +
      grid + layers + hoverPts + '</svg>';
  }

  function barChart(el, items, opts) {
    opts = opts || {};
    var W = 720, H = 180, pad = { l: 40, r: 12, t: 10, b: 24 };
    var iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
    var maxV = 0;
    items.forEach(function (it) { if (it.v > maxV) maxV = it.v; });
    maxV = Math.max(1, Math.ceil(maxV * 1.15));
    var n = items.length, bw = Math.max(4, Math.min(26, iw / n * 0.55));
    var html = '<svg class="chart-svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">';
    for (var i = 0; i <= 3; i++) {
      var gy = pad.t + (ih / 3) * i;
      html += '<line class="grid-line" x1="' + pad.l + '" y1="' + gy + '" x2="' + (W - pad.r) + '" y2="' + gy + '"/>';
      html += '<text x="' + (pad.l - 8) + '" y="' + (gy + 3) + '" text-anchor="end">' + Math.round(maxV - (maxV / 3) * i) + '</text>';
    }
    items.forEach(function (it, j) {
      var x = pad.l + (j / Math.max(1, n - 1)) * iw - bw / 2;
      var h = Math.max(1, (it.v / maxV) * ih);
      var y = pad.t + ih - h;
      var color = it.color || (it.ok === false ? 'var(--fail)' : it.ok ? 'var(--success)' : 'var(--accent)');
      html += '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + h.toFixed(1) + '" rx="2" fill="' + color + '" opacity="0.85"><title>' + esc(it.label) + ' · ' + fmtDur(it.v) + '</title></rect>';
    });
    html += '</svg>';
    el.innerHTML = html;
  }

  /* ================= pipeline graph ================= */

  var STAGE_ICONS = { checkout: 'git', build: 'b', test: 't', security: 's', deploy: 'd', production: '★' };

  function stageOrderFor(event) {
    // Build a stage list with statuses from the run's status + payload stage.
    var payload = event.payload || {};
    var status = String(event.status || 'pending').toLowerCase();
    var markAt = status === 'failed' ? (payload.stage || event.stage || null)
      : status === 'running' ? (payload.stage || event.stage || null) : null;
    var markIdx = markAt ? STAGES.findIndex(function (s) { return s.key === markAt; }) : -1;
    return STAGES.map(function (s, i) {
      var st;
      if (status === 'success' || status === 'passed') st = 'passed';
      else if (status === 'cancelled' || status === 'pending' || status === 'queued') st = 'pending';
      else if (markIdx === i) st = status; // failed / running at this stage
      else if (markIdx < 0) st = 'pending';
      else st = i < markIdx ? 'passed' : 'pending';
      return { key: s.key, label: s.label, icon: STAGE_ICONS[s.key], status: st };
    });
  }

  function pipelineRail(stages, opts) {
    opts = opts || {};
    var html = '<div class="pipeline-rail" role="list" aria-label="Pipeline stages">';
    stages.forEach(function (s, i) {
      var meta = opts.meta && opts.meta[s.key] ? opts.meta[s.key] : (s.status === 'passed' ? '✓' : s.status === 'failed' ? '✕' : s.status === 'running' ? '…' : '—');
      html += '<button class="pg-stage pg-' + s.status + '" data-stage="' + s.key + '" role="listitem" aria-label="' + esc(s.label) + ' ' + s.status + '">' +
        '<span class="pg-node">' + esc(s.icon) + '</span>' +
        '<span class="pg-name">' + esc(s.label) + '</span>' +
        '<span class="pg-meta">' + esc(meta) + '</span></button>';
      if (i < stages.length - 1) {
        var c = s.status === 'failed' ? 'fail' : (stages[i + 1].status === 'passed' ? 'done' : stages[i + 1].status === 'running' ? 'active' : '');
        html += '<div class="pg-conn ' + c + '" aria-hidden="true"></div>';
      }
    });
    html += '</div>';
    return html;
  }

  function pipelineVertical(stages, opts) {
    opts = opts || {};
    var html = '<div class="pg-vertical">';
    stages.forEach(function (s, i) {
      html += '<button class="pg-vstage pg-' + s.status + '" data-stage="' + s.key + '">' +
        '<span class="pg-vnode">' + esc(s.icon) + '</span>' +
        '<span class="pg-vname">' + esc(s.label) + '</span>' +
        '<span class="pg-vmeta">' + (opts.meta && opts.meta[s.key] ? opts.meta[s.key] : s.status) + '</span></button>';
      if (i < stages.length - 1) {
        var c = stages[i + 1].status === 'passed' ? 'done' : stages[i + 1].status === 'failed' ? 'fail' : stages[i + 1].status === 'running' ? 'active' : '';
        html += '<div class="pg-vconn ' + c + '" aria-hidden="true"></div>';
      }
    });
    html += '</div>';
    return html;
  }

  /* ================= cinematic hero (reference visual language) ================= */

  var SHORT_ICONS = { checkout: 'C', build: 'B', test: 'T', security: 'S', deploy: 'D', production: '★' };
  var HERO_XS = [160, 364, 568, 772, 976, 1064];
  var HERO_YS = [196, 150, 186, 142, 176, 150];

  function heroSmooth(points) {
    var d = 'M ' + points[0][0] + ' ' + points[0][1];
    for (var i = 0; i < points.length - 1; i++) {
      var p0 = points[Math.max(0, i - 1)], p1 = points[i], p2 = points[i + 1], p3 = points[Math.min(points.length - 1, i + 2)];
      var c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6;
      var c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6;
      d += ' C ' + c1x.toFixed(1) + ' ' + c1y.toFixed(1) + ', ' + c2x.toFixed(1) + ' ' + c2y.toFixed(1) + ', ' + p2[0] + ' ' + p2[1];
    }
    return d;
  }

  function heroRail(stages, status) {
    var pts = stages.map(function (s, i) { return [HERO_XS[i], HERO_YS[i]]; });
    var full = heroSmooth(pts);
    var html = '<svg class="hero-rail" viewBox="0 0 1200 300" preserveAspectRatio="xMidYMid meet" aria-hidden="true">' +
      '<defs><linearGradient id="hgrad" x1="0" y1="0" x2="1" y2="0">' +
      '<stop offset="0%" stop-color="var(--accent)" stop-opacity="0"/>' +
      '<stop offset="50%" stop-color="var(--accent-strong)" stop-opacity="1"/>' +
      '<stop offset="100%" stop-color="var(--accent)" stop-opacity="0"/></linearGradient></defs>' +
      '<path class="h-track" d="' + full + '"/>';
    stages.forEach(function (s, i) {
      if (i === 0) return;
      var a = pts[Math.max(0, i - 2)], b = pts[i - 1], c = pts[i], d2 = pts[Math.min(pts.length - 1, i + 1)];
      var c1x = b[0] + (c[0] - a[0]) / 6, c1y = b[1] + (c[1] - a[1]) / 6;
      var c2x = c[0] - (d2[0] - b[0]) / 6, c2y = c[1] - (d2[1] - b[1]) / 6;
      var seg = 'M ' + b[0] + ' ' + b[1] + ' C ' + c1x.toFixed(1) + ' ' + c1y.toFixed(1) + ', ' + c2x.toFixed(1) + ' ' + c2y.toFixed(1) + ', ' + c[0] + ' ' + c[1];
      var cls = s.status === 'passed' ? 'done' : s.status === 'failed' ? 'fail' : s.status === 'running' ? 'run' : '';
      html += '<path class="h-seg ' + cls + '" d="' + seg + '"/>';
    });
    if (status === 'running') html += '<path class="h-flow" d="' + full + '"/>';
    stages.forEach(function (s, i) {
      var x = HERO_XS[i], y = HERO_YS[i];
      html += '<g class="h-node ' + s.status + '" transform="translate(' + x + ' ' + y + ')">' +
        (s.status === 'running' ? '<circle class="halo" r="12" fill="none" stroke="var(--run)" stroke-width="1.4"/>' : '') +
        '<circle r="15"/><text>' + esc(SHORT_ICONS[s.key] || '·') + '</text></g>';
      html += '<text class="h-label' + (s.status === 'passed' ? ' done' : '') + '" x="' + x + '" y="' + (y + 35) + '">' + esc(s.label) + '</text>';
      var meta = s.status === 'passed' ? '✓ done' : s.status === 'failed' ? '✕ failed' : s.status === 'running' ? '● live' : '—';
      html += '<text class="h-meta" x="' + x + '" y="' + (y + 51) + '">' + meta + '</text>';
    });
    var dur = status === 'running' ? '3.2s' : status === 'passed' ? '6s' : '5s';
    html += '<circle class="h-dot" r="4"><animateMotion dur="' + dur + '" repeatCount="indefinite" path="' + full + '"/></circle>';
    html += '</svg>';
    return html;
  }

  function heroStage(ev, actions, opts) {
    opts = opts || {};
    var status = String(ev.status || 'pending').toLowerCase();
    var cls = (status === 'success' || status === 'passed') ? 'passed' : status === 'failed' ? 'failed' : status === 'running' ? 'running' : 'pending';
    var p = ev.payload || {};
    var rail = heroRail(stageOrderFor(ev), status);
    var stLabel = status === 'success' ? 'passed' : status;
    var pillCls = cls === 'passed' ? 'success' : cls === 'failed' ? 'fail' : cls === 'running' ? 'run' : '';
    var dotCls = cls === 'passed' ? 'dot-success' : cls === 'failed' ? 'dot-fail' : cls === 'running' ? 'dot-run' : 'dot-muted';
    return '<div class="hero-stage ' + cls + '">' + rail +
      '<div class="hero-top"><span class="hero-label">cerebrops / ' + esc(ev.pipeline_id || 'run') + '</span>' +
      '<div class="hero-pills"><span class="pill pill-' + pillCls + '"><span class="dot ' + dotCls + '"></span>' + esc(stLabel) + '</span>' +
      (opts.env ? '<span class="pill pill-mono">' + esc(opts.env) + '</span>' : '') +
      (opts.branch ? '<span class="pill pill-mono">' + esc(opts.branch) + '</span>' : '') + '</div></div>' +
      '<div class="hero-caption"><div style="min-width:0">' +
      '<div class="hero-title">' + esc(p.message || (ev.pipeline_id || 'pipeline run')) + '</div>' +
      '<div class="hero-sub">' + esc(fmtShortHash(ev.commit_hash)) + ' · ' + esc(ev.branch || 'main') + ' · ' + esc(p.author || '—') + ' · ' + fmtAgo(ev.ts) + (ev.duration != null ? ' · ' + fmtDur(ev.duration) : '') + '</div></div>' +
      '<div class="hero-actions">' + (actions || '') + '</div></div></div>';
  }

  function heroIdle(actions) {
    var stages = STAGES.map(function (s) { return { key: s.key, label: s.label, icon: s.icon, status: 'pending' }; });
    var url = location.origin + '/api/v1/pipeline/events';
    var curl = "curl -s -X POST '" + url + "' \\\n" +
      "  -H 'Content-Type: application/json' \\\n" +
      "  -d '{\"pipeline_id\":\"run-1\",\"status\":\"success\",\"stage\":\"deploy\",\"branch\":\"main\"}'";
    return '<div class="hero-stage pending">' + heroRail(stages, 'pending') +
      '<div class="hero-top"><span class="hero-label">cerebrops / waiting for first run</span>' +
      '<div class="hero-pills"><span class="pill"><span class="dot dot-muted"></span>idle</span></div></div>' +
      '<div class="hero-caption"><div style="min-width:0"><div class="hero-title">Nothing deployed yet. <span class="serif-it" style="color:var(--ink)">Let\'s change that.</span></div>' +
      '<div class="hero-sub">Point your CI at the webhook below — the dashboard fills itself in as runs land.</div></div>' +
      '<div class="hero-connect">' +
        '<div class="connect-head"><span class="connect-label">webhook</span>' +
          '<button class="hero-btn-ghost" data-copy="' + url + '">' + ICONS.copy + ' copy</button></div>' +
        '<pre class="connect-code">' + esc(curl) + '</pre>' +
        '<button class="hero-btn-ghost" data-hero="demo">' + ICONS.bolt + ' Load sample data</button>' +
      '</div></div></div>';
  }

  function heroMeta(ev) {
    var p = ev.payload || {};
    var status = String(ev.status || '').toLowerCase();
    var pillCls = (status === 'success' || status === 'passed') ? 'success' : status === 'failed' ? 'fail' : status === 'running' ? 'run' : '';
    var dotCls = pillCls === 'success' ? 'dot-success' : pillCls === 'fail' ? 'dot-fail' : pillCls === 'run' ? 'dot-run' : 'dot-muted';
    return '<div class="pill-row" style="margin:-6px 0 var(--sp-5)">' +
      '<span class="pill pill-' + pillCls + '"><span class="dot ' + dotCls + '"></span>' + esc(status === 'success' ? 'passed' : status) + '</span>' +
      '<span class="pill pill-mono">' + esc(ev.pipeline_id || 'run') + '</span>' +
      '<span class="pill">production</span>' +
      '<span class="pill pill-mono">' + esc(ev.branch || 'main') + '</span>' +
      '<span class="pill pill-mono">' + esc(fmtShortHash(ev.commit_hash)) + '</span>' +
      (ev.duration != null ? '<span class="pill pill-mono">' + fmtDur(ev.duration) + '</span>' : '') +
      (p.author ? '<span class="pill pill-mono">' + esc(p.author) + '</span>' : '') +
      (ev.source ? '<span class="pill pill-mono">' + esc(ev.source) + '</span>' : '') + '</div>';
  }

  /* ================= logs ================= */

  function makeLogs(event) {
    // Deterministic transcript for a run; grounded in the real payload when present.
    var p = event.payload || {};
    var seed = (event.id || event.pipeline_id || '').toString().split('').reduce(function (a, c) { return a + c.charCodeAt(0); }, 0);
    var rng = mulberry(seed || 7);
    var lines = [];
    var t = new Date(event.ts || Date.now()).getTime();
    var push = function (level, msg, secs) {
      lines.push({ t: new Date(t + (secs || lines.length * 2) * 1000), level: level, msg: msg });
    };
    push('info', 'Received event ' + (event.pipeline_id || 'run') + ' from ' + (event.source || 'webhook'), 0);
    push('info', 'Repository: ' + esc(p.repo || 'cerebrops/core') + ' · branch ' + (event.branch || 'main'), 1);
    push('info', 'Commit ' + (event.commit_hash || '').slice(0, 7) + ' — ' + (p.message || ''), 2);
    var stages = stageOrderFor(event);
    stages.forEach(function (s, i) {
      push('info', '── ' + s.label.toUpperCase() + ' ──', 4 + i * 4);
      if (s.status === 'passed') {
        push('ok', s.label + ' completed', 5 + i * 4);
      } else if (s.status === 'running') {
        push('info', s.label + ' in progress…', 5 + i * 4);
        push('info', 'Rolling update: 2/2 replicas ready', 6 + i * 4);
      } else if (s.status === 'failed') {
        push('info', 'Executing ' + s.label.toLowerCase() + '…', 5 + i * 4);
        push('error', 'exit code 1 · ' + s.label.toLowerCase() + ' failed', 6 + i * 4);
        push('error', '  at pipeline/run.py:214 in run_stage()', 7 + i * 4);
        push('warn', 'Retrying stage ' + s.label.toLowerCase() + ' (attempt 1/3)', 8 + i * 4);
      } else {
        push('info', 'Waiting for ' + s.label.toLowerCase() + '…', 5 + i * 4);
      }
    });
    if (event.status === 'success') {
      push('ok', 'Pipeline passed — ' + fmtDur(event.duration) + ' total', 4 + stages.length * 4);
      push('ok', 'Deployed to production', 5 + stages.length * 4);
    } else if (event.status === 'failed') {
      push('warn', 'Pipeline failed after ' + fmtDur(event.duration), 4 + stages.length * 4);
    }
    return lines;
  }

  function logLevelClass(l) { return l === 'ok' ? 'll-ok' : l === 'warn' ? 'll-warn' : l === 'error' ? 'll-error' : 'll-info'; }

  function renderLogViewer(el, lines, opts) {
    opts = opts || {};
    var state2 = { q: '', level: 'all', wrap: false, hl: [] };
    var body;

    function render() {
      var shown = [];
      lines.forEach(function (l, i) {
        var okLvl = state2.level === 'all' || l.level === state2.level;
        var okQ = !state2.q || l.msg.toLowerCase().indexOf(state2.q.toLowerCase()) !== -1;
        if (okLvl && okQ) shown.push([i, l]);
      });
      if (!shown.length) { body.innerHTML = '<div class="log-empty">No lines match <span class="mono">' + esc(state2.q || state2.level) + '</span>.</div>'; return; }
      body.innerHTML = shown.map(function (pair) {
        var i = pair[0], l = pair[1];
        var p = function (x) { return String(x).padStart(2, '0'); };
        var ts = p(l.t.getHours()) + ':' + p(l.t.getMinutes()) + ':' + p(l.t.getSeconds());
        return '<div class="log-line' + (state2.hl.indexOf(i) !== -1 ? ' hl' : '') + '">' +
          '<span class="ln">' + (i + 1) + '</span>' +
          '<span class="lt">' + ts + '</span>' +
          '<span class="ll ' + logLevelClass(l.level) + '">' + l.level.toUpperCase() + '</span>' +
          '<span class="lm">' + l.msg + '</span></div>';
      }).join('');
      if (opts.autoscroll !== false) body.scrollTop = body.scrollHeight;
    }

    function setLevel(lv) {
      state2.level = lv;
      $$('.log-flt', el).forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-lv') === lv); });
      render();
    }

    el.innerHTML =
      '<div class="log-toolbar">' +
        '<span class="log-title mono">' + esc(opts.title || 'run.log') + '</span>' +
        '<div class="seg" role="group" aria-label="Filter by level">' +
          '<button class="log-flt on" data-lv="all">all</button>' +
          '<button class="log-flt" data-lv="info">info</button>' +
          '<button class="log-flt" data-lv="ok">ok</button>' +
          '<button class="log-flt" data-lv="warn">warn</button>' +
          '<button class="log-flt" data-lv="error">error</button>' +
        '</div>' +
        '<label class="log-search">' + ICONS.search + '<input type="search" placeholder="Filter…" aria-label="Filter logs"></label>' +
        '<button class="icon-btn" data-act="wrap" title="Toggle line wrap" aria-label="Toggle line wrap">' + ICONS.wrap + '</button>' +
        '<button class="icon-btn" data-act="copy" title="Copy logs" aria-label="Copy logs">' + ICONS.copy + '</button>' +
        '<button class="icon-btn" data-act="download" title="Download logs" aria-label="Download logs">' + ICONS.download + '</button>' +
        '<button class="icon-btn" data-act="expand" title="Fullscreen" aria-label="Fullscreen">' + ICONS.expand + '</button>' +
      '</div>' +
      '<div class="log-body"></div>';

    body = $('.log-body', el);

    $('input', el).addEventListener('input', function (e) {
      state2.q = e.target.value;
      render();
    });
    $$('.log-flt', el).forEach(function (b) { b.addEventListener('click', function () { setLevel(b.getAttribute('data-lv')); }); });
    $('[data-act="wrap"]', el).addEventListener('click', function (b) {
      state2.wrap = !state2.wrap;
      body.classList.toggle('wrap', state2.wrap);
      b.currentTarget.classList.toggle('btn-on', state2.wrap);
    });
    $('[data-act="copy"]', el).addEventListener('click', function () {
      var text = lines.map(function (l) { return l.msg; }).join('\n');
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(function () { toast('Logs copied', 'run transcript → clipboard'); });
      else toast('Logs copied', 'run transcript → clipboard');
    });
    $('[data-act="download"]', el).addEventListener('click', function () {
      var text = lines.map(function (l, i) { return String(i + 1).padStart(3, '0') + '  ' + l.msg; }).join('\n');
      var blob = new Blob([text], { type: 'text/plain' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (opts.title || 'run') + '.log';
      a.click();
      URL.revokeObjectURL(a.href);
    });
    $('[data-act="expand"]', el).addEventListener('click', function () {
      openFullscreenLogs(lines, opts.title);
    });
    render();
  }

  function openFullscreenLogs(lines, title) {
    var ov = document.createElement('div');
    ov.className = 'fs-overlay';
    ov.innerHTML = '<div class="fs-box"><div class="fs-head"><span class="mono">' + esc(title || 'run.log') + '</span>' +
      '<button class="icon-btn" data-close aria-label="Close">' + ICONS.x + '</button></div><div class="fs-body"></div></div>';
    document.body.appendChild(ov);
    var body = $('.fs-body', ov);
    renderLogViewer(body, lines, { title: title, autoscroll: false });
    $('[data-close]', ov).addEventListener('click', function () { ov.remove(); });
    ov.addEventListener('click', function (e) { if (e.target === ov) ov.remove(); });
    document.addEventListener('keydown', function h(e) {
      if (e.key === 'Escape') { ov.remove(); document.removeEventListener('keydown', h); }
    });
  }

  /* ================= toasts ================= */

  function toast(msg, sub, type) {
    var region = $('#toasts');
    var el = document.createElement('div');
    el.className = 'toast';
    var icon = type === 'error' ? ICONS.x : type === 'warn' ? ICONS.bolt : ICONS.check;
    var color = type === 'error' ? 'var(--fail)' : type === 'warn' ? 'var(--warn)' : 'var(--success)';
    el.innerHTML = '<span style="color:' + color + ';display:inline-flex">' + icon + '</span><span class="toast-msg"><span>' + esc(msg) + '</span>' +
      (sub ? '<span class="toast-sub">' + esc(sub) + '</span>' : '') + '</span>';
    region.appendChild(el);
    setTimeout(function () {
      el.classList.add('toast-leave');
      setTimeout(function () { el.remove(); }, 240);
    }, 3200);
  }

  /* ================= notifications ================= */

  function notifications() {
    var alerts = (state.data && state.data.alerts) || [];
    var unread = alerts.filter(function (a) { return state.notifRead.indexOf('a' + a.id) === -1; });
    return unread;
  }

  function updateChrome() {
    var d = state.data || {};
    var unread = notifications();
    var badge = $('#notif-badge');
    if (badge) {
      badge.hidden = !unread.length;
      badge.textContent = unread.length > 9 ? '9+' : String(unread.length);
    }
    var cnt = $('#alert-count');
    if (cnt) {
      var fail = (d.alerts || []).filter(function (a) { return a.severity === 'page'; }).length;
      cnt.hidden = !fail;
      cnt.textContent = String(fail);
    }
    var dot = $('#side-dot'), txt = $('#side-status-text');
    if (dot && txt) {
      var ok = d.health === 'healthy';
      dot.className = 'dot ' + (ok ? 'dot-success' : 'dot-warn');
      txt.textContent = 'system · ' + (ok ? 'healthy' : 'degraded');
    }
  }

  function renderNotifPanel() {
    var panel = $('#notif-panel');
    var alerts = (state.data && state.data.alerts) || [];
    panel.innerHTML =
      '<div class="notif-head"><span>Notifications</span><button class="btn btn-sm btn-ghost" id="notif-markall">Mark all read</button></div>' +
      (alerts.length
        ? alerts.slice(0, 10).map(function (a) {
          var unread = state.notifRead.indexOf('a' + a.id) === -1;
          var sev = STATUS_MAP[String(a.severity).toLowerCase()] || { cls: 'badge-muted' };
          return '<div class="notif-item' + (unread ? ' unread' : '') + '">' +
            '<span class="badge ' + sev.cls + '">' + esc(a.severity || 'info') + '</span>' +
            '<div class="grow"><div class="notif-title">' + esc(a.message || a.alert_type) + '</div>' +
            '<div class="notif-time">' + fmtAgo(a.ts) + ' · ' + esc(a.alert_type) + '</div></div></div>';
        }).join('')
        : '<div class="empty"><p>No notifications yet. Alerts will land here.</p></div>');
    var mark = $('#notif-markall', panel);
    if (mark) mark.addEventListener('click', function () {
      (state.data.alerts || []).forEach(function (a) {
        if (state.notifRead.indexOf('a' + a.id) === -1) state.notifRead.push('a' + a.id);
      });
      try { localStorage.setItem('cb-notif-read', JSON.stringify(state.notifRead)); } catch (e) { /* noop */ }
      renderNotifPanel();
      updateChrome();
    });
  }

  /* ================= router ================= */

  function parseHash() {
    var h = location.hash.replace(/^#\/?/, '');
    var parts = h.split('/').filter(Boolean);
    return { view: parts[0] || 'overview', id: parts[1] || null };
  }

  var PAGE_TITLES = {
    overview: 'Overview', pipelines: 'Pipelines', deployments: 'Deployments',
    anomalies: 'Anomalies', alerts: 'Alerts', environments: 'Environments',
    analytics: 'Analytics', settings: 'Settings', pipeline: 'Pipeline',
  };

  function navigate() {
    var r = parseHash();
    state.view = r.view;
    state.params = { id: r.id };
    var viewEl = $('#view');
    viewEl.scrollTop = 0;
    $('#crumb-name').textContent = PAGE_TITLES[r.view] || r.view;
    $$('.side-link, .tab-item').forEach(function (a) {
      a.classList.toggle('active', a.getAttribute('data-route') === r.view);
    });
    document.body.classList.remove('side-open');
    $('#side-scrim').hidden = true;
    render();
  }

  function render() {
    var viewEl = $('#view');
    viewEl.classList.remove('page-enter');
    void viewEl.offsetWidth;
    viewEl.classList.add('page-enter');
    var fn = PAGES[state.view] || PAGES.overview;
    try {
      viewEl.innerHTML = fn(state.params);
    } catch (err) {
      viewEl.innerHTML = '<div class="error-state"><span class="err-code">RENDER_FAILED</span><h3>Something went wrong.</h3><p>We couldn\'t render this view.</p><button class="btn" onclick="location.hash=\'#/overview\'">Back to overview</button></div>';
      console.error('render failed', err);
    }
    afterRender();
  }

  function afterRender() {
    var viewEl = $('#view');
    $$('[data-toast]', viewEl).forEach(function (el) {
      el.addEventListener('click', function () {
        toast(el.getAttribute('data-toast'), el.getAttribute('data-toast-sub') || '');
      });
    });
    $$('[data-hero]', viewEl).forEach(function (el) {
      el.addEventListener('click', function () {
        var act = el.getAttribute('data-hero');
        if (act === 'open') location.hash = '#/pipeline/' + (el.getAttribute('data-id') || 0);
        else if (act === 'logs') {
          var target = $('#run-logs');
          if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else if (act === 'run') toast('Pipeline started', 'run queued on main');
        else if (act === 'retry') toast('Run retried', 'run requeued');
        else if (act === 'cancel') toast('Run cancelled', 'run stopped');
        else if (act === 'demo') {
          state.demo = true;
          try { localStorage.setItem('cb-demo', '1'); } catch (e) { /* noop */ }
          toast('Sample data on', 'showing demo dataset');
          refresh(true);
        }
      });
    });
    $$('[data-copy]', viewEl).forEach(function (el) {
      el.addEventListener('click', function () {
        var val = el.getAttribute('data-copy') || '';
        if (navigator.clipboard) navigator.clipboard.writeText(val).catch(function () { /* noop */ });
        toast('Webhook URL copied', val);
      });
    });

    // cinematic reveal-on-scroll for this view (re-runs on every render)
    var blocks = $$('.hero-stage, .stat-tile, .panel, .gcard', viewEl);
    if (blocks.length) {
      blocks.forEach(function (el, i) {
        el.classList.add('reveal');
        el.style.animationDelay = Math.min(i, 5) * 70 + 'ms';
      });
      if ('IntersectionObserver' in window) {
        var obs = new IntersectionObserver(function (entries) {
          entries.forEach(function (en) {
            if (en.isIntersecting) { en.target.classList.add('in'); obs.unobserve(en.target); }
          });
        }, { threshold: 0.08, rootMargin: '0px 0px -4% 0px' });
        blocks.forEach(function (el) { obs.observe(el); });
      } else {
        blocks.forEach(function (el) { el.classList.add('in'); });
      }
    }
  }

  /* ================= pages ================= */

  var PAGES = {};

  /* ---- overview ---- */

  PAGES.overview = function () {
    var d = state.data || {};
    var sum = d.summary || {};
    var series = d.metrics || {};
    var pipes = (d.pipeline || []).slice(0, 5);
    var anoms = (d.anomalies || []).slice(0, 4);
    var alerts = (d.alerts || []).slice(0, 5);

    var reqPts = series.request_count || [];
    var errPts = series.error_rate || [];

    var latest = (d.pipeline || [])[0];
    var hero = latest
      ? heroStage(latest,
          '<button class="hero-btn" data-hero="run">' + ICONS.bolt + ' Run pipeline</button>' +
          '<button class="hero-btn-ghost" data-hero="open" data-id="' + (latest.id || 0) + '">Open run ' + ICONS.arrow + '</button>',
          { env: 'production', branch: latest.branch })
      : heroIdle('<button class="hero-btn" data-hero="run">' + ICONS.bolt + ' Run pipeline</button>');

    var tiles =
      '<div class="stat-grid">' +
        statTile('Requests · 1h', fmtNum(sum.total), 'delta-flat', 'from metrics store', sparkline(reqPts.slice(-12), { color: 'var(--accent)' })) +
        statTile('Error rate', fmtPct(sum.error_rate_percent), errPctClass(sum.error_rate_percent), errPctSub(sum.error_rate_percent), sparkline(errPts.slice(-12), { color: errPctColor(sum.error_rate_percent) })) +
        statTile('Avg response', sum.avg_response_time_ms != null ? fmt1(sum.avg_response_time_ms) + ' ms' : '—', 'delta-flat', 'p95 watch · 500ms SLO', sparkline((series.response_time || []).slice(-12), { color: 'var(--run)' })) +
        statTile('Anomalies · 24h', fmtNum((d.anomalies || []).filter(function (a) { return a.status === 'detected'; }).length), 'delta-flat', 'AI detection runs', '') +
      '</div>';

    var pipesHtml = !pipes.length
      ? emptyState('No pipelines yet', 'Your first pipeline is one webhook away.', 'Send an event to /api/v1/pipeline/events')
      : pipes.map(function (e) {
        return '<div class="row-item clickable" onclick="location.hash=\'#/pipeline/' + (e.id || 0) + '\'">' +
          '<span class="row-commit">' + esc(fmtShortHash(e.commit_hash)) + '</span>' +
          '<div class="row-main"><div class="row-title">' + esc((e.payload && e.payload.message) || (e.pipeline_id || 'run')) + '</div>' +
          '<div class="row-sub">' + esc((e.payload && e.payload.project) || 'cerebrops') + ' · ' + esc(e.branch || '') + ' · ' + esc(e.source || '') + '</div></div>' +
          '<div class="row-right">' + statusBadge(e.status) + '<span class="row-time">' + fmtAgo(e.ts) + '</span></div></div>';
      }).join('');

    var anomHtml = !anoms.length
      ? emptyState('No anomalies yet', 'Detection is watching. You\'ll see deviations here.', '')
      : anoms.map(function (a) {
        var res = a.results || {};
        var rc = res.root_cause || {};
        var m = res.method || 'isolation-forest';
        return '<div class="row-item clickable" onclick="location.hash=\'#/anomalies\'">' +
          '<span class="dot ' + (a.status === 'detected' ? 'dot-warn' : 'dot-success') + '"></span>' +
          '<div class="row-main"><div class="row-title">' + (a.status === 'detected' ? 'Anomaly detected' : 'All clear') + ' <span class="chip mono">' + esc(m) + '</span></div>' +
          '<div class="row-sub">' + esc(topMetric(res)) + (rc.hypothesis ? ' · ' + esc(rc.hypothesis.split(' — ')[0]) : '') + '</div></div>' +
          '<div class="row-right">' + (a.severity ? '<span class="badge ' + (STATUS_MAP[a.severity] || {}).cls + '">' + esc(a.severity) + '</span>' : '') + '<span class="row-time">' + fmtAgo(a.ts) + '</span></div></div>';
      }).join('');

    var alertHtml = !alerts.length
      ? emptyState('No alerts', 'All quiet. Alerts land here when something needs you.', '')
      : alerts.map(function (a) {
        return '<div class="row-item">' +
          '<span class="dot ' + ((STATUS_MAP[String(a.severity).toLowerCase()] || {}).dot || 'dot-muted') + '"></span>' +
          '<div class="row-main"><div class="row-title">' + esc(a.message || a.alert_type) + '</div>' +
          '<div class="row-sub">' + esc(a.alert_type) + ' · ' + esc((a.payload && a.payload.channel) || '') + '</div></div>' +
          '<div class="row-right"><span class="row-time">' + fmtAgo(a.ts) + '</span></div></div>';
      }).join('');

    var activity = buildActivity();

    return '' +
      pageHead('Overview', 'Everything that happened to your code, in one place', '') +
      (state.demo ? '<div class="demo-ribbon" style="margin-bottom:var(--sp-4)">sample data · local demo</div>' : '') +
      hero +
      (latest ? heroMeta(latest) : '') +
      tiles +
      '<div class="grid-2">' +
        '<div class="stack-gap">' +
          '<div class="panel"><div class="panel-head"><h3>Recent pipelines</h3><a class="btn btn-ghost btn-sm" href="#/pipelines">View all</a></div>' + pipesHtml + '</div>' +
          '<div class="panel"><div class="panel-head"><h3>Recent anomalies</h3><a class="btn btn-ghost btn-sm" href="#/anomalies">View all</a></div>' + anomHtml + '</div>' +
        '</div>' +
        '<div class="stack-gap">' +
          '<div class="panel"><div class="panel-head"><h3>Activity</h3></div>' + (activity || '<div class="empty"><p>No activity yet.</p></div>') + '</div>' +
          '<div class="panel"><div class="panel-head"><h3>Alerts</h3><a class="btn btn-ghost btn-sm" href="#/alerts">View all</a></div>' + alertHtml + '</div>' +
        '</div>' +
      '</div>';
  };

  function statTile(label, value, deltaCls, deltaText, spark) {
    return '<div class="stat-tile"><div class="stat-label">' + esc(label) + '</div>' +
      '<div class="stat-value">' + value + '</div>' +
      '<div class="stat-delta ' + deltaCls + '">' + esc(deltaText) + '</div>' + spark + '</div>';
  }
  function errPctClass(v) { return v > 2 ? 'delta-down' : v > 1 ? 'delta-flat' : 'delta-up'; }
  function errPctSub(v) { return v > 2 ? 'above normal' : v > 1 ? 'watching' : 'nominal'; }
  function errPctColor(v) { return v > 2 ? 'var(--fail)' : v > 1 ? 'var(--warn)' : 'var(--success)'; }
  function topMetric(res) {
    var t = (res && res.top_metric_contributions) || {};
    var keys = Object.keys(t);
    if (!keys.length) return 'No metric contributions';
    return keys.map(function (k) { return k + ' ×' + fmt1(t[k]); }).join(' · ');
  }
  function buildActivity() {
    var items = [];
    (state.data.alerts || []).slice(0, 5).forEach(function (a) {
      items.push({ t: a.ts, icon: 'alert', cls: 'dot-warn', text: esc(a.message || a.alert_type), sub: 'alert' });
    });
    (state.data.pipeline || []).slice(0, 5).forEach(function (e) {
      items.push({ t: e.ts, icon: 'pipe', cls: e.status === 'success' ? 'dot-success' : e.status === 'failed' ? 'dot-fail' : 'dot-run', text: esc((e.payload && e.payload.message) || e.pipeline_id), sub: e.status });
    });
    items.sort(function (a, b) { return new Date(b.t) - new Date(a.t); });
    return items.slice(0, 6).map(function (it) {
      return '<div class="row-item"><span class="dot ' + it.cls + '"></span>' +
        '<div class="row-main"><div class="row-title">' + it.text + '</div><div class="row-sub">' + esc(it.sub) + '</div></div>' +
        '<span class="row-time">' + fmtAgo(it.t) + '</span></div>';
    }).join('');
  }

  /* ---- pipelines ---- */

  PAGES.pipelines = function () {
    var d = state.data || {};
    var pipes = d.pipeline || [];
    var counts = {};
    pipes.forEach(function (p) { counts[p.status] = (counts[p.status] || 0) + 1; });

    var seg = ['all', 'success', 'failed', 'running', 'pending', 'cancelled'].map(function (s) {
      var label = s === 'all' ? 'all' : s;
      return '<button class="seg-btn' + (s === 'all' ? ' on' : '') + '" data-flt="' + s + '">' + label + (s !== 'all' && counts[s] ? ' <span class="num">' + counts[s] + '</span>' : '') + '</button>';
    }).join('');

    var listHtml = !pipes.length
      ? emptyState('No pipelines yet', 'Your first pipeline is one commit away.', 'POST an event to /api/v1/pipeline/events')
      : '<div class="gallery" id="pipe-list">' + pipes.map(gcardRow).join('') + '</div>';

    return '' +
      pageHead('Pipelines', 'Every run, every stage, every outcome', '<button class="btn btn-primary" data-toast="Pipeline started" data-toast-sub="run queued on main">' + ICONS.bolt + ' Run pipeline</button>') +
      (state.demo ? '<div class="demo-ribbon" style="margin-bottom:var(--sp-4)">sample data · local demo</div>' : '') +
      '<div class="filter-bar">' +
        '<div class="seg" id="pipe-seg">' + seg + '</div>' +
        '<label class="grow" style="position:relative;display:block">' +
          '<input class="input" style="width:100%" id="pipe-q" type="search" placeholder="Filter by commit, branch, project…" aria-label="Filter pipelines">' +
        '</label>' +
      '</div>' +
      '<div class="panel">' + listHtml + '</div>';
  };

  function gcardRow(e) {
    var p = e.payload || {};
    var stages = stageOrderFor(e);
    var mini = '<div class="mini-rail">' + stages.map(function (s, i) {
      var h = '<span class="mr-node ' + s.status + '">' + esc(SHORT_ICONS[s.key] || '·') + '</span>';
      if (i < stages.length - 1) {
        var c = s.status === 'failed' ? 'fail' : (stages[i + 1].status === 'passed' ? 'done' : stages[i + 1].status === 'running' ? 'run' : '');
        h += '<span class="mr-conn ' + c + '"></span>';
      }
      return h;
    }).join('') + '</div>';
    var status = String(e.status || '').toLowerCase();
    var pillCls = status === 'success' ? 'success' : status === 'failed' ? 'fail' : status === 'running' ? 'run' : '';
    var dotCls = pillCls === 'success' ? 'dot-success' : pillCls === 'fail' ? 'dot-fail' : pillCls === 'run' ? 'dot-run' : 'dot-muted';
    return '<div class="gcard" onclick="location.hash=\'#/pipeline/' + (e.id || 0) + '\'" data-status="' + esc(e.status) + '">' +
      '<div class="gcard-preview">' + mini +
        '<div class="gcard-pills">' +
          '<span class="pill pill-' + pillCls + '"><span class="dot ' + dotCls + '"></span>' + esc(status === 'success' ? 'passed' : status) + '</span>' +
          '<span class="pill pill-mono">' + esc(fmtShortHash(e.commit_hash)) + '</span>' +
          (e.duration != null ? '<span class="pill pill-mono">' + fmtDur(e.duration) + '</span>' : '') +
        '</div></div>' +
      '<div class="gcard-body">' +
        '<div class="gcard-title">' + esc(p.message || (e.pipeline_id || 'run')) + '</div>' +
        '<div class="gcard-sub">' + esc(p.project || 'cerebrops') + ' · ' + esc(e.branch || '') + ' · ' + esc(p.author || '') + ' · ' + fmtAgo(e.ts) + '</div>' +
        '<div class="gcard-foot"><span class="gcard-hash">' + esc(e.pipeline_id || 'run') + '</span>' +
        '<span class="gcard-cta">View pipeline ' + ICONS.arrow + '</span></div>' +
      '</div></div>';
  }

  function bindPipelinesFilters() {
    var segEl = $('#pipe-seg');
    if (!segEl) return;
    var qEl = $('#pipe-q');
    function apply() {
      var flt = ($('.seg-btn.on', segEl) || { getAttribute: function () { return 'all'; } }).getAttribute('data-flt');
      var q = (qEl.value || '').toLowerCase();
      $$('#pipe-list .gcard').forEach(function (row) {
        var st = row.getAttribute('data-status');
        var okSt = flt === 'all' || st === flt;
        var okQ = !q || row.textContent.toLowerCase().indexOf(q) !== -1;
        row.style.display = okSt && okQ ? '' : 'none';
      });
    }
    $$('.seg-btn', segEl).forEach(function (b) {
      b.addEventListener('click', function () {
        $$('.seg-btn', segEl).forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on');
        apply();
      });
    });
    if (qEl) qEl.addEventListener('input', apply);
  }

  /* ---- pipeline detail ---- */

  PAGES.pipeline = function (params) {
    var d = state.data || {};
    var id = Number(params.id);
    var ev = (d.pipeline || []).find(function (e) { return e.id === id; });
    if (!ev) return '<div class="error-state"><span class="err-code">NOT_FOUND</span><h3>Run not found</h3><p>This pipeline run isn\'t in the store.</p><a class="btn" href="#/pipelines">Back to pipelines</a></div>';
    var p = ev.payload || {};
    var stages = stageOrderFor(ev);
    var meta = {};
    stages.forEach(function (s) {
      meta[s.key] = s.status === 'passed' ? '✓ ' + fmtDur((ev.duration || 40) / 6) : s.status === 'failed' ? '✕ exit 1' : s.status === 'running' ? '● live' : 'waiting';
    });
    var logs = makeLogs(ev);

    var hero = heroStage(ev,
      '<button class="hero-btn" data-hero="retry">' + ICONS.refresh + ' Retry</button>' +
      '<button class="hero-btn-ghost" data-hero="logs">' + ICONS.eye + ' View logs</button>',
      { env: 'production', branch: ev.branch });

    var sticky =
      '<div class="sticky-run">' +
        '<span class="sr-id">' + esc(ev.pipeline_id || 'run') + '</span>' + statusBadge(ev.status) +
        '<div class="sr-pills">' +
          '<span class="pill pill-mono">' + esc(fmtShortHash(ev.commit_hash)) + '</span>' +
          '<span class="pill pill-mono">' + esc(ev.branch || 'main') + '</span>' +
          (ev.duration != null ? '<span class="pill pill-mono">' + fmtDur(ev.duration) + '</span>' : '') +
        '</div>' +
        '<div class="sr-actions">' +
          '<button class="btn btn-sm" data-hero="retry">' + ICONS.refresh + ' Retry</button>' +
          '<button class="btn btn-sm btn-ghost" data-hero="logs">Logs</button>' +
        '</div></div>';

    var facts =
      '<div class="pipeline-card"><div class="pipeline-card-head"><h3>Run facts</h3><a class="btn btn-ghost btn-sm" href="#/pipelines">All runs</a></div>' +
      '<div class="pg-facts">' +
        factRow('Trigger', '<span class="chip mono">' + esc(ev.source || 'webhook') + '</span>') +
        factRow('Duration', '<span class="chip mono">' + fmtDur(ev.duration) + '</span>') +
        factRow('Started', '<span class="chip mono">' + fmtTime(ev.ts) + ' · ' + fmtAgo(ev.ts) + '</span>') +
        factRow('Branch', '<span class="chip mono">' + esc(ev.branch || '—') + '</span>') +
        factRow('Commit', '<span class="chip mono">' + esc(fmtShortHash(ev.commit_hash)) + '</span>') +
        factRow('Environment', statusBadge(ev.status === 'success' ? 'success' : ev.status === 'failed' ? 'failed' : 'running', { noDot: true })) +
      '</div></div>';

    return hero +
      sticky +
      '<div class="grid-2">' +
        '<div class="stack-gap">' +
          '<div class="pipeline-card"><div class="pipeline-card-head"><h3>Stages</h3><span class="page-sub">click a stage to inspect</span></div>' + pipelineVertical(stages, { meta: meta }) + '</div>' +
        '</div>' +
        '<div class="stack-gap">' + facts + '</div>' +
      '</div>' +
      '<div class="stack-gap" style="margin-top:var(--sp-4)">' +
        '<div class="panel"><div class="panel-head"><h3>Logs</h3><span class="page-sub mono">' + esc(ev.pipeline_id) + '.log</span></div>' +
        '<div id="run-logs"></div></div>' +
      '</div>';
  };

  function factRow(k, v) {
    return '<div class="fact-row"><span class="fact-k">' + esc(k) + '</span><span class="fact-v">' + v + '</span></div>';
  }

  function bindPipelineDetail() {
    var el = $('#run-logs');
    if (!el) return;
    var id = Number(state.params.id);
    var ev = (state.data.pipeline || []).find(function (e) { return e.id === id; });
    if (!ev) return;
    renderLogViewer(el, makeLogs(ev), { title: (ev.pipeline_id || 'run') + '.log' });
    var d = state.data || {};
    // stage click → open that stage's log slice
    $$('.pg-vstage', $('#view')).forEach(function (btn) {
      btn.addEventListener('click', function () {
        var key = btn.getAttribute('data-stage');
        var all = makeLogs(ev);
        var from = all.findIndex(function (l) { return l.msg.indexOf(key.toUpperCase()) !== -1; });
        var slice = from >= 0 ? all.slice(Math.max(0, from - 2)) : all;
        renderLogViewer(el, slice, { title: (ev.pipeline_id || 'run') + '.' + key + '.log' });
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    });
  }

  /* ---- deployments ---- */

  PAGES.deployments = function () {
    var d = state.data || {};
    var deploys = demoDeployments();
    var html = deploys.length
      ? deploys.map(function (dep) {
        return '<div class="tl-item ' + dep.status + '">' +
          '<span class="tl-dot"></span>' +
          '<div class="tl-head"><span class="tl-title mono">#' + esc(dep.id) + '</span>' + statusBadge(dep.status) +
          '<span class="tl-sub">' + esc(dep.env) + ' · ' + esc(dep.commit) + ' · ' + esc(dep.branch) + '</span></div>' +
          '<div class="tl-body"><div class="row-item" style="border:none;padding:var(--sp-2) 0">' +
            '<div class="row-main"><div class="row-sub">' + esc(dep.url || '') + ' · ' + fmtDur(dep.duration) + ' · ' + fmtAgo(dep.ts) + '</div></div>' +
            '<div class="row-right"><button class="btn btn-sm" data-toast="Deploy started" data-toast-sub="' + esc(dep.commit) + ' → ' + esc(dep.env) + '">Deploy</button>' +
            (dep.status === 'success' ? '<button class="btn btn-sm btn-ghost" data-toast="Rollback queued" data-toast-sub="restoring previous commit">Rollback</button>' : '') + '</div>' +
          '</div></div></div>';
      }).join('')
      : emptyState('Nothing deployed yet', 'Let\'s change that.', '');

    return '' +
      pageHead('Deployments', 'The journey from commit to live, in order', '<button class="btn btn-primary" data-toast="Deploy started" data-toast-sub="main → production">Deploy now</button>') +
      (state.demo ? '<div class="demo-ribbon" style="margin-bottom:var(--sp-4)">sample data · local demo</div>' : '') +
      '<div class="panel"><div class="panel-head"><h3>Timeline</h3><span class="page-sub">recent deploys</span></div><div class="panel-body"><div class="timeline">' + html + '</div></div></div>';
  };

  function demoDeployments() {
    var d = state.data || {};
    if (d.deployments) return d.deployments;
    // Derive from real pipeline events (deploy/production stages).
    var deploys = (d.pipeline || []).filter(function (e) {
      var s = String(e.stage || (e.payload && e.payload.stage) || '').toLowerCase();
      return s === 'deploy' || s === 'production';
    }).map(function (e, i) {
      return { id: (e.id || 1800) - i, env: 'Production', status: e.status === 'success' ? 'success' : e.status === 'failed' ? 'failed' : 'running', ts: e.ts, branch: e.branch, commit: e.commit_hash, duration: e.duration, url: 'app.cerebrops.dev' };
    });
    return deploys;
  }

  /* ---- anomalies ---- */

  PAGES.anomalies = function () {
    var d = state.data || {};
    var anoms = d.anomalies || [];
    var html = !anoms.length
      ? emptyState('No anomalies yet', 'Detection is watching. Deviations from your normal will show up here.', '')
      : '<div class="stack-gap">' + anoms.map(function (a) {
        var res = a.results || {};
        var rc = res.root_cause || {};
        var top = (res.top_metric_contributions) || {};
        var keys = Object.keys(top);
        return '<div class="anom-card">' +
          '<div class="anom-top">' +
            '<span class="dot ' + (a.status === 'detected' ? 'dot-warn' : 'dot-success') + '"></span>' +
            '<span class="anom-title">' + (a.status === 'detected' ? 'Anomaly detected' : 'All clear') + '</span>' +
            '<span class="chip mono">' + esc(res.method || 'isolation-forest') + '</span>' +
            (a.severity ? '<span class="badge ' + ((STATUS_MAP[a.severity] || {}).cls || 'badge-muted') + '">' + esc(a.severity) + '</span>' : '') +
            '<span class="grow"></span><span class="row-time">' + fmtAgo(a.ts) + '</span>' +
          '</div>' +
          '<div class="anom-body">' +
            (keys.length ? keys.map(function (k) {
              var v = top[k];
              var z = Math.min(100, Math.max(4, (v || 0) * 4));
              return '<div class="anom-metric"><div class="k mono">' + esc(k) + '</div><div class="v num">' + fmt1(v) + '×</div>' +
                '<div class="z-bar"><i style="width:' + z + '%"></i></div></div>';
            }).join('') : '<div class="anom-metric"><div class="k mono">points</div><div class="v num">' + (a.total_data_points || '—') + '</div></div>') +
            '<div class="anom-metric"><div class="k mono">data points</div><div class="v num">' + (a.total_data_points || '—') + '</div></div>' +
          '</div>' +
          (rc.hypothesis
            ? '<div class="anom-root">likely cause<div><p>' + esc(rc.hypothesis) + '</p></div></div>'
            : '') +
        '</div>';
      }).join('') + '</div>';

    return '' +
      pageHead('Anomalies', 'AI detection runs — forecast-residual and isolation forest', '<button class="btn" data-toast="Detection run queued" data-toast-sub="full sweep in ~60s">Run detection</button>') +
      (state.demo ? '<div class="demo-ribbon" style="margin-bottom:var(--sp-4)">sample data · local demo</div>' : '') +
      html;
  };

  /* ---- alerts ---- */

  PAGES.alerts = function () {
    var d = state.data || {};
    var alerts = d.alerts || [];
    var html = !alerts.length
      ? emptyState('No alerts', 'All quiet — alerts will land here when something needs you.', '')
      : '<div class="row-list">' + alerts.map(function (a) {
        var sev = STATUS_MAP[String(a.severity).toLowerCase()] || { cls: 'badge-muted', dot: 'dot-muted' };
        return '<div class="row-item">' +
          '<span class="dot ' + sev.dot + '"></span>' +
          '<div class="row-main"><div class="row-title">' + esc(a.message || a.alert_type) + '</div>' +
          '<div class="row-sub"><span class="mono">' + esc(a.alert_type) + '</span> · channel ' + esc((a.payload && a.payload.channel) || '—') + '</div></div>' +
          '<div class="row-right"><span class="badge ' + sev.cls + '">' + esc(a.severity || 'info') + '</span><span class="row-time">' + fmtAgo(a.ts) + '</span></div></div>';
      }).join('') + '</div>';

    return '' +
      pageHead('Alerts', 'What fired, when, and at what severity', '<a class="btn" href="' + (document.location.origin) + '/metrics-prom" target="_blank" rel="noopener">Prometheus</a>') +
      (state.demo ? '<div class="demo-ribbon" style="margin-bottom:var(--sp-4)">sample data · local demo</div>' : '') +
      '<div class="panel">' + html + '</div>';
  };

  /* ---- environments ---- */

  PAGES.environments = function () {
    var envs = ENVS.map(function (env) {
      var dbHost = env.name === 'Preview' ? 'preview.cerebrops.internal' : env.name.toLowerCase() + '.cerebrops.internal';
      var vars = [
        { k: 'DATABASE_URL', v: 'postgres://…:••••@' + dbHost + ':5432/cerebrops', secret: true },
        { k: 'API_KEY', v: 'sk_live_••••••••••••••••', secret: true },
        { k: 'NODE_ENV', v: env.name === 'Preview' ? 'preview' : env.name.toLowerCase(), secret: false },
        { k: 'LOG_LEVEL', v: env.name === 'Production' ? 'info' : 'debug', secret: false },
      ];
      return '<div class="env-card">' +
        '<div class="env-head">' +
          '<span class="dot ' + (env.status === 'success' ? 'dot-success' : 'dot-run') + '"></span>' +
          '<div><div class="env-name">' + esc(env.name) + '</div><div class="env-sub">' + esc(env.sub) + '</div></div>' +
          '<span class="grow"></span>' + statusBadge(env.status) +
        '</div>' +
        '<div class="env-body">' +
          '<div class="env-row"><span class="k">branch</span><span class="v"><span class="chip mono">' + esc(env.branch) + '</span></span></div>' +
          '<div class="env-row"><span class="k">url</span><span class="v">' + esc(env.url) + '</span></div>' +
          vars.map(function (v) {
            return '<div class="env-row"><span class="k">' + esc(v.k) + '</span>' +
              '<span class="v"><span data-var>' + esc(v.v) + '</span>' +
              (v.secret
                ? '<button class="var-reveal" data-reveal data-secret="1" data-real="sk_live_3f9a4c2b…" aria-label="Reveal ' + esc(v.k) + '">' + ICONS.eye + '</button>'
                : '') + '</span></div>';
          }).join('') +
        '</div></div>';
    }).join('');

    return '' +
      pageHead('Environments', 'Where your code lives — and what it knows', '<button class="btn" data-toast="Environment created" data-toast-sub="preview-2 ready">New environment</button>') +
      (state.demo ? '<div class="demo-ribbon" style="margin-bottom:var(--sp-4)">sample data · local demo</div>' : '') +
      '<div class="env-grid">' + envs + '</div>';
  };

  function bindEnvironments() {
    $$('[data-reveal]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var span = $('[data-var]', btn.parentElement);
        var secret = btn.getAttribute('data-secret') === '1';
        if (span.getAttribute('data-shown')) {
          span.textContent = span.getAttribute('data-hidden');
          span.removeAttribute('data-shown');
          if (secret) btn.innerHTML = ICONS.eye;
        } else {
          span.setAttribute('data-hidden', span.textContent);
          span.textContent = btn.getAttribute('data-real') || '••••••••••••';
          span.setAttribute('data-shown', '1');
          if (secret) btn.innerHTML = ICONS.eyeOff;
        }
      });
    });
  }

  /* ---- analytics ---- */

  PAGES.analytics = function () {
    var d = state.data || {};
    var series = d.metrics || {};
    var pipes = d.pipeline || [];
    var success = pipes.filter(function (p) { return p.status === 'success'; }).length;
    var rate = pipes.length ? Math.round(success / pipes.length * 100) : 0;

    var durItems = pipes.slice(0, 14).reverse().map(function (p) {
      return { label: (p.pipeline_id || '').replace('run-', '#'), v: p.duration || 0, ok: p.status === 'success', color: p.status === 'success' ? 'var(--success)' : p.status === 'failed' ? 'var(--fail)' : 'var(--accent)' };
    });

    var dora =
      '<div class="stat-grid" style="grid-template-columns:repeat(4,1fr)">' +
        statTile('Deploy frequency', fmtNum(deployCount(d)), 'delta-flat', 'per week', '') +
        statTile('Build success', rate + '%', rate > 85 ? 'delta-up' : 'delta-flat', 'last ' + pipes.length + ' runs', '') +
        statTile('Avg build time', fmtDur(avgDur(pipes)), 'delta-flat', 'all runs', '') +
        statTile('MTTR', '—', 'delta-flat', 'after 2w of real data', '') +
      '</div>';

    return '' +
      pageHead('Analytics', 'Pipeline throughput and signal health', '') +
      (state.demo ? '<div class="demo-ribbon" style="margin-bottom:var(--sp-4)">sample data · local demo</div>' : '') +
      dora +
      '<div class="grid-2-even">' +
        '<div class="chart-box"><h3>Request count</h3><p class="chart-sub">last 6 hours · 10m buckets</p><div class="chart-anchor" id="chart-req"></div></div>' +
        '<div class="chart-box"><h3>Error rate</h3><p class="chart-sub">percent of requests · spike flagged by detection</p><div class="chart-anchor" id="chart-err"></div></div>' +
      '</div>' +
      '<div class="grid-2-even" style="margin-top:var(--sp-4)">' +
        '<div class="chart-box"><h3>Build duration</h3><p class="chart-sub">last 14 runs · green = passed</p><div class="chart-anchor" id="chart-dur"></div></div>' +
        '<div class="chart-box"><h3>Response time</h3><p class="chart-sub">average seconds</p><div class="chart-anchor" id="chart-resp"></div></div>' +
      '</div>';
  };

  function deployCount(d) { return demoDeployments().length || 0; }
  function avgDur(pipes) {
    var ds = pipes.map(function (p) { return p.duration; }).filter(function (v) { return v != null; });
    if (!ds.length) return 0;
    return ds.reduce(function (a, b) { return a + b; }, 0) / ds.length;
  }

  function bindAnalytics() {
    var d = state.data || {};
    var series = d.metrics || {};
    ['chart-req', 'chart-err', 'chart-resp'].forEach(function (id) {
      var el = $('#' + id);
      if (!el) return;
      var key = id === 'chart-req' ? 'request_count' : id === 'chart-err' ? 'error_rate' : 'response_time';
      var pts = series[key] || [];
      areaChart(el, [{ points: pts, color: id === 'chart-err' ? 'var(--fail)' : id === 'chart-resp' ? 'var(--run)' : 'var(--accent)' }], { int: id === 'chart-req' });
    });
    var durEl = $('#chart-dur');
    if (durEl) {
      var pipes = d.pipeline || [];
      var durItems = pipes.slice(0, 14).reverse().map(function (p) {
        return { label: (p.pipeline_id || '').replace('run-', '#'), v: p.duration || 0, ok: p.status === 'success', color: p.status === 'success' ? 'var(--success)' : p.status === 'failed' ? 'var(--fail)' : 'var(--accent)' };
      });
      barChart(durEl, durItems);
    }
  }

  /* ---- settings ---- */

  PAGES.settings = function () {
    var demoOn = state.demo;
    var webhookUrl = location.origin + '/api/v1/pipeline/events';
    return '' +
      pageHead('Settings', 'Configure CerebrOps for your pipeline', '') +
      '<div class="set-group"><div class="set-group-head"><div><h3>Integration</h3><p>Point your CI at CerebrOps with one endpoint.</p></div>' +
        '<button class="btn btn-sm" id="copy-webhook">' + ICONS.copy + ' Copy webhook URL</button></div>' +
        '<div class="set-body">' +
          '<div class="set-row"><span class="k">Webhook URL</span><span class="mono" style="font-size:var(--text-xs);color:var(--ink-muted)">' + esc(webhookUrl) + '</span></div>' +
          '<div class="set-row"><span class="k">API key</span><span class="mono" style="font-size:var(--text-xs);color:var(--ink-muted)">' + (API_KEY ? esc(API_KEY.slice(0, 8)) + '••••••••' : 'not set — open access') + '</span></div>' +
          '<div class="set-row"><span class="k">Auth header</span><span class="mono" style="font-size:var(--text-xs);color:var(--ink-muted)">X-API-Key</span></div>' +
        '</div></div>' +

      '<div class="set-group"><div class="set-group-head"><div><h3>Workspace</h3><p>Local preferences that stick.</p></div></div>' +
        '<div class="set-body">' +
          '<div class="set-row"><div><div class="k">Sample data</div><div class="d">Explore the product with realistic demo data when the store is empty.</div></div>' +
            '<button class="switch' + (demoOn ? ' on' : '') + '" id="demo-switch" role="switch" aria-checked="' + demoOn + '" aria-label="Toggle sample data"></button></div>' +
          '<div class="set-row"><div><div class="k">Theme</div><div class="d">Dark and light both tuned for long sessions.</div></div>' +
            '<button class="btn btn-sm" id="theme-btn">Toggle theme</button></div>' +
        '</div></div>' +

      '<div class="set-group"><div class="set-group-head"><div><h3>Detection</h3><p>How CerebrOps learns your normal.</p></div></div>' +
        '<div class="set-body">' +
          '<div class="set-row"><div><div class="k">Forecast-residual detector</div><div class="d">Seasonal-naive profiles per metric · activates after 7 days of history.</div></div>' +
            '<span class="badge badge-success"><span class="dot dot-success"></span> on</span></div>' +
          '<div class="set-row"><div><div class="k">Isolation forest</div><div class="d">Unsupervised outlier ensemble on the same windows.</div></div>' +
            '<span class="badge badge-success"><span class="dot dot-success"></span> on</span></div>' +
          '<div class="set-row"><div><div class="k">Deploy-correlated root cause</div><div class="d">Attach the likely deploy to every anomaly alert.</div></div>' +
            '<span class="badge badge-success"><span class="dot dot-success"></span> on</span></div>' +
          '<div class="set-row"><div><div class="k">Z threshold</div><div class="d">Residual deviations above 4.0σ flag, 5.0σ hard-fires.</div></div>' +
            '<span class="chip mono">4.0 / 5.0</span></div>' +
        '</div></div>' +

      '<div class="set-group"><div class="set-group-head"><div><h3>Alerts</h3><p>Where pages land.</p></div></div>' +
        '<div class="set-body">' +
          '<div class="set-row"><div><div class="k">Slack</div><div class="d">Anomaly pages with the root-cause hypothesis attached.</div></div>' +
            '<span class="badge badge-success"><span class="dot dot-success"></span> connected</span></div>' +
          '<div class="set-row"><div><div class="k">Runbooks</div><div class="d">Every alert type has a playbook under docs/runbooks.</div></div>' +
            '<a class="btn btn-sm" href="#/settings">View</a></div>' +
        '</div></div>';
  };

  function bindSettings() {
    var copyBtn = $('#copy-webhook');
    if (copyBtn) copyBtn.addEventListener('click', function () {
      var url = location.origin + '/api/v1/pipeline/events';
      if (navigator.clipboard) navigator.clipboard.writeText(url);
      toast('Webhook URL copied', url);
    });
    var sw = $('#demo-switch');
    if (sw) sw.addEventListener('click', function () {
      state.demo = !state.demo;
      try { localStorage.setItem('cb-demo', state.demo ? '1' : '0'); } catch (e) { /* noop */ }
      sw.classList.toggle('on', state.demo);
      sw.setAttribute('aria-checked', String(state.demo));
      toast(state.demo ? 'Sample data on' : 'Sample data off', 'showing ' + (state.demo ? 'demo dataset' : 'live store data'));
      refresh(true);
    });
    var tb = $('#theme-btn');
    if (tb) tb.addEventListener('click', toggleTheme);
  }

  /* ================= helpers ================= */

  function pageHead(title, sub, actions) {
    return '<div class="page-head"><div><h1>' + esc(title) + '</h1><div class="page-sub">' + esc(sub) + '</div></div>' +
      (actions ? '<div class="page-actions">' + actions + '</div>' : '') + '</div>';
  }

  function emptyState(title, sub, hint) {
    return '<div class="empty"><div class="empty-icon">' + ICONS.spark + '</div><h3 class="serif-it" style="font-size:20px">' + esc(title) + '</h3><p>' + esc(sub) + '</p>' +
      (hint ? '<p class="mono" style="color:var(--ink-faint)">' + esc(hint) + '</p>' : '') + '</div>';
  }

  /* ================= command palette ================= */

  var paletteActions = [
    { group: 'Navigate', label: 'Overview', icon: 'doc', run: function () { location.hash = '#/overview'; } },
    { group: 'Navigate', label: 'Pipelines', icon: 'bolt', run: function () { location.hash = '#/pipelines'; } },
    { group: 'Navigate', label: 'Deployments', icon: 'arrow', run: function () { location.hash = '#/deployments'; } },
    { group: 'Navigate', label: 'Anomalies', icon: 'spark', run: function () { location.hash = '#/anomalies'; } },
    { group: 'Navigate', label: 'Alerts', icon: 'bell', run: function () { location.hash = '#/alerts'; } },
    { group: 'Navigate', label: 'Environments', icon: 'doc', run: function () { location.hash = '#/environments'; } },
    { group: 'Navigate', label: 'Analytics', icon: 'doc', run: function () { location.hash = '#/analytics'; } },
    { group: 'Navigate', label: 'Settings', icon: 'doc', run: function () { location.hash = '#/settings'; } },
    { group: 'Actions', label: 'Run pipeline', icon: 'play', run: function () { toast('Pipeline started', 'run queued on main'); } },
    { group: 'Actions', label: 'Toggle theme', icon: 'refresh', run: toggleTheme },
    { group: 'Actions', label: 'Toggle sample data', icon: 'bolt', run: function () {
      state.demo = !state.demo;
      try { localStorage.setItem('cb-demo', state.demo ? '1' : '0'); } catch (e) { /* noop */ }
      toast(state.demo ? 'Sample data on' : 'Sample data off');
      refresh(true);
    } },
    { group: 'Actions', label: 'Copy webhook URL', icon: 'copy', run: function () {
      var url = location.origin + '/api/v1/pipeline/events';
      if (navigator.clipboard) navigator.clipboard.writeText(url);
      toast('Webhook URL copied', url);
    } },
  ];

  function paletteItems() {
    var items = paletteActions.slice();
    var pipes = (state.data && state.data.pipeline) || [];
    pipes.slice(0, 6).forEach(function (p) {
      items.push({
        group: 'Pipelines',
        label: (p.pipeline_id || 'run') + ' · ' + ((p.payload && p.payload.message) || ''),
        icon: 'play',
        sub: p.status,
        run: function () { location.hash = '#/pipeline/' + (p.id || 0); },
      });
    });
    var anoms = (state.data && state.data.anomalies) || [];
    anoms.slice(0, 4).forEach(function (a) {
      items.push({
        group: 'Anomalies',
        label: (a.status === 'detected' ? 'Anomaly detected' : 'All clear') + ' · ' + ((a.results && a.results.method) || ''),
        icon: 'spark',
        sub: fmtAgo(a.ts),
        run: function () { location.hash = '#/anomalies'; },
      });
    });
    return items;
  }

  function openPalette() {
    var backdrop = $('#palette-backdrop');
    backdrop.hidden = false;
    var input = $('#palette-input');
    input.value = '';
    renderPalette(paletteItems(), '');
    input.focus();
  }

  function closePalette() {
    $('#palette-backdrop').hidden = true;
  }

  function renderPalette(items, q) {
    var box = $('#palette-results');
    q = q.trim().toLowerCase();
    var filtered = q
      ? items.filter(function (it) { return (it.label + ' ' + it.group + ' ' + (it.sub || '')).toLowerCase().indexOf(q) !== -1; })
      : items;
    if (!filtered.length) {
      box.innerHTML = '<div class="palette-item empty">No matches for <span class="mono">&nbsp;"' + esc(q) + '"</span></div>';
      return;
    }
    var groups = {};
    filtered.forEach(function (it) { (groups[it.group] = groups[it.group] || []).push(it); });
    var html = '';
    Object.keys(groups).forEach(function (g) {
      html += '<div class="palette-group">' + esc(g) + '</div>';
      groups[g].forEach(function (it, i) {
        html += '<button class="palette-item" data-i="' + i + '">' +
          '<span class="pi-icon">' + (ICONS[it.icon] || ICONS.bolt) + '</span>' +
          '<span class="pi-title">' + esc(it.label) + '</span>' +
          (it.sub ? '<span class="pi-sub">' + esc(it.sub) + '</span>' : '') + '</button>';
      });
    });
    box.innerHTML = html;
    box.setAttribute('data-items', JSON.stringify(filtered.map(function (it) { return it.label; })));
    var first = $('.palette-item', box);
    if (first) first.classList.add('selected');
  }

  function paletteSelect() {
    var box = $('#palette-results');
    var sel = $('.palette-item.selected', box);
    if (!sel) return;
    var items = paletteItems();
    var labels = JSON.parse(box.getAttribute('data-items') || '[]');
    var idx = Array.prototype.indexOf.call($$('.palette-item', box), sel);
    var label = labels[idx];
    var item = items.find(function (it) { return it.label === label; });
    if (item) { closePalette(); item.run(); }
  }

  function paletteMove(dir) {
    var box = $('#palette-results');
    var items = $$('.palette-item', box);
    if (!items.length) return;
    var cur = Array.prototype.indexOf.call(items, $('.palette-item.selected', box));
    var next = cur + dir;
    if (next < 0) next = items.length - 1;
    if (next >= items.length) next = 0;
    items[cur] && items[cur].classList.remove('selected');
    items[next].classList.add('selected');
    items[next].scrollIntoView({ block: 'nearest' });
  }

  /* ================= shell events ================= */

  function bindShell() {
    var collapsed = (function () { try { return localStorage.getItem('cb-collapsed') === '1'; } catch (e) { return false; } })();
    if (collapsed) document.body.classList.add('side-collapsed');

    $('#side-collapse').addEventListener('click', function () {
      document.body.classList.toggle('side-collapsed');
      try { localStorage.setItem('cb-collapsed', document.body.classList.contains('side-collapsed') ? '1' : '0'); } catch (e) { /* noop */ }
    });
    $('#hamburger').addEventListener('click', function () {
      document.body.classList.add('side-open');
      $('#side-scrim').hidden = false;
      $('#hamburger').setAttribute('aria-expanded', 'true');
    });
    $('#side-scrim').addEventListener('click', function () {
      document.body.classList.remove('side-open');
      this.hidden = true;
      $('#hamburger').setAttribute('aria-expanded', 'false');
    });

    $('#theme-toggle').addEventListener('click', toggleTheme);
    $('#search-trigger').addEventListener('click', openPalette);
    var tabRun = $('#tab-run');
    if (tabRun) tabRun.addEventListener('click', function () { toast('Pipeline started', 'run queued on main'); });

    var notifBtn = $('#notif-btn');
    var panel = $('#notif-panel');
    notifBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = !panel.hidden;
      panel.hidden = open;
      notifBtn.setAttribute('aria-expanded', String(!open));
      if (!open) renderNotifPanel();
    });
    document.addEventListener('click', function (e) {
      if (!panel.hidden && !panel.contains(e.target) && e.target !== notifBtn) {
        panel.hidden = true;
        notifBtn.setAttribute('aria-expanded', 'false');
      }
    });

    // palette
    var backdrop = $('#palette-backdrop');
    var input = $('#palette-input');
    backdrop.addEventListener('click', function (e) { if (e.target === backdrop) closePalette(); });
    input.addEventListener('input', function () { renderPalette(paletteItems(), input.value); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); paletteMove(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); paletteMove(-1); }
      else if (e.key === 'Enter') { e.preventDefault(); paletteSelect(); }
    });
    $('#palette-results').addEventListener('click', function (e) {
      var item = e.target.closest('.palette-item');
      if (!item) return;
      $$('.palette-item', this).forEach(function (x) { x.classList.remove('selected'); });
      item.classList.add('selected');
      paletteSelect();
    });

    // global keys
    document.addEventListener('keydown', function (e) {
      var mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); backdrop.hidden ? openPalette() : closePalette(); return; }
      if (e.key === 'Escape') { closePalette(); $('#notif-panel').hidden = true; return; }
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === '/') { e.preventDefault(); openPalette(); return; }
      if (e.key === 'r') { toast('Pipeline started', 'run queued on main'); return; }
      if (e.key === 'g') {
        pendingG = true;
        setTimeout(function () { pendingG = false; }, 900);
        return;
      }
      if (pendingG) {
        pendingG = false;
        if (e.key === 'p') location.hash = '#/pipelines';
        else if (e.key === 'd') location.hash = '#/deployments';
        else if (e.key === 'a') location.hash = '#/anomalies';
        else if (e.key === 'o') location.hash = '#/overview';
      }
    });
  }

  var pendingG = false;

  /* ================= per-view bindings ================= */

  function bindView() {
    switch (state.view) {
      case 'pipelines': bindPipelinesFilters(); break;
      case 'pipeline': bindPipelineDetail(); break;
      case 'environments': bindEnvironments(); break;
      case 'analytics': bindAnalytics(); break;
      case 'settings': bindSettings(); break;
    }
  }

  /* ================= boot ================= */

  function boot() {
    var stored = (function () { try { return localStorage.getItem('cb-theme'); } catch (e) { return null; } })();
    applyTheme(stored || 'dark');

    bindShell();
    window.addEventListener('hashchange', navigate);

    var viewEl = $('#view');
    viewEl.innerHTML =
      '<div class="stat-grid">' +
        Array(4).fill('<div class="stat-tile"><div class="skeleton skel-title"></div><div class="skeleton skel-text" style="width:60%;margin-top:10px"></div></div>').join('') +
      '</div>' +
      '<div class="grid-2"><div class="panel"><div class="panel-head"><div class="skeleton skel-text" style="width:120px"></div></div>' +
      '<div class="panel-body">' + Array(4).fill('<div class="skeleton skel-text" style="height:40px;margin-bottom:8px"></div>').join('') + '</div></div>' +
      '<div class="panel"><div class="panel-head"><div class="skeleton skel-text" style="width:120px"></div></div>' +
      '<div class="panel-body">' + Array(4).fill('<div class="skeleton skel-text" style="height:40px;margin-bottom:8px"></div>').join('') + '</div></div></div>';

    loadData().then(function () {
      navigate();
    });
    setInterval(function () { refresh(false); }, 45000);
  }

  // expose render hook so per-view bindings can be attached after innerHTML
  var _origRender = render;
  render = function () { _origRender(); bindView(); };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
