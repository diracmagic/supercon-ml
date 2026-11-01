'use strict';
// theory-drawings: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconTheoryDrawings = function initializeSuperconTheoryDrawings() {


  /* ---------- Theory & materials: mini card animations ----------
     MINI_DRAW[kind](c, C, W, H, t) draws one frame (W x H CSS px, t in seconds since the card came into view).
     MINI_STATIC[kind] is the time whose single frame best shows the idea (reduced motion).
     MINI_ALT[kind] describes the animation for screen readers. Everything else stays private to this closure. */
  MINI_DRAW = (function () {
    var TAU = Math.PI * 2;
    function md(t, p) { t = t % p; return t < 0 ? t + p : t; }
    function lerp(a, b, k) { return a + (b - a) * k; }
    function font(c, C, size, weight) { c.font = (weight || '400') + ' ' + size + 'px ' + C.font; }
    function textW(c, C, text, size, weight) { font(c, C, size, weight); return c.measureText(text).width; }
    function seg(c, x0, y0, x1, y1) { c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y1); c.stroke(); }
    function ring(c, x, y, r, stroke, lw, fill) {
      c.beginPath(); c.arc(x, y, r, 0, TAU);
      if (fill) { c.fillStyle = fill; c.fill(); }
      if (stroke) { c.lineWidth = lw || 1; c.strokeStyle = stroke; c.stroke(); }
    }
    // Thin arrow with a small filled head.
    function arrow(c, x0, y0, x1, y1, color, head, lw) {
      var a = Math.atan2(y1 - y0, x1 - x0), hd = head || 5;
      c.strokeStyle = color; c.fillStyle = color; c.lineWidth = lw || 1.25;
      c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1 - Math.cos(a) * hd * 0.8, y1 - Math.sin(a) * hd * 0.8); c.stroke();
      c.beginPath(); c.moveTo(x1, y1);
      c.lineTo(x1 - hd * Math.cos(a - 0.42), y1 - hd * Math.sin(a - 0.42));
      c.lineTo(x1 - hd * Math.cos(a + 0.42), y1 - hd * Math.sin(a + 0.42));
      c.closePath(); c.fill();
    }
    // Soft halo: three stacked translucent discs.
    function glow(c, x, y, r, color, a) {
      for (var i = 3; i >= 1; i--) { c.beginPath(); c.arc(x, y, r * i / 3, 0, TAU); c.fillStyle = stAlpha(color, a * 0.3); c.fill(); }
    }
    // Spin arrow of length L centred on (x, y), pointing along angle ang.
    function spin(c, x, y, ang, L, color, lw) {
      var dx = Math.cos(ang) * L / 2, dy = Math.sin(ang) * L / 2;
      arrow(c, x - dx, y - dy, x + dx, y + dy, color, Math.max(3.2, L * 0.38), lw || 1.25);
    }
    // Many spin arrows in two draw calls: get(i, out) writes [x, y, angle, length] for arrow i into out.
    var SPN = [0, 0, 0, 0];
    function spins(c, n, get, color, lw) {
      for (var pass = 0; pass < 2; pass++) {
        c.beginPath();
        for (var i = 0; i < n; i++) {
          get(i, SPN);
          var ca = Math.cos(SPN[2]), sa = Math.sin(SPN[2]), hd = Math.max(3.2, SPN[3] * 0.38);
          var x1 = SPN[0] + ca * SPN[3] / 2, y1 = SPN[1] + sa * SPN[3] / 2;
          if (!pass) { c.moveTo(SPN[0] - ca * SPN[3] / 2, SPN[1] - sa * SPN[3] / 2); c.lineTo(x1 - ca * hd * 0.8, y1 - sa * hd * 0.8); }
          else {
            c.moveTo(x1, y1);
            c.lineTo(x1 - hd * Math.cos(SPN[2] - 0.42), y1 - hd * Math.sin(SPN[2] - 0.42));
            c.lineTo(x1 - hd * Math.cos(SPN[2] + 0.42), y1 - hd * Math.sin(SPN[2] + 0.42)); c.closePath();
          }
        }
        if (!pass) { c.lineWidth = lw || 1.25; c.strokeStyle = color; c.stroke(); } else { c.fillStyle = color; c.fill(); }
      }
    }
    // Legend row: a swatch drawn by fn(x, y) then a label, vertically centred on y.
    function legend(c, C, x, y, text, sw, fn, opts) {
      fn(x + sw / 2, y);
      label(c, C, text, x + sw + 6, y + 0.5, { size: (opts && opts.size) || 11, color: (opts && opts.color) || C.ink2, base: 'middle' });
    }
    // Every kind runs inside save/restore so no state leaks into the engine.
    function guard(fn) {
      return function (c, C, W, H, t) {
        c.save();
        c.lineCap = 'butt'; c.lineJoin = 'round'; c.setLineDash([]); c.globalAlpha = 1;
        try { fn(c, C, W, H, t || 0); } finally { c.restore(); }
      };
    }

    /* London: field lines psi = y (1 - k R^2 / r^2) outside, (1 - k) y inside (k = 0 normal, 1 Meissner),
       plus B(x) = B0 [(1 - k) + k exp(-x / lambda)] inside the surface. */
    function drawLondon(c, C, W, H, t) {
      var P = 8, tt = md(t, P);
      var k = stSpan(tt, 1.0, 2.4) * (1 - stSpan(tt, 6.0, 7.4));
      var m = 10, pw = Math.round(Math.max(88, Math.min(150, W * 0.36)));
      var fx0 = m, fx1 = W - m - pw - 14, fy0 = m, fy1 = H - m;
      var cx = Math.round((fx0 + fx1) / 2), cy = (fy0 + fy1) / 2, R = 26, R2 = R * R;
      c.save();
      stRound(c, fx0, fy0, fx1 - fx0, fy1 - fy0, 8); c.fillStyle = C.surface; c.fill(); c.clip();
      c.beginPath(); c.arc(cx, cy, R, 0, TAU); c.fillStyle = mix(C.grid, C.track, k); c.fill();
      if (k > 0.01) ring(c, cx, cy, R - 2.5, stAlpha(C.accent, 0.4 * k), 3);
      ring(c, cx, cy, R, mix(C.axis, C.accent, k), 1);
      function psi(x, y) {
        var r2 = x * x + y * y;
        return r2 < R2 ? (1 - k) * y : y * (1 - k * R2 / r2);
      }
      c.setLineDash([5, 5]); c.lineDashOffset = -tt * 20;
      c.lineWidth = 1.2; c.strokeStyle = stAlpha(C.ink2, 0.75);
      for (var j = 0; j < 5; j++) {
        var cv = (j + 0.5) * 12;
        for (var s = -1; s <= 1; s += 2) {
          c.beginPath();
          for (var x = fx0 - 3; x <= fx1 + 3; x += 3) {
            var X = x - cx, lo = 0, hi = cv + R + 2;
            for (var it = 0; it < 13; it++) { var mid = (lo + hi) / 2; if (psi(X, mid) < cv) lo = mid; else hi = mid; }
            var y = cy + s * (lo + hi) / 2;
            if (x === fx0 - 3) c.moveTo(x, y); else c.lineTo(x, y);
          }
          c.stroke();
        }
      }
      c.setLineDash([]);
      c.restore();
      // B(x) inset
      var px0 = W - m - pw, px1 = W - m;
      stTag(c, C, k > 0.5 ? 'T < Tc' : 'T > Tc', px0, m + 10, { size: 11, align: 'left', rich: true, bg: C.surface, ring: k > 0.5 ? C.accent : C.axis });
      var yb = 90, yB = 50, xs = px0 + 16 + Math.round((pw - 16) * 0.22), lam = Math.max(14, (px1 - xs) * 0.24);
      stRound(c, xs, yB - 12, px1 - xs, yb - yB + 12, 3); c.fillStyle = mix(C.grid, C.track, k); c.fill();
      c.strokeStyle = C.axis; c.lineWidth = 1;
      seg(c, px0 + 12, yb + 0.5, px1, yb + 0.5);
      seg(c, xs + 0.5, yB - 12, xs + 0.5, yb);
      label(c, C, 'B', px0, yB + 0.5, { size: 11, color: C.muted, base: 'middle' });
      c.beginPath();
      for (var xx = px0 + 12; xx <= px1; xx += 2) {
        var bb = xx < xs ? 1 : (1 - k) + k * Math.exp(-(xx - xs) / lam);
        var yy = yb - bb * (yb - yB);
        if (xx === px0 + 12) c.moveTo(xx, yy); else c.lineTo(xx, yy);
      }
      c.lineWidth = 1.75; c.strokeStyle = C.accent; c.stroke();
      if (k > 0.02) {
        c.globalAlpha = k;
        var xl = xs + lam, yl = yb - ((1 - k) + k * Math.exp(-1)) * (yb - yB);
        c.setLineDash([2, 3]); c.strokeStyle = C.ink2; c.lineWidth = 1;
        seg(c, xl + 0.5, yl, xl + 0.5, yb + 4); c.setLineDash([]);
        label(c, C, 'λ', xl, yb + 15, { size: 11.5, color: C.ink2, align: 'center' });
        c.globalAlpha = 1;
      }
    }

    /* Ginzburg-Landau: F = a |psi|^2 + b |psi|^4 / 2 with a ∝ (T - Tc); type-II vortex lattice below Tc. */
    function drawGL(c, C, W, H, t) {
      var P = 9, tt = md(t, P);
      var cool = stSpan(tt, 1.4, 3.0), heat = stSpan(tt, 6.6, 8.2);
      var a = 0.8 - 2.0 * cool + 2.0 * heat, b = 1;
      var psiMin = a < 0 ? Math.sqrt(-a / b) : 0, psiB = psiMin * stSpan(tt, 2.1, 3.6);
      var m = 10, vw = Math.round(Math.max(100, Math.min(150, W * 0.38)));
      var gx0 = m, gx1 = W - m - vw - 14, cx = (gx0 + gx1) / 2;
      var span = 1.45, sx = ((gx1 - gx0) / 2 - 4) / span, y0 = 56, sy = 40;
      function F(p) { return a * p * p + 0.5 * b * p * p * p * p; }
      c.strokeStyle = C.axis; c.lineWidth = 1;
      seg(c, gx0, y0 + 0.5, gx1, y0 + 0.5);
      c.strokeStyle = C.grid; seg(c, Math.round(cx) + 0.5, 14, Math.round(cx) + 0.5, 86);
      label(c, C, 'F', Math.round(cx) + 5, 19, { size: 11, color: C.muted });
      label(c, C, 'ψ', gx1, y0 - 5, { size: 11.5, color: C.muted, align: 'right' });
      c.save();
      c.beginPath(); c.rect(gx0, 8, gx1 - gx0, H - 16); c.clip();
      c.beginPath();
      for (var i = 0; i <= 60; i++) {
        var p = -span + 2 * span * i / 60, x = cx + p * sx, y = y0 - F(p) * sy;
        if (i) c.lineTo(x, y); else c.moveTo(x, y);
      }
      c.lineWidth = 1.75; c.strokeStyle = C.accent; c.stroke();
      c.restore();
      var bx = cx + psiB * sx, by = y0 - F(psiB) * sy;
      var slope = -(2 * a * psiB + 2 * b * psiB * psiB * psiB) * sy / sx, nn = Math.sqrt(1 + slope * slope);
      dot(c, bx + 5 * slope / nn, by - 5 / nn, 4.5, C.warm);
      var below = a < 0;
      stTag(c, C, below ? 'T < Tc' : 'T > Tc', cx, 101, { size: 11, rich: true, bg: C.surface, ring: below ? C.accent : C.axis });
      // vortex panel
      var vx0 = W - m - vw, cxv = vx0 + vw / 2, cyv = 48, s = Math.min(32, vw / 3.3);
      var vis = stSpan(tt, 2.6, 3.6) * (1 - stSpan(tt, 6.6, 7.6));
      if (vis < 0.99) {
        c.fillStyle = stAlpha(C.muted, 0.7 * (1 - vis));
        c.beginPath();
        for (var gy = -2; gy <= 2; gy++) for (var gx = -3; gx <= 3; gx++) {
          var ux = cxv + gx * s * 0.5 + (gy % 2 ? s * 0.25 : 0), uy = cyv + gy * s * 0.43;
          c.moveTo(ux + 1.3, uy); c.arc(ux, uy, 1.3, 0, TAU);
        }
        c.fill();
      }
      if (vis > 0.01) {
        c.globalAlpha = vis;
        var th = -tt * 1.6, rs = s * 0.34;
        for (var r = -1; r <= 1; r++) {
          var n = r === 0 ? 3 : 2;
          for (var q = 0; q < n; q++) {
            var vx = cxv + (q - (n - 1) / 2) * s, vy = cyv + r * s * 0.866;
            c.beginPath(); c.arc(vx, vy, rs, th, th + TAU * 0.78); c.lineWidth = 1.2; c.strokeStyle = stAlpha(C.accent, 0.75); c.stroke();
            var hx = vx + rs * Math.cos(th), hy = vy + rs * Math.sin(th), tx = Math.sin(th), ty = -Math.cos(th);
            c.beginPath(); c.moveTo(hx + tx * 3.6, hy + ty * 3.6);
            c.lineTo(hx - ty * 2.4, hy + tx * 2.4); c.lineTo(hx + ty * 2.4, hy - tx * 2.4); c.closePath();
            c.fillStyle = stAlpha(C.accent, 0.75); c.fill();
            dot(c, vx, vy, 2.2, C.accent);
          }
        }
        c.globalAlpha = 1;
      }
      if (vis < 0.5) { c.globalAlpha = 1 - 2 * vis; label(c, C, 'uniform field', cxv, 106, { size: 11, align: 'center', color: C.ink2 }); }
      else { c.globalAlpha = 2 * vis - 1; label(c, C, 'vortices, Φ₀ each', cxv, 106, { size: 11, align: 'center', color: C.ink2 }); }
      c.globalAlpha = 1;
    }

    /* BCS: electron k↑ pulls the ions in and leaves a positive wake; an electron moving the other way (−k↓)
       falls into it and the two bind; the density of states opens a gap 2Δ with coherence peaks. */
    function drawBCS(c, C, W, H, t) {
      var P = 9, tt = md(t, P);
      var m = 10, dw = Math.round(Math.max(84, Math.min(130, W * 0.32)));
      var lx0 = m, lx1 = W - m - dw - 16, lane = 50, ro = 20;
      var sp = Math.max(17, Math.min(22, (lx1 - lx0) / 8)), ncol = Math.floor((lx1 - lx0 - 6) / sp) + 1;
      var ox = (lx0 + lx1) / 2 - (ncol - 1) * sp / 2;
      var xm = (lx0 + lx1) / 2, D = Math.min(24, (lx1 - lx0) * 0.15), tp = 3.6;
      var u1 = stClamp((tt - 0.2) / (tp - 0.2)), u2 = stClamp((tt - 1.0) / (tp - 1.0));
      var osc = stSpan(tt, tp, tp + 0.8) * 5 * Math.sin((tt - tp) * TAU / 1.6);
      var e1x = lerp(lx0 - 10, xm + D, 1 - (1 - u1) * (1 - u1)) + osc, e1y = lane - 4;
      var e2x = lerp(lx1 + 10, xm - D, 1 - (1 - u2) * (1 - u2)) - osc, e2y = lane + 4;
      var ea = 1 - stSpan(tt, 8.0, 8.7);
      var pair = stSpan(tt, tp - 0.2, tp + 0.6) * ea;
      function wake(d) { return d < -4 ? 0 : (1 - Math.exp(-(d + 4) / 5)) * Math.exp(-Math.max(0, d - 6) / 38); }
      c.save();
      c.beginPath(); c.rect(lx0, 8, lx1 - lx0, H - 16); c.clip();
      for (var i = 0; i < ncol; i++) {
        var x0 = ox + i * sp;
        var w = Math.min(1, (wake(e1x - x0) + (tt > 1.0 ? wake(x0 - e2x) : 0)) * ea);
        for (var r = -1; r <= 1; r += 2) {
          var x = x0 + 0.5 * Math.sin(tt * 7 + i * 1.7 + r), y = lane + r * ro - r * 3.5 * w + 0.5 * Math.cos(tt * 8 + i);
          dot(c, x, y, 3.6 + 0.5 * w, mix(C.muted, C.warm, w));
          c.strokeStyle = C.surface2; c.lineWidth = 1;
          seg(c, x - 1.8, y, x + 1.8, y); seg(c, x, y - 1.8, x, y + 1.8);
        }
      }
      if (pair > 0.01) {
        c.globalAlpha = pair * 0.8; c.setLineDash([3, 3]); c.strokeStyle = C.accent; c.lineWidth = 1.2;
        seg(c, e2x + 5, e2y, e1x - 5, e1y); c.setLineDash([]);
      }
      c.globalAlpha = ea;
      for (var q = 0; q < 2; q++) {   // e1 carries k↑ (spin drawn on its right), e2 carries −k↓ (spin on its left)
        var ex = q ? e2x : e1x, ey = q ? e2y : e1y;
        dot(c, ex, ey, 4.5, C.accent);
        c.strokeStyle = C.surface; c.lineWidth = 1.3; seg(c, ex - 2, ey, ex + 2, ey);
        spin(c, ex + (q ? -9 : 9), ey, (q ? 1 : -1) * Math.PI / 2, 9, C.ink2, 1.2);
      }
      c.restore();
      if (pair > 0.01) {
        c.globalAlpha = pair;
        stTag(c, C, 'k↑ and −k↓', Math.max(lx0 + 40, Math.min(lx1 - 40, xm)), 96, { size: 11.5, bg: C.surface, ring: C.accent });
        c.globalAlpha = 1;
      }
      // density of states N(E) = Re[(E − iΓ) / sqrt((E − iΓ)² − Δ²)]
      var gap = stSpan(tt, tp - 0.2, tp + 1.4) * (1 - stSpan(tt, 7.9, 8.7));
      var dx0 = W - m - dw, dx1 = W - m, yb = 92, y1 = 66, G = 0.06;
      label(c, C, 'N(E)', dx0, 19, { size: 11, color: C.muted });
      c.strokeStyle = C.axis; c.lineWidth = 1; seg(c, dx0, yb + 0.5, dx1, yb + 0.5);
      c.beginPath();
      for (var j = 0; j <= 80; j++) {
        var E = -3 + 6 * j / 80, xr = E, xi = -G, ar = xr * xr - xi * xi - gap * gap, ai = 2 * xr * xi;
        var mod = Math.sqrt(Math.sqrt(ar * ar + ai * ai)), ang = Math.atan2(ai, ar) / 2, sr = mod * Math.cos(ang), si = mod * Math.sin(ang);
        if (sr < 0) { sr = -sr; si = -si; }
        var den = sr * sr + si * si, n = den > 1e-9 ? (xr * sr + xi * si) / den : 1;
        var xx = dx0 + (dx1 - dx0) * j / 80, yy = yb - Math.min(2.3, Math.abs(n)) * (yb - y1);
        if (j) c.lineTo(xx, yy); else c.moveTo(xx, yy);
      }
      c.lineWidth = 1.75; c.strokeStyle = C.accent; c.stroke();
      if (gap > 0.6) {
        c.globalAlpha = stSpan(gap, 0.6, 0.95);
        var gx0 = dx0 + (dx1 - dx0) * (3 - gap) / 6, gx1 = dx0 + (dx1 - dx0) * (3 + gap) / 6;
        c.strokeStyle = C.ink2; c.fillStyle = C.ink2; c.lineWidth = 1;
        seg(c, gx0 + 2, 85, gx1 - 2, 85);
        c.beginPath(); c.moveTo(gx0 + 1, 85); c.lineTo(gx0 + 4.5, 83); c.lineTo(gx0 + 4.5, 87); c.closePath(); c.fill();
        c.beginPath(); c.moveTo(gx1 - 1, 85); c.lineTo(gx1 - 4.5, 83); c.lineTo(gx1 - 4.5, 87); c.closePath(); c.fill();
        label(c, C, '2Δ', (gx0 + gx1) / 2, 79, { size: 11, align: 'center', color: C.ink2 });
        c.globalAlpha = 1;
      }
    }

    /* Eliashberg: model α²F(ω) (acoustic + optical humps) filled from low to high ω;
       λ = 2∫α²F/ω dω and ω_log accumulate, Tc from Allen–Dynes with μ* = 0.10. Final λ ≈ 1.16, ω_log ≈ 308 K, Tc ≈ 26 K. */
    var ELI = (function () {
      var N = 160, wmax = 800, dw = wmax / N, f = [], lam = [0], lnw = [0], peak = 0;
      for (var i = 0; i < N; i++) {
        var x = (i + 0.5) * dw;
        var v = 0.88 * Math.exp(-Math.pow(x - 275, 2) / (2 * 62 * 62)) * x * x / (x * x + 90 * 90) +
          0.60 * Math.exp(-Math.pow(x - 640, 2) / (2 * 50 * 50));
        f.push(v); peak = Math.max(peak, v);
        lam.push(lam[i] + 2 * v / x * dw); lnw.push(lnw[i] + 2 * v / x * Math.log(x) * dw);
      }
      return { N: N, wmax: wmax, f: f, lam: lam, lnw: lnw, peak: peak };
    })();
    function eliAt(w) {   // running λ, ω_log and Allen–Dynes Tc for modes up to ω
      var q = stClamp(w / ELI.wmax) * ELI.N, i = Math.min(ELI.N - 1, Math.floor(q)), k = q - i;
      var lam = lerp(ELI.lam[i], ELI.lam[i + 1], k), ln = lerp(ELI.lnw[i], ELI.lnw[i + 1], k);
      var wlog = lam > 1e-6 ? Math.exp(ln / lam) : 0, mu = 0.10, d = lam - mu * (1 + 0.62 * lam);
      return { lam: lam, wlog: wlog, tc: d > 0 ? wlog / 1.2 * Math.exp(-1.04 * (1 + lam) / d) : 0 };
    }
    function drawEliashberg(c, C, W, H, t) {
      var P = 9, tt = md(t, P);
      var wf = ELI.wmax * stClamp((tt - 0.5) / 5.2), fade = 1 - stSpan(tt, 8.2, 8.8);
      var m = 10, rw = Math.round(Math.max(84, Math.min(120, W * 0.3)));
      var px0 = m + 2, px1 = W - m - rw - 14, yb = 98, yt = 32;
      function X(w) { return px0 + (px1 - px0) * w / ELI.wmax; }
      function Y(i) { return yb - (yb - yt) * ELI.f[i] / ELI.peak; }
      label(c, C, 'α²F(ω)', px0, 19, { size: 11, color: C.ink2 });
      c.strokeStyle = C.axis; c.lineWidth = 1; seg(c, px0, yb + 0.5, px1, yb + 0.5);
      c.beginPath();
      for (var i = 0; i < ELI.N; i++) { var x = X((i + 0.5) * ELI.wmax / ELI.N); if (i) c.lineTo(x, Y(i)); else c.moveTo(x, Y(i)); }
      c.setLineDash([2, 3]); c.strokeStyle = C.muted; c.stroke(); c.setLineDash([]);
      var n = Math.floor(wf / ELI.wmax * ELI.N);
      if (n > 1 && fade > 0.01) {
        c.globalAlpha = fade;
        c.beginPath(); c.moveTo(X(0), yb);
        for (var j = 0; j < n; j++) c.lineTo(X((j + 0.5) * ELI.wmax / ELI.N), Y(j));
        c.lineTo(X((n - 0.5) * ELI.wmax / ELI.N), yb); c.closePath();
        c.fillStyle = stAlpha(C.accent, 0.2); c.fill();
        c.beginPath();
        for (var q = 0; q < n; q++) { var xq = X((q + 0.5) * ELI.wmax / ELI.N); if (q) c.lineTo(xq, Y(q)); else c.moveTo(xq, Y(q)); }
        c.lineWidth = 1.75; c.strokeStyle = C.accent; c.stroke();
        if (wf < ELI.wmax) {
          var xs = X((n - 0.5) * ELI.wmax / ELI.N);
          c.strokeStyle = stAlpha(C.accent, 0.5); c.lineWidth = 1; seg(c, xs + 0.5, Y(n - 1), xs + 0.5, yb);
          dot(c, xs, Y(n - 1), 2.6, C.accent);
        }
        c.globalAlpha = 1;
      }
      var r = eliAt(wf), rx = W - m - rw;
      c.globalAlpha = Math.min(fade, stSpan(tt, 0, 0.4));
      stSym(c, C, [['λ = ' + r.lam.toFixed(2)]], rx, 42, { size: 12, weight: '600', color: C.ink });
      stRound(c, rx, 50, rw, 4, 2); c.fillStyle = C.grid; c.fill();
      if (r.lam > 0.005) { stRound(c, rx, 50, Math.max(4, rw * Math.min(1, r.lam / 1.4)), 4, 2); c.fillStyle = C.accent; c.fill(); }
      stText(c, C, 'Tc ≈ ' + (r.tc < 0.5 ? '0' : String(Math.round(r.tc))) + ' K', rx, 78, { size: 12, weight: '600', color: C.ink });
      c.globalAlpha = 1;
    }

    /* Josephson: with a voltage across S|I|S the phase difference φ = θR − θL advances steadily (2eV/ħ),
       the supercurrent I = Ic sin φ oscillates and pairs shuttle through the barrier (charge ∝ 1 − cos φ). */
    function drawJosephson(c, C, W, H, t) {
      var P = 6, tt = md(t, P), wJ = TAU / 3, phi = wJ * tt;
      var m = 10, tw = Math.round(Math.max(84, Math.min(140, W * 0.34)));
      var jx0 = m, jx1 = W - m - tw - 16, bx = Math.round((jx0 + jx1) / 2), bw = 8;
      var y0 = 12, y1 = 78, yc = (y0 + y1) / 2;
      var lx1 = bx - bw / 2, rx0 = bx + bw / 2;
      // superconductors and barrier
      stRound(c, jx0, y0, lx1 - jx0, y1 - y0, 6); c.fillStyle = C.track; c.fill();
      stRound(c, rx0, y0, jx1 - rx0, y1 - y0, 6); c.fillStyle = C.track; c.fill();
      c.fillStyle = C.axis; c.fillRect(lx1 + 1.5, y0, bw - 3, y1 - y0);
      // bias circuit with a voltage source
      var lcx = (jx0 + lx1) / 2, rcx = (rx0 + jx1) / 2, wy = 98;
      c.strokeStyle = stAlpha(C.ink2, 0.6); c.lineWidth = 1;
      c.beginPath(); c.moveTo(lcx, y1); c.lineTo(lcx, wy); c.lineTo(bx - 8, wy); c.moveTo(bx + 8, wy); c.lineTo(rcx, wy); c.lineTo(rcx, y1); c.stroke();
      ring(c, bx, wy, 8, stAlpha(C.ink2, 0.8), 1, C.surface);
      label(c, C, 'V', bx, wy + 0.5, { size: 10.5, weight: '600', color: C.ink2, align: 'center', base: 'middle' });
      // phasors: the phases wind in opposite senses so that φ = θR − θL grows at wJ
      [[lcx, -Math.PI / 2 - phi / 2], [rcx, -Math.PI / 2 + phi / 2]].forEach(function (p) {
        ring(c, p[0], yc, 11, stAlpha(C.accent, 0.45), 1, C.surface);
        arrow(c, p[0], yc, p[0] + 10 * Math.cos(p[1]), yc + 10 * Math.sin(p[1]), C.accent, 4.5, 1.5);
        dot(c, p[0], yc, 1.6, C.accent);
      });
      // Cooper pairs: displacement follows the transferred charge, so they move with the current
      var sp = 26, shift = sp * (1 - Math.cos(phi)) / 2;
      for (var lane = 0; lane < 2; lane++) {
        var ly = lane ? yc + 22 : yc - 22, off = lane ? sp / 2 : 0;
        for (var j = -8; j <= 8; j++) {
          var x = bx + j * sp + off - sp / 4 + shift;
          if (x < jx0 + 4 || x > jx1 - 4) continue;
          var a = stClamp((x - jx0 - 4) / 10) * stClamp((jx1 - 4 - x) / 10);
          var w = Math.max(0, 1 - Math.abs(x - bx) / 9), col = mix(C.accent, C.warm, w);
          c.globalAlpha = a;
          c.strokeStyle = col; c.lineWidth = 1; seg(c, x - 3, ly, x + 3, ly);
          dot(c, x - 3, ly, 2.3, col); dot(c, x + 3, ly, 2.3, col);
        }
      }
      c.globalAlpha = 1;
      // I(t) = Ic sin φ, the last 4 s
      var tx0 = W - m - tw, tx1 = W - m, ty = 58, amp = 20, Tw = 4;
      stSym(c, C, [['I = I'], ['c', 1], [' sin φ']], tx0, 20, { size: 11, color: C.ink2 });
      c.strokeStyle = C.axis; c.lineWidth = 1; seg(c, tx0, ty + 0.5, tx1, ty + 0.5);
      c.beginPath();
      for (var i = 0; i <= 64; i++) {
        var s = tt - Tw + Tw * i / 64, xx = tx0 + (tx1 - tx0 - 4) * i / 64, yy = ty - amp * Math.sin(wJ * s);
        if (i) c.lineTo(xx, yy); else c.moveTo(xx, yy);
      }
      c.lineWidth = 1.75; c.strokeStyle = C.accent; c.stroke();
      dot(c, tx1 - 4, ty - amp * Math.sin(phi), 3, C.warm);
    }

    /* Shared Brillouin-zone frame and legend for the two pairing-symmetry cards. */
    function zoneLayout(c, C, W, H, rows, S, over) {   // over: how far drawing may spill past the zone edge
      var lw = 0;
      for (var i = 0; i < rows.length; i++) lw = Math.max(lw, textW(c, C, rows[i], 11));
      lw += 22;
      var gap = 16, total = S + 2 * over + gap + lw, x0 = over + Math.max(10, Math.round((W - total) / 2));
      var y0 = Math.round((H - S) / 2);
      return { x0: x0, y0: y0, S: S, cx: x0 + S / 2, cy: y0 + S / 2, h: S / 2, lx: x0 + S + over + gap };
    }
    function zoneFrame(c, C, Z) {
      stRound(c, Z.x0, Z.y0, Z.S, Z.S, 4); c.fillStyle = C.surface; c.fill();
      c.lineWidth = 1; c.strokeStyle = C.axis; c.stroke();
    }
    function bandSwatch(c, C, color) {
      return function (x, y) {
        c.lineCap = 'round'; c.lineWidth = 5; c.strokeStyle = stAlpha(color, 0.55); seg(c, x - 5, y, x + 5, y);
        c.lineWidth = 1; c.strokeStyle = stAlpha(C.ink2, 0.7); seg(c, x - 5, y, x + 5, y); c.lineCap = 'butt';
      };
    }
    function zoneLegend(c, C, Z, rows, arrowA) {
      var y = Z.cy - 24;
      legend(c, C, Z.lx, y, rows[0], 12, bandSwatch(c, C, C.accent));
      legend(c, C, Z.lx, y + 24, rows[1], 12, bandSwatch(c, C, C.warm));
      c.globalAlpha = arrowA;
      legend(c, C, Z.lx, y + 48, rows[2], 12, function (x, yy) { arrow(c, x - 6, yy, x + 6, yy, C.ink, 4.5, 1.4); });
      c.globalAlpha = 1;
    }

    /* d-wave: hole-like cuprate Fermi surface, ε = −2t(cos kx + cos ky) − 4t′ cos kx cos ky − μ (t′ = −0.3t, μ = −t);
       gap Δ ∝ cos kx − cos ky as a band of thickness |Δ| (blue +, orange −), nodes on the diagonals;
       Q = (π, π) joins antinodal hot spots of opposite sign. */
    var DWV = (function () {
      function eps(kx, ky) { return -2 * (Math.cos(kx) + Math.cos(ky)) + 1.2 * Math.cos(kx) * Math.cos(ky) + 1.0; }
      var n = 28, arc = [];
      for (var i = 0; i <= n; i++) {   // arc around the (π, π) corner, from (π, k0) to (k0, π)
        var a = Math.PI * (1.5 - 0.5 * i / n), dx = Math.cos(a), dy = Math.sin(a), lo = 0, hi = Math.PI;
        for (var it = 0; it < 30; it++) { var mid = (lo + hi) / 2; if (eps(Math.PI + dx * mid, Math.PI + dy * mid) > 0) lo = mid; else hi = mid; }
        var r = (lo + hi) / 2, kx = Math.PI + dx * r, ky = Math.PI + dy * r;
        arc.push([kx, ky, (Math.cos(kx) - Math.cos(ky)) / 2]);
      }
      return { arc: arc, n: n, hot: Math.acos(Math.sqrt(1 / 1.2)) };   // hot spot: ε = 0 on |kx| + |ky| = π
    })();
    function drawDwave(c, C, W, H, t) {
      var P = 8, tt = md(t, P);
      var amp = stSpan(tt, 0.3, 1.5) * (1 - stSpan(tt, 7.0, 7.8));
      var qa = stSpan(tt, 1.6, 2.2) * (1 - stSpan(tt, 6.6, 7.2));
      var rows = ['Δ > 0', 'Δ < 0', 'Q = (π, π)'], Z = zoneLayout(c, C, W, H, rows, H - 20, 0);
      zoneFrame(c, C, Z);
      c.save();
      stRound(c, Z.x0, Z.y0, Z.S, Z.S, 4); c.clip();
      c.setLineDash([2, 3]); c.strokeStyle = stAlpha(C.muted, 0.55); c.lineWidth = 1;
      seg(c, Z.x0, Z.y0, Z.x0 + Z.S, Z.y0 + Z.S); seg(c, Z.x0, Z.y0 + Z.S, Z.x0 + Z.S, Z.y0); c.setLineDash([]);
      var A = DWV.arc, n = DWV.n, half = n / 2, bw = 5.5 * amp;
      for (var q = 0; q < 4; q++) {
        var sx = q & 1 ? -1 : 1, sy = q & 2 ? -1 : 1;
        for (var part = 0; part < 2; part++) {   // the two halves of the arc carry opposite signs
          var i0 = part ? half : 0, i1 = part ? n : half;
          c.beginPath();
          for (var dir = 0; dir < 2; dir++) {
            for (var s = 0; s <= i1 - i0; s++) {
              var i = dir ? i1 - s : i0 + s, ip = Math.max(0, i - 1), inx = Math.min(n, i + 1);
              var X = Z.cx + sx * A[i][0] / Math.PI * Z.h, Y = Z.cy - sy * A[i][1] / Math.PI * Z.h;
              var tx = sx * (A[inx][0] - A[ip][0]), ty = -sy * (A[inx][1] - A[ip][1]), tl = Math.sqrt(tx * tx + ty * ty) || 1;
              var o = (dir ? -1 : 1) * bw * Math.abs(A[i][2]);
              if (dir === 0 && s === 0) c.moveTo(X - ty / tl * o, Y + tx / tl * o); else c.lineTo(X - ty / tl * o, Y + tx / tl * o);
            }
          }
          c.closePath();
          c.fillStyle = stAlpha(A[part ? n : 0][2] > 0 ? C.accent : C.warm, 0.55); c.fill();
        }
        c.beginPath();
        for (var j = 0; j <= n; j++) {
          var XX = Z.cx + sx * A[j][0] / Math.PI * Z.h, YY = Z.cy - sy * A[j][1] / Math.PI * Z.h;
          if (j) c.lineTo(XX, YY); else c.moveTo(XX, YY);
        }
        c.lineWidth = 1; c.strokeStyle = stAlpha(C.ink2, 0.75); c.stroke();
      }
      c.restore();
      if (qa > 0.01) {
        var hs = DWV.hot, pulse = 0.55 + 0.45 * Math.sin(tt * TAU / 1.6);
        var x1 = Z.cx + hs / Math.PI * Z.h, y1 = Z.cy - (Math.PI - hs) / Math.PI * Z.h;
        var x2 = Z.cx + (hs - Math.PI) / Math.PI * Z.h, y2 = Z.cy + hs / Math.PI * Z.h;
        c.globalAlpha = qa * pulse;
        ring(c, x1, y1, 3.2 + 1.5 * pulse, C.ink, 1.2); ring(c, x2, y2, 3.2 + 1.5 * pulse, C.ink, 1.2);
        c.globalAlpha = qa * (0.5 + 0.5 * pulse);
        arrow(c, x1 - 3, y1 + 3, x2 + 4, y2 - 4, C.ink, 5.5, 1.5);
        c.globalAlpha = 1;
      }
      zoneLegend(c, C, Z, rows, Math.max(qa, 0.35));
    }

    /* s±: hole pockets at Γ (Δ > 0, blue) and electron pockets at the zone corners M (Δ < 0, orange) of the
       2-Fe Brillouin zone; the spin-fluctuation wave vector Q links a hole pocket to an electron pocket. */
    function drawSpm(c, C, W, H, t) {
      var P = 8, tt = md(t, P);
      var amp = stSpan(tt, 0.3, 1.5) * (1 - stSpan(tt, 7.0, 7.8));
      var qa = stSpan(tt, 1.6, 2.2) * (1 - stSpan(tt, 6.6, 7.2));
      // zone corners are M; the electron pockets are drawn whole, spilling into the neighbouring zones
      var rows = ['holes, Δ > 0', 'electrons, Δ < 0', 'spin fluct. Q'], Z = zoneLayout(c, C, W, H, rows, 72, 14), u = Z.h / Math.PI;
      zoneFrame(c, C, Z);
      function pocket(fn, color) {
        if (amp > 0.01) { c.lineWidth = 4 * amp; c.strokeStyle = stAlpha(color, 0.55); fn(); c.stroke(); }
        c.lineWidth = 1; c.strokeStyle = stAlpha(C.ink2, 0.75); fn(); c.stroke();
      }
      [0.24, 0.38].forEach(function (r) { pocket(function () { c.beginPath(); c.arc(Z.cx, Z.cy, r * Math.PI * u, 0, TAU); }, C.accent); });
      for (var q = 0; q < 4; q++) {
        var mx = Z.cx + (q & 1 ? -1 : 1) * Z.h, my = Z.cy + (q & 2 ? -1 : 1) * Z.h;
        [[0.4, 0.22], [0.22, 0.4]].forEach(function (e) {
          pocket(function () { c.beginPath(); c.ellipse(mx, my, e[0] * Math.PI * u, e[1] * Math.PI * u, 0, 0, TAU); }, C.warm);
        });
      }
      if (qa > 0.01) {
        // from the outer hole pocket at 45° to the inner edge of the M pocket (0.274π from the corner along the diagonal)
        var pulse = 0.55 + 0.45 * Math.sin(tt * TAU / 1.6), r0 = 0.38 * Math.PI * u * Math.SQRT1_2, kd = (1 - 0.274 * Math.SQRT1_2) * Math.PI * u;
        var x1 = Z.cx + r0 + 2, y1 = Z.cy - r0 - 2, x2 = Z.cx + kd - 2, y2 = Z.cy - kd + 2;
        c.globalAlpha = qa * (0.5 + 0.5 * pulse);
        arrow(c, x1, y1, x2, y2, C.ink, 5.5, 1.5);
        c.globalAlpha = qa * pulse;
        ring(c, x2 + 2, y2 - 2, 3 + 1.5 * pulse, C.ink, 1.2);
        c.globalAlpha = 1;
      }
      zoneLegend(c, C, Z, rows, Math.max(qa, 0.35));
    }

    /* Topological: a nanowire on a superconductor. As the bulk gaps out, two Majorana zero modes appear at the
       ends with |ψ|² ∝ exp(−x/ξ) from each end; the side spectrum shows bulk levels pushed off E = 0 and a level left at 0. */
    function drawTopo(c, C, W, H, t) {
      var P = 8, tt = md(t, P);
      var g = stSpan(tt, 1.2, 2.8) * (1 - stSpan(tt, 6.6, 7.6));
      var m = 10, ew = 40, mx1 = W - m - ew - 16;
      var sy0 = 87, sy1 = 108, wy0 = 80, wy1 = 87, wyc = (wy0 + wy1) / 2;
      stRound(c, m, sy0, mx1 - m, sy1 - sy0, 4); c.fillStyle = C.track; c.fill();
      label(c, C, 'superconductor', (m + mx1) / 2, (sy0 + sy1) / 2 + 1, { size: 10.5, color: C.ink2, align: 'center', base: 'middle' });
      var wx0 = m + 14, wx1 = mx1 - 14, L = wx1 - wx0, xi = 0.1 * L, yb = 73, amp = 40;
      function edge(s) { return (1 - Math.exp(-5 * s)) * Math.exp(-s) / 0.582; }   // vanishes at the wall, then decays as exp(−x/ξ)
      stRound(c, wx0, wy0, L, wy1 - wy0, 3.5); c.fillStyle = mix(C.axis, C.ink2, 0.35); c.fill();
      // |ψ|²: a bulk standing wave turns into two end-localised modes
      c.beginPath(); c.moveTo(wx0, yb);
      for (var i = 0; i <= 80; i++) {
        var u = i / 80, x = wx0 + u * L;
        var fb = 0.28 * (1 - Math.cos(TAU * 4 * u)) / 2, fe = edge(u * L / xi) + edge((1 - u) * L / xi);
        c.lineTo(x, yb - amp * ((1 - g) * fb + g * fe));
      }
      c.lineTo(wx1, yb); c.closePath();
      var col = mix(C.muted, C.warm, g);
      c.fillStyle = stAlpha(C.warm, 0.08 + 0.12 * g); c.fill();
      c.lineWidth = 1.5; c.strokeStyle = col; c.stroke();
      c.strokeStyle = C.axis; c.lineWidth = 1; seg(c, wx0, yb + 0.5, wx1, yb + 0.5);
      if (g > 0.01) {
        var br = 0.75 + 0.25 * Math.sin(tt * TAU / 2.4);
        [wx0 + 1, wx1 - 1].forEach(function (x) { glow(c, x, wyc, 10, C.warm, 0.7 * g * br); dot(c, x, wyc, 2.6, C.warm); });
        c.globalAlpha = g;
        var lw = textW(c, C, 'Majorana modes', 11), lx = (wx0 + wx1) / 2;
        label(c, C, 'Majorana modes', lx, 21, { size: 11, color: C.ink2, align: 'center' });
        c.strokeStyle = stAlpha(C.ink2, 0.45); c.lineWidth = 1;
        seg(c, lx - lw / 2 - 5, 17, wx0 + 7, yb - amp + 4); seg(c, lx + lw / 2 + 5, 17, wx1 - 7, yb - amp + 4);
        c.globalAlpha = 1;
      }
      // energy levels of the wire
      var ex = W - m - ew, ey = 58;
      arrow(c, ex, 98, ex, 18, C.axis, 4.5, 1);
      label(c, C, 'E', ex - 5, 22, { size: 11, color: C.muted, base: 'middle', align: 'right' });
      c.strokeStyle = stAlpha(C.ink2, 0.65); c.lineWidth = 1.25;
      for (var n = 0; n < 5; n++) {
        var e0 = (n + 0.5) * 6, e = Math.sqrt(e0 * e0 + 256 * g * g);
        seg(c, ex + 8, ey - e, W - m, ey - e); seg(c, ex + 8, ey + e, W - m, ey + e);
      }
      if (g > 0.01) { c.globalAlpha = g; c.lineWidth = 2; c.strokeStyle = C.warm; seg(c, ex + 8, ey, W - m, ey); c.globalAlpha = 1; }
    }

    /* Moiré: two triangular lattices twisted by θ (drawn at 5× the true angle so the pattern is visible; moiré period
       a / (2 sin(θ/2))). The two central bands flatten as θ → θm ≈ 1.1° (bandwidth ∝ |θ − θm|). */
    function drawMoire(c, C, W, H, t) {
      var P = 10, tt = md(t, P);
      var k = stSpan(tt, 0.6, 4.2) * (1 - stSpan(tt, 6.6, 9.6));
      var th = 2.0 - 0.9 * k, thm = 1.1, w = 0.04 + 0.96 * Math.abs(th - thm) / 0.9;
      var m = 10, mw = Math.round(Math.max(104, Math.min(170, W * 0.42))), mh = H - 2 * m;
      var cx = m + mw / 2, cy = m + mh / 2, a = 6.5, ang = th * 5 * Math.PI / 180;
      c.save();
      stRound(c, m, m, mw, mh, 8); c.fillStyle = C.surface; c.fill(); c.clip();
      var N = Math.ceil(Math.sqrt(mw * mw + mh * mh) / 2 / a * 1.25);
      for (var layer = 0; layer < 2; layer++) {
        var rot = (layer ? 0.5 : -0.5) * ang + 0.15 * Math.sin(tt * TAU / P), cs = Math.cos(rot), sn = Math.sin(rot);
        c.beginPath();
        for (var i = -N; i <= N; i++) for (var j = -N; j <= N; j++) {
          var px = (i + 0.5 * j) * a, py = j * a * 0.8660254;
          var x = cx + px * cs - py * sn, y = cy + px * sn + py * cs;
          if (x < m - 2 || x > m + mw + 2 || y < m - 2 || y > m + mh + 2) continue;
          c.moveTo(x + 1.35, y); c.arc(x, y, 1.35, 0, TAU);
        }
        c.fillStyle = stAlpha(C.accent, layer ? 0.7 : 0.9); c.fill();
      }
      c.restore();
      // bands along a k path; the two central bands flatten at the magic angle
      var bx0 = m + mw + 16, bx1 = W - m, ey = 62;
      c.strokeStyle = C.axis; c.lineWidth = 1; seg(c, bx0 + 0.5, 28, bx0 + 0.5, 96);
      function band(fn, color, lw) {
        c.beginPath();
        for (var q = 0; q <= 40; q++) { var u = q / 40, xx = bx0 + 4 + (bx1 - bx0 - 4) * u, yy = ey - fn(u); if (q) c.lineTo(xx, yy); else c.moveTo(xx, yy); }
        c.lineWidth = lw; c.strokeStyle = color; c.stroke();
      }
      band(function (u) { return 21 + 8 * (1 - Math.sin(Math.PI * u)); }, C.muted, 1.25);
      band(function (u) { return -21 - 8 * (1 - Math.sin(Math.PI * u)); }, C.muted, 1.25);
      band(function (u) { return w * 15 * Math.sin(Math.PI * u) + 1.2; }, C.accent, 1.75);
      band(function (u) { return -w * 15 * Math.sin(Math.PI * u) - 1.2; }, C.accent, 1.75);
      stTag(c, C, 'θ = ' + th.toFixed(2) + '°', bx0, 18, { size: 11, align: 'left', bg: C.surface, ring: k > 0.9 ? C.accent : C.axis });
      if (k > 0.6) { c.globalAlpha = stSpan(k, 0.6, 0.95); label(c, C, 'flat bands', bx0 + 4, 108, { size: 11, color: C.accent, weight: '600' }); c.globalAlpha = 1; }
    }

    /* NbTi / Nb3Sn magnet: solenoid cut along its axis (⊙ on top, ⊗ below, so B points left to right inside),
       current pulses run turn by turn along the winding, uniform field through the bore, fringing past the ends. */
    function drawMagnet(c, C, W, H, t) {
      var P = 6, tt = md(t, P);
      var m = 10, x0 = Math.round(W * 0.2), x1 = Math.round(W * 0.8), yT = 18, yB = 80, yc = (yT + yB) / 2, r = 4.5;
      var n = Math.max(6, Math.floor((x1 - x0) / 13) + 1), dx = (x1 - x0) / (n - 1), Lh = (x1 - x0) / 2, xm = (x0 + x1) / 2;
      c.save();
      c.beginPath(); c.rect(m, m, W - 2 * m, 92 - m); c.clip();
      c.setLineDash([5, 5]); c.lineDashOffset = -tt * 20; c.lineWidth = 1.2; c.strokeStyle = stAlpha(C.ink2, 0.7);
      for (var i = -2; i <= 2; i++) {
        c.beginPath();
        for (var x = m; x <= W - m; x += 3) {
          var d = Math.max(0, Math.abs(x - xm) - Lh), y = yc + i * 9 * (1 + 1.1 * d * d / (d * d + 500));
          if (x === m) c.moveTo(x, y); else c.lineTo(x, y);
        }
        c.stroke();
      }
      c.restore();
      c.fillStyle = stAlpha(C.ink2, 0.8);
      c.beginPath(); c.moveTo(xm + 5, yc); c.lineTo(xm - 2, yc - 4); c.lineTo(xm - 2, yc + 4); c.closePath(); c.fill();
      var jp = md(tt / 2, 1) * (n + 4) - 2;
      for (var j = 0; j < n; j++) {
        var w = Math.exp(-(j - jp) * (j - jp) / 1.6), x2 = x0 + j * dx, col = mix(C.accent, C.warm, w);
        for (var row = 0; row < 2; row++) {
          var yy = row ? yB : yT;
          if (w > 0.05) { c.beginPath(); c.arc(x2, yy, 8, 0, TAU); c.fillStyle = stAlpha(C.warm, 0.3 * w); c.fill(); }
          ring(c, x2, yy, r, col, 1.4, C.surface);
          if (!row) dot(c, x2, yy, 1.6, col);
          else { c.strokeStyle = col; c.lineWidth = 1.2; seg(c, x2 - 2.3, yy - 2.3, x2 + 2.3, yy + 2.3); seg(c, x2 + 2.3, yy - 2.3, x2 - 2.3, yy + 2.3); }
        }
      }
      label(c, C, 'MRI · accelerators', W / 2, 107, { size: 11, color: C.ink2, align: 'center' });
    }

    /* MgB2: boron honeycomb seen from above with Mg over the hexagon centres. In the E2g phonon the two boron
       sublattices move in opposite in-plane directions, stretching and squeezing the B–B bonds. */
    function drawMgB2(c, C, W, H, t) {
      var P = 6, tt = md(t, P), ph = Math.sin(tt * TAU / 1.2), u = 1.3 * ph, b = 12, ax = Math.sqrt(3) * b;
      var m = 10, lg = Math.round(textW(c, C, 'E₂g phonon', 11.5, '600')) + 2;
      var x0 = m, x1 = W - m - lg - 16, y0 = m, y1 = H - m;
      c.save();
      stRound(c, x0, y0, x1 - x0, y1 - y0, 8); c.fillStyle = C.surface; c.fill(); c.clip();
      // Bravais lattice R = i a1 + j a2 with a1 = (√3 b, 0), a2 = (√3 b / 2, 1.5 b); A at R, B at R + (0, b)
      var ox = x0 + 4, oy = y0 + 3, rows = Math.ceil((y1 - y0) / (1.5 * b)) + 1, cols = Math.ceil((x1 - x0) / ax) + 2;
      var cxm = (x0 + x1) / 2, cym = (y0 + y1) / 2, best = 1e9, hx = 0, hy = 0, pass, j, i, i0, rx, ry;
      for (pass = 0; pass < 3; pass++) {
        c.beginPath();
        for (j = -1; j <= rows; j++) {
          i0 = -Math.ceil(j / 2) - 1;
          for (i = i0; i <= i0 + cols; i++) {
            rx = ox + i * ax + j * ax / 2; ry = oy + j * 1.5 * b;
            if (pass === 0) {   // bonds A(i,j) to B(i,j), B(i,j−1), B(i+1,j−1)
              c.moveTo(rx + u, ry); c.lineTo(rx - u, ry + b);
              c.moveTo(rx + u, ry); c.lineTo(rx - ax / 2 - u, ry - 0.5 * b);
              c.moveTo(rx + u, ry); c.lineTo(rx + ax / 2 - u, ry - 0.5 * b);
            } else if (pass === 1) {   // Mg above the hexagon centre R + (√3 b / 2, b / 2), not moving in this mode
              var gx = rx + ax / 2, gy = ry + b / 2, dd = (gx - cxm) * (gx - cxm) + (gy - cym) * (gy - cym);
              if (dd < best) { best = dd; hx = gx; hy = gy; }
              c.moveTo(gx + 3.6, gy); c.arc(gx, gy, 3.6, 0, TAU);
            } else {
              c.moveTo(rx + u + 2.6, ry); c.arc(rx + u, ry, 2.6, 0, TAU);
              c.moveTo(rx - u + 2.6, ry + b); c.arc(rx - u, ry + b, 2.6, 0, TAU);
            }
          }
        }
        if (pass === 0) { c.strokeStyle = stAlpha(C.ink2, 0.45); c.lineWidth = 1.2; c.stroke(); }
        else { c.fillStyle = pass === 1 ? stAlpha(C.aqua, 0.75) : C.accent; c.fill(); }
      }
      // displacement arrows on the six borons of the central hexagon: vertices at −150°, −30°, 90° are A, the others B
      if (Math.abs(ph) > 0.2) {
        c.globalAlpha = stClamp((Math.abs(ph) - 0.2) / 0.5);
        for (var k = 0; k < 6; k++) {
          var ang = -5 * Math.PI / 6 + k * Math.PI / 3, sgn = (k % 2 === 0 ? 1 : -1) * (ph > 0 ? 1 : -1);
          var vx = hx + b * Math.cos(ang) + (k % 2 === 0 ? u : -u), vy = hy + b * Math.sin(ang);
          arrow(c, vx + sgn * 3.6, vy, vx + sgn * 10.5, vy, C.warm, 3.6, 1.3);
        }
        c.globalAlpha = 1;
      }
      c.restore();
      var lx = W - m - lg;
      label(c, C, 'E₂g phonon', lx, 33, { size: 11.5, weight: '600', color: C.ink });
      legend(c, C, lx, 57, 'boron', 8, function (x, y) { dot(c, x, y, 2.6, C.accent); });
      legend(c, C, lx, 79, 'Mg', 8, function (x, y) { dot(c, x, y, 3.6, stAlpha(C.aqua, 0.75)); });
    }

    /* REBCO coated conductor, cut along the tape: substrate, buffer, thin REBCO layer and silver/copper cap.
       Current (dots) flows in the REBCO layer; liquid-nitrogen bubbles nucleate on the tape and rise (77 K). */
    var RB_BUB = (function () {
      var r = stRng(11), out = [];
      for (var i = 0; i < 14; i++) out.push({ x: (i + 0.2 + 0.6 * r()) / 14, ph: r(), n: 2 + (i % 2), s: 1.6 + 1.2 * r() });
      return out;
    })();
    function drawRebco(c, C, W, H, t) {
      var P = 8, tt = md(t, P);
      var m = 10, tx0 = m + 12, tx1 = W - m - Math.round(textW(c, C, 'REBCO', 11, '600')) - 20;
      stRound(c, m, m, W - 2 * m, H - 2 * m, 8); c.fillStyle = stAlpha(C.accent, C.dark ? 0.1 : 0.06); c.fill();
      var yCap = 46, yRe = 52, yBuf = 58, ySub = 61, yEnd = 76;
      c.fillStyle = mix(C.warm, C.muted, 0.45); c.fillRect(tx0, yCap, tx1 - tx0, yRe - yCap);
      c.fillStyle = C.accent; c.fillRect(tx0, yRe, tx1 - tx0, yBuf - yRe);
      c.fillStyle = mix(C.muted, C.surface, 0.45); c.fillRect(tx0, yBuf, tx1 - tx0, ySub - yBuf);
      c.fillStyle = C.muted; c.fillRect(tx0, ySub, tx1 - tx0, yEnd - ySub);
      // supercurrent in the REBCO layer
      c.fillStyle = C.surface; c.beginPath();
      for (var x = tx0 + 3 + md(tt * 18, 12); x < tx1 - 2; x += 12) { c.moveTo(x + 1.5, (yRe + yBuf) / 2); c.arc(x, (yRe + yBuf) / 2, 1.5, 0, TAU); }
      c.fill();
      // boiling: bubbles leave the tape surface and rise
      c.lineWidth = 1;
      for (var i = 0; i < RB_BUB.length; i++) {
        var q = RB_BUB[i], p = md(tt / (P / q.n) + q.ph, 1);
        var bx = tx0 + 6 + q.x * (tx1 - tx0 - 12) + 1.5 * Math.sin(p * 9 + i), by = yCap - 3 - p * (yCap - 3 - m - 9);
        var a = stSpan(p, 0, 0.12) * (1 - stSpan(p, 0.8, 1));
        if (a <= 0.01) continue;
        c.globalAlpha = a;
        ring(c, bx, by, q.s * (0.7 + 0.6 * p), stAlpha(C.ink2, 0.7), 1, stAlpha(C.surface, 0.5));
      }
      c.globalAlpha = 1;
      label(c, C, 'REBCO', tx1 + 8, (yRe + yBuf) / 2 + 0.5, { size: 11, weight: '600', color: C.accent, base: 'middle' });
      label(c, C, '77 K, liquid nitrogen', tx0, 98, { size: 11, color: C.ink2 });
    }

    /* Hg-1223 pressure quench: pressure (muted) ramps to about 30 GPa and is released abruptly; Tc (blue) climbs
       from 133 K toward 164 K under pressure and stays near 151 K after the quench (metastable state). */
    function hgP(u) {
      return u < 0.08 ? 0 : u < 0.5 ? 30 * stEase((u - 0.08) / 0.42) : u < 0.62 ? 30 : u < 0.635 ? 30 * (0.635 - u) / 0.015 : 0;
    }
    function hgTc(u) { return u < 0.62 ? 133 + 31 * hgP(u) / 30 : u < 0.635 ? lerp(164, 151, (u - 0.62) / 0.015) : 151; }
    function drawHg1223(c, C, W, H, t) {
      var P = 9, tt = md(t, P);
      var uc = stClamp((tt - 0.4) / 5.6), fade = 1 - stSpan(tt, 8.2, 8.8);
      var m = 10, qw = 54, px0 = m + 2, px1 = W - m - qw - 18;
      function X(u) { return px0 + (px1 - px0) * u; }
      function YT(v) { return 84 - (v - 125) / 45 * 66; }
      function YP(p) { return 100 - p / 30 * 20; }
      c.strokeStyle = C.axis; c.lineWidth = 1; seg(c, px0, 100.5, px1, 100.5);
      c.globalAlpha = fade;
      var n = Math.max(1, Math.round(uc * 120));
      c.beginPath();
      for (var i = 0; i <= n; i++) { var u = uc * i / n; if (i) c.lineTo(X(u), YP(hgP(u))); else c.moveTo(X(u), YP(hgP(u))); }
      c.lineWidth = 1.5; c.strokeStyle = C.muted; c.stroke();
      c.beginPath();
      for (var j = 0; j <= n; j++) { var v = uc * j / n; if (j) c.lineTo(X(v), YT(hgTc(v))); else c.moveTo(X(v), YT(hgTc(v))); }
      c.lineWidth = 1.75; c.strokeStyle = C.accent; c.stroke();
      if (uc < 1) { dot(c, X(uc), YT(hgTc(uc)), 2.8, C.accent); dot(c, X(uc), YP(hgP(uc)), 2.4, C.muted); }
      label(c, C, '133 K', px0, 86, { size: 10.5, weight: '600', color: C.accent });
      if (uc > 0.45) { c.globalAlpha = fade * stSpan(uc, 0.45, 0.52); label(c, C, '164 K', X(0.56), 20, { size: 10.5, weight: '600', color: C.accent, align: 'center' }); }
      if (uc > 0.3) { c.globalAlpha = fade * stSpan(uc, 0.3, 0.4); label(c, C, '30 GPa', X(0.56), 75, { size: 10.5, color: C.muted, align: 'center' }); }
      if (uc > 0.7) { c.globalAlpha = fade * stSpan(uc, 0.7, 0.8); label(c, C, '151 K', px1, 39, { size: 10.5, weight: '600', color: C.accent, align: 'right' }); }
      c.globalAlpha = 1;
      // three CuO2 planes, squeezed under pressure and left slightly denser after the quench
      var p = hgP(uc) * fade, d = 15 * (1 - 0.16 * p / 30) - (uc > 0.62 ? 0.8 * fade : 0), qx0 = W - m - qw, qcy = 58;
      for (var r = -1; r <= 1; r++) {
        var y = qcy + r * d;
        c.strokeStyle = stAlpha(C.ink2, 0.35); c.lineWidth = 1; seg(c, qx0, y, qx0 + qw, y);
        for (var k = 0; k < 8; k++) {
          var x = qx0 + 3 + k * (qw - 6) / 7;
          if (k % 2) dot(c, x, y, 1.6, C.muted); else dot(c, x, y, 2.6, C.accent);
        }
      }
      label(c, C, '3 × CuO₂', qx0 + qw / 2, 104, { size: 10.5, color: C.muted, align: 'center' });
      if (p > 0.5) {
        c.globalAlpha = stClamp(p / 30);
        var qcx = qx0 + qw / 2, tp = qcy - d - 5, bt = qcy + d + 5;
        arrow(c, qcx, tp - 12, qcx, tp, C.muted, 4.5, 1.3); arrow(c, qcx, bt + 12, qcx, bt, C.muted, 4.5, 1.3);
        c.globalAlpha = 1;
      }
    }

    /* Iron pnictide layer: square Fe lattice with As above (large) and below (small) the plaquette centres in a
       checkerboard; Fe moments fluctuate about the stripe antiferromagnet: rows of parallel moments that alternate
       from row to row, with the moments along the alternation direction as in BaFe2As2. */
    var FE_PH = (function () { var r = stRng(5), a = []; for (var i = 0; i < 200; i++) a.push(r() * TAU); return a; })();
    function drawIron(c, C, W, H, t) {
      var P = 8, tt = md(t, P);
      var rows = ['As above', 'As below', 'spin fluctuations'], lw = 0, m = 10;
      for (var q = 0; q < 3; q++) lw = Math.max(lw, textW(c, C, rows[q], 11));
      lw += 20;
      var s = 21, nr = 5, x0 = m, x1 = W - m - lw - 16, nc = Math.max(4, Math.floor((x1 - x0) / s) + 1);
      var ox = x0 + (x1 - x0 - (nc - 1) * s) / 2, oy = 60 - 2 * s;
      function asDots(up) {   // As in a checkerboard: above (large) or below (small) the plaquette centres
        var r = up ? 4.6 : 2.4;
        c.beginPath();
        for (var a = 0; a < nc - 1; a++) for (var b = 0; b < nr - 1; b++) {
          if (((a + b) % 2 === 0) !== up) continue;
          var x = ox + (a + 0.5) * s, y = oy + (b + 0.5) * s;
          c.moveTo(x + r, y); c.arc(x, y, r, 0, TAU);
        }
        c.fillStyle = up ? stAlpha(C.ink2, 0.5) : stAlpha(C.muted, 0.6); c.fill();
      }
      asDots(false);
      c.beginPath();
      for (var i = 0; i < nc * nr; i++) { var fx = ox + (i % nc) * s, fy = oy + Math.floor(i / nc) * s; c.moveTo(fx + 3, fy); c.arc(fx, fy, 3, 0, TAU); }
      c.fillStyle = C.accent; c.fill();
      spins(c, nc * nr, function (i, o) {
        var i2 = i % nc, j2 = Math.floor(i / nc), k = (i2 * 7 + j2 * 3) % (FE_PH.length - 3);
        o[0] = ox + i2 * s; o[1] = oy + j2 * s;
        o[2] = (j2 % 2 ? Math.PI / 2 : -Math.PI / 2) + 0.42 * Math.sin(TAU * 2 * tt / P + FE_PH[k]) * (0.6 + 0.4 * Math.sin(TAU * tt / P + FE_PH[k + 1]));
        o[3] = 13 * (0.82 + 0.18 * Math.sin(TAU * 3 * tt / P + FE_PH[k + 2]));
      }, C.warm, 1.4);
      asDots(true);
      var lx = W - m - lw, ly = 38;
      legend(c, C, lx, ly, rows[0], 12, function (x, y) { dot(c, x, y, 4.6, stAlpha(C.ink2, 0.5)); });
      legend(c, C, lx, ly + 22, rows[1], 12, function (x, y) { dot(c, x, y, 2.4, stAlpha(C.muted, 0.6)); });
      legend(c, C, lx, ly + 44, rows[2], 12, function (x, y) { spin(c, x, y, -Math.PI / 2, 13, C.warm, 1.4); });
    }

    /* LaH10-type clathrate: a hydrogen cage around La squeezed between two diamond anvils; H vibrates fast
       (light atoms, high phonon frequencies); readouts once compressed. */
    var HY_PH = (function () { var r = stRng(9), a = []; for (var i = 0; i < 48; i++) a.push(r() * TAU); return a; })(), HY_X = [], HY_Y = [];
    function drawHydride(c, C, W, H, t) {
      var P = 8, tt = md(t, P);
      var k = stSpan(tt, 0.8, 2.6) * (1 - stSpan(tt, 6.4, 7.6));
      var m = 10, rw = Math.round(Math.max(textW(c, C, 'Tc ≈ 250 K', 12, '600'), textW(c, C, '~170 GPa', 11.5))) + 2;
      var aw = 34, gw = 2 * aw + 26 + rw, cx = Math.round(Math.max(m + aw, (W - gw) / 2 + aw)), cy = 60;
      var rc = 24 * (1 - 0.13 * k), gap = lerp(37, 28, k);
      // anvils
      [-1, 1].forEach(function (sd) {
        var yt = sd < 0 ? m : H - m, yc = cy + sd * gap;
        c.beginPath(); c.moveTo(cx - aw, yt); c.lineTo(cx + aw, yt); c.lineTo(cx + 12, yc); c.lineTo(cx - 12, yc); c.closePath();
        c.fillStyle = stAlpha(C.track, C.dark ? 0.9 : 0.8); c.fill(); c.lineWidth = 1; c.strokeStyle = stAlpha(C.accent, 0.55); c.stroke();
        c.strokeStyle = stAlpha(C.accent, 0.3);
        seg(c, cx - aw * 0.45, yt, cx - 5, yc); seg(c, cx + aw * 0.45, yt, cx + 5, yc);
      });
      // cage seen along an axis: outer ring of 12 H, inner hexagon of 6 H, spokes between them
      var jit = 1.1, f = TAU * 32 / P, px = HY_X, py = HY_Y;
      for (var i = 0; i < 18; i++) {
        var outer = i < 12, ang = outer ? i * TAU / 12 : (2 * (i - 12) + 1) * TAU / 12, rr = outer ? rc : rc * 0.6;
        px[i] = cx + rr * Math.cos(ang) + jit * Math.sin(f * tt + HY_PH[i]);
        py[i] = cy + rr * Math.sin(ang) + jit * Math.sin(f * tt + HY_PH[i + 21]);
      }
      c.strokeStyle = stAlpha(C.ink2, 0.35); c.lineWidth = 1; c.beginPath();
      for (var j = 0; j < 12; j++) { var nj = (j + 1) % 12; c.moveTo(px[j], py[j]); c.lineTo(px[nj], py[nj]); }
      for (var q = 0; q < 6; q++) {
        var o = 12 + q, on = 12 + (q + 1) % 6;
        c.moveTo(px[o], py[o]); c.lineTo(px[on], py[on]); c.moveTo(px[o], py[o]); c.lineTo(px[2 * q + 1], py[2 * q + 1]);
      }
      c.stroke();
      dot(c, cx, cy, 8.5, stAlpha(C.aqua, 0.9));
      label(c, C, 'La', cx, cy + 0.5, { size: 10.5, weight: '600', color: C.surface, align: 'center', base: 'middle' });
      c.fillStyle = C.accent; c.beginPath();
      for (var h = 0; h < 18; h++) { c.moveTo(px[h] + 2.3, py[h]); c.arc(px[h], py[h], 2.3, 0, TAU); }
      c.fill();
      var ra = stSpan(k, 0.75, 1), rx = cx + aw + 26;
      if (ra > 0.01) {
        c.globalAlpha = ra;
        label(c, C, '~170 GPa', rx, 52, { size: 11.5, color: C.ink2 });
        stText(c, C, 'Tc ≈ 250 K', rx, 74, { size: 12, weight: '600', color: C.accent });
        c.globalAlpha = 1;
      }
    }

    /* Bilayer La3Ni2O7 film: two NiO2 planes bridged by apical O (Ni–O–Ni along the vertical); interlayer pairs,
       one partner in each plane, form across the bilayer; the substrate squeezes the film in-plane (compressive strain). */
    var NI_PH = (function () { var r = stRng(3), a = []; for (var i = 0; i < 24; i++) a.push(r()); return a; })();
    function drawNickelate(c, C, W, H, t) {
      var P = 8, tt = md(t, P);
      var m = 10, sy0 = 96, sy1 = 110, yU = 46, yL = 74, yA = 60, sp = 32;
      stRound(c, m, sy0, W - 2 * m, sy1 - sy0, 3); c.fillStyle = mix(C.grid, C.muted, 0.35); c.fill();
      label(c, C, 'substrate: compressive strain', W / 2, (sy0 + sy1) / 2 + 0.5, { size: 10.5, color: C.ink2, align: 'center', base: 'middle' });
      var fx0 = m + 30, fx1 = W - m - 30, n = Math.max(3, Math.floor((fx1 - fx0) / sp) + 1), ox = (W - (n - 1) * sp) / 2;
      // bonds: Ni–O chains in each plane, Ni–O–Ni bridges between them
      c.strokeStyle = stAlpha(C.ink2, 0.4); c.lineWidth = 1.1; c.beginPath();
      c.moveTo(ox - 14, yU); c.lineTo(ox + (n - 1) * sp + 14, yU); c.moveTo(ox - 14, yL); c.lineTo(ox + (n - 1) * sp + 14, yL);
      for (var i = 0; i < n; i++) { c.moveTo(ox + i * sp, yU - 10); c.lineTo(ox + i * sp, yL + 10); }
      c.stroke();
      c.fillStyle = C.muted; c.beginPath();
      for (var j = 0; j < n; j++) {
        var x = ox + j * sp;
        c.moveTo(x + 2, yU - 10); c.arc(x, yU - 10, 2, 0, TAU); c.moveTo(x + 2, yA); c.arc(x, yA, 2, 0, TAU);
        c.moveTo(x + 2, yL + 10); c.arc(x, yL + 10, 2, 0, TAU);
        if (j < n - 1) { c.moveTo(x + sp / 2 + 2, yU); c.arc(x + sp / 2, yU, 2, 0, TAU); c.moveTo(x + sp / 2 + 2, yL); c.arc(x + sp / 2, yL, 2, 0, TAU); }
      }
      c.fill();
      c.fillStyle = C.accent; c.beginPath();
      for (var k = 0; k < n; k++) { var xk = ox + k * sp; c.moveTo(xk + 3.6, yU); c.arc(xk, yU, 3.6, 0, TAU); c.moveTo(xk + 3.6, yL); c.arc(xk, yL, 3.6, 0, TAU); }
      c.fill();
      // interlayer pairs fade in and out at staggered times, the two partners closing in across the bilayer
      for (var q = 0; q < n - 1; q++) {
        var ph = md(2 * tt / P + NI_PH[q], 1), v = stSpan(ph, 0.05, 0.3) * (1 - stSpan(ph, 0.65, 0.9));
        if (v < 0.02) continue;
        var px = ox + q * sp + 9, y1 = lerp(yU + 2, yU + 6, v), y2 = lerp(yL - 2, yL - 6, v);
        c.globalAlpha = v;
        c.strokeStyle = C.warm; c.lineWidth = 1.2; seg(c, px, y1, px, y2);
        dot(c, px, y1, 2.4, C.warm); dot(c, px, y2, 2.4, C.warm);
      }
      c.globalAlpha = 1;
      var pull = 1.5 * Math.sin(tt * TAU / 2);
      arrow(c, m + 2 + pull, yA, m + 18 + pull, yA, C.ink2, 5, 1.4);
      arrow(c, W - m - 2 - pull, yA, W - m - 18 - pull, yA, C.ink2, 5, 1.4);
      label(c, C, 'interlayer pairs', W / 2, 24, { size: 11, weight: '600', color: C.warm, align: 'center' });
    }

    /* Magic-angle graphene device: resistance versus filling of the flat bands at low temperature; a correlated
       insulator peak at half filling, superconducting domes (R → 0) on either side, metal elsewhere. */
    function mgDome(v) {
      var x = Math.min(Math.abs(v - 0.33), Math.abs(v - 0.67)) / 0.085;
      return x >= 1 ? 0 : x < 0.55 ? 1 : 0.5 + 0.5 * Math.cos(Math.PI * (x - 0.55) / 0.45);
    }
    function mgR(v) { var d = v - 0.5; return (0.36 + 0.3 * d * d) * (1 - mgDome(v)) + 0.6 * Math.exp(-d * d / (2 * 0.032 * 0.032)); }
    function drawMagic(c, C, W, H, t) {
      var P = 10, tt = md(t, P), vg = 0.06 + 0.88 * (0.5 - 0.5 * Math.cos(TAU * tt / P));
      var m = 10, px0 = m + 12, px1 = W - m, yb = 88, sc = 52;
      function X(v) { return px0 + (px1 - px0) * v; }
      // superconducting domes under the trace
      [0.33, 0.67].forEach(function (c0) {
        c.beginPath(); c.ellipse(X(c0), yb, (px1 - px0) * 0.075, 15, 0, Math.PI, TAU); c.closePath();
        c.fillStyle = stAlpha(C.accent, C.dark ? 0.22 : 0.14); c.fill();
      });
      c.strokeStyle = C.axis; c.lineWidth = 1; seg(c, px0, yb + 0.5, px1, yb + 0.5);
      seg(c, X(0.5) + 0.5, yb, X(0.5) + 0.5, yb + 4);
      c.beginPath();
      for (var i = 0; i <= 160; i++) { var v = i / 160, y = yb - sc * mgR(v); if (i) c.lineTo(X(v), y); else c.moveTo(X(v), y); }
      c.lineWidth = 1.75; c.strokeStyle = C.accent; c.stroke();
      label(c, C, 'R', px0 - 5, yb - sc * mgR(0) + 0.5, { size: 11, color: C.muted, align: 'right', base: 'middle' });
      label(c, C, 'half filling', X(0.5), 104, { size: 10.5, color: C.muted, align: 'center' });
      // gate marker
      var gx = X(vg), gy = yb - sc * mgR(vg);
      c.strokeStyle = stAlpha(C.ink, 0.5); c.lineWidth = 1; c.setLineDash([2, 3]); seg(c, gx + 0.5, 32, gx + 0.5, yb); c.setLineDash([]);
      dot(c, gx, gy, 3.4, C.warm, C.surface);
      var d = Math.abs(vg - 0.5), state = mgDome(vg) > 0.5 ? 'superconductor' : d < 0.07 ? 'correlated insulator' : 'metal';
      var ringc = state === 'metal' ? C.axis : state === 'superconductor' ? C.accent : C.warm;
      stTag(c, C, state, px0, 16, { size: 11, align: 'left', bg: C.surface, ring: ringc });
    }

    /* Spin-triplet candidates: an electron pair with parallel spins (S = 1) in a rotating two-lobed p-wave orbital
       whose sign flips under inversion (odd parity); beside it, a kagome net with a breathing 2×2 charge-density wave. */
    var KAG = (function () {
      // kagome sites R, R + a1/2, R + a2/2 (a1 = (1, 0), a2 = (1/2, √3/2)); 2×2 order: hexagons H(i, j) with i, j even
      var s3 = Math.sqrt(3) / 2, sites = [], idx = {}, bonds = [], hexes = [], R = 2.75;
      var cx = 0.75, cy = s3 / 2;   // centre the patch on the selected hexagon H(0, 0) = (a1 + a2) / 2
      function pos(i, j, k) { var x = i + 0.5 * j + (k === 1 ? 0.5 : k === 2 ? 0.25 : 0), y = j * s3 + (k === 2 ? s3 / 2 : 0); return [x - cx, y - cy]; }
      function hc(i, j) { var p = pos(i, j, 0); return [p[0] + 0.75, p[1] + s3 / 2]; }
      function sel(i, j) { return ((i % 2) + 2) % 2 === 0 && ((j % 2) + 2) % 2 === 0; }
      for (var i = -5; i <= 5; i++) for (var j = -5; j <= 5; j++) for (var k = 0; k < 3; k++) {
        var p = pos(i, j, k);
        if (p[0] * p[0] + p[1] * p[1] > R * R) continue;
        // the two hexagons this site borders; move toward the selected one, if any
        var h1 = k === 0 ? [i - 1, j] : [i, j], h2 = k === 0 ? [i, j - 1] : k === 1 ? [i, j - 1] : [i - 1, j], ux = 0, uy = 0;
        var hs = sel(h1[0], h1[1]) ? h1 : sel(h2[0], h2[1]) ? h2 : null;
        if (hs) { var q = hc(hs[0], hs[1]); ux = (q[0] - p[0]) * 2; uy = (q[1] - p[1]) * 2; }
        idx[i + ',' + j + ',' + k] = sites.length;
        sites.push([p[0], p[1], ux, uy]);
      }
      function link(a, b) { if (a !== undefined && b !== undefined) bonds.push([a, b]); }
      for (var i2 = -5; i2 <= 5; i2++) for (var j2 = -5; j2 <= 5; j2++) {
        var s0 = idx[i2 + ',' + j2 + ',0'], s1 = idx[i2 + ',' + j2 + ',1'], s2 = idx[i2 + ',' + j2 + ',2'];
        link(s0, s1); link(s0, s2); link(s1, s2);
        var d0 = idx[(i2 + 1) + ',' + j2 + ',0'], d2 = idx[(i2 + 1) + ',' + (j2 - 1) + ',2'];
        link(s1, d0); link(s1, d2); link(d0, d2);
        if (sel(i2, j2)) { var hq = hc(i2, j2); if (hq[0] * hq[0] + hq[1] * hq[1] < (R - 0.45) * (R - 0.45)) hexes.push(hq); }
      }
      return { sites: sites, bonds: bonds, hexes: hexes, R: R };
    })();
    function drawTriplet(c, C, W, H, t) {
      var P = 8, tt = md(t, P), m = 10;
      var half = (W - 2 * m - 12) / 2, lx = m + half / 2, rx = W - m - half / 2, cy = 52;
      // p-wave orbital, polar plot r = L cos²(φ − α): + lobe blue, − lobe orange; the pair sits on opposite lobes
      var L = Math.min(40, half * 0.46), al = TAU * tt / P;
      for (var s = 0; s < 2; s++) {
        var a0 = al + s * Math.PI;
        c.beginPath();
        for (var i = 0; i <= 32; i++) {
          var ph = a0 - Math.PI / 2 + Math.PI * i / 32, r = L * Math.pow(Math.cos(ph - a0), 2);
          var x = lx + r * Math.cos(ph), y = cy + r * Math.sin(ph);
          if (i) c.lineTo(x, y); else c.moveTo(x, y);
        }
        c.closePath();
        var col = s ? C.warm : C.accent;
        c.fillStyle = stAlpha(col, 0.16); c.fill(); c.lineWidth = 1.2; c.strokeStyle = stAlpha(col, 0.8); c.stroke();
      }
      for (var e = 0; e < 2; e++) {
        var ea = al + e * Math.PI, ex = lx + 0.58 * L * Math.cos(ea), ey = cy + 0.58 * L * Math.sin(ea);
        dot(c, ex, ey, 4, C.accent, C.surface);
        spin(c, ex + 8.5, ey, -Math.PI / 2, 9, C.ink, 1.3);
      }
      label(c, C, 'S = 1, odd parity', lx, 106, { size: 11, color: C.ink2, align: 'center' });
      // kagome net with a breathing 2×2 CDW (star-of-David ↔ inverse star)
      var a = Math.min(15.5, (half - 8) / (2 * KAG.R)), br = Math.sin(TAU * tt / 2), dl = 0.13 * br;
      c.fillStyle = stAlpha(C.warm, 0.1 + 0.1 * Math.abs(br));
      for (var h = 0; h < KAG.hexes.length; h++) {
        var hx = rx + KAG.hexes[h][0] * a, hy = cy + KAG.hexes[h][1] * a, hr = a * 0.5 * (1 - 0.9 * dl * 2);
        c.beginPath();
        for (var v = 0; v < 6; v++) { var an = v * Math.PI / 3; if (v) c.lineTo(hx + hr * Math.cos(an), hy + hr * Math.sin(an)); else c.moveTo(hx + hr * Math.cos(an), hy + hr * Math.sin(an)); }
        c.closePath(); c.fill();
      }
      var S = KAG.sites;
      c.beginPath();
      for (var b = 0; b < KAG.bonds.length; b++) {
        var p0 = S[KAG.bonds[b][0]], p1 = S[KAG.bonds[b][1]];
        c.moveTo(rx + (p0[0] + dl * p0[2]) * a, cy + (p0[1] + dl * p0[3]) * a);
        c.lineTo(rx + (p1[0] + dl * p1[2]) * a, cy + (p1[1] + dl * p1[3]) * a);
      }
      c.lineWidth = 1.1; c.strokeStyle = stAlpha(C.ink2, 0.45); c.stroke();
      c.fillStyle = C.accent; c.beginPath();
      for (var n = 0; n < S.length; n++) {
        var sx = rx + (S[n][0] + dl * S[n][2]) * a, sy = cy + (S[n][1] + dl * S[n][3]) * a;
        c.moveTo(sx + 2, sy); c.arc(sx, sy, 2, 0, TAU);
      }
      c.fill();
      label(c, C, 'kagome CsV₃Sb₅', rx, 106, { size: 11, color: C.ink2, align: 'center' });
    }

    /* Heavy fermions: a lattice of f-electron moments; light conduction electrons move among them and slow down as
       screening (Kondo) clouds form around the moments, becoming heavy quasiparticles. */
    var HV = { P: 10, a1: 1.6, b1: 4.0, a2: 8.0, b2: 9.6, kap: 0.88 };
    function hvS(tt) {   // ∫0^tt s(τ) dτ for s = smoothstep up on [a1, b1], down on [a2, b2]
      function I(u) { u = stClamp(u); return u * u * u - u * u * u * u / 2; }
      var h = HV, up = (h.b1 - h.a1) * I((tt - h.a1) / (h.b1 - h.a1)) + Math.max(0, Math.min(tt, h.a2) - h.b1);
      if (tt <= h.a2) return up;
      return up + (Math.min(tt, h.b2) - h.a2) - (h.b2 - h.a2) * I((tt - h.a2) / (h.b2 - h.a2));
    }
    var HV_E = (function () { var r = stRng(21), a = []; for (var i = 0; i < 8; i++) a.push({ f: (Math.floor(i / 2) + 0.2 + 0.25 * r()) / 4, ph: r() * TAU, lane: i % 2 }); return a; })();
    var HV_M = (function () { var r = stRng(4), a = []; for (var i = 0; i < 40; i++) a.push(r() * TAU); return a; })();
    function drawHeavy(c, C, W, H, t) {
      var P = HV.P, tt = md(t, P), s = stSpan(tt, HV.a1, HV.b1) * (1 - stSpan(tt, HV.a2, HV.b2));
      var m = 10, sx = 34, x0 = m + 14, x1 = W - m - 14, nc = Math.max(5, Math.floor((x1 - x0) / sx) + 1);
      var ox = (W - (nc - 1) * sx) / 2;
      var nm = 3 * nc;
      for (var pass = 0; pass < 2; pass++) {   // screening clouds, then the f-moment discs
        if (!pass && s <= 0.01) continue;
        c.beginPath();
        for (var i = 0; i < nm; i++) {
          var x = ox + (i % nc) * sx, y = 20 + 26 * Math.floor(i / nc), r = pass ? 6.5 : 6 + 6 * s;
          c.moveTo(x + r, y); c.arc(x, y, r, 0, TAU);
        }
        if (!pass) { c.fillStyle = stAlpha(C.accent, 0.13 * s); c.fill(); }
        else { c.fillStyle = stAlpha(C.warm, 0.12); c.fill(); c.lineWidth = 1.2; c.strokeStyle = stAlpha(C.warm, 0.7); c.stroke(); }
      }
      c.globalAlpha = 1 - 0.6 * s;   // screened moments fade
      spins(c, nm, function (i, o) {
        var ii = i % nc, jj = Math.floor(i / nc), k = (ii * 3 + jj * 11) % HV_M.length;
        o[0] = ox + ii * sx; o[1] = 20 + 26 * jj; o[3] = 10;
        o[2] = HV_M[k] + 0.6 * Math.sin(TAU * tt / P + HV_M[(k + 7) % HV_M.length]);
      }, C.warm, 1.3);
      c.globalAlpha = 1;
      // conduction electrons: position = v0 (τ − κ ∫s dτ), with v0 chosen so each loop closes on itself
      var Lw = W - 2 * m + 12, peff = P - HV.kap * hvS(P), v0 = 2 * Lw / peff, dist = v0 * (tt - HV.kap * hvS(tt));
      c.save(); c.beginPath(); c.rect(m, m, W - 2 * m, 88 - m); c.clip();
      for (var e = 0; e < HV_E.length; e++) {
        var q = HV_E[e], dir = q.lane ? -1 : 1, base = q.f * Lw + dir * dist;
        var ex = m - 6 + md(base, Lw), ey = (q.lane ? 59 : 33) + 2 * Math.sin(ex * 0.09 + q.ph);
        c.globalAlpha = stClamp((ex - m) / 10) * stClamp((W - m - ex) / 10);
        if (s > 0.05) { c.beginPath(); c.arc(ex, ey, 4 + 3 * s, 0, TAU); c.fillStyle = stAlpha(C.accent, 0.18 * s); c.fill(); }
        dot(c, ex, ey, 2.6, C.accent);
      }
      c.globalAlpha = 1;
      c.restore();
      var heavy = stSpan(tt, HV.a1 + 1.2, HV.b1 + 0.2) * (1 - stSpan(tt, HV.a2, HV.a2 + 0.6));
      var light = (1 - stSpan(tt, HV.a1, HV.a1 + 0.6)) + stSpan(tt, HV.b2 - 0.4, HV.b2);
      if (light > 0.01) { c.globalAlpha = Math.min(1, light); stTag(c, C, 'm* ≈ mₑ', W / 2, 100, { size: 11, bg: C.surface, ring: C.axis }); }
      if (heavy > 0.01) { c.globalAlpha = heavy; stTag(c, C, 'm* ≈ 100–1000 mₑ', W / 2, 100, { size: 11, bg: C.surface, ring: C.accent }); }
      c.globalAlpha = 1;
    }

    return {
      london: guard(drawLondon), gl: guard(drawGL), bcs: guard(drawBCS), eliashberg: guard(drawEliashberg),
      josephson: guard(drawJosephson), dwave: guard(drawDwave), spm: guard(drawSpm), topo: guard(drawTopo),
      moire: guard(drawMoire), magnet: guard(drawMagnet), mgb2: guard(drawMgB2), rebco: guard(drawRebco),
      hg1223: guard(drawHg1223), iron: guard(drawIron), hydride: guard(drawHydride), nickelate: guard(drawNickelate),
      magic: guard(drawMagic), triplet: guard(drawTriplet), heavy: guard(drawHeavy)
    };
  })();

  MINI_STATIC = {
    london: 4.5, gl: 5.0, bcs: 5.8, eliashberg: 7.0, josephson: 0.6, dwave: 4.0, spm: 4.0, topo: 4.5, moire: 5.4,
    magnet: 1.0, mgb2: 0.3, rebco: 3.0, hg1223: 7.5, iron: 2.0, hydride: 4.5, nickelate: 1.0, magic: 1.9, triplet: 0.5, heavy: 6.5
  };

};
