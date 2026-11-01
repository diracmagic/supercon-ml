'use strict';
// news-drawings: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconNewsDrawings = function initializeSuperconNewsDrawings() {


  /* ---------- news illustrations: one original drawing per news topic (same engine as the card animations) ---------- */
  (function () {
    var TAU = Math.PI * 2;
    function md(t, p) { t = t % p; return t < 0 ? t + p : t; }
    function seg(c, x0, y0, x1, y1) { c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y1); c.stroke(); }
    function disc(c, x, y, r, fill) { c.beginPath(); c.arc(x, y, r, 0, TAU); c.fillStyle = fill; c.fill(); }
    function halo(c, x, y, r, color, a) { for (var i = 3; i >= 1; i--) disc(c, x, y, r * i / 3, stAlpha(color, a * 0.28)); }
    function arrowHead(c, x0, y0, x1, y1, color, hd, lw) {
      var a = Math.atan2(y1 - y0, x1 - x0);
      c.strokeStyle = color; c.fillStyle = color; c.lineWidth = lw || 1.3;
      c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1 - Math.cos(a) * hd * 0.8, y1 - Math.sin(a) * hd * 0.8); c.stroke();
      c.beginPath(); c.moveTo(x1, y1); c.lineTo(x1 - hd * Math.cos(a - 0.45), y1 - hd * Math.sin(a - 0.45));
      c.lineTo(x1 - hd * Math.cos(a + 0.45), y1 - hd * Math.sin(a + 0.45)); c.closePath(); c.fill();
    }
    function spinAt(c, x, y, ang, L, color) {
      var dx = Math.cos(ang) * L / 2, dy = Math.sin(ang) * L / 2;
      arrowHead(c, x - dx, y - dy, x + dx, y + dy, color, Math.max(2.6, L * 0.4), 1.2);
    }
    function guard(fn) {
      return function (c, C, W, H, t) {
        c.save(); c.lineCap = 'round'; c.lineJoin = 'round'; c.setLineDash([]); c.globalAlpha = 1;
        try { fn(c, C, W, H, t || 0, Math.min(W / 112, H / 84)); } finally { c.restore(); }
      };
    }
    var D = {};

    // Cuprates: a CuO2 plane and the four-lobed d-wave pair state on it
    D.cuprate = function (c, C, W, H, t, k) {
      var s = 22 * k, nx = Math.ceil(W / s) + 1, ny = Math.ceil(H / s) + 1, ox = (W - (nx - 1) * s) / 2, oy = (H - (ny - 1) * s) / 2;
      c.strokeStyle = C.grid; c.lineWidth = 1;
      for (var i = 0; i < nx; i++) seg(c, ox + i * s, 0, ox + i * s, H);
      for (var j = 0; j < ny; j++) seg(c, 0, oy + j * s, W, oy + j * s);
      for (i = 0; i < nx; i++) for (j = 0; j < ny; j++) {
        disc(c, ox + i * s + s / 2, oy + j * s, 1.6 * k, C.muted); disc(c, ox + i * s, oy + j * s + s / 2, 1.6 * k, C.muted);
        disc(c, ox + i * s, oy + j * s, 2.8 * k, C.accent);
      }
      var cx = W / 2, cy = H / 2, a = 0.75 + 0.25 * Math.sin(TAU * t / 3);
      [[1, 0, C.accent], [0, 1, C.warm], [-1, 0, C.accent], [0, -1, C.warm]].forEach(function (q) {
        c.beginPath(); c.ellipse(cx + q[0] * 13 * k * a, cy + q[1] * 13 * k * a, (q[0] ? 11 : 6) * k * a, (q[0] ? 6 : 11) * k * a, 0, 0, TAU);
        c.fillStyle = stAlpha(q[2], 0.42); c.fill();
      });
      disc(c, cx, cy, 3.2 * k, C.ink);
    };
    // Nickelates: two NiO2 layers joined by apical oxygens, with a pair spanning the layers
    D.nickelate = function (c, C, W, H, t, k) {
      var n = 5, dx = W * 0.16, x0 = W * 0.18, skew = 10 * k, ys = [H * 0.3, H * 0.7];
      ys.forEach(function (y) {
        c.beginPath(); c.moveTo(x0 - 8 * k, y + 6 * k); c.lineTo(x0 + (n - 1) * dx + 4 * k, y + 6 * k); c.lineTo(x0 + (n - 1) * dx + skew + 12 * k, y - 6 * k); c.lineTo(x0 + skew, y - 6 * k); c.closePath();
        c.fillStyle = stAlpha(C.accent, 0.12); c.fill();
      });
      for (var i = 0; i < n; i++) {
        var x = x0 + i * dx + skew / 2;
        c.strokeStyle = C.axis; c.lineWidth = 1.4; seg(c, x, ys[0], x, ys[1]);
        disc(c, x, (ys[0] + ys[1]) / 2, 2 * k, C.muted);
        disc(c, x, ys[0], 3.2 * k, C.accent); disc(c, x, ys[1], 3.2 * k, C.accent);
      }
      var px = x0 + skew / 2 + md(t * 0.35, 1) * (n - 1) * dx;
      halo(c, px, ys[0], 9 * k, C.warm, 0.7); halo(c, px, ys[1], 9 * k, C.warm, 0.7);
      c.strokeStyle = stAlpha(C.warm, 0.8); c.lineWidth = 1.6; c.setLineDash([2 * k, 2 * k]); seg(c, px, ys[0] + 4 * k, px, ys[1] - 4 * k); c.setLineDash([]);
      disc(c, px, ys[0], 2.6 * k, C.warm); disc(c, px, ys[1], 2.6 * k, C.warm);
    };
    // Iron-based: iron square lattice, arsenic above and below, fluctuating stripe spins
    D.iron = function (c, C, W, H, t, k) {
      var s = 24 * k, nx = Math.floor(W / s) + 1, ny = Math.floor(H / s) + 1, ox = (W - (nx - 1) * s) / 2, oy = (H - (ny - 1) * s) / 2;
      for (var i = 0; i < nx - 1; i++) for (var j = 0; j < ny - 1; j++) disc(c, ox + (i + 0.5) * s, oy + (j + 0.5) * s, ((i + j) % 2 ? 2.2 : 3.8) * k, stAlpha(C.muted, (i + j) % 2 ? 0.45 : 0.7));
      for (i = 0; i < nx; i++) for (j = 0; j < ny; j++) {
        var x = ox + i * s, y = oy + j * s, ang = (j % 2 ? 1 : -1) * Math.PI / 2 + 0.35 * Math.sin(TAU * t / 2.6 + i * 0.9 + j * 0.4), L = 13 * k;
        disc(c, x, y, 2.6 * k, C.accent);
        arrowHead(c, x - Math.cos(ang) * L / 2, y - Math.sin(ang) * L / 2, x + Math.cos(ang) * L / 2, y + Math.sin(ang) * L / 2, C.warm, 3.6 * k, 1.4);
      }
    };
    // Hydrides: a hydrogen cage around a metal atom, squeezed between two diamond anvils
    D.hydride = function (c, C, W, H, t, k) {
      var sq = 0.5 + 0.5 * Math.sin(TAU * t / 4), cx = W / 2, cy = H / 2, gap = (16 + 6 * (1 - sq)) * k;
      c.fillStyle = stAlpha(C.accent, 0.16); c.strokeStyle = stAlpha(C.accent, 0.6); c.lineWidth = 1.2;
      [-1, 1].forEach(function (sd) {
        c.beginPath(); c.moveTo(cx - 26 * k, cy + sd * (gap + 22 * k)); c.lineTo(cx + 26 * k, cy + sd * (gap + 22 * k)); c.lineTo(cx + 8 * k, cy + sd * gap); c.lineTo(cx - 8 * k, cy + sd * gap); c.closePath(); c.fill(); c.stroke();
      });
      var r = (13 - 2.5 * sq) * k;
      for (var i = 0; i < 12; i++) {
        var a = TAU * i / 12 + t * 0.4, ring = i % 2, rr = r * (ring ? 0.75 : 1);
        var x = cx + Math.cos(a) * rr * 1.3 + 0.8 * k * Math.sin(t * 17 + i), y = cy + Math.sin(a) * rr * 0.75 + (ring ? -2 : 2) * k + 0.8 * k * Math.cos(t * 19 + i);
        disc(c, x, y, 1.9 * k, C.accent);
      }
      disc(c, cx, cy, 4.6 * k, C.gold || C.warm);
      c.strokeStyle = stAlpha(C.warm, 0.6 * sq); c.lineWidth = 1.4;
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (d) { arrowHead(c, cx + d[0] * 40 * k, cy + d[1] * (gap + 14 * k), cx + d[0] * 32 * k, cy + d[1] * (gap + 6 * k), stAlpha(C.warm, 0.7 * sq), 3.2 * k, 1.2); });
    };
    // Moiré and 2D: two triangular lattices twisted by a small, slowly changing angle
    D.moire = function (c, C, W, H, t, k) {
      var a = 7 * k, th = (3 + 2 * Math.sin(TAU * t / 9)) * Math.PI / 180, cx = W / 2, cy = H / 2, R = Math.hypot(W, H) / 2 + a;
      [[0, C.accent], [th, C.warm]].forEach(function (L) {
        var cs = Math.cos(L[0]), sn = Math.sin(L[0]), n = Math.ceil(R / a) + 1;
        c.beginPath();
        for (var i = -n; i <= n; i++) for (var j = -n; j <= n; j++) {
          var u = (i + j / 2) * a, v = j * a * 0.866, x = cx + u * cs - v * sn, y = cy + u * sn + v * cs;
          if (x < -2 || x > W + 2 || y < -2 || y > H + 2) continue;
          c.moveTo(x + 1.3 * k, y); c.arc(x, y, 1.3 * k, 0, TAU);
        }
        c.fillStyle = stAlpha(L[1], 0.55); c.fill();
      });
    };
    // Kagome: corner-sharing triangles with a breathing charge-density wave
    D.kagome = function (c, C, W, H, t, k) {
      var a = 22 * k, b = 0.5 + 0.5 * Math.sin(TAU * t / 3.5), cx = W / 2, cy = H / 2;
      for (var i = -3; i <= 3; i++) for (var j = -2; j <= 2; j++) {
        var x0 = cx + (i + j / 2) * a, y0 = cy + j * a * 0.866;
        var up = [[x0, y0], [x0 + a / 2, y0], [x0 + a / 4, y0 - a * 0.433]];
        var big = (i + 2 * j) % 2 === 0, sc = 1 + (big ? 0.12 : -0.12) * b, gx = (up[0][0] + up[1][0] + up[2][0]) / 3, gy = (up[0][1] + up[1][1] + up[2][1]) / 3;
        var p = up.map(function (q) { return [gx + (q[0] - gx) * sc, gy + (q[1] - gy) * sc]; });
        c.beginPath(); c.moveTo(p[0][0], p[0][1]); c.lineTo(p[1][0], p[1][1]); c.lineTo(p[2][0], p[2][1]); c.closePath();
        c.fillStyle = stAlpha(big ? C.warm : C.accent, 0.12 + 0.12 * b * (big ? 1 : 0)); c.fill();
        c.strokeStyle = stAlpha(C.accent, 0.7); c.lineWidth = 1.2; c.stroke();
        p.forEach(function (q) { disc(c, q[0], q[1], 2 * k, C.accent); });
      }
    };
    // Heavy fermions: light electrons slow down and dress up as they pass large f-moments
    var HEAVY = (function () { var r = stRng(13), a = []; for (var i = 0; i < 9; i++) a.push([r(), r(), r() * TAU]); return a; })();
    D.heavy = function (c, C, W, H, t, k) {
      var mom = [[0.25, 0.32], [0.62, 0.28], [0.42, 0.72], [0.82, 0.68]];
      mom.forEach(function (m, i) {
        halo(c, m[0] * W, m[1] * H, 14 * k, C.warm, 0.45);
        spinAt(c, m[0] * W, m[1] * H, -Math.PI / 2 + 0.6 * Math.sin(t * 0.9 + i * 1.7), 16 * k, C.warm);
      });
      HEAVY.forEach(function (e, i) {
        var x = md(e[0] * W + t * 14 * k * (0.6 + 0.4 * Math.sin(t + e[2])), W), y = e[1] * H + 4 * k * Math.sin(t * 1.5 + e[2]);
        var near = 0;
        mom.forEach(function (m) { near = Math.max(near, 1 - Math.hypot(x - m[0] * W, y - m[1] * H) / (22 * k)); });
        if (near > 0) halo(c, x, y, 7 * k, C.accent, 0.5 * near);
        disc(c, x, y, 2.2 * k, C.accent);
      });
    };
    // Triplet pairing: a rotating p-wave orbital carrying two parallel spins
    D.triplet = function (c, C, W, H, t, k) {
      var cx = W / 2, cy = H / 2, a = t * 0.7, L = 18 * k;
      [[1, C.accent], [-1, C.warm]].forEach(function (q) {
        var x = cx + q[0] * Math.cos(a) * L, y = cy + q[0] * Math.sin(a) * L * 0.8;
        c.beginPath(); c.ellipse(x, y, 15 * k, 9 * k, a, 0, TAU); c.fillStyle = stAlpha(q[1], 0.3); c.fill();
        spinAt(c, x, y, -Math.PI / 2, 14 * k, q[1]);
      });
      c.strokeStyle = stAlpha(C.ink2, 0.35); c.lineWidth = 1; c.setLineDash([2 * k, 3 * k]);
      c.beginPath(); c.ellipse(cx, cy, L, L * 0.8, 0, 0, TAU); c.stroke(); c.setLineDash([]);
      disc(c, cx, cy, 2 * k, C.ink2);
    };
    // Topological: a nanowire on a superconductor with Majorana modes glowing at its ends
    D.topo = function (c, C, W, H, t, k) {
      var y = H * 0.48, x0 = W * 0.14, x1 = W * 0.86, g = 0.6 + 0.4 * Math.sin(TAU * t / 2.4);
      c.fillStyle = stAlpha(C.accent, 0.18); c.fillRect(W * 0.06, y + 7 * k, W * 0.88, 14 * k);
      stRound(c, x0, y - 5 * k, x1 - x0, 10 * k, 5 * k); c.fillStyle = C.surface; c.fill(); c.strokeStyle = C.axis; c.lineWidth = 1.2; c.stroke();
      c.beginPath();
      for (var i = 0; i <= 60; i++) {
        var u = i / 60, x = x0 + u * (x1 - x0), env = Math.exp(-u * 7) + Math.exp(-(1 - u) * 7), yy = y - 14 * k * env * g * (0.6 + 0.4 * Math.cos(u * 40));
        if (i) c.lineTo(x, yy); else c.moveTo(x, yy);
      }
      c.strokeStyle = stAlpha(C.gold || C.warm, 0.8); c.lineWidth = 1.4; c.stroke();
      halo(c, x0 + 4 * k, y, 10 * k * g, C.gold || C.warm, 0.8); halo(c, x1 - 4 * k, y, 10 * k * g, C.gold || C.warm, 0.8);
    };
    // Electron–phonon: an electron pulls the ions together behind it; a partner rides the wake
    D.eph = function (c, C, W, H, t, k) {
      var s = 14 * k, nx = Math.ceil(W / s) + 1, rows = [H * 0.3, H * 0.7], ex = md(t * 22 * k, W + 40 * k) - 20 * k, ey = H / 2;
      rows.forEach(function (ry, ri) {
        for (var i = 0; i < nx; i++) {
          var x = i * s, d = x - ex, pull = d < 0 ? Math.exp(d / (26 * k)) : Math.exp(-d / (6 * k));
          disc(c, x, ry + (ri ? -1 : 1) * 5 * k * pull, 3 * k, C.muted);
        }
      });
      c.fillStyle = stAlpha(C.warm, 0.12); c.fillRect(ex - 40 * k, rows[0], 40 * k, rows[1] - rows[0]);
      halo(c, ex, ey, 8 * k, C.accent, 0.6); disc(c, ex, ey, 3 * k, C.accent);
      var px = ex - 26 * k; halo(c, px, ey, 7 * k, C.accent, 0.4); disc(c, px, ey, 2.6 * k, C.accent);
    };
    // Vortices and junctions: a lattice of swirling flux vortices
    D.vortex = function (c, C, W, H, t, k) {
      var a = 30 * k, cx = W / 2, cy = H / 2;
      for (var i = -2; i <= 2; i++) for (var j = -1; j <= 1; j++) {
        var x = cx + (i + (j % 2 ? 0.5 : 0)) * a, y = cy + j * a * 0.866;
        if (x < -10 || x > W + 10) continue;
        disc(c, x, y, 3 * k, stAlpha(C.accent, 0.8));
        for (var r = 1; r <= 2; r++) {
          var rr = r * 6 * k, a0 = t * (3 - r) + i + j;
          c.beginPath(); c.arc(x, y, rr, a0, a0 + TAU * 0.7); c.strokeStyle = stAlpha(C.accent, 0.55 - r * 0.15); c.lineWidth = 1.2; c.stroke();
          arrowHead(c, x + Math.cos(a0 + TAU * 0.68) * rr, y + Math.sin(a0 + TAU * 0.68) * rr, x + Math.cos(a0 + TAU * 0.7) * rr, y + Math.sin(a0 + TAU * 0.7) * rr, stAlpha(C.accent, 0.55 - r * 0.15), 3 * k, 1.2);
        }
      }
    };
    // AI and data: a crystal feeds a small network whose output lights up
    D.ai = function (c, C, W, H, t, k) {
      var cols = [W * 0.42, W * 0.62, W * 0.84], n = [4, 3, 1], pts = cols.map(function (x, ci) { var a = []; for (var i = 0; i < n[ci]; i++) a.push([x, H * (n[ci] === 1 ? 0.5 : 0.2 + 0.6 * i / (n[ci] - 1))]); return a; });
      for (var i = 0; i < 3; i++) for (var j = 0; j < 3; j++) disc(c, W * 0.08 + i * 9 * k, H * 0.32 + j * 10 * k, 2.4 * k, (i + j) % 2 ? C.muted : C.accent);
      c.strokeStyle = C.axis; c.lineWidth = 1; arrowHead(c, W * 0.29, H / 2, W * 0.36, H / 2, C.axis, 3 * k, 1);
      var ph = md(t / 2.2, 1);
      for (var l = 0; l < 2; l++) pts[l].forEach(function (p) { pts[l + 1].forEach(function (q) {
        var on = Math.max(0, 1 - Math.abs(ph * 3 - (l + 0.5)) * 1.6);
        c.strokeStyle = stAlpha(on > 0.05 ? C.warm : C.grid, on > 0.05 ? 0.3 + 0.6 * on : 1); c.lineWidth = 1; seg(c, p[0], p[1], q[0], q[1]);
      }); });
      pts.forEach(function (col, ci) { col.forEach(function (p) {
        var on = Math.max(0, 1 - Math.abs(ph * 3 - ci) * 1.6);
        if (on > 0.05) halo(c, p[0], p[1], 8 * k, C.warm, 0.6 * on);
        disc(c, p[0], p[1], 3 * k, C.accent);
      }); });
    };
    // Quantum devices: a transmon qubit and its state swinging around a Bloch circle
    D.qubit = function (c, C, W, H, t, k) {
      var cx = W * 0.32, cy = H / 2, s = 9 * k;
      c.fillStyle = stAlpha(C.accent, 0.35); c.strokeStyle = C.accent; c.lineWidth = 1.2;
      [[0, -1], [1, 0], [0, 1], [-1, 0]].forEach(function (d) { c.fillRect(cx + d[0] * 2 * s - (d[0] ? s * 0.6 : s * 0.5), cy + d[1] * 2 * s - (d[1] ? s * 0.6 : s * 0.5), d[0] ? s * 1.2 : s, d[1] ? s * 1.2 : s); });
      c.fillRect(cx - s * 0.5, cy - s * 0.5, s, s);
      c.fillStyle = C.warm; c.fillRect(cx + s * 0.5, cy - 1.5 * k, s * 0.9, 3 * k);
      var bx = W * 0.74, by = H / 2, R = Math.min(W * 0.18, H * 0.34), a = TAU * t / 3;
      c.strokeStyle = C.axis; c.lineWidth = 1; c.beginPath(); c.arc(bx, by, R, 0, TAU); c.stroke();
      c.beginPath(); c.ellipse(bx, by, R, R * 0.3, 0, 0, TAU); c.strokeStyle = C.grid; c.stroke();
      arrowHead(c, bx, by, bx + Math.sin(a) * R * 0.9, by - Math.cos(a) * R * 0.9, C.warm, 4 * k, 1.6);
    };
    // Anything else: a magnet floating above a cold superconductor (the Meissner effect)
    D.general = function (c, C, W, H, t, k) {
      var cx = W / 2, by = H * 0.72, f = 3 * k * Math.sin(TAU * t / 3);
      c.beginPath(); c.ellipse(cx, by + 6 * k, W * 0.34, 9 * k, 0, 0, TAU); c.fillStyle = stAlpha(C.accent, 0.35); c.fill();
      c.beginPath(); c.ellipse(cx, by, W * 0.34, 9 * k, 0, 0, TAU); c.fillStyle = C.surface; c.fill(); c.strokeStyle = C.axis; c.lineWidth = 1; c.stroke();
      halo(c, cx, by, 16 * k, C.aqua || C.accent, 0.55);
      var my = H * 0.36 + f, w = 15 * k;
      c.beginPath(); c.moveTo(cx - w, my); c.lineTo(cx, my - w * 0.32); c.lineTo(cx + w, my); c.lineTo(cx, my + w * 0.32); c.closePath(); c.fillStyle = mix(C.warm, '#ffffff', 0.45); c.fill();
      c.beginPath(); c.moveTo(cx - w, my); c.lineTo(cx, my + w * 0.32); c.lineTo(cx, my + w * 1.6); c.lineTo(cx - w, my + w * 1.28); c.closePath(); c.fillStyle = C.warm; c.fill();
      c.beginPath(); c.moveTo(cx + w, my); c.lineTo(cx, my + w * 0.32); c.lineTo(cx, my + w * 1.6); c.lineTo(cx + w, my + w * 1.28); c.closePath(); c.fillStyle = mix(C.warm, '#000000', 0.2); c.fill();
    };

    var ALT = {
      cuprate: 'A copper-oxide plane with a four-lobed d-wave pair state pulsing on it.',
      nickelate: 'Two nickel-oxide layers joined by oxygen bridges, with a pair of electrons spanning the layers.',
      iron: 'An iron square lattice with arsenic above and below and fluctuating stripe-ordered spins.',
      hydride: 'A cage of hydrogen atoms around a metal atom, squeezed between two diamond anvils.',
      moire: 'Two atomic lattices twisted by a small angle, forming a slowly changing moiré pattern.',
      kagome: 'A kagome lattice of corner-sharing triangles with a breathing charge-density wave.',
      heavy: 'Light electrons slow down and gather clouds around large f-electron moments.',
      triplet: 'A rotating p-wave orbital carrying two parallel spins.',
      topo: 'A nanowire on a superconductor with Majorana modes glowing at its two ends.',
      eph: 'An electron pulls the ions together behind it and a second electron rides in the wake.',
      vortex: 'A triangular lattice of swirling magnetic-flux vortices.',
      ai: 'A crystal structure feeds a small neural network whose layers light up in turn.',
      qubit: 'A cross-shaped superconducting qubit beside a Bloch circle whose arrow swings back and forth.',
      general: 'A magnet floating above a cold superconductor, the Meissner effect.'
    };
    Object.keys(D).forEach(function (kind) {
      MINI_DRAW['news-' + kind] = guard(D[kind]);
      MINI_STATIC['news-' + kind] = 1.2;
      MINI_ALT['news-' + kind] = ALT[kind];
    });
  })();

  // Which drawing goes with a news item: its first material or physics topic in this order; a qubit for device stories; else the floating magnet.
  NEWS_ART = [['Hydrides', 'hydride'], ['Cuprates', 'cuprate'], ['Nickelates', 'nickelate'], ['Iron-based', 'iron'],
    ['Moiré and 2D', 'moire'], ['Kagome', 'kagome'], ['Heavy fermions', 'heavy'], ['Triplet and ruthenates', 'triplet'],
    ['Topological', 'topo'], ['Electron–phonon', 'eph'], ['Vortices and junctions', 'vortex'], ['AI and data', 'ai']];

};
