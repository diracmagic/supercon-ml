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

    // CuO2 plane fragment; the camera moves, no pairing state or phonon is asserted.
    D.cuprate = function (c, C, W, H, t, k) {
      c.translate(W / 2, H / 2); c.rotate(.035 * Math.sin(t / 3)); c.translate(-W / 2, -H / 2);
      var s = 22 * k, nx = Math.ceil(W / s) + 1, ny = Math.ceil(H / s) + 1, ox = (W - (nx - 1) * s) / 2, oy = (H - (ny - 1) * s) / 2;
      c.strokeStyle = C.grid; c.lineWidth = 1;
      for (var i = 0; i < nx; i++) seg(c, ox + i * s, 0, ox + i * s, H);
      for (var j = 0; j < ny; j++) seg(c, 0, oy + j * s, W, oy + j * s);
      for (i = 0; i < nx; i++) for (j = 0; j < ny; j++) {
        disc(c, ox + i * s + s / 2, oy + j * s, 1.6 * k, C.muted); disc(c, ox + i * s, oy + j * s + s / 2, 1.6 * k, C.muted);
        disc(c, ox + i * s, oy + j * s, 2.8 * k, C.accent);
      }
    };
    // Only bilayer articles use this projected Ni–O fragment, without a pairing claim.
    D.nickelate = function (c, C, W, H, t, k) {
      c.translate(1.5 * k * Math.sin(t / 3), 0);
      var n = 5, dx = W * 0.16, x0 = W * 0.18, skew = 10 * k, ys = [H * 0.3, H * 0.7];
      ys.forEach(function (y) {
        c.beginPath(); c.moveTo(x0 - 8 * k, y + 6 * k); c.lineTo(x0 + (n - 1) * dx + 4 * k, y + 6 * k); c.lineTo(x0 + (n - 1) * dx + skew + 12 * k, y - 6 * k); c.lineTo(x0 + skew, y - 6 * k); c.closePath();
        c.fillStyle = stAlpha(C.accent, 0.12); c.fill();
      });
      for (var i = 0; i < n; i++) {
        var x = x0 + i * dx + skew / 2;
        c.strokeStyle = C.axis; c.lineWidth = 1.4; seg(c, x, ys[0], x, ys[1]);
        disc(c, x, (ys[0] + ys[1]) / 2, 2 * k, C.muted);
        if (i < n - 1) ys.forEach(function (y) { c.strokeStyle = C.axis; seg(c, x, y, x + dx, y); disc(c, x + dx / 2, y, 2 * k, C.muted); });
        disc(c, x, ys[0], 3.2 * k, C.accent); disc(c, x, ys[1], 3.2 * k, C.accent);
      }
    };
    // Iron-plane motif only; does not assume an As ligand or stripe-magnetic order.
    D.iron = function (c, C, W, H, t, k) {
      var s = 24 * k, nx = Math.floor(W / s) + 1, ny = Math.floor(H / s) + 1, ox = (W - (nx - 1) * s) / 2, oy = (H - (ny - 1) * s) / 2;
      c.translate(W / 2, H / 2); c.rotate(.035 * Math.sin(t / 3)); c.translate(-W / 2, -H / 2);
      for (var i = 0; i < nx; i++) for (var j = 0; j < ny; j++) {
        var x = ox + i * s, y = oy + j * s;
        c.strokeStyle = C.axis; c.lineWidth = 1;
        if (i + 1 < nx) seg(c, x, y, x + s, y);
        if (j + 1 < ny) seg(c, x, y, x, y + s);
        disc(c, x, y, 3 * k, C.accent);
      }
    };
    // Pressure apparatus: the central rectangle is a sample, not a guessed atomic cage.
    D.pressure = function (c, C, W, H, t, k) {
      var sq = 0.5 + 0.5 * Math.sin(TAU * t / 4), cx = W / 2, cy = H / 2, gap = (16 + 6 * (1 - sq)) * k;
      c.fillStyle = stAlpha(C.accent, 0.16); c.strokeStyle = stAlpha(C.accent, 0.6); c.lineWidth = 1.2;
      [-1, 1].forEach(function (sd) {
        c.beginPath(); c.moveTo(cx - 26 * k, cy + sd * (gap + 22 * k)); c.lineTo(cx + 26 * k, cy + sd * (gap + 22 * k)); c.lineTo(cx + 8 * k, cy + sd * gap); c.lineTo(cx - 8 * k, cy + sd * gap); c.closePath(); c.fill(); c.stroke();
      });
      c.fillStyle = C.warm; c.fillRect(cx - 12 * k, cy - 4 * k, 24 * k, 8 * k);
      c.strokeStyle = stAlpha(C.warm, 0.6 * sq); c.lineWidth = 1.4;
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (d) { arrowHead(c, cx + d[0] * 40 * k, cy + d[1] * (gap + 14 * k), cx + d[0] * 32 * k, cy + d[1] * (gap + 6 * k), stAlpha(C.warm, 0.7 * sq), 3.2 * k, 1.2); });
    };
    // Chemical building blocks, intentionally unbonded: no universal hydride cage exists.
    D.hydride = function (c, C, W, H, t, k) {
      var atoms = [[.2, .3], [.48, .24], [.75, .32], [.3, .68], [.65, .7]];
      c.font = (10 * k) + 'px sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
      atoms.forEach(function (p, i) { var x = W * p[0], y = H * p[1] + 2 * k * Math.sin(t + i); disc(c, x, y, 9 * k, stAlpha(C.accent, .25)); c.fillStyle = C.ink; c.fillText('H', x, y); });
      disc(c, W * .5, H * .49, 10 * k, C.warm); c.fillStyle = C.surface; c.fillText('M', W * .5, H * .49);
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
    // Kagome geometry: both triangle orientations, fixed distances, no assumed CDW.
    var KAGOME_NEWS = (function () {
      var points = [], edges = [], basis = [[0, 0], [1, 0], [.5, Math.sqrt(3) / 2]];
      for (var i = -3; i <= 3; i++) for (var j = -3; j <= 3; j++) basis.forEach(function (q) { points.push([2 * i + j + q[0], Math.sqrt(3) * j + q[1]]); });
      for (i = 0; i < points.length; i++) for (j = i + 1; j < points.length; j++) if (Math.abs(Math.hypot(points[i][0] - points[j][0], points[i][1] - points[j][1]) - 1) < 1e-6) edges.push([i, j]);
      return { points: points, edges: edges };
    })();
    D.kagome = function (c, C, W, H, t, k) {
      var a = 14 * k, points = KAGOME_NEWS.points;
      c.translate(W / 2, H / 2); c.rotate(.035 * Math.sin(t / 3));
      c.strokeStyle = stAlpha(C.accent, .7); c.lineWidth = 1.2;
      KAGOME_NEWS.edges.forEach(function (edge) { var p = points[edge[0]], q = points[edge[1]]; seg(c, p[0] * a, p[1] * a, q[0] * a, q[1] * a); });
      points.forEach(function (q) { disc(c, q[0] * a, q[1] * a, 2 * k, C.accent); });
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
    // Candidate boundary/channel schematic; no observed Majorana mode is asserted.
    D.topo = function (c, C, W, H, t, k) {
      var y = H * 0.48, x0 = W * 0.14, x1 = W * 0.86, g = 0.6 + 0.4 * Math.sin(TAU * t / 2.4);
      c.fillStyle = stAlpha(C.accent, 0.18); c.fillRect(W * 0.06, y + 7 * k, W * 0.88, 14 * k);
      stRound(c, x0, y - 5 * k, x1 - x0, 10 * k, 5 * k); c.fillStyle = C.surface; c.fill(); c.strokeStyle = C.axis; c.lineWidth = 1.2; c.stroke();
      c.strokeStyle = stAlpha(C.warm, .4 + .3 * g); c.lineWidth = 2;
      seg(c, x0, y - 9 * k, x1, y - 9 * k);
    };
    // Electron–phonon coupling cartoon; not literal Cooper-pair trajectories.
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
    // Legacy illustration remains available for an explicitly reviewed Meissner article.
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

    // Subject-specific diagrams reuse the original canvas palette and motion, not random artwork.
    D.layered = function (c, C, W, H, t, k, count) {
      count = count || 4;
      for (var layer = 0; layer < count; layer++) {
        var y = H * .23 + layer * H * .54 / (count - 1), shift = 2 * k * Math.sin(t / 3);
        c.fillStyle = stAlpha(C.accent, .1 + .04 * layer); c.strokeStyle = C.accent; c.lineWidth = 1;
        c.beginPath(); c.moveTo(W * .16 + shift, y); c.lineTo(W * .68 + shift, y); c.lineTo(W * .84 + shift, y - 9 * k); c.lineTo(W * .32 + shift, y - 9 * k); c.closePath(); c.fill(); c.stroke();
      }
    };
    D['layered-six'] = function (c, C, W, H, t, k) { D.layered(c, C, W, H, t, k, 6); };
    D.stripes = function (c, C, W, H, t, k) {
      for (var i = 0; i < 8; i++) for (var j = 0; j < 5; j++) {
        var a = .25 + .65 * (1 + Math.cos(i * Math.PI / 2)) / 2;
        disc(c, W * .12 + i * 12 * k, H * .18 + j * 13 * k, (2 + a) * k, stAlpha(C.accent, a));
      }
      c.strokeStyle = stAlpha(C.warm, .7); c.lineWidth = 2;
      var scan = W * (.12 + .76 * md(t / 5, 1)); seg(c, scan, H * .1, scan, H * .88);
    };
    D.literature = function (c, C, W, H, t, k) {
      for (var i = 2; i >= 0; i--) {
        var x = W * .12 + i * 4 * k, y = H * .18 + i * 4 * k;
        c.fillStyle = C.surface; c.strokeStyle = C.axis; c.lineWidth = 1;
        c.fillRect(x, y, 33 * k, 43 * k); c.strokeRect(x, y, 33 * k, 43 * k);
        for (var line = 0; line < 4; line++) { c.strokeStyle = line === Math.floor(md(t, 4)) ? C.warm : C.accent; seg(c, x + 6 * k, y + (10 + line * 8) * k, x + 27 * k, y + (10 + line * 8) * k); }
      }
      arrowHead(c, W * .55, H * .5, W * .68, H * .5, C.warm, 3 * k, 1.2);
      c.strokeStyle = C.accent;
      for (i = 0; i < 3; i++) { c.strokeRect(W * .72, H * .25 + i * 16 * k, 20 * k, 10 * k); disc(c, W * .76, H * .31 + i * 16 * k, 1.5 * k, C.warm); }
    };
    D.features = function (c, C, W, H, t, k) {
      var centers = [[.24, .32], [.7, .28], [.48, .72]];
      c.strokeStyle = C.grid; c.lineWidth = 1;
      centers.forEach(function (p, i) { var q = centers[(i + 1) % 3]; seg(c, p[0] * W, p[1] * H, q[0] * W, q[1] * H); });
      centers.forEach(function (p, group) {
        for (var i = 0; i < 7; i++) { var a = i * 2.4, r = (5 + i) * k; disc(c, p[0] * W + Math.cos(a) * r, p[1] * H + Math.sin(a) * r, 2 * k, group === 1 ? C.warm : C.accent); }
        c.beginPath(); c.arc(p[0] * W, p[1] * H, (15 + Math.sin(t + group)) * k, 0, TAU); c.strokeStyle = stAlpha(C.accent, .5); c.stroke();
      });
    };
    D.graph = function (c, C, W, H, t, k) {
      var points = [[.2, .3], [.45, .18], [.7, .32], [.28, .72], [.57, .68], [.82, .6]], edges = [[0, 1], [1, 2], [0, 3], [1, 4], [2, 5], [3, 4], [4, 5]];
      edges.forEach(function (edge, i) { var p = points[edge[0]], q = points[edge[1]], phase = md(t / 2 + i / edges.length, 1); c.strokeStyle = C.axis; c.lineWidth = 1.4; seg(c, p[0] * W, p[1] * H, q[0] * W, q[1] * H); disc(c, (p[0] + phase * (q[0] - p[0])) * W, (p[1] + phase * (q[1] - p[1])) * H, 2 * k, C.warm); });
      points.forEach(function (p) { disc(c, p[0] * W, p[1] * H, 4 * k, C.accent); });
    };
    D.search = function (c, C, W, H, t, k) {
      for (var i = 0; i < 6; i++) {
        var x = W * .12 + (i % 3) * 31 * k, y = H * .22 + Math.floor(i / 3) * 29 * k;
        c.strokeStyle = i === Math.floor(md(t, 6)) ? C.warm : C.axis; c.lineWidth = i === Math.floor(md(t, 6)) ? 2.2 : 1;
        c.strokeRect(x, y, 23 * k, 21 * k);
        disc(c, x + 8 * k, y + 7 * k, 2 * k, C.accent); disc(c, x + 16 * k, y + 14 * k, 2 * k, C.accent);
      }
    };
    D.measurement = function (c, C, W, H, t, k) {
      c.fillStyle = C.accent; c.fillRect(W * .2, H * .55, W * .6, 10 * k);
      c.strokeStyle = C.axis; c.lineWidth = 1.4;
      [.25, .4, .6, .75].forEach(function (x, i) { seg(c, W * x, H * .55, W * x, H * (i === 0 || i === 3 ? .75 : .35)); disc(c, W * x, H * .55, 2.2 * k, C.warm); });
      c.beginPath(); c.arc(W / 2, H * .29, 12 * k, 0, TAU); c.stroke();
      var angle = -.8 + .3 * Math.sin(t); seg(c, W / 2, H * .29, W / 2 + 9 * k * Math.sin(angle), H * .29 - 9 * k * Math.cos(angle));
    };
    D.spectrum = function (c, C, W, H, t, k) {
      c.strokeStyle = C.axis; c.lineWidth = 1; seg(c, W * .14, H * .78, W * .88, H * .78); seg(c, W * .14, H * .78, W * .14, H * .18);
      c.strokeStyle = C.accent; c.lineWidth = 1.7; c.beginPath();
      for (var i = 0; i <= 60; i++) { var u = i / 60, height = .12 + .4 * Math.exp(-Math.pow((u - .3) / .1, 2)) + .3 * Math.exp(-Math.pow((u - .68) / .14, 2)), x = W * (.15 + .72 * u), y = H * (.78 - height); if (i) c.lineTo(x, y); else c.moveTo(x, y); } c.stroke();
      var scan = W * (.15 + .72 * md(t / 5, 1)); c.strokeStyle = C.warm; seg(c, scan, H * .2, scan, H * .78);
    };
    D.light = function (c, C, W, H, t, k) {
      c.fillStyle = C.accent; c.fillRect(W * .64, H * .24, 15 * k, H * .55);
      c.strokeStyle = C.warm; c.lineWidth = 1.5; c.beginPath();
      for (var i = 0; i <= 60; i++) { var u = i / 60, x = W * (.1 + .5 * u), y = H * .5 + 9 * k * Math.sin(u * 20 - t * 5); if (i) c.lineTo(x, y); else c.moveTo(x, y); } c.stroke();
      arrowHead(c, W * .52, H * .5, W * .63, H * .5, C.warm, 4 * k, 1.5);
    };
    D.junction = function (c, C, W, H, t, k) {
      c.fillStyle = stAlpha(C.accent, .4); c.fillRect(W * .17, H * .28, W * .29, H * .44); c.fillRect(W * .54, H * .28, W * .29, H * .44);
      c.fillStyle = C.axis; c.fillRect(W * .48, H * .28, W * .04, H * .44);
      disc(c, W * (.28 + .44 * md(t / 3, 1)), H * .5, 3 * k, C.warm);
    };
    D.interval = function (c, C, W, H, t, k) {
      for (var i = 0; i < 4; i++) { var y = H * (.22 + i * .19), x = W * (.35 + i * .1), width = (12 + i * 4) * k; c.strokeStyle = C.accent; c.lineWidth = 2; seg(c, x - width, y, x + width, y); seg(c, x - width, y - 4 * k, x - width, y + 4 * k); seg(c, x + width, y - 4 * k, x + width, y + 4 * k); disc(c, x, y, (2.5 + .5 * Math.sin(t + i)) * k, C.warm); }
    };
    D.routing = function (c, C, W, H, t, k) {
      c.strokeStyle = C.axis; c.lineWidth = 1.4;
      [[.2, .5, .48, .5], [.48, .5, .76, .25], [.48, .5, .76, .75]].forEach(function (p) { seg(c, W * p[0], H * p[1], W * p[2], H * p[3]); });
      [[.2, .5], [.48, .5], [.76, .25], [.76, .75]].forEach(function (p, i) { disc(c, W * p[0], H * p[1], (i ? 5 : 4) * k, i === 2 + Math.floor(md(t / 2, 2)) ? C.warm : C.accent); });
    };
    D['two-stage'] = function (c, C, W, H, t, k) {
      D.routing(c, C, W, H, t, k);
      c.font = (8 * k) + 'px sans-serif'; c.textAlign = 'center'; c.fillStyle = C.ink;
      c.fillText('SC score', W * .47, H * .37); c.fillText('Tc', W * .77, H * .12); c.fillText('low score', W * .75, H * .92);
    };
    D.tree = function (c, C, W, H, t, k) {
      var points = [[.5, .18], [.28, .43], [.72, .43], [.14, .76], [.41, .76], [.6, .76], [.86, .76]];
      for (var i = 1; i < points.length; i++) { var parent = points[Math.floor((i - 1) / 2)], child = points[i]; c.strokeStyle = C.axis; c.lineWidth = 1.3; seg(c, W * parent[0], H * parent[1], W * child[0], H * child[1]); }
      points.forEach(function (p, i) { disc(c, W * p[0], H * p[1], 4 * k, i === Math.floor(md(t, 7)) ? C.warm : C.accent); });
    };

    // Detector schematic: an absorber read out by superconducting sensors; the event repeats.
    D.detector = function (c, C, W, H, t, k) {
      var x0 = W * .12, x1 = W * .88, y0 = H * .44, y1 = H * .88, cx = W / 2, cy = (y0 + y1) / 2, ph = md(t / 3.2, 1), gold = C.gold || C.warm;
      c.fillStyle = stAlpha(C.muted, .16); c.strokeStyle = stAlpha(C.ink2, .5); c.lineWidth = 1.2;
      c.beginPath(); c.rect(x0, y0, x1 - x0, y1 - y0); c.fill(); c.stroke();
      c.strokeStyle = stAlpha(C.muted, .3); c.lineWidth = 1;
      for (var row = 1; row < 4; row++) seg(c, x0 + 3 * k, y0 + (y1 - y0) * row / 4, x1 - 3 * k, y0 + (y1 - y0) * row / 4);
      var a = Math.min(1, ph / .28), sx = W * .2, sy = H * .02, r = ph < .28 ? 0 : (ph - .28) / .72;
      if (ph < .55) { c.setLineDash([2.5 * k, 2.5 * k]); c.strokeStyle = stAlpha(C.warm, .9 - ph); c.lineWidth = 1.4; seg(c, sx, sy, sx + (cx - sx) * a, sy + (cy - sy) * a); c.setLineDash([]); }
      if (ph < .28) { halo(c, sx + (cx - sx) * a, sy + (cy - sy) * a, 6 * k, C.warm, .7); disc(c, sx + (cx - sx) * a, sy + (cy - sy) * a, 2.2 * k, C.warm); }
      for (var i = 0; i < 3; i++) {
        var q = r - i * .13; if (q <= 0) continue;
        c.beginPath(); c.ellipse(cx, cy, q * (x1 - x0) / 2, q * (y1 - y0) / 2, 0, 0, TAU); c.strokeStyle = stAlpha(C.accent, .9 * (1 - q)); c.lineWidth = 1.6; c.stroke();
      }
      if (r > 0 && r < .4) halo(c, cx, cy, 8 * k, C.warm, 1 - r / .4);
      for (var j = 0; j < 4; j++) {
        var px = x0 + (x1 - x0) * (.14 + j * .24), lit = r > 0 ? Math.max(0, 1 - Math.abs(r * (x1 - x0) / 2 - Math.abs(px - cx)) / (10 * k)) : 0;
        if (lit > .05) halo(c, px, y0 - 1.5 * k, 7 * k, gold, lit);
        c.strokeStyle = lit > .05 ? gold : C.accent; c.lineWidth = 1.3; c.beginPath(); c.moveTo(px - 5 * k, y0 - 1 * k);
        for (var z = 0; z < 4; z++) { c.lineTo(px - 5 * k + (z + .5) * 2.5 * k, y0 - (z % 2 ? 1 : 5) * k); }
        c.lineTo(px + 5 * k, y0 - 1 * k); c.stroke();
      }
    };
    // Superconducting diode: carriers pass freely one way and dissipate the other way.
    D.diode = function (c, C, W, H, t, k) {
      var y = H * .48, x0 = W * .1, x1 = W * .9, ph = md(t / 6, 1), fwd = ph < .5, e = Math.sin(Math.PI * (fwd ? ph : ph - .5) / .5);
      stRound(c, x0, y - 8 * k, x1 - x0, 16 * k, 8 * k); c.fillStyle = stAlpha(fwd ? C.accent : C.warm, fwd ? .2 : .1 + .12 * e); c.fill();
      c.strokeStyle = stAlpha(C.accent, .7); c.lineWidth = 1.2; c.stroke();
      for (var i = 0; i < 8; i++) {
        var u = md(i / 8 + t * (fwd ? .22 : .07), 1), x = fwd ? x0 + 4 * k + (x1 - x0 - 8 * k) * u : x1 - 4 * k - (x1 - x0 - 8 * k) * u;
        disc(c, x, y + (fwd ? 0 : 2.6 * k * Math.sin(t * 11 + i * 2.3)), 2.3 * k, fwd ? C.accent : C.warm);
      }
      if (fwd) arrowHead(c, W * .28, H * .2, W * .72, H * .2, stAlpha(C.accent, .3 + .65 * e), 5.5 * k, 2.2);
      else { arrowHead(c, W * .64, H * .2, W * .36, H * .2, stAlpha(C.warm, .3 + .65 * e), 4 * k, 1.4); for (var j = 0; j < 3; j++) halo(c, W * (.3 + j * .2), y, 7 * k, C.warm, .45 * e); }
      c.fillStyle = stAlpha(C.accent, .8); c.fillRect(W * .5, H * .8, W * .32, 4 * k);
      c.fillStyle = stAlpha(C.warm, .8); c.fillRect(W * .5 - W * .17, H * .8, W * .17, 4 * k);
      c.fillStyle = C.ink2; c.fillRect(W * .5 - .6, H * .76, 1.2, 4 * k + H * .08);
    };
    // Spin fluctuations: antiferromagnetically correlated spins whose tilts ripple across a square net.
    D.spinfluct = function (c, C, W, H, t, k) {
      var s = 20 * k, nx = Math.floor(W * .84 / s) + 1, ny = Math.floor(H * .78 / s) + 1, ox = (W - (nx - 1) * s) / 2, oy = (H - (ny - 1) * s) / 2;
      c.strokeStyle = stAlpha(C.muted, .35); c.lineWidth = 1;
      for (var i = 0; i < nx; i++) seg(c, ox + i * s, oy, ox + i * s, oy + (ny - 1) * s);
      for (var j = 0; j < ny; j++) seg(c, ox, oy + j * s, ox + (nx - 1) * s, oy + j * s);
      for (i = 0; i < nx; i++) for (j = 0; j < ny; j++) {
        var x = ox + i * s, y = oy + j * s, w = Math.sin(i * .95 + j * .55 - t * 1.7), up = (i + j) % 2 ? 1 : -1;
        if (w > .6) halo(c, x, y, 7 * k, C.gold || C.warm, (w - .6) * 1.6);
        spinAt(c, x, y, -Math.PI / 2 * up + .45 * w, 13 * k, up > 0 ? C.warm : C.accent);
      }
    };
    // Gaps on several Fermi pockets: ring thickness stands for gap size, no sign or node is drawn.
    D.multigap = function (c, C, W, H, t, k) {
      var b = Math.min(W * .4, H * .42), cx = W / 2, cy = H / 2, br = .78 + .22 * Math.sin(TAU * t / 4), a = t * .9;
      c.setLineDash([2 * k, 3 * k]); c.strokeStyle = stAlpha(C.muted, .55); c.lineWidth = 1; c.strokeRect(cx - b, cy - b, 2 * b, 2 * b); c.setLineDash([]);
      function ring(x, y, r, a0, a1, gap, col) {
        c.beginPath(); c.arc(x, y, r, a0, a1); c.strokeStyle = stAlpha(col, .3); c.lineWidth = gap; c.stroke();
        c.beginPath(); c.arc(x, y, r, a0, a1); c.strokeStyle = col; c.lineWidth = 1.3; c.stroke();
      }
      ring(cx, cy, b * .42, 0, TAU, 10 * k * br, C.accent);
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (d) { var a0 = Math.atan2(-d[1], -d[0]) - Math.PI / 4; ring(cx + d[0] * b, cy + d[1] * b, b * .36, a0, a0 + Math.PI / 2, 4.5 * k * br, C.warm); });
      halo(c, cx + Math.cos(a) * b * .42, cy + Math.sin(a) * b * .42, 5 * k, C.accent, .8); disc(c, cx + Math.cos(a) * b * .42, cy + Math.sin(a) * b * .42, 2 * k, C.surface);
    };
    // Zeeman splitting: a field separates spin-up and spin-down Fermi circles; a pair links k and -k across them.
    D.zeeman = function (c, C, W, H, t, k) {
      var cx = W * .56, cy = H / 2, r0 = Math.min(W, H) * .28, d = .1 + .09 * (1 + Math.sin(TAU * t / 5)) / 2, a = t * .7;
      [[1 + d, C.warm, -1], [1 - d, C.accent, 1]].forEach(function (s) {
        var r = r0 * s[0];
        c.beginPath(); c.arc(cx, cy, r, 0, TAU); c.fillStyle = stAlpha(s[1], .1); c.fill(); c.strokeStyle = s[1]; c.lineWidth = 1.5; c.stroke();
        for (var i = 0; i < 4; i++) { var q = i * Math.PI / 2 + Math.PI / 4; spinAt(c, cx + Math.cos(q) * r, cy + Math.sin(q) * r, s[2] * Math.PI / 2, 8 * k, s[1]); }
      });
      var p = [cx + Math.cos(a) * r0 * (1 + d), cy + Math.sin(a) * r0 * (1 + d)], q = [cx - Math.cos(a) * r0 * (1 - d), cy - Math.sin(a) * r0 * (1 - d)];
      c.setLineDash([2 * k, 2 * k]); c.strokeStyle = stAlpha(C.ink2, .6); c.lineWidth = 1.2; seg(c, p[0], p[1], q[0], q[1]); c.setLineDash([]);
      disc(c, p[0], p[1], 2.4 * k, C.warm); disc(c, q[0], q[1], 2.4 * k, C.accent);
      arrowHead(c, W * .12, H * .8, W * .12, H * .8 - (14 + 60 * d) * k, stAlpha(C.ink2, .75), 4 * k, 1.8);
    };
    // Tunnelling-style density of states with a gap and two coherence peaks; the dot sweeps the bias.
    D.gapdos = function (c, C, W, H, t, k) {
      var x0 = W * .08, x1 = W * .92, y0 = H * .82, top = H * .12, mid = W / 2, d = W * .13;
      function Y(x) {
        var e = (x - mid) / d, g = .09, ar = e * e - g * g - 1, ai = -2 * e * g, m = Math.hypot(ar, ai), sr = Math.sqrt((m + ar) / 2), si = (ai < 0 ? -1 : 1) * Math.sqrt(Math.max(0, (m - ar) / 2));
        var n = Math.abs((e * sr - g * si) / (sr * sr + si * si || 1));
        return y0 - (y0 - top) * Math.min(1, n / 3.2);
      }
      c.strokeStyle = stAlpha(C.ink2, .5); c.lineWidth = 1; seg(c, x0, y0, x1, y0); c.setLineDash([1.5 * k, 2.5 * k]); seg(c, mid, y0, mid, top); c.setLineDash([]);
      c.beginPath(); c.moveTo(x0, y0);
      for (var i = 0; i <= 90; i++) { var x = x0 + (x1 - x0) * i / 90; c.lineTo(x, Y(x)); }
      c.lineTo(x1, y0); c.closePath(); c.fillStyle = stAlpha(C.accent, .14); c.fill();
      c.beginPath();
      for (i = 0; i <= 90; i++) { x = x0 + (x1 - x0) * i / 90; if (i) c.lineTo(x, Y(x)); else c.moveTo(x, Y(x)); }
      c.strokeStyle = C.accent; c.lineWidth = 1.7; c.stroke();
      var sx = mid + (x1 - x0) * .44 * Math.sin(TAU * t / 6);
      c.strokeStyle = stAlpha(C.warm, .55); c.setLineDash([2 * k, 2 * k]); seg(c, sx, top, sx, y0); c.setLineDash([]);
      halo(c, sx, Y(sx), 6 * k, C.warm, .7); disc(c, sx, Y(sx), 2.3 * k, C.warm);
    };
    // Spatially modulated pair amplitude (FFLO / pair-density-wave type); pairs drift to suggest finite momentum.
    D.fflo = function (c, C, W, H, t, k) {
      var y = H * .5, x0 = W * .05, x1 = W * .95, A = H * .26, q = TAU * 2.25 / (x1 - x0), sh = t * .35;
      function f(x) { return Math.cos(q * (x - x0) - sh); }
      [[1, C.accent], [-1, C.warm]].forEach(function (s) {
        c.beginPath(); c.moveTo(x0, y);
        for (var i = 0; i <= 90; i++) { var x = x0 + (x1 - x0) * i / 90; c.lineTo(x, y - A * Math.max(0, s[0] * f(x)) * s[0]); }
        c.lineTo(x1, y); c.closePath(); c.fillStyle = stAlpha(s[1], .2); c.fill();
      });
      c.beginPath();
      for (var i = 0; i <= 90; i++) { var x = x0 + (x1 - x0) * i / 90; if (i) c.lineTo(x, y - A * f(x)); else c.moveTo(x, y - A * f(x)); }
      c.strokeStyle = C.accent; c.lineWidth = 1.6; c.stroke();
      c.strokeStyle = stAlpha(C.ink2, .45); c.lineWidth = 1; seg(c, x0, y, x1, y);
      for (var j = 0; j < 6; j++) {
        var px = x0 + (x1 - x0) * md(j / 6 + t * .06, 1), p = f(px) * f(px), py = H * .88;
        if (p < .08) continue;
        c.strokeStyle = stAlpha(C.ink2, .6 * p); c.lineWidth = 1; seg(c, px - 3 * k, py, px + 3 * k, py);
        disc(c, px - 3 * k, py, 2 * k, stAlpha(C.accent, p)); disc(c, px + 3 * k, py, 2 * k, stAlpha(C.warm, p));
      }
    };
    // Broken time-reversal symmetry: one circulation is chosen over its faint, dashed time-reversed partner.
    D.trsb = function (c, C, W, H, t, k) {
      var cx = W / 2, cy = H * .56, R = Math.min(W * .3, H * .36), a = t * 1.2;
      c.beginPath(); c.ellipse(cx, cy, R, R * .55, 0, 0, TAU); c.fillStyle = stAlpha(C.accent, .18); c.fill(); c.strokeStyle = stAlpha(C.accent, .55); c.lineWidth = 1.2; c.stroke();
      c.setLineDash([2 * k, 3 * k]); c.strokeStyle = stAlpha(C.muted, .6); c.lineWidth = 1.1;
      c.beginPath(); c.ellipse(cx, cy, R * 1.3, R * .74, 0, -a, -a - TAU * .55, true); c.stroke(); c.setLineDash([]);
      for (var i = 0; i < 2; i++) {
        var a0 = a + i * Math.PI, a1 = a0 + TAU * .32;
        c.beginPath(); c.ellipse(cx, cy, R * .78, R * .43, 0, a0, a1); c.strokeStyle = C.accent; c.lineWidth = 2; c.stroke();
        arrowHead(c, cx + Math.cos(a1 - .15) * R * .78, cy + Math.sin(a1 - .15) * R * .43, cx + Math.cos(a1) * R * .78, cy + Math.sin(a1) * R * .43, C.accent, 4 * k, 2);
      }
      for (var j = 0; j < 3; j++) {
        var x = cx + (j - 1) * R * .6, l = (8 + 4 * Math.sin(TAU * t / 2.5 + j * 2.1)) * k;
        arrowHead(c, x, cy - R * .62, x, cy - R * .62 - l, stAlpha(C.warm, .85), 3.6 * k, 1.6);
      }
    };
    // Kekulé bond pattern on a honeycomb: every third hexagon carries the strong bonds (a tripled cell).
    var KEKULE = (function () {
      var bonds = {}, sites = {}, out = { weak: [], strong: [], rings: [], sites: [] }, s3 = Math.sqrt(3);
      for (var i = -6; i <= 6; i++) for (var j = -6; j <= 6; j++) {
        var hx = s3 * (i + j / 2), hy = 1.5 * j, strong = ((i - j) % 3 + 3) % 3 === 0, v = [];
        if (Math.hypot(hx, hy) > 7.5) continue;
        for (var m = 0; m < 6; m++) v.push([hx + Math.cos(Math.PI / 6 + m * Math.PI / 3), hy + Math.sin(Math.PI / 6 + m * Math.PI / 3)]);
        if (strong) out.rings.push([hx, hy]);
        for (m = 0; m < 6; m++) {
          var p = v[m], q = v[(m + 1) % 6], key = Math.round((p[0] + q[0]) * 50) + ',' + Math.round((p[1] + q[1]) * 50);
          if (!bonds[key] || strong) bonds[key] = [p, q, strong];
          sites[Math.round(p[0] * 100) + ',' + Math.round(p[1] * 100)] = p;
        }
      }
      Object.keys(bonds).forEach(function (key) { (bonds[key][2] ? out.strong : out.weak).push(bonds[key]); });
      Object.keys(sites).forEach(function (key) { out.sites.push(sites[key]); });
      return out;
    })();
    D.kekule = function (c, C, W, H, t, k) {
      var a = 11 * k, g = .55 + .45 * Math.sin(TAU * t / 3.5);
      c.translate(W / 2, H / 2); c.rotate(.04 * Math.sin(t / 3));
      KEKULE.rings.forEach(function (r) { c.beginPath(); c.arc(r[0] * a, r[1] * a, a * .62, 0, TAU); c.fillStyle = stAlpha(C.accent, .1 + .14 * g); c.fill(); });
      c.strokeStyle = stAlpha(C.muted, .5); c.lineWidth = 1;
      KEKULE.weak.forEach(function (b) { seg(c, b[0][0] * a, b[0][1] * a, b[1][0] * a, b[1][1] * a); });
      c.strokeStyle = stAlpha(C.accent, .55 + .45 * g); c.lineWidth = 1.4 + 1.2 * g;
      KEKULE.strong.forEach(function (b) { seg(c, b[0][0] * a, b[0][1] * a, b[1][0] * a, b[1][1] * a); });
      KEKULE.sites.forEach(function (p) { disc(c, p[0] * a, p[1] * a, 1.5 * k, C.ink2); });
    };
    // Optical cavity: two mirrors and a standing mode around a thin sample; flickering dots suggest vacuum fluctuations.
    D.cavity = function (c, C, W, H, t, k) {
      var xl = W * .14, xr = W * .86, y0 = H * .12, y1 = H * .88, cy = H / 2, amp = Math.cos(TAU * t / 2.6), E = (y1 - y0) * .34, gold = C.gold || C.warm;
      c.fillStyle = stAlpha(C.ink2, .6); c.fillRect(xl - 5 * k, y0, 5 * k, y1 - y0); c.fillRect(xr, y0, 5 * k, y1 - y0);
      c.setLineDash([2 * k, 3 * k]); c.strokeStyle = stAlpha(C.warm, .35); c.lineWidth = 1;
      [1, -1].forEach(function (s) { c.beginPath(); for (var i = 0; i <= 50; i++) { var u = i / 50, x = xl + (xr - xl) * u, y = cy - s * E * Math.sin(Math.PI * u); if (i) c.lineTo(x, y); else c.moveTo(x, y); } c.stroke(); });
      c.setLineDash([]);
      for (var j = 0; j < 7; j++) {
        var n = Math.floor(t * .8 + j * .37), p = md(t * .8 + j * .37, 1), u = md(Math.sin(n * 12.9898 + j * 78.233) * 43758.5453, 1), v = md(Math.sin(n * 39.346 + j * 11.135) * 24634.634, 1);
        var gx = xl + (xr - xl) * (.1 + .8 * u), gy = y0 + (y1 - y0) * (.12 + .76 * v), s = Math.sin(Math.PI * p);
        halo(c, gx, gy, 4 * k * s, gold, .55 * s);
      }
      c.beginPath();
      for (var i = 0; i <= 60; i++) { var u2 = i / 60, x = xl + (xr - xl) * u2, y = cy - E * Math.sin(Math.PI * u2) * amp; if (i) c.lineTo(x, y); else c.moveTo(x, y); }
      c.strokeStyle = C.warm; c.lineWidth = 1.8; c.stroke();
      c.fillStyle = C.accent; c.fillRect(W / 2 - 2 * k, cy - 14 * k, 4 * k, 28 * k);
    };
    // Accelerating structure: superconducting cells whose fields alternate while a bunch crosses in step.
    D.rf = function (c, C, W, H, t, k) {
      var n = 4, x0 = W * .08, x1 = W * .92, cw = (x1 - x0) / n, cy = H / 2, ry = H * .32, ph = TAU * t / 2;
      c.setLineDash([2 * k, 2.5 * k]); c.strokeStyle = stAlpha(C.ink2, .45); c.lineWidth = 1; seg(c, W * .02, cy, W * .98, cy); c.setLineDash([]);
      for (var i = 0; i < n; i++) {
        var x = x0 + (i + .5) * cw, f = Math.cos(ph + i * Math.PI);
        c.beginPath(); c.ellipse(x, cy, cw * .5, ry, 0, 0, TAU); c.fillStyle = stAlpha(C.accent, .12); c.fill(); c.strokeStyle = stAlpha(C.accent, .8); c.lineWidth = 1.4; c.stroke();
        if (Math.abs(f) > .08) arrowHead(c, x - f * cw * .3, cy - ry * .45, x + f * cw * .3, cy - ry * .45, stAlpha(C.warm, .25 + .7 * Math.abs(f)), 3.5 * k, 1.4);
      }
      var bx = x0 + cw * md(t + .5, n), bunch = Math.max(.3, Math.sin(Math.PI * bx / W));
      halo(c, bx, cy, 7 * k, C.gold || C.warm, .9 * bunch); disc(c, bx, cy, 2.4 * k, C.warm);
    };
    // Coplanar transmission line with a microwave packet travelling along the centre conductor.
    D.resonator = function (c, C, W, H, t, k) {
      var y = H / 2, x0 = W * .05, x1 = W * .95, gap = 6 * k, px = x0 + (x1 - x0) * md(t / 3.5, 1);
      c.fillStyle = stAlpha(C.muted, .25); c.fillRect(x0, H * .14, x1 - x0, y - gap - H * .14); c.fillRect(x0, y + gap, x1 - x0, H * .86 - y - gap);
      c.fillStyle = stAlpha(C.accent, .8); c.fillRect(x0, y - 2.5 * k, x1 - x0, 5 * k);
      c.beginPath();
      for (var i = 0; i <= 100; i++) { var x = x0 + (x1 - x0) * i / 100, env = Math.exp(-Math.pow((x - px) / (13 * k), 2)), yy = y - 15 * k * env * Math.sin((x - px) / (2.6 * k)); if (i) c.lineTo(x, yy); else c.moveTo(x, yy); }
      c.strokeStyle = C.warm; c.lineWidth = 1.6; c.stroke();
      halo(c, px, y, 8 * k, C.gold || C.warm, .5);
    };
    // Superconducting magnet: current circulates in the windings and field lines thread the bore.
    D.coil = function (c, C, W, H, t, k) {
      var cx = W / 2, cy = H / 2, n = 6, sp = W * .085, rx = 4.5 * k, ry = H * .27, x0 = cx - sp * (n - 1) / 2, f = .45 + .35 * Math.sin(TAU * t / 3);
      c.strokeStyle = stAlpha(C.warm, f); c.lineWidth = 1.2;
      [[.47, .43], [.43, .34]].forEach(function (e, i) {
        c.beginPath(); c.ellipse(cx, cy, W * e[0], H * e[1], 0, 0, TAU); c.stroke();
        arrowHead(c, cx + 3 * k, cy - H * e[1], cx - 3 * k, cy - H * e[1], stAlpha(C.warm, f), 3.2 * k, 1.2);
        arrowHead(c, cx + 3 * k, cy + H * e[1], cx - 3 * k, cy + H * e[1], stAlpha(C.warm, f), 3.2 * k, 1.2);
      });
      c.strokeStyle = stAlpha(C.accent, .35); c.lineWidth = 1.3;
      for (var i = 0; i < n; i++) { c.beginPath(); c.ellipse(x0 + i * sp, cy, rx, ry, 0, Math.PI / 2, Math.PI * 1.5); c.stroke(); }
      arrowHead(c, W * .14, cy, W * .86, cy, C.warm, 4.5 * k, 1.8);
      for (i = 0; i < n; i++) {
        var x = x0 + i * sp, a = -Math.PI / 2 + md(t * 1.1 + i * .3, 1) * Math.PI;
        c.beginPath(); c.ellipse(x, cy, rx, ry, 0, -Math.PI / 2, Math.PI / 2); c.strokeStyle = C.accent; c.lineWidth = 2.2; c.stroke();
        disc(c, x + rx * Math.cos(a), cy + ry * Math.sin(a), 1.9 * k, C.gold || C.warm);
      }
    };
    // Superconducting cable: current flows along the conductor and rings of field surround it.
    D.cable = function (c, C, W, H, t, k) {
      var y = H / 2, x0 = W * .08, x1 = W * .9, r = 9 * k, loops = [.25, .5, .75];
      function loop(u, i, front) {
        var x = x0 + (x1 - x0) * u, p = .35 + .4 * (1 + Math.sin(TAU * t / 3 - i * 1.4)) / 2;
        c.beginPath(); c.ellipse(x, y, 5 * k, r * 2.5, 0, front ? -Math.PI / 2 : Math.PI / 2, front ? Math.PI / 2 : Math.PI * 1.5); c.strokeStyle = stAlpha(C.warm, front ? p : p * .5); c.lineWidth = 1.4; c.stroke();
        if (front) arrowHead(c, x + 5 * k * Math.cos(.35), y + r * 2.5 * Math.sin(.35), x + 5 * k * Math.cos(.6), y + r * 2.5 * Math.sin(.6), stAlpha(C.warm, p), 3 * k, 1.3);
      }
      loops.forEach(function (u, i) { loop(u, i, false); });
      c.fillStyle = stAlpha(C.accent, .2); c.fillRect(x0, y - r, x1 - x0, 2 * r);
      c.strokeStyle = C.accent; c.lineWidth = 1.3; seg(c, x0, y - r, x1, y - r); seg(c, x0, y + r, x1, y + r);
      c.beginPath(); c.ellipse(x1, y, 4 * k, r, 0, 0, TAU); c.fillStyle = C.surface; c.fill(); c.stroke();
      for (var s = 0; s < 3; s++) {
        c.beginPath();
        for (var i = 0; i <= 40; i++) { var x = x0 + (x1 - x0) * i / 40, yy = y + r * .62 * Math.sin((x - x0) / (9 * k) + s * 2.1); if (i) c.lineTo(x, yy); else c.moveTo(x, yy); }
        c.strokeStyle = stAlpha(C.accent, .55); c.lineWidth = 1; c.stroke();
      }
      for (var j = 0; j < 5; j++) { var cxp = x0 + (x1 - x0) * md(j / 5 + t * .2, 1); disc(c, cxp, y + r * .62 * Math.sin((cxp - x0) / (9 * k) + j * 2.1), 1.8 * k, C.gold || C.warm); }
      loops.forEach(function (u, i) { loop(u, i, true); });
    };
    // Flux through a superconducting ring and an illustrative response repeating with each flux quantum.
    D.ring = function (c, C, W, H, t, k) {
      var cx = W * .27, cy = H * .5, R = Math.min(W * .17, H * .28), phi = md(t / 8, 1) * 3, frac = phi - Math.round(phi), dir = frac >= 0 ? 1 : -1, gold = C.gold || C.warm;
      c.beginPath(); c.arc(cx, cy, R, 0, TAU); c.strokeStyle = stAlpha(C.accent, .3); c.lineWidth = 8 * k; c.stroke();
      c.beginPath(); c.arc(cx, cy, R, 0, TAU); c.strokeStyle = C.accent; c.lineWidth = 1.3; c.stroke();
      halo(c, cx, cy, R * .7, gold, .25 + .5 * Math.abs(frac));
      c.beginPath(); c.arc(cx, cy, 3.5 * k, 0, TAU); c.strokeStyle = C.warm; c.lineWidth = 1.3; c.stroke(); disc(c, cx, cy, 1.4 * k, C.warm);
      if (Math.abs(frac) > .04) for (var i = 0; i < 2; i++) { var a = i * Math.PI + t; arrowHead(c, cx + Math.cos(a) * R, cy + Math.sin(a) * R, cx + Math.cos(a + dir * .5) * R, cy + Math.sin(a + dir * .5) * R, C.surface, 3.4 * k, 1.4); }
      var px0 = W * .54, px1 = W * .94, py = H * .74, A = H * .4;
      c.strokeStyle = stAlpha(C.ink2, .5); c.lineWidth = 1; seg(c, px0, py, px1, py);
      c.beginPath();
      for (var j = 0; j <= 90; j++) { var p = 3 * j / 90, d = p - Math.round(p), y = py - A * (.3 + .7 * (1 - 4 * d * d)); if (j) c.lineTo(px0 + (px1 - px0) * j / 90, y); else c.moveTo(px0, y); }
      c.strokeStyle = C.accent; c.lineWidth = 1.5; c.stroke();
      var mx = px0 + (px1 - px0) * phi / 3, my = py - A * (.3 + .7 * (1 - 4 * frac * frac));
      halo(c, mx, my, 5 * k, C.warm, .7); disc(c, mx, my, 2.2 * k, C.warm);
    };
    // Ultracold atoms in the wells of an optical lattice; two spin states in two colours, some hopping.
    D.coldatoms = function (c, C, W, H, t, k) {
      var x0 = W * .04, x1 = W * .96, base = H * .76, A = H * .3, n = 5, wl = (x1 - x0) / n;
      function V(x) { return base - A * (1 + Math.cos(TAU * (x - x0) / wl)) / 2; }
      c.beginPath(); c.moveTo(x0, H * .94);
      for (var i = 0; i <= 100; i++) { var x = x0 + (x1 - x0) * i / 100; c.lineTo(x, V(x)); }
      c.lineTo(x1, H * .94); c.closePath(); c.fillStyle = stAlpha(C.accent, .1); c.fill();
      c.beginPath();
      for (i = 0; i <= 100; i++) { x = x0 + (x1 - x0) * i / 100; if (i) c.lineTo(x, V(x)); else c.moveTo(x, V(x)); }
      c.strokeStyle = stAlpha(C.accent, .7); c.lineWidth = 1.4; c.stroke();
      for (var w = 0; w < n; w++) {
        var wx = x0 + (w + .5) * wl, wy = V(wx) - 3.5 * k, pair = w % 2 === 0;
        if (pair) halo(c, wx, wy - 1 * k, 7 * k, C.gold || C.warm, .45 + .25 * Math.sin(t * 2 + w));
        disc(c, wx - (pair ? 3 * k : 0), wy + 1.2 * k * Math.sin(t * 3 + w), 2.6 * k, C.accent);
        if (pair) disc(c, wx + 3 * k, wy + 1.2 * k * Math.sin(t * 3 + w + 1), 2.6 * k, C.warm);
      }
      var hp = md(t / 2.5, 1), hw = Math.floor(md(t / 2.5, n * 2) / 2) % (n - 1), hx = x0 + (hw + .5 + hp) * wl, hy = V(hx) - 3.5 * k;
      disc(c, hx, hy, 2.6 * k, (hw % 2) ? C.accent : C.warm);
    };
    // Field (warm) decays over the penetration depth while the pair amplitude (blue) recovers over the coherence length.
    D.penetration = function (c, C, W, H, t, k) {
      var xb = W * .36, x0 = W * .06, x1 = W * .94, y0 = H * .84, top = H * .14, s = Math.sin(TAU * t / 6), lam = (15 + 4 * s) * k, xi = (8 - 2.5 * s) * k, hgt = (y0 - top) * .82;
      c.fillStyle = stAlpha(C.accent, .14); c.fillRect(xb, top - 4 * k, x1 - xb, y0 - top + 4 * k);
      for (var i = 0; i < 9; i++) {
        var fx = x0 + i * 4.5 * k + md(t * 6 * k, 4.5 * k); if (fx > xb + lam * 2.5) break;
        var B = fx < xb ? 1 : Math.exp(-(fx - xb) / lam);
        c.strokeStyle = stAlpha(C.warm, .15 + .25 * B); c.lineWidth = 1; seg(c, fx, top, fx, y0);
      }
      c.strokeStyle = stAlpha(C.ink2, .5); c.lineWidth = 1; seg(c, x0, y0, x1, y0); seg(c, xb, top - 4 * k, xb, y0);
      [[C.warm, function (x) { return x < xb ? 1 : Math.exp(-(x - xb) / lam); }], [C.accent, function (x) { return x < xb ? 0 : Math.tanh((x - xb) / xi); }]].forEach(function (L) {
        c.beginPath();
        for (var j = 0; j <= 80; j++) { var x = x0 + (x1 - x0) * j / 80, y = y0 - hgt * L[1](x); if (j) c.lineTo(x, y); else c.moveTo(x, y); }
        c.strokeStyle = L[0]; c.lineWidth = 1.8; c.stroke();
      });
    };
    // Thin film on a substrate in perspective; the interface glows and carriers move along it.
    D.interface = function (c, C, W, H, t, k) {
      var x0 = W * .1, x1 = W * .72, dx = W * .16, dy = H * .17, ys = H * .56, fh = 10 * k, sh = H * .24, g = .5 + .5 * Math.sin(TAU * t / 3);
      function quad(p, fill) { c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(p[2], p[3]); c.lineTo(p[4], p[5]); c.lineTo(p[6], p[7]); c.closePath(); c.fillStyle = fill; c.fill(); }
      quad([x0, ys, x1, ys, x1, ys + sh, x0, ys + sh], stAlpha(C.muted, .3));
      quad([x1, ys, x1 + dx, ys - dy, x1 + dx, ys - dy + sh, x1, ys + sh], stAlpha(C.muted, .45));
      quad([x0, ys - fh, x1, ys - fh, x1, ys, x0, ys], stAlpha(C.accent, .5));
      quad([x1, ys - fh, x1 + dx, ys - fh - dy, x1 + dx, ys - dy, x1, ys], stAlpha(C.accent, .65));
      quad([x0, ys - fh, x1, ys - fh, x1 + dx, ys - fh - dy, x0 + dx, ys - fh - dy], stAlpha(C.accent, .22));
      c.strokeStyle = stAlpha(C.warm, .45 + .5 * g); c.lineWidth = 2; seg(c, x0, ys, x1, ys); seg(c, x1, ys, x1 + dx, ys - dy);
      for (var i = 0; i < 6; i++) { var u = md(i / 6 + t * .12, 1), x = x0 + (x1 - x0) * u; halo(c, x, ys, 4 * k, C.warm, .5); disc(c, x, ys, 1.6 * k, C.gold || C.warm); }
      c.strokeStyle = stAlpha(C.ink2, .25); c.lineWidth = 1;
      for (var j = 1; j < 4; j++) seg(c, x0, ys + sh * j / 4, x1, ys + sh * j / 4);
    };
    // Proximity effect: pairs from a superconductor (left) leak into a neighbour where the pair amplitude decays.
    D.proximity = function (c, C, W, H, t, k) {
      var xb = W * .44, x0 = W * .06, x1 = W * .94, y0 = H * .84, top = H * .16, L = 16 * k;
      function f(x) { return x < xb ? 1 : Math.exp(-(x - xb) / L); }
      c.fillStyle = stAlpha(C.accent, .2); c.fillRect(x0, top, xb - x0, y0 - top);
      c.fillStyle = stAlpha(C.muted, .18); c.fillRect(xb, top, x1 - xb, y0 - top);
      c.strokeStyle = stAlpha(C.ink2, .5); c.lineWidth = 1; seg(c, xb, top, xb, y0);
      c.beginPath();
      for (var i = 0; i <= 80; i++) { var x = x0 + (x1 - x0) * i / 80, y = y0 - (y0 - top) * .55 * f(x) - 4 * k; if (i) c.lineTo(x, y); else c.moveTo(x, y); }
      c.strokeStyle = C.accent; c.lineWidth = 1.7; c.stroke();
      for (var j = 0; j < 5; j++) {
        var px = x0 + 4 * k + (x1 - x0) * .9 * md(j / 5 + t * .09, 1), a = f(px), py = top + (y0 - top) * (.16 + .1 * j);
        if (a < .06) continue;
        c.strokeStyle = stAlpha(C.ink2, .6 * a); seg(c, px - 3 * k, py, px + 3 * k, py);
        disc(c, px - 3 * k, py, 2 * k, stAlpha(C.accent, a)); disc(c, px + 3 * k, py, 2 * k, stAlpha(C.warm, a));
      }
    };
    // A single atomic sheet in perspective; a soft wave crosses it.
    D.monolayer = function (c, C, W, H, t, k) {
      var cx = W / 2, cy = H * .52, w = W * .34, d = H * .3, tl = 1 + .08 * Math.sin(TAU * t / 6), wave = md(t / 3, 1) * 2.6 - 1.3;
      function P(u, v) { return [cx + (u * .82 + v * .42) * w, cy + (v * .62 * tl - u * .12) * d]; }
      var p = [P(-1, -1), P(1, -1), P(1, 1), P(-1, 1)];
      c.beginPath(); c.moveTo(p[0][0], p[0][1]); for (var i = 1; i < 4; i++) c.lineTo(p[i][0], p[i][1]); c.closePath();
      c.fillStyle = stAlpha(C.accent, .14); c.fill(); c.strokeStyle = stAlpha(C.accent, .7); c.lineWidth = 1.2; c.stroke();
      for (var a = 0; a < 6; a++) for (var b = 0; b < 5; b++) {
        var u = -1 + (a + (b % 2) * .5 + .25) * 2 / 6.5, v = -1 + (b + .5) * 2 / 5, q = P(u, v), near = Math.max(0, 1 - Math.abs(u + v * .4 - wave) / .32);
        if (near > .05) halo(c, q[0], q[1], 5 * k, C.gold || C.warm, .55 * near);
        disc(c, q[0], q[1], 2.2 * k, near > .5 ? C.warm : C.accent);
      }
    };
    // Heat flows along a sample from a hot (warm) end to a cold (blue) end.
    D.thermal = function (c, C, W, H, t, k) {
      var x0 = W * .1, x1 = W * .9, y = H * .56, h = 18 * k, n = 16, sw = (x1 - x0) / n;
      for (var i = 0; i < n; i++) { var u = i / (n - 1); c.fillStyle = stAlpha(C.warm, .75 * (1 - u)); c.fillRect(x0 + i * sw, y - h / 2, sw + .6, h); c.fillStyle = stAlpha(C.accent, .75 * u); c.fillRect(x0 + i * sw, y - h / 2, sw + .6, h); }
      c.strokeStyle = stAlpha(C.ink2, .5); c.lineWidth = 1; c.strokeRect(x0, y - h / 2, x1 - x0, h);
      for (var j = 0; j < 7; j++) { var p = md(j / 7 + t * .16, 1), x = x0 + (x1 - x0) * p; disc(c, x, y + h * .28 * Math.sin(t * 4 + j * 1.9), (2.6 - 1.2 * p) * k, stAlpha(C.surface, .85)); }
      for (var a = 0; a < 3; a++) { var s = md(t / 2 + a / 3, 1); arrowHead(c, W * (.22 + .2 * a), H * .2, W * (.36 + .2 * a), H * .2, stAlpha(C.ink2, .3 + .5 * Math.sin(Math.PI * s)), 3.8 * k, 1.5); }
    };
    // Neutral timeline: milestone flags rise in turn; positions carry no dates or values.
    D.timeline = function (c, C, W, H, t, k) {
      var x0 = W * .1, x1 = W * .9, y = H * .74, n = 5, p = md(t / 7 + .5, 1) * 1.2;
      arrowHead(c, x0, y, x1 + 2 * k, y, stAlpha(C.ink2, .6), 4 * k, 1.4);
      for (var i = 0; i < n; i++) {
        var u = (i + .5) / n, x = x0 + (x1 - x0) * u, on = Math.max(0, Math.min(1, (p - u) * 5)), hgt = (18 + 7 * (i % 3)) * k * on;
        if (on > 0) {
          c.strokeStyle = stAlpha(C.ink2, .7); c.lineWidth = 1.2; seg(c, x, y, x, y - hgt);
          c.beginPath(); c.moveTo(x, y - hgt); c.lineTo(x + 9 * k * on, y - hgt + 3.5 * k); c.lineTo(x, y - hgt + 7 * k); c.closePath(); c.fillStyle = i % 2 ? C.warm : C.accent; c.fill();
          if (on < 1) halo(c, x, y, 7 * k, C.gold || C.warm, 1 - on);
        }
        disc(c, x, y, 2.4 * k, on > 0 ? C.ink2 : stAlpha(C.muted, .7));
      }
    };
    // A magnetic material (spins, warm) beside a superconducting region (blue) where pairs move.
    D.magnetism = function (c, C, W, H, t, k) {
      var xb = W * .5, top = H * .14, bot = H * .86;
      c.fillStyle = stAlpha(C.warm, .1); c.fillRect(W * .05, top, xb - W * .05, bot - top);
      c.fillStyle = stAlpha(C.accent, .18); c.fillRect(xb, top, W * .45, bot - top);
      c.strokeStyle = stAlpha(C.ink2, .5); c.lineWidth = 1; seg(c, xb, top, xb, bot);
      for (var i = 0; i < 3; i++) for (var j = 0; j < 3; j++) spinAt(c, W * (.13 + i * .13), top + (bot - top) * (.2 + j * .3), -Math.PI / 2 + .8 * Math.sin(t * .8 + i * .9 + j * .5), 12 * k, C.warm);
      for (var p = 0; p < 4; p++) {
        var px = xb + 8 * k + (W * .45 - 16 * k) * md(p / 4 + t * .08, 1), py = top + (bot - top) * (.22 + .19 * p);
        c.strokeStyle = stAlpha(C.ink2, .6); seg(c, px - 3 * k, py, px + 3 * k, py);
        disc(c, px - 3 * k, py, 2 * k, C.accent); disc(c, px + 3 * k, py, 2 * k, C.warm);
      }
    };
    // Schematic phase diagram: two transition lines cross, giving regions for each order and one with both.
    D.competition = function (c, C, W, H, t, k) {
      var x0 = W * .12, x1 = W * .92, y0 = H * .86, y1 = H * .1, h = y0 - y1;
      var A0 = y0 - h * .82, A1 = y0 - h * .12, B0 = y0 - h * .12, B1 = y0 - h * .82, xc = (x0 + x1) / 2, yc = (A0 + A1) / 2;
      function tri(pts, fill) { c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (var i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]); c.closePath(); c.fillStyle = fill; c.fill(); }
      tri([[x0, A0], [xc, yc], [x0, B0]], stAlpha(C.accent, .22));
      tri([[x1, B1], [xc, yc], [x1, A1]], stAlpha(C.warm, .22));
      tri([[x0, B0], [xc, yc], [x1, A1], [x1, y0], [x0, y0]], stAlpha(C.accent, .16));
      tri([[x0, B0], [xc, yc], [x1, A1], [x1, y0], [x0, y0]], stAlpha(C.warm, .14));
      c.lineWidth = 1.8; c.strokeStyle = C.accent; seg(c, x0, A0, x1, A1); c.strokeStyle = C.warm; seg(c, x0, B0, x1, B1);
      arrowHead(c, x0, y0, x1 + 3 * k, y0, stAlpha(C.ink2, .6), 3.5 * k, 1.2); arrowHead(c, x0, y0, x0, y1 - 3 * k, stAlpha(C.ink2, .6), 3.5 * k, 1.2);
      halo(c, xc, yc, 7 * k, C.gold || C.warm, .5 + .4 * Math.sin(TAU * t / 2));
      var a = TAU * t / 7, mx = xc + Math.cos(a) * (x1 - x0) * .3, my = yc + Math.sin(a) * h * .3;
      disc(c, mx, my, 3 * k, C.surface); c.beginPath(); c.arc(mx, my, 3 * k, 0, TAU); c.strokeStyle = C.ink2; c.lineWidth = 1.3; c.stroke();
    };
    // Magnetic molecules on a superconducting surface; glows mark possible in-gap bound states.
    D.molecule = function (c, C, W, H, t, k) {
      var sy = H * .68, r = 7 * k, xs = [.28, .5, .72], gold = C.gold || C.warm;
      c.fillStyle = stAlpha(C.accent, .22); c.fillRect(W * .04, sy, W * .92, H * .26);
      c.strokeStyle = stAlpha(C.accent, .7); c.lineWidth = 1.2; seg(c, W * .04, sy, W * .96, sy);
      for (var i = 0; i < 12; i++) disc(c, W * (.08 + i * .076), sy + 7 * k, 1.4 * k, stAlpha(C.accent, .6));
      xs.forEach(function (u, i) { halo(c, W * u, sy + 2 * k, 11 * k, gold, .35 + .3 * Math.sin(TAU * t / 2.4 + i * 1.3)); });
      c.strokeStyle = stAlpha(C.ink2, .6); c.lineWidth = 1.4; seg(c, W * xs[0] + r, sy - 12 * k, W * xs[2] - r, sy - 12 * k);
      xs.forEach(function (u, i) {
        var x = W * u, y = sy - 12 * k;
        c.beginPath(); for (var m = 0; m < 6; m++) { var a = Math.PI / 6 + m * Math.PI / 3; if (m) c.lineTo(x + r * Math.cos(a), y + r * Math.sin(a)); else c.moveTo(x + r * Math.cos(a), y + r * Math.sin(a)); }
        c.closePath(); c.fillStyle = C.surface; c.fill(); c.strokeStyle = C.ink2; c.lineWidth = 1.3; c.stroke();
        spinAt(c, x, y - 15 * k, -Math.PI / 2 + .5 * Math.sin(t * 1.3 + i * 2), 13 * k, C.warm);
      });
    };
    // Neutral animated source icon: a page and a magnifier, no crystal, trace or discovery claim.
    D.research = function (c, C, W, H, t, k) {
      var x = W * .27, y = H * .12, w = W * .42, h = H * .76, f = 9 * k, lines = [.3, .44, .56, .68, .8];
      c.beginPath(); c.moveTo(x, y); c.lineTo(x + w - f, y); c.lineTo(x + w, y + f); c.lineTo(x + w, y + h); c.lineTo(x, y + h); c.closePath();
      c.fillStyle = C.surface; c.fill(); c.strokeStyle = stAlpha(C.ink2, .55); c.lineWidth = 1.2; c.stroke();
      c.beginPath(); c.moveTo(x + w - f, y); c.lineTo(x + w - f, y + f); c.lineTo(x + w, y + f); c.closePath(); c.fillStyle = stAlpha(C.muted, .35); c.fill();
      c.fillStyle = stAlpha(C.accent, .75); c.fillRect(x + 6 * k, y + h * .12, w * .5, 3.5 * k);
      var mx = x + w * (.52 + .3 * Math.sin(TAU * t / 6)), my = y + h * (.56 + .16 * Math.cos(TAU * t / 6));
      lines.forEach(function (u, i) {
        var ly = y + h * u, near = Math.max(0, 1 - Math.abs(ly - my) / (9 * k));
        c.strokeStyle = near > .1 ? stAlpha(C.warm, .5 + .5 * near) : stAlpha(C.ink2, .35); c.lineWidth = 1.5;
        seg(c, x + 6 * k, ly, x + w - (i === lines.length - 1 ? 16 : 6) * k, ly);
      });
      c.beginPath(); c.arc(mx, my, 8.5 * k, 0, TAU); c.fillStyle = stAlpha(C.accent, .12); c.fill(); c.strokeStyle = C.accent; c.lineWidth = 1.8; c.stroke();
      c.lineWidth = 2.6; seg(c, mx + 6.2 * k, my + 6.2 * k, mx + 12 * k, my + 12 * k);
    };
    var ALT = {
      cuprate: 'Idealised CuO₂-plane fragment: a square copper net with oxygen at link midpoints. Only the viewing angle changes; this is not a complete crystal or measured motion.',
      nickelate: 'Idealised section of a bilayer nickelate, with Ni–O–Ni bridges. The view moves; no pairing mechanism or measured atomic motion is implied.',
      iron: 'Idealised iron-plane square net. The viewing angle changes; no ligand, magnetic order or pairing mechanism is specified.',
      hydride: 'Hydride chemical building blocks: hydrogen and a metal, shown unbonded. Positions do not reconstruct a crystal or imply a hydrogen cage or pressure.',
      pressure: 'Qualitative diamond-anvil pressure apparatus with a sample between the tips. No crystal topology, pressure value or measured transition is depicted.',
      moire: 'Two atomic lattices twisted by a small angle, forming a slowly changing moiré pattern.',
      kagome: 'Idealised kagome plane with corner-sharing triangles and hexagonal holes. The view rotates; no charge-density wave or measured motion is implied.',
      heavy: 'Qualitative heavy-electron dressing cartoon with local moments. Not particle trajectories or a claim about the article’s pairing state.',
      triplet: 'Illustration of one proposed triplet-pairing component: parallel spins with an odd-parity orbital. This does not establish triplet pairing in the article’s material.',
      topo: 'Qualitative boundary/channel motif for a topological candidate. This is not evidence of a Majorana mode or a reconstructed device.',
      eph: 'Classical electron–lattice coupling cartoon. Ionic response is exaggerated; this is not a Cooper-pair trajectory or a measured vibration.',
      vortex: 'A triangular lattice of swirling magnetic-flux vortices.',
      ai: 'A crystal structure feeds a small neural network whose layers light up in turn.',
      qubit: 'A cross-shaped superconducting qubit beside a Bloch circle whose arrow swings back and forth.',
      general: 'A magnet floating above a cold superconductor, the Meissner effect.',
      layered: 'Layered-material schematic with four illustrative sheets. The sheet count and spacing are not the article’s measured structure; no twist is implied.',
      'layered-six': 'Six graphene layers, matching the layer count named in the article. Spacing and viewing angle are schematic; no twist, atomic stacking registry or measured motion is implied.',
      stripes: 'Qualitative lattice-model/stripe-analysis motif. Site shading illustrates a possible modulation, not a measured density, established ground state or electron motion.',
      literature: 'Literature-processing schematic: papers are read into structured records. No crystal structure or experimental discovery is implied.',
      features: 'Illustrative clusters and links in a learned feature space. These points are not actual embeddings or measured material data.',
      graph: 'Message passing on an illustrative graph. Node positions are not crystallographic coordinates and moving markers represent computation.',
      search: 'Candidate-search schematic: alternative proposals are examined in turn. The symbols are not generated or synthesized crystal structures.',
      measurement: 'Illustrative sample contacts and measurement meter. No measured trace, transition temperature or successful result is shown.',
      spectrum: 'Qualitative spectroscopy/response-analysis schematic. The curve is illustrative, not measured or digitised article data.',
      light: 'Qualitative incident electromagnetic wave and sample. No wavelength, timescale or measured sample response is specified.',
      junction: 'Qualitative weak-link schematic between two electrodes. The moving marker is illustrative, not a literal pair trajectory.',
      interval: 'Illustrative prediction intervals around model estimates. Their lengths are not the paper’s numerical intervals or a coverage measurement.',
      routing: 'Model-routing schematic: an input follows one of two model branches. This is not an accuracy or mechanism claim.',
      'two-stage': 'Two-stage prediction schematic: an SC catalog-label score and a conditional Tc estimate. The score is not a universally calibrated probability.',
      tree: 'Illustrative decision-tree branches used in a boosted-tree model. Not a neural network or a rendering of the fitted tree.',
      research: 'An animated research-paper icon with a magnifier. No material structure, measurement or superconducting discovery is asserted.',
      detector: 'Particle-detector schematic: an absorber with superconducting sensors on top; an incoming particle deposits energy and the spreading signal reaches the sensors. No detector geometry, signal size or sensitivity from the article is shown.',
      diode: 'Superconducting-diode schematic: current flows without loss one way (blue) but turns dissipative at a lower current the other way (warm); the bars compare the two critical currents. Directions and sizes are illustrative, not measured.',
      spinfluct: 'Square lattice of antiferromagnetically correlated spins whose tilts ripple across the plane, a cartoon of spin fluctuations or spin waves. No measured spectrum, correlation length or pairing mechanism is shown.',
      multigap: 'Fermi pockets ringed by superconducting gaps of different size (band thickness); colours only distinguish the pockets. Shapes and sizes are illustrative; no measured gap map, node or sign structure is asserted.',
      zeeman: 'Zeeman-split Fermi circles: a magnetic field (arrow) separates spin-up (warm) and spin-down (blue) electrons, and a dashed pair joins opposite momenta across the split. Field and splitting are illustrative, not the article’s values.',
      gapdos: 'Tunnelling-style density of states with a gap and two coherence peaks; the dot sweeps the bias. A textbook shape, not the article’s measured spectrum; no nodal or nodeless gap is implied.',
      fflo: 'Pair amplitude modulated in space (pair-density-wave or FFLO type), with pairs drifting to suggest finite momentum. Period, amplitude and motion are illustrative, not measured.',
      trsb: 'Broken time-reversal symmetry cartoon: one circulation sense is chosen over its time-reversed partner (faint, dashed), with weak spontaneous fields (arrows). Not the article’s pairing state or measured field.',
      kekule: 'Honeycomb lattice with a Kekulé bond pattern: every third hexagon carries the strong bonds, tripling the unit cell. It illustrates the proposed lattice-scale modulation, not a calculated pair amplitude.',
      cavity: 'Optical-cavity schematic: two mirrors hold a standing electromagnetic mode around a thin sample; flickering dots suggest vacuum fluctuations. No pump light, resonator design or measured Tc change is depicted.',
      rf: 'Superconducting accelerating cavity: the field in neighbouring cells alternates while a particle bunch crosses in step. Cell count, fields and timing are illustrative, not the article’s design or gradient.',
      resonator: 'Superconducting transmission line (centre conductor between ground planes) carrying a microwave packet. Wavelength, packet shape and speed are illustrative, not measured.',
      coil: 'Superconducting-magnet schematic: current circulates in the windings and field lines pass through the bore and return outside. Winding count and field lines are illustrative, not the article’s magnet design or field.',
      cable: 'Superconducting-cable schematic: current flows along twisted strands and rings of magnetic field surround the conductor. Strand count, current and field are illustrative, not design values.',
      ring: 'Superconducting ring threaded by magnetic flux, beside an illustrative response that repeats with each flux quantum. The curve is schematic, not the article’s measured oscillation.',
      coldatoms: 'Ultracold atoms in the wells of an optical lattice, two spin states in two colours, one atom hopping. Positions and pairing are illustrative, not the article’s images or data.',
      penetration: 'Superconductor boundary: the magnetic field (warm) decays over the penetration depth while the pair amplitude (blue) recovers over the coherence length. Lengths are illustrative, not computed or measured values.',
      interface: 'Thin film on a substrate with the interface highlighted; moving dots suggest carriers in the interface layer. Thicknesses, materials and motion are illustrative, not the article’s structure.',
      proximity: 'Proximity-effect schematic: pairs from a superconductor (left) leak into a neighbouring material, where the pair amplitude decays. The decay length and motion are illustrative.',
      monolayer: 'A single atomic sheet seen in perspective, with a soft wave crossing it. The lattice pattern and tilt are illustrative; no specific crystal or measured property is shown.',
      thermal: 'Heat flowing along a sample from a hot end (warm) to a cold end (blue). Gradient and flow are illustrative, not measured transport data.',
      timeline: 'Neutral timeline: milestone flags rise in turn. Positions and heights carry no dates, values or ranking.',
      magnetism: 'A magnetic material (spins, warm) beside a superconducting region (blue) carrying pairs. The spin arrangement is illustrative, not the article’s magnetic order.',
      competition: 'Schematic phase diagram: two transition lines cross, giving a region for each order and one where both coexist; the ring wanders through them. Axes and lines are illustrative, not a measured phase diagram.',
      molecule: 'Magnetic molecules on a superconducting surface, each with a spin; glows beneath them mark possible in-gap bound states. Counts, spins and glows are illustrative, not measured spectra.'
    };
    Object.keys(D).forEach(function (kind) {
      MINI_DRAW['news-' + kind] = guard(D[kind]);
      MINI_STATIC['news-' + kind] = 1.2;
      MINI_ALT['news-' + kind] = ALT[kind];
    });
  })();

  // Available legacy illustrations. Automatic selection is conservative in newsArt().
  NEWS_ART = [['Hydrides', 'hydride'], ['Cuprates', 'cuprate'], ['Nickelates', 'nickelate'], ['Iron-based', 'iron'],
    ['Moiré and 2D', 'moire'], ['Kagome', 'kagome'], ['Heavy fermions', 'heavy'], ['Triplet and ruthenates', 'triplet'],
    ['Topological', 'topo'], ['Electron–phonon', 'eph'], ['Vortices and junctions', 'vortex'], ['AI and data', 'ai']];

};
