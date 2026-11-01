'use strict';
// nobel-drawings: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconNobelDrawings = function initializeSuperconNobelDrawings() {


  /* ---------- illustrations for the Nobel Prize cards (original drawings, same engine as the card animations) ---------- */
  (function () {
    var TAU = Math.PI * 2;
    function md(t, p) { t = t % p; return t < 0 ? t + p : t; }
    function gold(C) { return C.gold || C.warm; }
    function line(c, pts, color, lw, dash) {
      c.beginPath();
      pts.forEach(function (p, i) { if (i) c.lineTo(p[0], p[1]); else c.moveTo(p[0], p[1]); });
      c.strokeStyle = color; c.lineWidth = lw || 1.5; c.setLineDash(dash || []); c.stroke(); c.setLineDash([]);
    }

    // 1913 · Kamerlingh Onnes: the resistance of mercury drops to zero at 4.2 K
    MINI_DRAW.onnes = function (c, C, W, H, t) {
      var tt = md(t, 8), sweep = 0.5 - 0.5 * Math.cos(TAU * tt / 8);
      // flask of liquid helium
      var fx = 16, fy = 18, fw = Math.min(46, W * 0.14), fh = H - 36;
      stRound(c, fx, fy, fw, fh, 8); c.fillStyle = C.surface; c.fill(); c.lineWidth = 1.2; c.strokeStyle = C.axis; c.stroke();
      c.fillStyle = stAlpha(C.accent, 0.22); c.fillRect(fx + 3, fy + fh * 0.42, fw - 6, fh * 0.58 - 4);
      for (var b = 0; b < 4; b++) {
        var by = fy + fh - 8 - md(t * 14 + b * 11, fh * 0.55);
        dot(c, fx + 9 + (b * 9) % (fw - 16), by, 1.6, stAlpha(C.accent, 0.7));
      }
      label(c, C, 'He', fx + fw / 2, fy + fh * 0.3, { align: 'center', size: 11, weight: '600', color: C.ink2 });
      // R(T) plot
      var x0 = fx + fw + 34, x1 = W - 14, y0 = 16, y1 = H - 26;
      line(c, [[x0, y0], [x0, y1], [x1, y1]], C.axis, 1);
      label(c, C, 'R', x0 - 8, y0 + 8, { align: 'right', size: 11, color: C.muted });
      label(c, C, 'T', x1, y1 + 15, { align: 'right', size: 11, color: C.muted });
      function X(T) { return x0 + (T - 4.0) / 0.4 * (x1 - x0); }
      function R(T) { return T > 4.21 ? 0.72 + (T - 4.21) * 0.6 : T > 4.19 ? 0.72 * (T - 4.19) / 0.02 : 0; }
      function Y(r) { return y1 - r * (y1 - y0); }
      var pts = [];
      for (var i = 0; i <= 80; i++) { var T = 4.0 + 0.4 * i / 80; pts.push([X(T), Y(R(T))]); }
      line(c, pts, C.accent, 1.75);
      var Tm = 4.4 - 0.4 * sweep;
      line(c, [[X(4.2), y0 + 4], [X(4.2), y1]], C.grid, 1, [3, 3]);
      label(c, C, '4.2 K', X(4.2), y1 + 15, { align: 'center', size: 11, weight: '600', color: C.ink2 });
      dot(c, X(Tm), Y(R(Tm)), 4.2, gold(C), C.surface2);
      var zero = Tm < 4.19;
      stTag(c, C, zero ? 'mercury: R = 0' : 'mercury', x0 + 10, y0 + 10, { align: 'left', size: 11, bg: zero ? stAlpha(gold(C), 0.18) : C.surface, ring: zero ? gold(C) : C.grid, color: C.ink });
    };
    MINI_STATIC.onnes = 4.6;
    MINI_ALT.onnes = 'Liquid helium cools mercury; its resistance falls suddenly to zero at 4.2 kelvin.';

    // 1987 · Bednorz and Müller: layered copper oxides, with pairs moving in the CuO2 planes
    MINI_DRAW.cuprate = function (c, C, W, H, t) {
      var planes = [H * 0.34, H * 0.68], sk = 10, a = Math.max(18, Math.min(26, (W - 40) / 12)), n = Math.floor((W - 40) / a);
      var x0 = (W - n * a) / 2;
      planes.forEach(function (py, k) {
        c.beginPath(); c.moveTo(x0, py + 6); c.lineTo(x0 + sk, py - 6); c.lineTo(x0 + n * a + sk, py - 6); c.lineTo(x0 + n * a, py + 6); c.closePath();
        c.fillStyle = stAlpha(C.accent, 0.09); c.fill();
        for (var i = 0; i <= n; i++) {
          var cx = x0 + i * a;
          dot(c, cx + sk / 2, py, 3.4, C.accent);
          if (i < n) dot(c, cx + a / 2 + sk / 2, py, 2.1, C.warm);
        }
        for (var j = 0; j < 3; j++) {
          var px = x0 + md(t * (k ? -26 : 26) + j * (n * a / 3), n * a);
          dot(c, px + 2, py - 1, 2.1, gold(C)); dot(c, px + 9, py - 1, 2.1, gold(C));
          c.strokeStyle = stAlpha(gold(C), 0.7); c.lineWidth = 1; c.beginPath(); c.moveTo(px + 3, py - 1); c.lineTo(px + 8, py - 1); c.stroke();
        }
      });
      for (var i2 = 0; i2 < n; i2 += 2) dot(c, x0 + i2 * a + a / 2 + 5, H * 0.51, 3.6, C.aqua || C.ink2, C.surface2);
      label(c, C, 'CuO₂ planes', 12, 14, { size: 11, weight: '600', color: C.ink2 });
      stTag(c, C, 'La–Ba–Cu–O · 35 K', W - 10, 14, { align: 'right', size: 11, bg: stAlpha(gold(C), 0.16), ring: gold(C), color: C.ink });
      label(c, C, 'Cu', x0 + sk / 2 - 2, H - 8, { size: 10.5, color: C.accent });
      label(c, C, 'O', x0 + sk / 2 + 20, H - 8, { size: 10.5, color: C.warm });
      label(c, C, 'pairs', x0 + sk / 2 + 36, H - 8, { size: 10.5, color: gold(C) });
    };
    MINI_STATIC.cuprate = 2;
    MINI_ALT.cuprate = 'Two copper-oxide planes of a layered ceramic, with electron pairs moving along the planes.';

    // 2025 · Clarke, Devoret and Martinis: a Josephson circuit as a particle in a tilted washboard, with quantised levels and tunnelling
    MINI_DRAW.mqt = function (c, C, W, H, t) {
      var tt = md(t, 9), x0 = 16, x1 = W - 16, y0 = 24, y1 = H - 20, tilt = 0.2;
      function U(ph) { return -Math.cos(ph) - tilt * ph; }
      var p0 = -0.75 * Math.PI, p1 = 2.45 * Math.PI, lo = Infinity, hi = -Infinity, i, ph;
      for (i = 0; i <= 120; i++) { ph = p0 + (p1 - p0) * i / 120; lo = Math.min(lo, U(ph)); hi = Math.max(hi, U(ph)); }
      function X(p) { return x0 + (p - p0) / (p1 - p0) * (x1 - x0); }
      function Y(u) { return y0 + (hi - u) / (hi - lo) * (y1 - y0); }
      var pts = [];
      for (i = 0; i <= 160; i++) { ph = p0 + (p1 - p0) * i / 160; pts.push([X(ph), Y(U(ph))]); }
      line(c, pts, C.accent, 1.75);
      // the first well: minimum near phi = asin(tilt), barrier top near pi - asin(tilt)
      var pm = Math.asin(tilt), pb = Math.PI - Math.asin(tilt), um = U(pm), ub = U(pb);
      var levels = [0.22, 0.5, 0.76];
      levels.forEach(function (f, k) {
        var u = um + f * (ub - um), half = 0.55 + 0.32 * k;
        line(c, [[X(pm - half), Y(u)], [X(pm + half), Y(u)]], k ? stAlpha(gold(C), 0.55) : gold(C), k ? 1.2 : 2);
      });
      var u0 = um + levels[0] * (ub - um), phase = tt < 4 ? 0 : tt < 5.2 ? (tt - 4) / 1.2 : 1;
      var pxNow = phase < 1 ? pm + (pb + 0.7 - pm) * phase : pb + 0.7 + Math.min(3.4, (tt - 5.2) * 1.3);
      var uNow = phase < 1 ? u0 : U(pxNow) + 0.05;
      var r = 4.5 + (phase < 1 && tt < 4 ? 0.8 * Math.sin(t * 5) : 0);
      if (phase > 0 && phase < 1) line(c, [[X(pm + 0.5), Y(u0)], [X(pb + 0.7), Y(u0)]], stAlpha(gold(C), 0.8), 1.2, [3, 3]);
      dot(c, X(pxNow), Y(uNow) - 4, r, gold(C), C.surface2);
      label(c, C, 'quantised levels', 12, 14, { size: 11, weight: '600', color: gold(C) });
      var tun = tt > 4 && tt < 7;
      label(c, C, tun ? 'tunnels through the barrier' : 'phase φ of the junction', W - 12, 14, { align: 'right', size: 11, weight: tun ? '600' : '400', color: tun ? C.ink : C.muted });
    };
    MINI_STATIC.mqt = 4.6;
    MINI_ALT.mqt = 'The phase of a Josephson junction behaves like a particle in a tilted washboard: it sits on quantised levels and tunnels through the barrier.';

    // 1962 · Landau: the phonon–roton spectrum of superfluid helium-4
    MINI_DRAW.landau = function (c, C, W, H, t) {
      var x0 = 30, x1 = W - 14, y0 = 14, y1 = H - 22;
      line(c, [[x0, y0], [x0, y1], [x1, y1]], C.axis, 1);
      label(c, C, 'ε', x0 - 8, y0 + 8, { align: 'right', size: 11, color: C.muted });
      label(c, C, 'p', x1, y1 + 14, { align: 'right', size: 11, color: C.muted });
      function E(p) { return 1.15 * p * Math.exp(-p * p / 1.6) + 0.55 * (1 - Math.exp(-p * p / 1.2)) + 0.12 * Math.max(0, p - 2.1) * Math.max(0, p - 2.1); }
      function X(p) { return x0 + p / 3 * (x1 - x0); }
      function Y(e) { return y1 - e / 1.05 * (y1 - y0); }
      var pts = [], pr = 0, er = 9;
      for (var i = 0; i <= 120; i++) { var p = 3 * i / 120, e = E(p); pts.push([X(p), Y(e)]); if (p > 1.2 && e < er) { er = e; pr = p; } }
      line(c, pts, C.accent, 1.75);
      line(c, [[X(0), Y(0)], [X(3), Y(er / pr * 3)]], stAlpha(gold(C), 0.9), 1.2, [4, 3]);
      var pp = 3 * (0.5 - 0.5 * Math.cos(TAU * md(t, 9) / 9));
      dot(c, X(pp), Y(E(pp)), 3.8, gold(C), C.surface2);
      label(c, C, 'phonons', X(0.35) + 4, Y(E(0.35)) - 6, { size: 10.5, color: C.ink2 });
      label(c, C, 'roton', X(pr), Y(er) + 14, { align: 'center', size: 10.5, weight: '600', color: C.ink2 });
      label(c, C, 'superfluid ⁴He', W - 12, y0 + 6, { align: 'right', size: 11, weight: '600', color: C.ink });
      label(c, C, 'critical velocity', W - 12, y0 + 20, { align: 'right', size: 10.5, color: gold(C) });
    };
    MINI_STATIC.landau = 3;
    MINI_ALT.landau = 'Landau’s excitation spectrum of superfluid helium: phonons at low momentum and a roton minimum, which set the critical velocity.';

    // 1996 · Lee, Osheroff and Richardson: helium-3 atoms pair with parallel spins in p-wave orbits
    MINI_DRAW.he3 = function (c, C, W, H, t) {
      var cx = W * 0.32, cy = H / 2, R = Math.min(H * 0.32, W * 0.14), ang = t * 1.2;
      c.save(); c.translate(cx, cy); c.rotate(ang);
      [-1, 1].forEach(function (s) {
        c.beginPath(); c.ellipse(s * R * 0.75, 0, R * 0.78, R * 0.42, 0, 0, TAU);
        c.fillStyle = stAlpha(s < 0 ? C.accent : C.warm, 0.18); c.fill(); c.lineWidth = 1.1; c.strokeStyle = s < 0 ? C.accent : C.warm; c.stroke();
      });
      c.restore();
      for (var k = 0; k < 2; k++) {
        var a = ang + k * Math.PI, ax = cx + Math.cos(a) * R * 0.9, ay = cy + Math.sin(a) * R * 0.9;
        dot(c, ax, ay, 5.5, gold(C), C.surface2);
        stArrow(c, ax + 9, ay + 6, ax + 9, ay - 8, C.ink, 4);
      }
      label(c, C, '³He pair', W * 0.58, cy - 12, { size: 12, weight: '600', color: C.ink });
      label(c, C, 'spins parallel, p-wave orbit', W * 0.58, cy + 4, { size: 11, color: C.ink2 });
      label(c, C, 'below 2.5 mK', W * 0.58, cy + 20, { size: 11, color: gold(C) });
    };
    MINI_STATIC.he3 = 0.6;
    MINI_ALT.he3 = 'Two helium-3 atoms bound as a pair with parallel spins and a two-lobed p-wave orbit that rotates.';

    // 2013 · Englert and Higgs: the Mexican-hat potential, with phase and amplitude (Higgs) modes
    MINI_DRAW.higgs = function (c, C, W, H, t) {
      var cx = W * 0.3, cy = H * 0.62, rx = Math.min(W * 0.22, 100), ry = rx * 0.32;
      for (var k = 5; k >= 1; k--) {
        var f = k / 5;
        c.beginPath(); c.ellipse(cx, cy, rx * f, ry * f, 0, 0, TAU);
        c.strokeStyle = stAlpha(C.accent, 0.25 + 0.12 * k); c.lineWidth = 1; c.stroke();
      }
      // the hump in the middle and the brim, as a cross-section above the rings
      var prof = [];
      for (var i = 0; i <= 60; i++) { var x = -1 + 2 * i / 60, v = 0.55 * Math.pow(x * x - 0.38, 2) * 6.5; prof.push([cx + x * rx, cy - ry - 8 - v * 14]); }
      line(c, prof, C.accent, 1.5);
      var a = t * 0.9, amp = 0.62 + 0.12 * Math.sin(t * 4.2) * (md(t, 8) > 4 ? 1 : 0);
      dot(c, cx + Math.cos(a) * rx * amp, cy + Math.sin(a) * ry * amp, 5, gold(C), C.surface2);
      var hm = md(t, 8) > 4;
      label(c, C, hm ? 'Higgs mode' : 'phase mode', W - 12, H / 2 - 2, { align: 'right', size: 12, weight: '600', color: hm ? gold(C) : C.ink });
      label(c, C, 'in superconductors too', W - 12, H / 2 + 14, { align: 'right', size: 10.5, color: C.muted });
    };
    MINI_STATIC.higgs = 5.2;
    MINI_ALT.higgs = 'A ball rolls in the trough of a Mexican-hat potential (the phase mode) and bobs in and out (the amplitude, or Higgs, mode).';

    // 2016 · Thouless, Haldane and Kosterlitz: vortex–antivortex pairs unbind in a thin film
    var BKT = (function () { var r = stRng(9), a = []; for (var i = 0; i < 7; i++) a.push([r(), r(), r() * TAU, 0.5 + r()]); return a; })();
    MINI_DRAW.bkt = function (c, C, W, H, t) {
      var tt = md(t, 10), sep = tt < 4 ? 0 : tt < 7 ? (tt - 4) / 3 : 1 - (tt - 7) / 3;
      sep = stClamp(sep);
      BKT.forEach(function (v) {
        var cx = 26 + v[0] * (W * 0.5 - 40), cy = 20 + v[1] * (H - 40), d = 7 + sep * 22 * v[3], th = v[2] + t * 0.15;
        [[1, C.accent], [-1, C.warm]].forEach(function (s) {
          var x = cx + s[0] * Math.cos(th) * d / 2, y = cy + s[0] * Math.sin(th) * d / 2;
          c.beginPath(); c.arc(x, y, 6, 0, TAU * 0.8); c.strokeStyle = s[1]; c.lineWidth = 1.2; c.stroke();
          var e = s[0] > 0 ? TAU * 0.8 : 0;
          dot(c, x + 6 * Math.cos(e), y + 6 * Math.sin(e), 1.6, s[1]);
          dot(c, x, y, 1.6, s[1]);
        });
        if (sep < 0.3) { c.strokeStyle = stAlpha(gold(C), 0.6); c.lineWidth = 1; c.beginPath(); c.moveTo(cx - Math.cos(th) * d / 2, cy - Math.sin(th) * d / 2); c.lineTo(cx + Math.cos(th) * d / 2, cy + Math.sin(th) * d / 2); c.stroke(); }
      });
      var free = sep > 0.5;
      label(c, C, free ? 'free vortices' : 'bound pairs', W - 12, H / 2 - 4, { align: 'right', size: 12, weight: '600', color: free ? C.warm : gold(C) });
      label(c, C, free ? 'warm: above T(BKT)' : 'cold: below T(BKT)', W - 12, H / 2 + 12, { align: 'right', size: 10.5, color: C.muted });
    };
    MINI_STATIC.bkt = 1;
    MINI_ALT.bkt = 'Vortices and antivortices in a thin film stay bound in pairs at low temperature and unbind above the BKT transition.';
  })();

};
