/* ============================================================
   CerebrOps landing — hero pipeline animation, scroll story,
   reveals, count-ups. Zero dependencies, respects reduced motion.
   ============================================================ */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ============================================================
     Cinematic hero — entrance animation + scroll parallax
     ============================================================ */

  /* --- wordmark: GSAP ScrambleTextPlugin --- */
  var wordmark = document.getElementById('hero-wordmark');
  if (wordmark && typeof gsap !== 'undefined' && typeof ScrambleTextPlugin !== 'undefined') {
    gsap.registerPlugin(ScrambleTextPlugin);
    // store the final text
    var wmText = wordmark.textContent.trim();
    // start with scrambled text
    wordmark.textContent = wmText;
    // set initial state
    wordmark.classList.add('revealed');
    // create scramble animation
    gsap.fromTo(wordmark, {
      scrambleText: {
        text: wmText,
        chars: 'uppercase',
        revealDelay: 0.5,
        speed: 0.8,
        delimiter: ''
      },
      opacity: 0,
      y: 20
    }, {
      duration: 2.0,
      scrambleText: {
        text: wmText,
        chars: 'uppercase',
        revealDelay: 0.5,
        speed: 0.8,
        delimiter: ''
      },
      opacity: 0.92,
      y: 0,
      ease: 'power2.out',
      delay: 0.8
    });
  }

  /* --- headline: no JS splitting needed, just add .revealed class --- */
  var cinemaTitle = document.getElementById('hero-cinema-title');

  /* --- entrance sequence --- */
  if (!reduced) {
    setTimeout(function () {
      if (cinemaTitle) cinemaTitle.classList.add('revealed');
    }, 300);
    // wordmark handled by GSAP above if available
    if (typeof gsap === 'undefined' || typeof ScrambleTextPlugin === 'undefined') {
      setTimeout(function () {
        if (wordmark) wordmark.classList.add('revealed');
      }, 700);
    }
  } else {
    if (cinemaTitle) cinemaTitle.classList.add('revealed');
    if (wordmark) wordmark.classList.add('revealed');
  }

  /* --- navbar: hide on hero, show on scroll --- */
  var nav = document.querySelector('.landing-nav');
  if (nav && heroSection) {
    var navTicking = false;
    function checkNav() {
      if (navTicking) return;
      navTicking = true;
      requestAnimationFrame(function () {
        var scrollY = window.pageYOffset || document.documentElement.scrollTop;
        var heroH = heroSection.offsetHeight;
        if (scrollY > heroH * 0.6) {
          nav.classList.add('visible');
        } else {
          nav.classList.remove('visible');
        }
        navTicking = false;
      });
    }
    window.addEventListener('scroll', checkNav, { passive: true });
    checkNav();
  }

  /* --- scroll parallax --- */
  var heroSection = document.querySelector('.hero-cinematic');
  var cinemaContent = document.querySelector('.hero-cinema-content');
  var wordmarkWrap = document.querySelector('.hero-wordmark-wrap');

  if (heroSection && !reduced) {
    var ticking = false;
    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        var scrollY = window.pageYOffset || document.documentElement.scrollTop;
        var heroH = heroSection.offsetHeight;
        if (heroH <= 0) { ticking = false; return; }
        var progress = Math.min(1, Math.max(0, scrollY / heroH));

        // headline moves up, fades
        if (cinemaContent) {
          var isMobile = window.innerWidth <= 760;
          var baseTx = isMobile ? 'translateX(-50%) ' : '';
          cinemaContent.style.transform = baseTx + 'translateY(calc(-55% + ' + (-progress * 80) + 'px))';
          cinemaContent.style.opacity = String(1 - progress * 1.2);
        }
        // wordmark moves down, fades
        if (wordmarkWrap) {
          wordmarkWrap.style.transform = 'translateY(' + (progress * 50) + 'px)';
          wordmarkWrap.style.opacity = String(0.9 - progress * 1.1);
        }
        // video dims slightly
        var vid = heroSection.querySelector('.hero-video');
        if (vid) {
          vid.style.filter = 'brightness(' + (1.12 - progress * 0.35) + ') saturate(1.06)';
        }

        ticking = false;
      });
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

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
  var revealEls = document.querySelectorAll('.reveal, .split, .gsap-reveal');
  if ('IntersectionObserver' in window) {
    var revealObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); revealObs.unobserve(e.target); }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
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

  /* ============================================================
     Chapter animations — scroll-driven
     ============================================================ */

  /* --- Chapter 01: Pipeline scroll activation --- */
  var pipelineViz = document.getElementById('pipeline-viz');
  if (pipelineViz && !reduced) {
    var pipeNodes = pipelineViz.querySelectorAll('.pipe-node');
    var pipePulse = pipelineViz.querySelector('.pipe-pulse');
    var pipeInfo = document.getElementById('pipe-info');
    var pipeStageEl = document.getElementById('pipe-info-stage');
    var pipeDetailEl = document.getElementById('pipe-info-detail');
    var stageNames = ['COMMIT', 'BUILD', 'TEST', 'SECURITY', 'DEPLOY', 'PRODUCTION'];
    var stageDetails = ['7d2f9a1 · main', '42s · cached', '312 passed · 98.5%', 'trivy · 0 critical', 'rolling · 2/2 ready', 'live · watching'];
    var pipeActivated = false;

    if (pipeNodes.length) {
      var pipeObs = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting && !pipeActivated) {
            pipeActivated = true;
            activatePipeline();
            pipeObs.unobserve(e.target);
          }
        });
      }, { threshold: 0.3 });
      pipeObs.observe(pipelineViz);
    }

    function activatePipeline() {
      var delay = 0;
      pipeNodes.forEach(function (node, i) {
        setTimeout(function () {
          // deactivate previous
          if (i > 0) {
            pipeNodes[i - 1].classList.remove('active');
            pipeNodes[i - 1].classList.add('done');
          }
          node.classList.add('active');
          // move pulse
          if (pipePulse) {
            var circle = node.querySelector('circle');
            if (circle) {
              var ctm = circle.getCTM();
              if (ctm) {
                pipePulse.setAttribute('cx', ctm.e);
                pipePulse.setAttribute('cy', ctm.f);
                pipePulse.setAttribute('opacity', '1');
              }
            }
          }
          // update info
          if (pipeStageEl) pipeStageEl.textContent = stageNames[i];
          if (pipeDetailEl) pipeDetailEl.textContent = stageDetails[i];
        }, delay);
        delay += 400;
      });
      // final state
      setTimeout(function () {
        pipeNodes[pipeNodes.length - 1].classList.remove('active');
        pipeNodes[pipeNodes.length - 1].classList.add('done');
        if (pipePulse) pipePulse.setAttribute('opacity', '0');
        if (pipeStageEl) pipeStageEl.textContent = 'COMPLETE';
        if (pipeDetailEl) pipeDetailEl.textContent = 'RUN_1842 · healthy';
      }, delay + 200);
    }
  }

  /* --- Chapter 02: Detection graph animation --- */
  var detectViz = document.getElementById('detect-viz');
  if (detectViz && !reduced) {
    var detectActivated = false;
    var detectObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !detectActivated) {
          detectActivated = true;
          animateDetection();
          detectObs.unobserve(e.target);
        }
      });
    }, { threshold: 0.3 });
    detectObs.observe(detectViz);

    function animateDetection() {
      var fill = detectViz.querySelector('.detect-fill');
      var dot = detectViz.querySelector('.detect-anomaly-dot');
      var line = detectViz.querySelector('.detect-anomaly-line');
      var label = detectViz.querySelector('.detect-anomaly-label');
      // Wait for normal path to be visible, then show anomaly
      setTimeout(function () {
        if (fill) { fill.style.transition = 'opacity 0.8s'; fill.style.opacity = '1'; }
        if (dot) { dot.style.transition = 'opacity 0.5s'; dot.style.opacity = '1'; }
        if (line) { line.style.transition = 'opacity 0.5s'; line.style.opacity = '0.6'; }
        if (label) { label.style.transition = 'opacity 0.5s'; label.style.opacity = '1'; }
      }, 600);
    }
  }

  /* --- Chapter 03: Trace tree animation --- */
  var traceViz = document.getElementById('trace-viz');
  if (traceViz && !reduced) {
    var traceItems = traceViz.querySelectorAll('.trace-item');
    var traceActivated = false;

    if (traceItems.length) {
      var traceObs = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting && !traceActivated) {
            traceActivated = true;
            animateTrace();
            traceObs.unobserve(e.target);
          }
        });
      }, { threshold: 0.3 });
      traceObs.observe(traceViz);
    }

    function animateTrace() {
      traceItems.forEach(function (item, i) {
        setTimeout(function () {
          item.classList.add('trace-item--active');
        }, i * 250);
      });
    }
  }

  /* --- Chapter 04: Observability counters --- */
  var obsConsole = document.getElementById('obs-console');
  if (obsConsole && !reduced) {
    var obsActivated = false;
    var obsObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !obsActivated) {
          obsActivated = true;
          // trigger count-up on all data-count elements within
          obsConsole.querySelectorAll('[data-count]').forEach(function (el) {
            countUp(el);
          });
          obsObs.unobserve(e.target);
        }
      });
    }, { threshold: 0.3 });
    obsObs.observe(obsConsole);
  }

  /* --- Chapter 05: Flow signals --- */
  var flowViz = document.getElementById('flow-viz');
  if (flowViz && !reduced) {
    var flowActivated = false;
    var flowObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !flowActivated) {
          flowActivated = true;
          flowViz.classList.add('in');
          flowObs.unobserve(e.target);
        }
      });
    }, { threshold: 0.3 });
    flowObs.observe(flowViz);
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
