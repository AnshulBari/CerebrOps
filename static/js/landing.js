/* ============================================================
   CerebrOps landing — hero pipeline animation, scroll story,
   reveals, count-ups. Zero dependencies, respects reduced motion.
   ============================================================ */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- word-level split for primary headlines ---------- */
  function splitWords(root) {
    var counter = 0;
    Array.prototype.slice.call(root.childNodes).forEach(function (node) {
      if (node.nodeType === 3) { // text node → one masked unit per word
        var parts = node.nodeValue.split(/(\s+)/);
        var frag = document.createDocumentFragment();
        parts.forEach(function (part) {
          if (!part) return;
          if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(part)); return; }
          counter += 1;
          var wv = document.createElement('span');
          wv.className = 'wv';
          var wi = document.createElement('span');
          wi.className = 'wvi';
          wi.style.transitionDelay = (counter * 55) + 'ms';
          wi.textContent = part;
          wv.appendChild(wi);
          frag.appendChild(wv);
        });
        node.parentNode.replaceChild(frag, node);
      } else if (node.nodeType === 1 && node.tagName.toLowerCase() !== 'br') {
        // element child (gradient / serif accent) rises as one unit
        counter += 1;
        var wv2 = document.createElement('span');
        wv2.className = 'wv';
        var wi2 = document.createElement('span');
        wi2.className = 'wvi';
        wi2.style.transitionDelay = (counter * 55) + 'ms';
        node.parentNode.insertBefore(wv2, node);
        wv2.appendChild(wi2);
        wi2.appendChild(node);
      }
    });
  }
  document.querySelectorAll('.split').forEach(splitWords);

  /* ---------- reveal on scroll ---------- */
  var revealEls = document.querySelectorAll('.reveal, .split');
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

  /* ---------- count-up stats ---------- */
  function countUp(el) {
    var target = parseFloat(el.getAttribute('data-count') || '0');
    var dur = 900;
    var t0 = null;
    function frame(t) {
      if (!t0) t0 = t;
      var p = Math.min(1, (t - t0) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      var val = target * eased;
      el.textContent = (target % 1 === 0)
        ? Math.round(val).toLocaleString()
        : val.toFixed(1);
      if (p < 1) requestAnimationFrame(frame);
      else el.textContent = (target % 1 === 0) ? Math.round(target).toLocaleString() : target.toFixed(1);
    }
    requestAnimationFrame(frame);
  }
  if ('IntersectionObserver' in window && !reduced) {
    var statObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          var valEl = e.target.querySelector('[data-count]') || e.target;
          countUp(valEl);
          statObs.unobserve(e.target);
        }
      });
    }, { threshold: 0.5 });
    document.querySelectorAll('.obs-stat').forEach(function (s) { statObs.observe(s); });
  } else {
    document.querySelectorAll('[data-count]').forEach(function (el) {
      var t = parseFloat(el.getAttribute('data-count'));
      el.textContent = (t % 1 === 0) ? t.toLocaleString() : t.toFixed(1);
    });
  }

  /* ---------- hero pipeline cycle ---------- */
  var hero = document.getElementById('hero-pipeline');
  var pulse = document.getElementById('pulse');
  var meta = document.getElementById('vis-meta');
  var commitEl = document.getElementById('vis-commit');
  var checkEl = document.getElementById('vis-check');
  var liveDot = document.getElementById('vis-live-dot');

  var commits = [
    ['7d2f9a1', 'fix: backpressure on webhook ingress'],
    ['9c41be2', 'feat: forecast-residual detection v2'],
    ['3a08f77', 'chore: pin trivy-action to 0.35.0'],
    ['e5d90b4', 'feat: deploy-correlated root cause'],
  ];
  var durations = [42, 18, 9, 26, 11];

  if (hero && !reduced) {
    var stages = Array.prototype.slice.call(hero.querySelectorAll('.stage'));
    var idx = 0;
    var runNo = 1842;
    var commitIdx = 0;

    function stageCenter(i) {
      var el = stages[i];
      return el.offsetLeft + el.offsetWidth / 2;
    }

    function placePulse(i) {
      pulse.style.left = stageCenter(i) + 'px';
    }

    function setStage(i, state) {
      var el = stages[i];
      el.classList.toggle('done', state === 'done');
      el.classList.toggle('on', state === 'on');
      var time = el.querySelector('[data-time]');
      if (state === 'on' && time && time.textContent === '—') {
        var secs = durations[i % durations.length] * (i + 1) / 6 | 0;
        time.textContent = '0:' + String(secs).padStart(2, '0');
      }
      if (state === 'done') {
        var t = el.querySelector('[data-time]');
        if (t && t.textContent === '—') t.textContent = '0:' + String(durations[i % durations.length] | 0).padStart(2, '0');
      }
    }

    function reset() {
      stages.forEach(function (s) { s.classList.remove('on', 'done'); });
      stages.forEach(function (s) {
        var t = s.querySelector('[data-time]');
        if (t) t.textContent = '—';
      });
      checkEl.style.opacity = '0';
    }

    function tick() {
      if (idx >= stages.length) {
        // run finished — show the green check, then start a new commit
        checkEl.style.opacity = '1';
        idx = 0;
        setTimeout(function () {
          reset();
          runNo += 1;
          commitIdx = (commitIdx + 1) % commits.length;
          commitEl.textContent = commits[commitIdx][0] + ' · ' + commits[commitIdx][1];
          meta.textContent = 'run-' + runNo + ' · ' + durations[0] + 's';
          setTimeout(function () { tick(); }, 420);
        }, 1400);
        return;
      }
      var i = idx;
      placePulse(i);
      setStage(i, 'on');
      var prev = i - 1;
      if (prev >= 0) setStage(prev, 'done');
      idx += 1;
      setTimeout(tick, 760);
    }

    window.addEventListener('resize', function () {
      pulse.style.left = stageCenter(Math.max(0, idx - 1)) + 'px';
    });
    tick();
  } else if (hero) {
    hero.querySelectorAll('.stage').forEach(function (s, i) {
      s.classList.add(i < 6 ? 'done' : 'on');
      s.classList.add('done');
    });
    if (checkEl) checkEl.style.opacity = '1';
  }

  /* ---------- scroll story: activate stages ---------- */
  var storyBlocks = document.querySelectorAll('.story-block');
  var storyStages = document.querySelectorAll('.story-stage');
  if ('IntersectionObserver' in window && storyBlocks.length) {
    var storyObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var key = e.target.getAttribute('data-story');
        storyStages.forEach(function (s) {
          s.classList.toggle('active', s.getAttribute('data-stage') === key);
        });
        storyObs.unobserve(e.target);
      });
    }, { rootMargin: '-40% 0px -45% 0px' });
    storyBlocks.forEach(function (b) { storyObs.observe(b); });
  } else if (storyStages.length) {
    storyStages[storyStages.length - 1].classList.add('active');
  }
})();
