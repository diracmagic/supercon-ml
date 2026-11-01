'use strict';
// mini-player: shared lexical function definitions; no startup side effects.

  const miniCanvas = function miniCanvas(kind) {
    var cv = h('canvas', { class: 'mini', role: 'img', 'aria-label': MINI_ALT[kind] || '' });
    var it = { cv: cv, kind: kind, t: 0, vis: !window.IntersectionObserver, W: 0, H: 0, dpr: 0, ctx: null };
    MINI.items.push(it);
    if (window.IntersectionObserver) {
      if (!MINI.obs) MINI.obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          MINI.items.forEach(function (x) { if (x.cv === e.target) x.vis = e.isIntersecting; });
        });
        miniKick();
      }, { rootMargin: '60px' });
      MINI.obs.observe(cv);
    }
    return cv;
  };

  const miniPrune = function miniPrune() {
    MINI.items = MINI.items.filter(function (it) {
      if (it.cv.isConnected) return true;
      if (MINI.obs) MINI.obs.unobserve(it.cv);
      return false;
    });
  };

  const miniOn = function miniOn() { return (view === 'learn' || view === 'papers' || view === 'authors') && !document.hidden; };

  const miniKick = function miniKick() {
    if (MINI.raf || !miniOn()) return;
    MINI.last = 0;
    MINI.raf = requestAnimationFrame(miniFrame);
  };

  const miniFrame = function miniFrame(ts) {
    MINI.raf = 0;
    if (!miniOn()) return;
    var moving = motionOK(), dt = moving && MINI.last ? Math.min(0.05, (ts - MINI.last) / 1000) : 0, any = false;
    MINI.last = ts;
    var C = colors();
    MINI.items.forEach(function (it) {
      if (!it.vis || !it.cv.isConnected) return;
      var W = Math.round(it.cv.clientWidth), H = Math.round(it.cv.clientHeight), dpr = Math.min(2, window.devicePixelRatio || 1);
      if (!W || !H) return;
      if (W !== it.W || H !== it.H || dpr !== it.dpr) {
        it.W = W; it.H = H; it.dpr = dpr;
        it.cv.width = Math.round(W * dpr); it.cv.height = Math.round(H * dpr);
        it.ctx = it.cv.getContext('2d');
      }
      it.t += dt;
      var c = it.ctx;
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      c.clearRect(0, 0, W, H);
      c.fillStyle = C.surface2;
      c.fillRect(0, 0, W, H);
      var fn = MINI_DRAW[it.kind];
      if (fn) { c.save(); fn(c, C, W, H, moving ? it.t : (MINI_STATIC[it.kind] || 4)); c.restore(); }
      any = true;
    });
    if (moving && any) MINI.raf = requestAnimationFrame(miniFrame);
  };
