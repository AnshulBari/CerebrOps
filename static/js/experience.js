/* ============================================================
   CerebrOps experience — Three.js scenes
   Three particle worlds behind the hero card:
     pipeline       → double-helix of commits with a traveling pulse
     detection      → vortex with periodic anomaly flares
     observability  → rising signal beams
   ============================================================ */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- reveal on scroll ---------- */
  var revealEls = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var revealObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); revealObs.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { revealObs.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add('in'); });
  }

  var backdrop = document.getElementById('xp-canvas');
  var host = backdrop ? backdrop.parentElement : document.getElementById('hero-card');
  var tag = document.getElementById('scene-tag');
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.xp-tab'));
  if (!host || !window.THREE) return;

  var BLUE = new THREE.Color('#4c8dff');
  var BLUE_HI = new THREE.Color('#8ab4ff');
  var AMBER = new THREE.Color('#ff9d4d');
  var PURPLE = new THREE.Color('#7c5cff');
  var TEAL = new THREE.Color('#3dd6c9');

  /* ---------- renderer / camera ----------
     Three creates its own canvas so a pre-existing context on the
     fallback backdrop can never break renderer creation. */
  var renderer = null;
  var canvas = null;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    canvas = renderer.domElement;
    canvas.style.position = 'absolute';
    canvas.style.inset = '0';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.zIndex = '1';
    host.insertBefore(canvas, host.firstChild);
  } catch (err) {
    renderer = null;
    canvas = null;
  }
  if (!renderer || !canvas) return; // CSS backdrop keeps the card presentable
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(58, 1, 0.1, 120);
  camera.position.set(0, 0, 12.5);

  var pointer = { x: 0, y: 0 };
  var scrollVel = 0;
  var activeGroup = null;
  var worlds = {};

  function makePoints(count, colorFn, size) {
    var pos = new Float32Array(count * 3);
    var col = new Float32Array(count * 3);
    var c = new THREE.Color();
    for (var i = 0; i < count; i++) {
      pos[i * 3] = 0; pos[i * 3 + 1] = 0; pos[i * 3 + 2] = 0;
      colorFn(i, count, pos, c);
      col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
    }
    var geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
    var mat = new THREE.PointsMaterial({
      size: size || 0.09,
      vertexColors: true,
      transparent: true,
      opacity: 0.92,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      sizeAttenuation: true,
    });
    mat.userData.baseSize = mat.size; // calibration adjusts from here
    return new THREE.Points(geo, mat);
  }

  /* ================= WORLD 1 — pipeline helix ================= */
  function buildHelix() {
    var group = new THREE.Group();
    var N = 1400;
    var pts = makePoints(N, function (i, count, pos, c) {
      var t = i / count;
      var strand = i % 2;
      var turns = 2.6;
      var ang = t * Math.PI * 2 * turns + (strand ? Math.PI : 0);
      var radius = 3.9 + Math.sin(t * 22) * 0.18;
      var y = (t - 0.5) * 11;
      pos[0] = Math.cos(ang) * radius;
      pos[1] = y;
      pos[2] = Math.sin(ang) * radius;
      var c2 = strand ? BLUE : AMBER;
      var mix = 0.5 + 0.5 * Math.sin(t * 40 + strand * 2);
      c.copy(c2).lerp(BLUE_HI, strand ? mix * 0.3 : mix * 0.45);
      c.multiplyScalar(0.9 + 0.35 * Math.sin(t * 40 + (strand ? Math.PI : 0)));
    }, 0.5);
    group.add(pts);

    // the traveling commit pulse
    var pulseMat = new THREE.PointsMaterial({
      size: 1.3, color: 0xffffff, transparent: true, opacity: 0.95,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    pulseMat.userData.baseSize = pulseMat.size;
    var pulseGeo = new THREE.BufferGeometry();
    pulseGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3), 3));
    var pulse = new THREE.Points(pulseGeo, pulseMat);
    group.add(pulse);

    group.userData = {
      update: function (time, delta) {
        var t = (time * 0.12) % 1;
        var ang = t * Math.PI * 2 * 2.6;
        var y = (t - 0.5) * 11;
        pulse.position.set(Math.cos(ang) * 3.9, y, Math.sin(ang) * 3.9);
        pulse.visible = true;
        pulseMat.opacity = 0.55 + 0.4 * Math.sin(time * 6);
        group.rotation.y += delta * 0.18;
      },
    };
    pulse.visible = false;
    return group;
  }

  /* ================= WORLD 2 — detection vortex ================= */
  function buildVortex() {
    var group = new THREE.Group();
    var N = 2600;
    var pts = makePoints(N, function (i, count, pos, c) {
      var t = i / count;
      var turns = 5 + Math.floor(t * 7);
      var ang = t * Math.PI * 2 * turns;
      var r = 5.4 * (1 - t * 0.92);
      pos[0] = Math.cos(ang) * r;
      pos[1] = Math.sin(t * 16 + ang) * 0.55 * (1 - t);
      pos[2] = Math.sin(ang) * r;
      c.copy(BLUE).lerp(PURPLE, t * 0.85);
      c.multiplyScalar(0.92 + 0.3 * Math.sin(t * 30));
    }, 0.45);

    // anomaly flares: 60 red embers orbiting the edge
    var embers = makePoints(60, function (i, count, pos, c) {
      var ang = (i / count) * Math.PI * 2;
      pos[0] = Math.cos(ang) * 5.3;
      pos[1] = 0;
      pos[2] = Math.sin(ang) * 5.3;
      c.setRGB(1, 0.45, 0.36);
    }, 0.8);

    var flareMat = new THREE.PointsMaterial({
      size: 1.2, color: 0xff6b5e, transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    flareMat.userData.baseSize = flareMat.size;
    var flareGeo = new THREE.BufferGeometry();
    flareGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3), 3));
    var flare = new THREE.Points(flareGeo, flareMat);

    group.add(pts); group.add(embers); group.add(flare);

    group.userData = {
      update: function (time, delta) {
        var r = 0.35 + 0.65 * Math.abs(Math.sin(time * 0.6));
        embers.rotation.y = time * 0.4;
        flareMat.opacity = Math.max(0, Math.sin(time * 0.8) - 0.6) * 3.2;
        var ang = time * 0.5;
        flare.position.set(Math.cos(ang) * 4.2, 0, Math.sin(ang) * 4.2);
        group.rotation.y += delta * 0.1;
        group.rotation.z = Math.sin(time * 0.15) * 0.04;
      },
    };
    return group;
  }

  /* ================= WORLD 3 — observability beams ================= */
  function buildBeams() {
    var group = new THREE.Group();
    var N = 1100;
    var pts = makePoints(N, function (i, count, pos, c) {
      var ang = (i % 90) / 90 * Math.PI * 2;
      var r = 0.8 + (i / count) * 5.2;
      pos[0] = Math.cos(ang) * r * (0.6 + 0.4 * ((i * 7) % 10) / 10);
      pos[1] = ((i * 13) % 100) / 100 * 10 - 5;
      pos[2] = Math.sin(ang) * r * (0.6 + 0.4 * ((i * 7) % 10) / 10);
      var p = pos[1] / 10 + 0.5;
      c.copy(TEAL).lerp(BLUE, p);
      c.multiplyScalar(0.85 + 0.35 * (((i * 11) % 7) / 7));
    }, 0.5);

    // beam cores
    var coreN = 26;
    var cores = makePoints(coreN, function (i, count, pos, c) {
      var ang = (i / count) * Math.PI * 2 + 0.4;
      var r = 0.9 + (i % 5) * 1.15;
      pos[0] = Math.cos(ang) * r;
      pos[1] = 0;
      pos[2] = Math.sin(ang) * r;
      c.copy(BLUE_HI).lerp(TEAL, (i % 3) / 3);
    }, 0.9);

    group.add(pts); group.add(cores);

    group.userData = {
      update: function (time, delta) {
        var p = pts.geometry.attributes.position;
        var arr = p.array;
        for (var i = 0; i < N; i++) {
          arr[i * 3 + 1] += delta * (0.7 + ((i * 7) % 5) * 0.18);
          if (arr[i * 3 + 1] > 5.2) arr[i * 3 + 1] = -5.2;
        }
        p.needsUpdate = true;
        cores.rotation.y = time * 0.25;
        group.rotation.y += delta * 0.03;
      },
    };
    return group;
  }

  /* ---------- build worlds ---------- */
  worlds.pipeline = buildHelix();
  worlds.detection = buildVortex();
  worlds.observability = buildBeams();
  scene.add(worlds.pipeline);
  scene.add(worlds.detection);
  scene.add(worlds.observability);
  worlds.detection.visible = false;
  worlds.observability.visible = false;
  activeGroup = worlds.pipeline;

  /* ---------- adaptive density ----------
     GL point sizes render differently across drivers/headless GL
     (this webview draws them ~20x smaller than a real GPU). Render one
     frame, measure how much of the canvas is lit, and scale every
     particle material to hit a target density — correct everywhere. */
  function calibrateParticles() {
    var target = 0.0042; // ~0.42% of pixels lit
    worlds.pipeline.userData.update(0.35, 0.016);
    renderer.render(scene, camera);
    var gl = renderer.getContext();
    var w = renderer.domElement.width, h = renderer.domElement.height;
    if (!w || !h) return;
    var px = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
    var lit = 0;
    for (var i = 0; i < px.length; i += 4) {
      if (px[i] + px[i + 1] + px[i + 2] > 60) lit++;
    }
    var frac = lit / (w * h);
    // lit pixels scale with area, so the size multiplier is a square root
    var mult = Math.sqrt(Math.max(0.15, Math.min(12, target / Math.max(frac, 1e-6))));
    [worlds.pipeline, worlds.detection, worlds.observability].forEach(function (g) {
      g.children.forEach(function (child) {
        var m = child.material;
        if (m && m.userData && m.userData.baseSize != null) m.size = m.userData.baseSize * mult;
      });
    });
  }
  calibrateParticles();

  var SCENE_TAGS = { pipeline: 'pipeline · helix', detection: 'detection · vortex', observability: 'observability · beams' };

  function setWorld(key) {
    if (activeGroup === worlds[key]) return;
    if (activeGroup) activeGroup.visible = false;
    activeGroup = worlds[key];
    activeGroup.visible = true;
    canvas.classList.remove('xp-fade');
    void canvas.offsetWidth;
    canvas.classList.add('xp-fade');
    if (tag) tag.textContent = SCENE_TAGS[key] || key;
  }

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.classList.toggle('on', on);
        t.setAttribute('aria-pressed', String(on));
      });
      setWorld(tab.getAttribute('data-scene'));
    });
  });

  /* ---------- resize ---------- */
  function resize() {
    var rect = canvas.parentElement.getBoundingClientRect();
    var w = Math.max(1, rect.width);
    var h = Math.max(1, rect.height);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  if (window.ResizeObserver) {
    new ResizeObserver(resize).observe(canvas.parentElement);
  } else {
    window.addEventListener('resize', resize);
  }
  resize();

  /* ---------- pointer parallax ---------- */
  var card = document.getElementById('hero-card');
  window.addEventListener('pointermove', function (e) {
    var r = (card || document.body).getBoundingClientRect();
    pointer.x = ((e.clientX - r.left) / r.width - 0.5) * 2;
    pointer.y = ((e.clientY - r.top) / r.height - 0.5) * 2;
  }, { passive: true });

  /* ---------- scroll response ---------- */
  var lastScroll = window.scrollY;
  window.addEventListener('scroll', function () {
    scrollVel = window.scrollY - lastScroll;
    lastScroll = window.scrollY;
  }, { passive: true });

  /* ---------- render loop ----------
     rAF is the primary driver; some environments (headless webviews,
     aggressively throttled tabs) never fire it, so a watchdog falls back
     to a timer loop after 600ms of zero frames. */
  var clock = new THREE.Clock();
  var rafId = null;
  var timerId = null;
  var usingTimer = false;
  var frames = 0;

  function stopLoop() {
    if (rafId) cancelAnimationFrame(rafId);
    if (timerId) clearInterval(timerId);
    rafId = null; timerId = null;
  }
  function startLoop() {
    if (reduced) return;
    if (usingTimer) timerId = setInterval(tick, 33);
    else rafId = requestAnimationFrame(tick);
  }

  function tick() {
    frames++;
    var dt = Math.min(clock.getDelta(), 0.05);
    var t = clock.elapsedTime;
    if (activeGroup && activeGroup.userData.update) activeGroup.userData.update(t, dt);

    // parallax + scroll energy
    var px = pointer.x * 0.9 + scrollVel * 0.02;
    camera.position.x += (px - camera.position.x) * 0.05;
    camera.position.y += (-pointer.y * 0.6 - camera.position.y) * 0.05;
    camera.lookAt(0, 0, 0);
    scrollVel *= 0.92;

    renderer.render(scene, camera);
    // in timer mode the interval re-fires on its own; only rAF needs re-arming
    if (!usingTimer) rafId = requestAnimationFrame(tick);
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) stopLoop();
    else startLoop();
  });

  if (reduced) {
    worlds.pipeline.userData.update(0.35, 0.016);
    renderer.render(scene, camera);
  } else {
    startLoop();
    setTimeout(function () {
      if (frames === 0) {
        // rAF never fired (headless webview / throttled tab): fall back to
        // a timer loop AND paint one frame now so the hero is never empty.
        usingTimer = true;
        stopLoop();
        startLoop();
        if (activeGroup && activeGroup.userData.update) activeGroup.userData.update(0.35, 0.016);
        renderer.render(scene, camera);
      }
    }, 600);
  }

  /* ================= countdown ================= */
  var countEl = document.getElementById('ea-count');
  if (countEl) {
    var target = (function () {
      try {
        var v = parseInt(localStorage.getItem('cb-ea-target'), 10);
        if (v && v > Date.now()) return v;
      } catch (e) { /* noop */ }
      var t2 = Date.now() + (18 * 3600 + 58 * 60 + 33) * 1000;
      try { localStorage.setItem('cb-ea-target', String(t2)); } catch (e) { /* noop */ }
      return t2;
    })();

    function fmt(n) { return String(Math.max(0, Math.floor(n))).padStart(2, '0'); }
    function paint() {
      var s = Math.max(0, (target - Date.now()) / 1000);
      var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
      countEl.textContent = fmt(h) + ':' + fmt(m) + ':' + fmt(sec) + ' left';
    }
    paint();
    setInterval(paint, 1000);
  }

  /* ================= FAQ icons ================= */
  document.querySelectorAll('.faq-item').forEach(function (item) {
    item.addEventListener('toggle', function () {
      var icon = item.querySelector('.faq-icon');
      if (icon) icon.textContent = item.open ? '×' : '+';
    });
  });
})();
