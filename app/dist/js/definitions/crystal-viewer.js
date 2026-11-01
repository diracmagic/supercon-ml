'use strict';
// crystal-viewer: shared lexical function definitions; no startup side effects.

  const xtOn = function xtOn() { return view === 'candidates' && !document.hidden; };

  const xtItem = function xtItem(cv, M, big) {
    var it = { cv: cv, m: M, big: big, vis: !window.IntersectionObserver, W: 0, H: 0, dpr: 0, ctx: null, off: 0, pitch: XT_PITCH0, drag: null, dirty: true };
    XT.items.push(it);
    if (window.IntersectionObserver) {
      if (!XT.obs) XT.obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { XT.items.forEach(function (x) { if (x.cv === e.target) { x.vis = e.isIntersecting; x.dirty = true; } }); });
        xtKick();
      }, { rootMargin: '80px' });
      XT.obs.observe(cv);
    }
    return it;
  };

  const xtForget = function xtForget(it) { if (XT.obs) XT.obs.unobserve(it.cv); };

  const xtReset = function xtReset() { XT.items.forEach(xtForget); XT.items = []; };

  const xtDirty = function xtDirty() { XT.items.forEach(function (it) { it.dirty = true; it.W = 0; }); };

  const xtKick = function xtKick() {
    if (XT.raf || !xtOn()) return;
    XT.last = 0;
    XT.raf = requestAnimationFrame(xtFrame);
  };

  const xtFrame = function xtFrame(ts) {
    XT.raf = 0;
    if (!xtOn()) return;
    var moving = XT.play && motionOK(), dt = moving && XT.last ? Math.min(0.05, (ts - XT.last) / 1000) : 0;
    XT.last = ts;
    XT.t += dt;
    var C = null;
    XT.items.forEach(function (it) {
      if (!it.vis || !it.cv.isConnected || !(moving || it.dirty)) return;
      C = C || xtColors();
      xtPaint(it, C);
    });
    if (moving) XT.raf = requestAnimationFrame(xtFrame);
  };

  const xtColors = function xtColors() {
    var C = colors();
    C.slots = [cssVar('--series-1'), cssVar('--series-2'), cssVar('--series-3'), C.ink2].map(function (x) { return hexRgb(x); });
    C.bg = hexRgb(C.surface);
    C.bg2 = hexRgb(C.surface2);
    C.edge = hexRgb(C.axis);
    C.inkRgb = hexRgb(C.ink);
    return C;
  };

  const xtPaint = function xtPaint(it, C) {
    var W = Math.round(it.cv.clientWidth), H = Math.round(it.cv.clientHeight), dpr = Math.min(2, window.devicePixelRatio || 1);
    if (!W || !H) return;
    if (W !== it.W || H !== it.H || dpr !== it.dpr) {
      it.W = W; it.H = H; it.dpr = dpr;
      it.cv.width = Math.round(W * dpr); it.cv.height = Math.round(H * dpr);
      it.ctx = it.cv.getContext('2d');
    }
    var c = it.ctx;
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, W, H);
    xtDraw(c, C, W, H, it.m, XT_YAW0 + XT.t * XT_SPEED + it.off, it.pitch, it.big);
    it.dirty = false;
  };

  const xtMix = function xtMix(a, b, k) { return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]; };

  const xtCss = function xtCss(a) { return 'rgb(' + Math.round(a[0]) + ',' + Math.round(a[1]) + ',' + Math.round(a[2]) + ')'; };

  const xtDraw = function xtDraw(c, C, W, H, M, yaw, pitch, big) {
    var cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    var pad = big ? 10 : 3, sc = (Math.min(W, H) / 2 - pad) / M.R, ox = W / 2, oy = H / 2, ball = big ? 0.42 : 0.5;
    var proj = function (p) {
      var x1 = p[0] * cy - p[1] * sy, y1 = p[0] * sy + p[1] * cy;
      return { x: ox + sc * x1, y: oy - sc * (y1 * sp + p[2] * cp), z: p[2] * sp - y1 * cp };
    };
    var P = M.pts.map(function (a) { return proj(a.p); }), K = M.corners.map(proj), R = M.R;
    var rad = M.pts.map(function (a) { return Math.max(big ? 3 : 1.4, sc * a.r * ball); });
    var items = [];
    M.edges.forEach(function (e) { items.push({ k: 0, i: e[0], j: e[1], z: (K[e[0]].z + K[e[1]].z) / 2 }); });
    if (big) M.bonds.forEach(function (b) { items.push({ k: 1, i: b[0], j: b[1], z: (P[b[0]].z + P[b[1]].z) / 2 }); });
    P.forEach(function (q, i) { items.push({ k: 2, i: i, z: q.z }); });
    items.sort(function (u, v) { return u.z - v.z; });
    var white = [255, 255, 255], black = [0, 0, 0], fogTo = big ? C.bg : C.bg2;
    c.lineCap = 'round';
    items.forEach(function (o) {
      var fog = Math.max(0, Math.min(1, (R - o.z) / (2 * R))) * (C.dark ? 0.6 : 0.5);
      if (o.k === 0) {
        c.strokeStyle = xtCss(xtMix(C.edge, fogTo, fog * 0.7));
        c.lineWidth = big ? 1.2 : 0.8;
        c.beginPath(); c.moveTo(K[o.i].x, K[o.i].y); c.lineTo(K[o.j].x, K[o.j].y); c.stroke();
      } else if (o.k === 1) {
        var A = P[o.i], B = P[o.j], dx = B.x - A.x, dy = B.y - A.y, L = Math.sqrt(dx * dx + dy * dy), ra = rad[o.i], rb = rad[o.j];
        if (L <= ra + rb + 1) return;
        var ux = dx / L, uy = dy / L, mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2;
        c.lineWidth = Math.max(1.5, Math.min(3.2, sc * 0.16));
        c.lineCap = 'butt';
        c.strokeStyle = xtCss(xtMix(C.slots[Math.min(M.pts[o.i].slot, 3)], fogTo, fog));
        c.beginPath(); c.moveTo(A.x + ux * ra * 0.9, A.y + uy * ra * 0.9); c.lineTo(mx, my); c.stroke();
        c.strokeStyle = xtCss(xtMix(C.slots[Math.min(M.pts[o.j].slot, 3)], fogTo, fog));
        c.beginPath(); c.moveTo(mx, my); c.lineTo(B.x - ux * rb * 0.9, B.y - uy * rb * 0.9); c.stroke();
        c.lineCap = 'round';
      } else {
        var q = P[o.i], r = rad[o.i], base = xtMix(C.slots[Math.min(M.pts[o.i].slot, 3)], fogTo, fog);
        if (big) {
          var g = c.createRadialGradient(q.x - r * 0.35, q.y - r * 0.4, r * 0.1, q.x, q.y, r);
          g.addColorStop(0, xtCss(xtMix(base, white, 0.5)));
          g.addColorStop(0.55, xtCss(base));
          g.addColorStop(1, xtCss(xtMix(base, black, 0.28)));
          c.fillStyle = g;
        } else c.fillStyle = xtCss(base);
        c.beginPath(); c.arc(q.x, q.y, r, 0, 2 * Math.PI); c.fill();
        c.lineWidth = big ? 0.8 : 0.6;
        c.strokeStyle = xtCss(xtMix(base, C.dark ? black : C.inkRgb, 0.35));
        c.stroke();
        if (!big && r >= 2.5) {
          c.fillStyle = 'rgba(255,255,255,' + (C.dark ? 0.28 : 0.4) + ')';
          c.beginPath(); c.arc(q.x - r * 0.32, q.y - r * 0.34, r * 0.32, 0, 2 * Math.PI); c.fill();
        }
      }
    });
  };

  // drag (mouse, pen or a sideways swipe) or the arrow keys turn the large structure
  const xtDragOn = function xtDragOn(cv, it) {
    cv.addEventListener('pointerdown', function (e) {
      if (e.button !== undefined && e.button !== 0) return;
      it.drag = { x: e.clientX, y: e.clientY, off: it.off, pitch: it.pitch, t: XT.t };
      try { cv.setPointerCapture(e.pointerId); } catch (err) { /* capture is optional */ }
    });
    cv.addEventListener('pointermove', function (e) {
      if (!it.drag) return;
      it.off = it.drag.off + (e.clientX - it.drag.x) * 0.012 - (XT.t - it.drag.t) * XT_SPEED;
      it.pitch = Math.max(-1.35, Math.min(1.35, it.drag.pitch + (e.clientY - it.drag.y) * 0.01));
      it.dirty = true;
      xtKick();
    });
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(function (ev) { cv.addEventListener(ev, function () { it.drag = null; }); });
    cv.addEventListener('keydown', function (e) {
      var k = e.key;
      if (k === 'ArrowLeft' || k === 'ArrowRight') it.off += (k === 'ArrowLeft' ? -1 : 1) * Math.PI / 12;
      else if (k === 'ArrowUp' || k === 'ArrowDown') it.pitch = Math.max(-1.35, Math.min(1.35, it.pitch + (k === 'ArrowUp' ? 0.17 : -0.17)));
      else return;
      e.preventDefault();
      it.dirty = true;
      xtKick();
    });
  };

  // a structure as drawn: the stored sites plus their copies on the cell's faces, edges and corners, in a frame with c up
  const xtNum = function xtNum(x) { return typeof x === 'number' && isFinite(x); };

  const xtDot = function xtDot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; };

  const xtLen = function xtLen(a) { return Math.sqrt(xtDot(a, a)); };

  const xtUnit = function xtUnit(a) { var n = xtLen(a) || 1; return [a[0] / n, a[1] / n, a[2] / n]; };

  const xtAngle = function xtAngle(a, b) { return Math.acos(Math.max(-1, Math.min(1, xtDot(a, b) / (xtLen(a) * xtLen(b) || 1)))); };

  const xtModel = function xtModel(c) {
    var s = c && c.atoms;
    if (!s || typeof s !== 'object' || s.__m === false) return null;
    if (s.__m) return s.__m;
    var Lt = s.lattice, E = s.elements, F = s.frac;
    var ok = Array.isArray(Lt) && Lt.length === 3 && Array.isArray(E) && Array.isArray(F) && E.length > 0 && E.length === F.length && E.length <= 200 &&
      Lt.every(function (v) { return Array.isArray(v) && v.length === 3 && v.every(xtNum); }) &&
      F.every(function (v) { return Array.isArray(v) && v.length === 3 && v.every(xtNum); }) &&
      E.every(function (e) { return typeof e === 'string' && XT_Z[e] !== undefined; });
    var A = ok && Lt[0], B = ok && Lt[1], Cv = ok && Lt[2];
    var vol = ok ? A[0] * (B[1] * Cv[2] - B[2] * Cv[1]) - A[1] * (B[0] * Cv[2] - B[2] * Cv[0]) + A[2] * (B[0] * Cv[1] - B[1] * Cv[0]) : 0;
    if (!ok || !(Math.abs(vol) > 1) || Math.abs(vol) > 1e5) { xtKeep(s, false); return null; }
    var up = xtUnit(Cv), xa = [A[0] - up[0] * xtDot(A, up), A[1] - up[1] * xtDot(A, up), A[2] - up[2] * xtDot(A, up)];
    if (xtLen(xa) < 1e-6) xa = [B[0] - up[0] * xtDot(B, up), B[1] - up[1] * xtDot(B, up), B[2] - up[2] * xtDot(B, up)];
    xa = xtUnit(xa);
    var ya = [up[1] * xa[2] - up[2] * xa[1], up[2] * xa[0] - up[0] * xa[2], up[0] * xa[1] - up[1] * xa[0]];
    var toFrame = function (f) {
      var v = [0, 1, 2].map(function (k) { return (f[0] - 0.5) * A[k] + (f[1] - 0.5) * B[k] + (f[2] - 0.5) * Cv[k]; });
      return [xtDot(v, xa), xtDot(v, ya), xtDot(v, up)];
    };
    // elements in the order of the formula, then any others as they appear
    var els = [];
    String(c.formula).replace(/[A-Z][a-z]?/g, function (x) { if (E.indexOf(x) >= 0 && els.indexOf(x) < 0) els.push(x); return x; });
    E.forEach(function (e) { if (els.indexOf(e) < 0) els.push(e); });
    var pts = [], eps = 0.02;
    for (var i = 0; i < E.length && pts.length < 400; i++) {
      var f = F[i].map(function (x) { var y = x - Math.floor(x); return y > 1 - 1e-4 ? 0 : y; });
      var o = f.map(function (x) { return x < eps ? [x, x + 1] : x > 1 - eps ? [x, x - 1] : [x]; });
      for (var a = 0; a < o[0].length; a++) for (var b = 0; b < o[1].length; b++) for (var d = 0; d < o[2].length; d++) {
        pts.push({ p: toFrame([o[0][a], o[1][b], o[2][d]]), slot: els.indexOf(E[i]), r: XT_R[XT_Z[E[i]]] / 100 });
      }
    }
    var corners = [], edges = [], k;
    for (k = 0; k < 8; k++) corners.push(toFrame([k & 1, (k >> 1) & 1, (k >> 2) & 1]));
    for (k = 0; k < 8; k++) [1, 2, 4].forEach(function (bit) { if (!(k & bit)) edges.push([k, k | bit]); });
    // bonds: neighbours closer than 1.12 times the sum of their covalent radii
    var bonds = [];
    for (i = 0; i < pts.length && bonds.length < 1500; i++) for (var j = i + 1; j < pts.length; j++) {
      var dx = pts[i].p[0] - pts[j].p[0], dy = pts[i].p[1] - pts[j].p[1], dz = pts[i].p[2] - pts[j].p[2], dd = Math.sqrt(dx * dx + dy * dy + dz * dz);
      if (dd > 0.5 && dd < 1.12 * (pts[i].r + pts[j].r)) bonds.push([i, j]);
    }
    var R = 0;
    pts.forEach(function (q) { R = Math.max(R, xtLen(q.p) + q.r * 0.5); });
    corners.forEach(function (p) { R = Math.max(R, xtLen(p)); });
    var count = {};
    E.forEach(function (e) { count[e] = (count[e] || 0) + 1; });
    var M = { pts: pts, corners: corners, edges: edges, bonds: bonds, R: R || 1, els: els, count: count, n: E.length,
      abc: [xtLen(A), xtLen(B), xtLen(Cv)], ang: [xtAngle(B, Cv), xtAngle(A, Cv), xtAngle(A, B)], vol: Math.abs(vol) };
    xtKeep(s, M);
    return M;
  };

  // the drawn model is kept on the structure object, hidden from JSON, so that a re-render does not rebuild it
  const xtKeep = function xtKeep(s, M) { try { Object.defineProperty(s, '__m', { value: M, enumerable: false, configurable: true }); } catch (err) { /* rebuilt next time */ } };
