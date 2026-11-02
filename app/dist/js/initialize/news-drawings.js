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
    // Neutral animated source icon: no crystal, experimental trace or discovery claim.
    D.research = function (c, C, W, H, t, k) {
      var x = W * .24, y = H * .18, width = W * .52, height = H * .64;
      c.fillStyle = C.surface; c.strokeStyle = C.axis; c.lineWidth = 1.2;
      c.beginPath(); c.rect(x, y, width, height); c.fill(); c.stroke();
      for (var i = 0; i < 4; i++) { c.strokeStyle = stAlpha(C.accent, .35 + .35 * (1 + Math.sin(t * 1.4 - i)) / 2); c.lineWidth = i ? 1.5 : 2.5; seg(c, x + 8 * k, y + (12 + i * 10) * k, x + width - (i === 3 ? 20 : 8) * k, y + (12 + i * 10) * k); }
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
      research: 'An animated research-paper icon. No material structure, measurement or superconducting discovery is asserted.',
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
      tree: 'Illustrative decision-tree branches used in a boosted-tree model. Not a neural network or a rendering of the fitted tree.'
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
