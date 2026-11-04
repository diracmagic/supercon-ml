'use strict';
// news-looks: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconNewsLooks = function initializeSuperconNewsLooks() {


  /* ---------- news thumbnails: further subject schematics, then one look per article ----------
     A look adds a badge for a method named in the article, element dots for a formula in its
     headline and a thermometer for a temperature in its headline. Colour set, mirroring and
     close-up framing are neutral variants that keep thumbnails of the same theme distinct. */
  (function () {
    var TAU = Math.PI * 2;
    function md(t, p) { t = t % p; return t < 0 ? t + p : t; }
    function seg(c, x0, y0, x1, y1) { c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y1); c.stroke(); }
    function disc(c, x, y, r, fill) { c.beginPath(); c.arc(x, y, r, 0, TAU); c.fillStyle = fill; c.fill(); }
    function circ(c, x, y, r, color, lw) { c.beginPath(); c.arc(x, y, r, 0, TAU); c.strokeStyle = color; c.lineWidth = lw || 1; c.stroke(); }
    function halo(c, x, y, r, color, a) { for (var i = 3; i >= 1; i--) disc(c, x, y, r * i / 3, stAlpha(color, a * 0.28)); }
    function poly(c, pts, close) { c.beginPath(); pts.forEach(function (p, i) { if (i) c.lineTo(p[0], p[1]); else c.moveTo(p[0], p[1]); }); if (close) c.closePath(); }
    function arrow(c, x0, y0, x1, y1, color, hd, lw) {
      var a = Math.atan2(y1 - y0, x1 - x0);
      c.strokeStyle = color; c.fillStyle = color; c.lineWidth = lw || 1.3;
      c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1 - Math.cos(a) * hd * 0.8, y1 - Math.sin(a) * hd * 0.8); c.stroke();
      c.beginPath(); c.moveTo(x1, y1); c.lineTo(x1 - hd * Math.cos(a - 0.45), y1 - hd * Math.sin(a - 0.45));
      c.lineTo(x1 - hd * Math.cos(a + 0.45), y1 - hd * Math.sin(a + 0.45)); c.closePath(); c.fill();
    }
    function spin(c, x, y, ang, L, color) {
      var dx = Math.cos(ang) * L / 2, dy = Math.sin(ang) * L / 2;
      arrow(c, x - dx, y - dy, x + dx, y + dy, color, Math.max(2.4, L * 0.38), 1.2);
    }
    function axes(c, C, x0, y0, x1, y1, k) {
      arrow(c, x0, y0, x1, y0, stAlpha(C.ink2, .6), 3.5 * k, 1.2); arrow(c, x0, y0, x0, y1, stAlpha(C.ink2, .6), 3.5 * k, 1.2);
    }
    // A sinusoid drawn along a segment (light, scattered waves).
    function wave(c, x0, y0, x1, y1, n, amp, color, ph, lw) {
      var L = Math.max(1e-6, Math.sqrt((x1 - x0) * (x1 - x0) + (y1 - y0) * (y1 - y0))), ux = (x1 - x0) / L, uy = (y1 - y0) / L;
      c.beginPath();
      for (var i = 0; i <= 24; i++) {
        var s = i / 24, w = amp * Math.sin(TAU * n * s - ph), x = x0 + (x1 - x0) * s - uy * w, y = y0 + (y1 - y0) * s + ux * w;
        if (i) c.lineTo(x, y); else c.moveTo(x, y);
      }
      c.strokeStyle = color; c.lineWidth = lw || 1.2; c.stroke();
    }
    function pair(c, C, x, y, k, a) {
      c.strokeStyle = stAlpha(C.ink2, .5 * a); c.lineWidth = 1; seg(c, x - 3 * k, y, x + 3 * k, y);
      disc(c, x - 3 * k, y, 2 * k, stAlpha(C.accent, a)); disc(c, x + 3 * k, y, 2 * k, stAlpha(C.accent, a));
    }
    function guard(fn) {
      return function (c, C, W, H, t, info) {
        c.save(); c.lineCap = 'round'; c.lineJoin = 'round'; c.setLineDash([]); c.globalAlpha = 1;
        try { fn(c, C, W, H, t || 0, Math.min(W / 112, H / 84), info || null); } finally { c.restore(); }
      };
    }
    var D = {};
    // Zhang–Rice singlets: an oxygen hole around a copper binds to that copper's spin, on alternating plaquettes.
    D.zr = function (c, C, W, H, t, k) {
      var s = 19 * k, nx = Math.floor(W / s) + 1, ny = Math.floor(H / s) + 1, ox = (W - (nx - 1) * s) / 2, oy = (H - (ny - 1) * s) / 2, i, j, x, y;
      c.strokeStyle = stAlpha(C.muted, .22); c.lineWidth = 1;
      for (i = 0; i < nx; i++) seg(c, ox + i * s, 0, ox + i * s, H);
      for (j = 0; j < ny; j++) seg(c, 0, oy + j * s, W, oy + j * s);
      for (i = 0; i < nx; i++) for (j = 0; j < ny; j++) {
        x = ox + i * s; y = oy + j * s;
        var a = (i + j) % 2 === 0 && i > 0 && j > 0 && i < nx - 1 && j < ny - 1 ? Math.max(0, Math.sin(t * 1.1 - i * .9 - j * .7)) : 0;
        if (a > .02) {
          poly(c, [[x - s / 2, y], [x, y - s / 2], [x + s / 2, y], [x, y + s / 2]], true);
          c.fillStyle = stAlpha(C.warm, .3 * a); c.fill(); c.strokeStyle = stAlpha(C.warm, .85 * a); c.lineWidth = 1.3; c.stroke();
        }
        disc(c, x + s / 2, y, 1.5 * k, stAlpha(C.muted, .8)); disc(c, x, y + s / 2, 1.5 * k, stAlpha(C.muted, .8));
        var up = (i + j) % 2 === 0 ? -1 : 1;
        if (a > .5) {
          spin(c, x - 2.6 * k, y, -Math.PI / 2, 8 * k, C.accent); spin(c, x + 2.6 * k, y, Math.PI / 2, 8 * k * Math.min(1, (a - .5) * 3), C.warm);
        } else { disc(c, x, y, 1.8 * k, stAlpha(C.ink2, .6)); spin(c, x, y, up * Math.PI / 2, 7 * k, stAlpha(C.accent, .85)); }
      }
    };
    // Two orientation domains meet at a wandering wall where superconducting puddles glow.
    D.domains = function (c, C, W, H, t, k) {
      var g = 7 * k, wall = function (y) { return W * (.5 + .13 * Math.sin(y / H * 4.4 + t * .5) + .05 * Math.sin(y / H * 9 - t * .3)); };
      for (var x = g / 2; x < W; x += g) for (var y = g / 2; y < H; y += g) {
        var d = (x - wall(y)) / (9 * k), left = d < 0, near = Math.exp(-d * d), ang = (left ? 1 : -1) * Math.PI / 4 + near * .9 * Math.sin(t * 1.6 + y * .2), L = g * .36;
        c.strokeStyle = stAlpha(left ? C.accent : C.warm, .35 + .35 * (1 - near)); c.lineWidth = 1.2;
        seg(c, x - Math.cos(ang) * L, y - Math.sin(ang) * L, x + Math.cos(ang) * L, y + Math.sin(ang) * L);
      }
      c.beginPath();
      for (var yy = 0; yy <= H + 2 * k; yy += 2 * k) { if (yy) c.lineTo(wall(yy), yy); else c.moveTo(wall(yy), yy); }
      c.strokeStyle = stAlpha(C.ink2, .55); c.lineWidth = 1.6; c.stroke();
      for (var p = 0; p < 3; p++) { var py = H * md(p / 3 + t * .06, 1); halo(c, wall(py), py, 9 * k, C.gold || C.warm, .6); }
    };
    // Schematic superconducting dome; a named half-dome keeps the far side dashed.
    D.dome = function (c, C, W, H, t, k, info) {
      var x0 = W * .12, x1 = W * .9, y0 = H * .86, y1 = H * .1, w = x1 - x0, h = (y0 - y1) * .8, half = !!(info && /half[- ]dome/i.test(info.title || ''));
      var tc = function (u) { var q = (u - .5) / .34; return q * q < 1 ? 1 - q * q : 0; }, pts = [], i;
      for (i = 0; i <= 36; i++) { var u = .16 + .68 * i / 36; pts.push([x0 + w * u, y0 - h * tc(u)]); }
      poly(c, [[x0 + w * .16, y0]].concat(pts), true); c.fillStyle = stAlpha(C.accent, .2); c.fill();
      c.strokeStyle = C.accent; c.lineWidth = 1.8; poly(c, half ? pts.slice(0, 19) : pts); c.stroke();
      if (half) { c.setLineDash([3 * k, 3 * k]); c.strokeStyle = stAlpha(C.accent, .5); poly(c, pts.slice(18)); c.stroke(); c.setLineDash([]); }
      axes(c, C, x0, y0, x1 + 2 * k, y1, k);
      var v = .16 + (half ? .34 : .68) * (.5 - .5 * Math.cos(TAU * t / 7)), x = x0 + w * v, y = y0 - h * tc(v);
      c.strokeStyle = stAlpha(C.ink2, .45); c.lineWidth = 1; c.setLineDash([2 * k, 2 * k]); seg(c, x, y0, x, y); c.setLineDash([]);
      halo(c, x, y, 7 * k, C.warm, .5); disc(c, x, y, 2.8 * k, C.warm);
    };
    // Quasiparticle interference: waves scattered by two surface impurities overlap.
    D.qpi = function (c, C, W, H, t, k) {
      for (var x = 5 * k; x < W; x += 8 * k) for (var y = 5 * k; y < H; y += 8 * k) disc(c, x, y, .8 * k, stAlpha(C.muted, .55));
      var src = [[W * .36, H * .44], [W * .65, H * .6]], lam = 8.5 * k, R = W * .55;
      src.forEach(function (p, i) {
        for (var n = 0; n < 8; n++) {
          var r = lam * (n + md(t * .7 + i * .37, 1)), a = Math.max(0, 1 - r / R);
          circ(c, p[0], p[1], r, stAlpha(i ? C.warm : C.accent, .6 * a), 1.4);
        }
      });
      src.forEach(function (p) { halo(c, p[0], p[1], 6 * k, C.ink2, .5); disc(c, p[0], p[1], 2.6 * k, C.ink2); });
    };
    // Crossed Andreev reflection: an electron enters from one lead, a hole leaves through the other.
    D.andreev = function (c, C, W, H, t, k) {
      var sx = W * .6, top = H * .3, bot = H * .7, lh = 9 * k, f = md(t / 3.2, 1), q, g;
      c.fillStyle = stAlpha(C.accent, .2); c.fillRect(sx, H * .14, W * .34, H * .72);
      c.strokeStyle = C.accent; c.lineWidth = 1.4; c.strokeRect(sx, H * .14, W * .34, H * .72);
      [top, bot].forEach(function (y) {
        c.fillStyle = stAlpha(C.muted, .22); c.fillRect(W * .05, y - lh / 2, sx - W * .05, lh);
        c.strokeStyle = stAlpha(C.ink2, .45); c.lineWidth = 1; c.strokeRect(W * .05, y - lh / 2, sx - W * .05, lh);
      });
      for (q = 0; q < 3; q++) pair(c, C, sx + W * (.08 + .1 * q), H * (.3 + .2 * q) + 2 * k * Math.sin(t * 1.5 + q), k, .45);
      arrow(c, W * .12, top - lh, W * .3, top - lh, stAlpha(C.ink2, .4), 3 * k, 1);
      arrow(c, W * .3, bot + lh, W * .12, bot + lh, stAlpha(C.warm, .55), 3 * k, 1);
      if (f < .45) disc(c, W * .07 + (sx - W * .07) * f / .45, top, 3 * k, C.ink2);
      else {
        g = (f - .45) / .55;
        halo(c, sx, H * .5, 10 * k, C.gold || C.warm, .6 * (1 - g));
        circ(c, sx - (sx - W * .07) * g, bot, 3 * k, C.warm, 1.6);
        pair(c, C, sx + 4 * k + W * .26 * g, H * .5, k, 1);
      }
    };
    // Field–temperature diagram with a low-field region and a separate high-field pocket.
    D.reentrant = function (c, C, W, H, t, k) {
      var x0 = W * .12, x1 = W * .92, y0 = H * .86, y1 = H * .1, w = x1 - x0, h = y0 - y1, low = [], i;
      for (i = 0; i <= 20; i++) { var u = .36 * i / 20; low.push([x0 + w * u, y0 - h * .72 * Math.sqrt(Math.max(0, 1 - Math.pow(u / .36, 2)))]); }
      poly(c, [[x0, y0]].concat(low), true); c.fillStyle = stAlpha(C.accent, .22); c.fill();
      c.strokeStyle = C.accent; c.lineWidth = 1.8; poly(c, low); c.stroke();
      c.beginPath(); c.ellipse(x0 + w * .72, y0, w * .15, h * .38, 0, Math.PI, TAU); c.closePath();
      c.fillStyle = stAlpha(C.accent, .22); c.fill(); c.strokeStyle = C.accent; c.stroke();
      axes(c, C, x0, y0, x1 + 2 * k, y1, k);
      var v = .5 - .5 * Math.cos(TAU * t / 8), x = x0 + w * v, y = y0 - h * .1, inside = v < .35 || Math.abs(v - .72) < .145;
      if (inside) { halo(c, x, y, 8 * k, C.accent, .55); pair(c, C, x, y - 8 * k, k, 1); disc(c, x, y, 2.8 * k, C.accent); }
      else { disc(c, x, y, 2.8 * k, C.surface || '#ffffff'); circ(c, x, y, 2.8 * k, C.ink2, 1.3); }
    };
    // A square lattice wrapped into a cylinder, with charge modulation travelling along its length.
    D.cylinder = function (c, C, W, H, t, k) {
      var n = 8, legs = 8, cy = H * .5, ry = H * .3, rx = 5.5 * k, x0 = W * .13, dx = W * .74 / (n - 1), rot = t * .35, i, j, a, f;
      for (j = 0; j < legs; j++) {
        a = j * TAU / legs + rot; f = Math.sin(a);
        c.strokeStyle = stAlpha(C.muted, f > 0 ? .5 : .18); c.lineWidth = 1;
        seg(c, x0 + rx * f, cy + ry * Math.cos(a), x0 + dx * (n - 1) + rx * f, cy + ry * Math.cos(a));
      }
      for (i = 0; i < n; i++) {
        var x = x0 + i * dx, rho = .5 + .5 * Math.cos(TAU * (i / 4 - t * .18));
        c.beginPath(); c.ellipse(x, cy, rx, ry, 0, 0, TAU); c.strokeStyle = stAlpha(C.muted, .45); c.lineWidth = 1; c.stroke();
        if (rho > .6) { c.beginPath(); c.ellipse(x, cy, rx + 2 * k, ry + 2 * k, 0, 0, TAU); c.strokeStyle = stAlpha(C.warm, (rho - .6) * 1.5); c.lineWidth = 2.4 * k; c.stroke(); }
        for (j = 0; j < legs; j++) {
          a = j * TAU / legs + rot; f = Math.sin(a);
          disc(c, x + rx * f, cy + ry * Math.cos(a), (f > 0 ? 2.2 : 1.5) * k,
            f > 0 ? (rho > .5 ? stAlpha(C.warm, .45 + .55 * rho) : stAlpha(C.accent, .95 - .4 * rho)) : stAlpha(C.muted, .5));
        }
      }
    };
    // Neural-network wavefunction: lattice spins feed a small network whose output is the amplitude.
    D.nqs = function (c, C, W, H, t, k) {
      var sy = H * .84, hy = H * .5, oy = H * .16, ns = 7, nh = 4, sites = [], hid = [], i, j;
      for (i = 0; i < ns; i++) sites.push(W * (.12 + .76 * i / (ns - 1)));
      for (j = 0; j < nh; j++) hid.push(W * (.26 + .48 * j / (nh - 1)));
      c.lineWidth = .8; c.strokeStyle = stAlpha(C.muted, .3);
      for (i = 0; i < ns; i++) for (j = 0; j < nh; j++) seg(c, sites[i], sy - 7 * k, hid[j], hy);
      c.strokeStyle = stAlpha(C.muted, .45);
      for (j = 0; j < nh; j++) seg(c, hid[j], hy, W * .5, oy);
      for (var s = 0; s < 5; s++) {
        var f = md(t * .55 + s * .21, 1), xa = sites[(s * 3) % ns], xb = hid[s % nh], g;
        if (f < .6) { g = f / .6; disc(c, xa + (xb - xa) * g, sy - 7 * k + (hy - sy + 7 * k) * g, 1.6 * k, C.warm); }
        else { g = (f - .6) / .4; disc(c, xb + (W * .5 - xb) * g, hy + (oy - hy) * g, 1.6 * k, C.warm); }
      }
      for (j = 0; j < nh; j++) { disc(c, hid[j], hy, 3.4 * k, C.surface || '#ffffff'); circ(c, hid[j], hy, 3.4 * k, C.accent, 1.4); }
      halo(c, W * .5, oy, 9 * k, C.gold || C.warm, .4 + .3 * (.5 + .5 * Math.sin(t * 2.2))); disc(c, W * .5, oy, 4 * k, C.accent);
      for (i = 0; i < ns; i++) { var up = Math.sin(t * .6 + i * 2.1) > 0 ? -1 : 1; spin(c, sites[i], sy, up * Math.PI / 2, 10 * k, up < 0 ? C.accent : C.warm); }
    };
    // Displaced sites, vacancies and impurities, with bound pairs that keep moving through them.
    D.disorder = function (c, C, W, H, t, k) {
      var s = 14 * k, nx = Math.floor(W / s), ny = Math.floor(H / s), ox = (W - (nx - 1) * s) / 2, oy = (H - (ny - 1) * s) / 2, rng = stRng(41), p;
      for (var i = 0; i < nx; i++) for (var j = 0; j < ny; j++) {
        var x = ox + i * s + (rng() - .5) * 5 * k, y = oy + j * s + (rng() - .5) * 5 * k, r = rng();
        if (r < .08) { c.setLineDash([1.5 * k, 1.5 * k]); circ(c, x, y, 2.4 * k, stAlpha(C.muted, .8), 1); c.setLineDash([]); }
        else if (r < .18) disc(c, x, y, 2.8 * k, C.warm);
        else disc(c, x, y, 1.9 * k, stAlpha(C.ink2, .55));
      }
      for (p = 0; p < 2; p++) {
        var a = t * .45 + p * Math.PI, px = W * (.5 + .32 * Math.sin(a)), py = H * (.5 + .28 * Math.sin(2 * a + p)), b = t * 2.6 + p, ex = Math.cos(b) * 4 * k, ey = Math.sin(b) * 4 * k;
        halo(c, px, py, 9 * k, C.accent, .45);
        c.strokeStyle = stAlpha(C.accent, .8); c.lineWidth = 1.2; seg(c, px - ex, py - ey, px + ex, py + ey);
        disc(c, px - ex, py - ey, 2.3 * k, C.accent); disc(c, px + ex, py + ey, 2.3 * k, C.accent);
      }
    };
    // Copper–oxygen octahedron whose apical oxygens move in and out of the plane.
    D.apical = function (c, C, W, H, t, k) {
      var cx = W * .5, cy = H * .54, q = 15 * k, d = (22 + 4 * Math.sin(t * 1.4)) * k;
      var P = function (X, Y, Z) { return [cx + X * q - Y * q * .55, cy + X * q * .18 + Y * q * .38 - Z]; };
      poly(c, [P(-2.3, -2.3, 0), P(2.3, -2.3, 0), P(2.3, 2.3, 0), P(-2.3, 2.3, 0)], true);
      c.fillStyle = stAlpha(C.accent, .1); c.fill(); c.strokeStyle = stAlpha(C.muted, .5); c.lineWidth = 1; c.stroke();
      var O = [P(1, 0, 0), P(0, 1, 0), P(-1, 0, 0), P(0, -1, 0)], top = P(0, 0, d), bot = P(0, 0, -d), cu = P(0, 0, 0), i;
      [P(2, 0, 0), P(-2, 0, 0), P(0, 2, 0), P(0, -2, 0)].forEach(function (n) { c.strokeStyle = stAlpha(C.muted, .55); seg(c, cu[0], cu[1], n[0], n[1]); disc(c, n[0], n[1], 2.4 * k, stAlpha(C.accent, .5)); });
      c.strokeStyle = stAlpha(C.accent, .75); c.lineWidth = 1.1;
      for (i = 0; i < 4; i++) { seg(c, O[i][0], O[i][1], O[(i + 1) % 4][0], O[(i + 1) % 4][1]); seg(c, top[0], top[1], O[i][0], O[i][1]); seg(c, bot[0], bot[1], O[i][0], O[i][1]); }
      c.strokeStyle = stAlpha(C.warm, .7); c.setLineDash([2 * k, 2 * k]); seg(c, cu[0], cu[1], top[0], top[1]); seg(c, cu[0], cu[1], bot[0], bot[1]); c.setLineDash([]);
      O.forEach(function (o) { disc(c, o[0], o[1], 2.6 * k, C.ink2); });
      disc(c, cu[0], cu[1], 3.6 * k, C.accent);
      [top, bot].forEach(function (o) { halo(c, o[0], o[1], 7 * k, C.warm, .5); disc(c, o[0], o[1], 3.3 * k, C.warm); });
    };
    // d-wave gap on a circular Fermi surface: lobes of alternating sign, nodes on the diagonals.
    D.dwave = function (c, C, W, H, t, k) {
      var cx = W * .5, cy = H * .5, R = 16 * k, A = 13 * k * (.9 + .1 * Math.sin(t * 1.5)), B = 35 * k, i, th;
      c.strokeStyle = stAlpha(C.muted, .45); c.lineWidth = 1; c.strokeRect(cx - B, cy - B, 2 * B, 2 * B);
      c.strokeStyle = stAlpha(C.muted, .3); seg(c, cx - B, cy, cx + B, cy); seg(c, cx, cy - B, cx, cy + B);
      for (var q = 0; q < 4; q++) {
        c.beginPath();
        for (i = 0; i <= 16; i++) { th = q * Math.PI / 2 - Math.PI / 4 + Math.PI / 2 * i / 16; var r = R + A * Math.abs(Math.cos(2 * th)); if (i) c.lineTo(cx + r * Math.cos(th), cy - r * Math.sin(th)); else c.moveTo(cx + r * Math.cos(th), cy - r * Math.sin(th)); }
        for (i = 16; i >= 0; i--) { th = q * Math.PI / 2 - Math.PI / 4 + Math.PI / 2 * i / 16; c.lineTo(cx + R * Math.cos(th), cy - R * Math.sin(th)); }
        c.closePath(); c.fillStyle = stAlpha(q % 2 ? C.warm : C.accent, .35); c.fill(); c.strokeStyle = q % 2 ? C.warm : C.accent; c.lineWidth = 1.3; c.stroke();
      }
      circ(c, cx, cy, R, C.ink2, 1.2);
      for (i = 0; i < 4; i++) { th = Math.PI / 4 + i * Math.PI / 2; disc(c, cx + R * Math.cos(th), cy - R * Math.sin(th), 2 * k, C.ink2); }
      th = t * .7; var gap = A * Math.abs(Math.cos(2 * th));
      c.strokeStyle = C.ink2; c.lineWidth = 1.6; seg(c, cx + R * Math.cos(th), cy - R * Math.sin(th), cx + (R + gap) * Math.cos(th), cy - (R + gap) * Math.sin(th));
      disc(c, cx + R * Math.cos(th), cy - R * Math.sin(th), 2.6 * k, C.gold || C.warm);
    };
    var ALT = {
      zr: 'Copper–oxygen plane with Zhang–Rice singlets: a hole on the four oxygens around a copper binds to that copper’s spin (shaded diamonds) on alternating plaquettes. Placement and timing are illustrative, not the article’s images or calculation.',
      domains: 'Two domains of different local orientation meet at a wandering wall where small superconducting puddles glow. Domain shapes, sizes and motion are illustrative, not the article’s maps.',
      dome: 'Schematic superconducting dome: the transition temperature rises and falls as a tuning parameter changes, and the dot follows the boundary; a half-dome named in the headline leaves the far side dashed. The axes carry no values; not a measured phase diagram.',
      qpi: 'Quasiparticle-interference cartoon: waves scattered from two surface impurities overlap into ripples. Wavelength and pattern are illustrative, not the article’s measured maps or wavevectors.',
      andreev: 'Crossed Andreev reflection: an electron arriving through one normal lead leaves as a hole through the other while a Cooper pair enters the superconductor. Paths and timing are illustrative, not measured conductance.',
      reentrant: 'Schematic field–temperature diagram with a low-field superconducting region and a separate high-field pocket; the dot sweeps the field at low temperature. Shapes are illustrative, not the article’s measured phase boundaries.',
      cylinder: 'Square lattice wrapped into a cylinder, as in cylinder lattice-model calculations; shading travels along its length to suggest charge modulation. Leg count, period and motion are illustrative, not computed densities.',
      nqs: 'Neural-network wavefunction cartoon: spins on lattice sites feed a small network whose output is the wavefunction amplitude. Network size, connections and spins are illustrative, not the article’s architecture or results.',
      disorder: 'Lattice with displaced sites, vacancies and impurity atoms, through which bound pairs keep moving. Positions and motion are illustrative, not a measured disorder level or pairing strength.',
      apical: 'Copper–oxygen octahedron: the apical oxygens above and below the copper move in and out of the CuO₂ plane. The motion is exaggerated and illustrative, not the article’s structure or a measured vibration.',
      dwave: 'Schematic d-wave gap on a circular Fermi surface: four lobes of alternating sign with nodes on the diagonals; the bar shows the gap where the dot sits. Sizes are illustrative, not a measured gap map.'
    };
    Object.keys(D).forEach(function (kind) {
      MINI_DRAW['news-' + kind] = guard(D[kind]);
      MINI_STATIC['news-' + kind] = 1.2;
      MINI_ALT['news-' + kind] = ALT[kind];
    });

    // ---------- per-article looks ----------
    // Colour sets use the app's own series colours in both themes.
    var PAL = [null, ['aqua', 'gold', 'accent', 'warm'], ['warm', 'accent', 'gold', 'aqua'], ['accent', 'aqua', 'warm', 'gold']];
    function palette(C, p) {
      var m = PAL[p], o = {}, key;
      if (!m || !C.aqua || !C.gold) return C;
      for (key in C) o[key] = C[key];
      o.accent = C[m[0]]; o.warm = C[m[1]]; o.aqua = C[m[2]]; o.gold = C[m[3]];
      return o;
    }
    // Mirror and close-up framings; plots, timelines and labelled drawings keep their orientation.
    var FLIP = [0, 1, 0, 1, 0, 1], ZOOM = [[1, .5, .5], [1, .5, .5], [1.16, .3, .45], [1.16, .3, .45], [1.26, .5, .5], [1.26, .64, .55]],
      KEEP = [[1, .5, .5], [1.14, .22, .5], [1.16, .78, .5], [1.2, .5, .25], [1.2, .5, .8], [1.3, .5, .5]],
      FIXED = /^(?:hydride|two-stage|timeline|competition|dome|reentrant|spectrum|gapdos|ring|interval|routing|tree|features|measurement|research|literature|search|graph|ai|general|penetration)$/;
    function frame(c, W, H, v, keep) {
      var z = (keep ? KEEP : ZOOM)[v] || KEEP[0];
      if (!keep && FLIP[v]) { c.translate(W, 0); c.scale(-1, 1); }
      if (z[0] !== 1) { c.translate(W * z[1], H * z[2]); c.scale(z[0], z[0]); c.translate(-W * z[1], -H * z[2]); }
    }
    // Element dots use the conventional CPK/Jmol colours; each dot is outlined for both themes.
    var EL = {};
    ('H:ffffff,Li:cc80ff,Be:c2ff00,B:ffb5b5,C:909090,N:3050f8,O:ff0d0d,F:90e050,Na:ab5cf2,Mg:8aff00,Al:bfa6a6,Si:f0c8a0,P:ff8000,S:ffff30,Cl:1ff01f,' +
      'K:8f40d4,Ca:3dff00,Sc:e6e6e6,Ti:bfc2c7,V:a6a6ab,Cr:8a99c7,Mn:9c7ac7,Fe:e06633,Co:f090a0,Ni:50d050,Cu:c88033,Zn:7d80b0,Ga:c28f8f,Ge:668f8f,' +
      'As:bd80e3,Se:ffa100,Br:a62929,Rb:702eb0,Sr:00ff00,Y:94ffff,Zr:94e0e0,Nb:73c2c9,Mo:54b5b5,Ru:248f8f,Rh:0a7d8c,Pd:006985,Ag:c0c0c0,Cd:ffd98f,' +
      'In:a67573,Sn:668080,Sb:9e63b5,Te:d47a00,I:940094,Cs:57178f,Ba:00c900,La:70d4ff,Ce:ffffc7,Pr:d9ffc7,Nd:c7ffc7,Sm:8fffc7,Eu:61ffc7,Gd:45ffc7,' +
      'Yb:00bf38,Lu:00ab24,Hf:4dc2ff,Ta:4da6ff,W:2194d6,Re:267dab,Os:266696,Ir:175487,Pt:d0d0e0,Au:ffd123,Hg:b8b8d0,Tl:a6544d,Pb:575961,Bi:9e4fb5,' +
      'Th:00baff,U:008fff').split(',').forEach(function (e) { var p = e.split(':'); EL[p[0]] = '#' + p[1]; });
    function page(c, C, x, y, u) {
      c.fillStyle = C.surface || '#ffffff'; c.fillRect(x - .62 * u, y - .9 * u, 1.24 * u, 1.8 * u);
      c.strokeStyle = stAlpha(C.ink2, .7); c.lineWidth = 1; c.strokeRect(x - .62 * u, y - .9 * u, 1.24 * u, 1.8 * u);
      c.strokeStyle = stAlpha(C.ink2, .45);
      for (var i = 0; i < 4; i++) seg(c, x - .38 * u, y - .55 * u + i * .37 * u, x + (i === 3 ? .1 : .38) * u, y - .55 * u + i * .37 * u);
    }
    function bubble(c, x, y, w, h, color, left) {
      c.fillStyle = color; c.fillRect(x - w / 2, y - h / 2, w, h);
      var s = left ? -1 : 1;
      poly(c, [[x + s * w * .3, y + h / 2], [x + s * w * .45, y + h * .95], [x + s * w * .05, y + h / 2]], true); c.fill();
    }
    // Small animated badges for a method or notice named in the article.
    var ICON = {
      stm: function (c, C, x, y, u, t) {
        var sx = x + .3 * u * Math.sin(t * 1.3), i;
        c.strokeStyle = stAlpha(C.ink2, .6); c.lineWidth = 1; seg(c, x - u, y + .75 * u, x + u, y + .75 * u);
        for (i = 0; i < 5; i++) disc(c, x - .8 * u + .4 * u * i, y + .62 * u, .13 * u, C.ink2);
        poly(c, [[sx - .38 * u, y - u], [sx + .38 * u, y - u], [sx, y + .2 * u]], true); c.fillStyle = C.accent; c.fill();
        disc(c, sx, y + .4 * u, .1 * u + .06 * u * (1 + Math.sin(t * 5)), C.warm);
      },
      arpes: function (c, C, x, y, u, t) {
        c.strokeStyle = stAlpha(C.ink2, .65); c.lineWidth = 1.2; seg(c, x - u, y + .7 * u, x + u, y + .7 * u);
        wave(c, x - u, y - .9 * u, x - .1 * u, y + .6 * u, 2.5, .13 * u, C.warm, t * 6, 1.1);
        var f = md(t * .7, 1); disc(c, x + .05 * u + .8 * u * f, y + .55 * u - 1.4 * u * f, .2 * u, stAlpha(C.accent, 1 - .6 * f));
      },
      neutron: function (c, C, x, y, u, t) {
        c.fillStyle = stAlpha(C.ink2, .75); c.fillRect(x - .25 * u, y - .25 * u, .5 * u, .5 * u);
        c.setLineDash([.15 * u, .2 * u]); c.strokeStyle = stAlpha(C.ink2, .35); c.lineWidth = 1;
        seg(c, x - u, y, x - .3 * u, y); seg(c, x + .3 * u, y - .25 * u, x + .9 * u, y - .75 * u); c.setLineDash([]);
        for (var i = 0; i < 2; i++) {
          var f = md(t * .6 + i * .5, 1), g = f < .5 ? f * 2 : (f - .5) * 2;
          if (f < .5) disc(c, x - u + .7 * u * g, y, .16 * u, C.accent); else disc(c, x + .3 * u + .6 * u * g, y - .25 * u - .5 * u * g, .16 * u, C.warm);
        }
      },
      muon: function (c, C, x, y, u, t) {
        var a = t * 2.4;
        circ(c, x, y, .8 * u, stAlpha(C.muted, .6), 1);
        c.beginPath(); c.arc(x, y, .8 * u, a - 1.4, a); c.strokeStyle = stAlpha(C.warm, .75); c.lineWidth = 1.4; c.stroke();
        arrow(c, x, y, x + .8 * u * Math.cos(a), y + .8 * u * Math.sin(a), C.accent, .42 * u, 1.3); disc(c, x, y, .16 * u, C.ink2);
      },
      nmr: function (c, C, x, y, u, t) {
        for (var i = -1; i <= 1; i++) { c.beginPath(); c.ellipse(x + i * .55 * u, y, .2 * u, .8 * u, 0, 0, TAU); c.strokeStyle = stAlpha(C.ink2, .55); c.lineWidth = 1; c.stroke(); }
        var a = -Math.PI / 2 + .45 * Math.sin(t * 3);
        arrow(c, x - .5 * u * Math.cos(a), y - .5 * u * Math.sin(a), x + .6 * u * Math.cos(a), y + .6 * u * Math.sin(a), C.warm, .4 * u, 1.3);
      },
      raman: function (c, C, x, y, u, t) {
        wave(c, x - u, y + .15 * u, x - .2 * u, y + .15 * u, 1.5, .2 * u, C.accent, t * 5, 1.1); disc(c, x, y + .15 * u, .2 * u, C.ink2);
        wave(c, x + .15 * u, y, x + .85 * u, y - .75 * u, 2.6, .14 * u, C.warm, t * 7, 1.1);
      },
      xray: function (c, C, x, y, u, t) {
        for (var i = -1; i <= 1; i++) for (var j = -1; j <= 1; j++) disc(c, x + .28 * u * i, y + .28 * u * j, .09 * u, C.ink2);
        c.strokeStyle = stAlpha(C.accent, .85); c.lineWidth = 1.2; seg(c, x - u, y + .1 * u, x - .4 * u, y + .05 * u);
        for (i = 0; i < 2; i++) { c.strokeStyle = stAlpha(C.warm, .35 + .45 * Math.max(0, Math.sin(t * 2.5 + i * 2))); seg(c, x + .38 * u, y + (i ? .1 : -.1) * u, x + .95 * u, y + (i ? .5 : -.75) * u); }
      },
      optics: function (c, C, x, y, u, t) {
        c.fillStyle = stAlpha(C.accent, .3); c.fillRect(x + .35 * u, y - u, .45 * u, 2 * u);
        wave(c, x - u, y - .8 * u, x + .3 * u, y, 2, .12 * u, C.warm, t * 6, 1.1);
        wave(c, x + .3 * u, y, x - u, y + .8 * u, 2, .12 * u, stAlpha(C.warm, .55), t * 6, 1.1);
      },
      pulse: function (c, C, x, y, u, t) {
        var m = x - u + 2 * u * md(t * .45, 1);
        c.beginPath();
        for (var i = 0; i <= 28; i++) { var px = x - u + 2 * u * i / 28, e = Math.exp(-Math.pow((px - m) / (.35 * u), 2)), py = y - .6 * u * e * Math.sin((px - m) / (.09 * u)); if (i) c.lineTo(px, py); else c.moveTo(px, py); }
        c.strokeStyle = C.warm; c.lineWidth = 1.3; c.stroke();
      },
      anvil: function (c, C, x, y, u, t) {
        var g = (.32 - .1 * (.5 + .5 * Math.sin(t * 1.6))) * u;
        c.fillStyle = stAlpha(C.accent, .35); c.strokeStyle = C.accent; c.lineWidth = 1;
        poly(c, [[x - .65 * u, y - u], [x + .65 * u, y - u], [x + .22 * u, y - g], [x - .22 * u, y - g]], true); c.fill(); c.stroke();
        poly(c, [[x - .65 * u, y + u], [x + .65 * u, y + u], [x + .22 * u, y + g], [x - .22 * u, y + g]], true); c.fill(); c.stroke();
        c.fillStyle = C.warm; c.fillRect(x - .2 * u, y - g * .7, .4 * u, g * 1.4);
      },
      strain: function (c, C, x, y, u, t) {
        var w = .45 * u + .15 * u * Math.sin(t * 1.8);
        c.fillStyle = stAlpha(C.accent, .3); c.fillRect(x - w, y - .35 * u, 2 * w, .7 * u);
        c.strokeStyle = C.accent; c.lineWidth = 1; c.strokeRect(x - w, y - .35 * u, 2 * w, .7 * u);
        arrow(c, x - w - .1 * u, y, x - u, y, C.warm, .3 * u, 1.2); arrow(c, x + w + .1 * u, y, x + u, y, C.warm, .3 * u, 1.2);
      },
      field: function (c, C, x, y, u, t) {
        for (var i = -1; i <= 1; i++) {
          var yy = y + i * .55 * u;
          arrow(c, x - u, yy, x + u, yy, stAlpha(C.accent, .85), .32 * u, 1.1);
          disc(c, x - u + 1.6 * u * md(t * .8 + i * .3, 1), yy, .11 * u, C.warm);
        }
      },
      heat: function (c, C, x, y, u, t) {
        var lvl = .55 + .3 * Math.sin(t * 1.2);
        c.strokeStyle = C.ink2; c.lineWidth = 1; c.strokeRect(x - .17 * u, y - u, .34 * u, 1.45 * u);
        c.fillStyle = C.warm; c.fillRect(x - .1 * u, y + .45 * u - 1.35 * u * lvl, .2 * u, 1.35 * u * lvl); disc(c, x, y + .62 * u, .3 * u, C.warm);
        c.strokeStyle = stAlpha(C.ink2, .5);
        for (var i = 0; i < 3; i++) seg(c, x + .25 * u, y - .7 * u + i * .4 * u, x + .45 * u, y - .7 * u + i * .4 * u);
      },
      contacts: function (c, C, x, y, u, t) {
        c.fillStyle = stAlpha(C.accent, .3); c.fillRect(x - u, y - .2 * u, 2 * u, .4 * u);
        c.fillStyle = C.ink2;
        for (var i = 0; i < 4; i++) c.fillRect(x - .82 * u + i * .5 * u, y - .45 * u, .18 * u, .25 * u);
        disc(c, x - u + 2 * u * md(t * .5, 1), y, .13 * u, C.warm);
      },
      gate: function (c, C, x, y, u, t) {
        c.fillStyle = C.ink2; c.fillRect(x - .8 * u, y - .75 * u, 1.6 * u, .22 * u);
        c.fillStyle = stAlpha(C.accent, .3); c.fillRect(x - u, y + .25 * u, 2 * u, .4 * u);
        var a = .5 + .5 * Math.sin(t * 1.5);
        arrow(c, x, y - .45 * u, x, y + .12 * u, stAlpha(C.ink2, .5), .25 * u, 1);
        for (var i = 0; i < 4; i++) disc(c, x - .6 * u + i * .4 * u, y + .45 * u, .11 * u, stAlpha(C.warm, a));
      },
      dope: function (c, C, x, y, u, t) {
        for (var i = -1; i <= 1; i++) for (var j = -1; j <= 1; j++) {
          var sub = i === -j && i !== 0, a = sub ? .5 + .5 * Math.sin(t * 1.4 + i) : 0;
          if (a > .5) halo(c, x + .6 * u * i, y + .6 * u * j, .45 * u, C.warm, a - .3);
          disc(c, x + .6 * u * i, y + .6 * u * j, .16 * u, sub ? C.warm : C.ink2);
        }
      },
      calc: function (c, C, x, y, u, t) {
        var on = Math.floor(md(t * 2, 9));
        for (var n = 0; n < 9; n++) {
          c.fillStyle = n === on ? C.accent : stAlpha(C.accent, n < on ? .4 : .12);
          c.fillRect(x - .9 * u + .6 * u * (n % 3) + .05 * u, y - .9 * u + .6 * u * Math.floor(n / 3) + .05 * u, .5 * u, .5 * u);
        }
      },
      ml: function (c, C, x, y, u, t) {
        var A = [-.75, 0, .75], B = [-.4, .4], i, j, f = md(t * .7, 1);
        c.strokeStyle = stAlpha(C.muted, .6); c.lineWidth = .8;
        for (i = 0; i < 3; i++) for (j = 0; j < 2; j++) seg(c, x - .8 * u, y + A[i] * u, x, y + B[j] * u);
        for (j = 0; j < 2; j++) seg(c, x, y + B[j] * u, x + .8 * u, y);
        disc(c, x - .8 * u + 1.6 * u * f, y + (f < .5 ? A[0] + (B[0] - A[0]) * f * 2 : B[0] * (2 - f * 2)) * u, .12 * u, C.warm);
        A.forEach(function (v) { disc(c, x - .8 * u, y + v * u, .17 * u, C.accent); });
        B.forEach(function (v) { disc(c, x, y + v * u, .17 * u, C.accent); });
        disc(c, x + .8 * u, y, .2 * u, C.ink2);
      },
      phonon: function (c, C, x, y, u, t) {
        var xs = [], i, n;
        for (i = 0; i < 4; i++) xs.push(x - .8 * u + .53 * u * i + .12 * u * Math.sin(t * 3 - i * 1.4));
        c.strokeStyle = stAlpha(C.ink2, .55); c.lineWidth = 1;
        for (i = 0; i < 3; i++) {
          c.beginPath(); c.moveTo(xs[i], y);
          for (n = 1; n < 6; n++) c.lineTo(xs[i] + (xs[i + 1] - xs[i]) * n / 6, y + (n % 2 ? -.15 : .15) * u);
          c.lineTo(xs[i + 1], y); c.stroke();
        }
        xs.forEach(function (px) { disc(c, px, y, .2 * u, C.accent); });
      },
      device: function (c, C, x, y, u, t) {
        c.fillStyle = stAlpha(C.accent, .4); c.fillRect(x - u, y - .45 * u, .8 * u, .9 * u); c.fillRect(x + .2 * u, y - .45 * u, .8 * u, .9 * u);
        disc(c, x - .3 * u + .6 * u * md(t * .6, 1), y, .14 * u, C.warm);
      },
      edge: function (c, C, x, y, u, t) {
        var f = md(t * .35, 1) * 4, side = Math.floor(f), g = f - side, pts = [[-1, -1], [1, -1], [1, 1], [-1, 1]], a = pts[side % 4], b = pts[(side + 1) % 4];
        c.fillStyle = stAlpha(C.accent, .18); c.fillRect(x - .75 * u, y - .75 * u, 1.5 * u, 1.5 * u);
        c.strokeStyle = C.accent; c.lineWidth = 1.2; c.strokeRect(x - .75 * u, y - .75 * u, 1.5 * u, 1.5 * u);
        disc(c, x + .75 * u * (a[0] + (b[0] - a[0]) * g), y + .75 * u * (a[1] + (b[1] - a[1]) * g), .16 * u, C.warm);
      },
      film: function (c, C, x, y, u, t) {
        c.fillStyle = stAlpha(C.muted, .5); c.fillRect(x - u, y + .3 * u, 2 * u, .5 * u);
        c.fillStyle = stAlpha(C.accent, .55); c.fillRect(x - u, y, 2 * u, .22 * u);
        c.fillStyle = stAlpha(C.accent, .85); c.fillRect(x - u, y - .3 * u, 2 * u * (.35 + .65 * md(t * .25, 1)), .22 * u);
      },
      spectro: function (c, C, x, y, u, t) {
        c.strokeStyle = stAlpha(C.ink2, .5); c.lineWidth = 1; seg(c, x - u, y + .7 * u, x + u, y + .7 * u);
        c.beginPath();
        for (var i = 0; i <= 20; i++) { var s = i / 10 - 1, py = y + .65 * u - 1.3 * u * (Math.exp(-Math.pow((s + .45) / .14, 2)) + .7 * Math.exp(-Math.pow((s - .4) / .2, 2))); if (i) c.lineTo(x + s * u, py); else c.moveTo(x + s * u, py); }
        c.strokeStyle = C.accent; c.lineWidth = 1.2; c.stroke();
        var m = x - u + 2 * u * md(t * .3, 1); c.strokeStyle = stAlpha(C.warm, .8); seg(c, m, y - .8 * u, m, y + .7 * u);
      },
      fix: function (c, C, x, y, u) {
        page(c, C, x, y, u);
        c.strokeStyle = C.warm; c.lineWidth = 1.4; seg(c, x - .5 * u, y - .18 * u, x + .5 * u, y - .18 * u);
        poly(c, [[x - .12 * u, y + .62 * u], [x + .08 * u, y + .3 * u], [x + .28 * u, y + .62 * u]]); c.stroke();
      },
      reply: function (c, C, x, y, u, t) {
        var a = Math.sin(t * 1.5) > 0;
        bubble(c, x - .3 * u, y - .35 * u, 1.1 * u, .7 * u, a ? C.accent : stAlpha(C.accent, .35), true);
        bubble(c, x + .3 * u, y + .3 * u, 1.1 * u, .7 * u, a ? stAlpha(C.warm, .35) : C.warm, false);
      },
      add: function (c, C, x, y, u) {
        page(c, C, x - .15 * u, y, u * .9); disc(c, x + .55 * u, y + .55 * u, .38 * u, C.warm);
        c.strokeStyle = C.surface || '#ffffff'; c.lineWidth = 1.4; seg(c, x + .35 * u, y + .55 * u, x + .75 * u, y + .55 * u); seg(c, x + .55 * u, y + .35 * u, x + .55 * u, y + .75 * u);
      },
      retract: function (c, C, x, y, u) { page(c, C, x, y, u); c.strokeStyle = C.warm; c.lineWidth = 1.8; seg(c, x - .8 * u, y + .9 * u, x + .8 * u, y - .9 * u); }
    };
    function badges(c, C, W, H, t, k, L) {
      var r = 10.5 * k, bx = W - r - 3 * k, by = r + 3 * k, id = L.notice || L.probe, ink = stAlpha(C.ink2, .3), back = stAlpha(C.surface || '#ffffff', .94);
      if (id && ICON[id]) { disc(c, bx, by, r, back); circ(c, bx, by, r, ink, 1); ICON[id](c, C, bx, by, r * .6, t); }
      if (!L.comp.length && !L.tc) return;
      var h = 12 * k, y = H - 3 * k - h / 2, x0 = 3 * k, w = 4 * k, max = 0, rs = [];
      L.comp.forEach(function (e) { max = Math.max(max, e.n); });
      L.comp.forEach(function (e) { var rr = 4 * k * Math.sqrt(.3 + .7 * Math.min(1, e.n / (max || 1))); rs.push(rr); w += 2 * rr + 2 * k; });
      w = Math.max(w + (L.tc ? 8 * k : 2 * k), h);
      c.beginPath(); c.arc(x0 + h / 2, y, h / 2, Math.PI / 2, Math.PI * 1.5); c.lineTo(x0 + w - h / 2, y - h / 2);
      c.arc(x0 + w - h / 2, y, h / 2, -Math.PI / 2, Math.PI / 2); c.closePath();
      c.fillStyle = back; c.fill(); c.strokeStyle = ink; c.lineWidth = 1; c.stroke();
      var x = x0 + 4 * k;
      L.comp.forEach(function (e, j) {
        var rr = rs[j], bob = .7 * k * Math.sin(t * 2.2 + j * 1.3);
        x += rr; disc(c, x, y + bob, rr, EL[e.el] || '#9a9a9a'); circ(c, x, y + bob, rr, stAlpha(C.ink2, .55), .8); x += rr + 2 * k;
      });
      if (L.tc) {
        // A temperature named in the headline, on a logarithmic 1–300 K scale.
        var tx = x + 2 * k, top = y - 4.2 * k, bot = y + 2.4 * k, lvl = Math.max(.06, Math.min(1, Math.log(1 + L.tc) / Math.log(301)));
        c.strokeStyle = C.ink2; c.lineWidth = 1; c.strokeRect(tx - 1.2 * k, top, 2.4 * k, bot - top);
        c.fillStyle = C.warm; c.fillRect(tx - .6 * k, bot - (bot - top) * lvl, 1.2 * k, (bot - top) * lvl);
        disc(c, tx, bot + 1.1 * k, 1.9 * k, C.warm);
      }
    }
    Object.keys(MINI_DRAW).forEach(function (kind) {
      if (kind.indexOf('news-') !== 0) return;
      var base = MINI_DRAW[kind], keep = FIXED.test(kind.slice(5));
      MINI_DRAW[kind] = function (c, C, W, H, t, info) {
        var L = info && info.look;
        if (!L) { base(c, C, W, H, t, info); return; }
        var P = palette(C, L.p), k = Math.min(W / 112, H / 84), tt = (t || 0) + L.ph;
        c.save(); frame(c, W, H, L.v, keep); base(c, P, W, H, tt, info); c.restore();
        c.save(); c.lineCap = 'round'; c.lineJoin = 'round'; c.setLineDash([]); c.globalAlpha = 1;
        try { badges(c, P, W, H, tt, k, L); } finally { c.restore(); }
      };
    });
  })();

};
