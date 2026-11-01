'use strict';
// mechanism-drawings: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconMechanismDrawings = function initializeSuperconMechanismDrawings() {


  /* ---------- classic high-Tc mechanisms: card animations (original drawings, same engine as the other cards) ---------- */
  (function () {
    var TAU = Math.PI * 2, UP = -Math.PI / 2, DOWN = Math.PI / 2;
    function md(t, p) { t = t % p; return t < 0 ? t + p : t; }
    function textW(c, C, text, size, weight) { c.font = (weight || '400') + ' ' + size + 'px ' + C.font; return c.measureText(text).width; }
    function seg(c, x0, y0, x1, y1) { c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y1); c.stroke(); }
    function ring(c, x, y, r, stroke, lw, fill) {
      c.beginPath(); c.arc(x, y, r, 0, TAU);
      if (fill) { c.fillStyle = fill; c.fill(); }
      if (stroke) { c.lineWidth = lw || 1; c.strokeStyle = stroke; c.stroke(); }
    }
    function arrow(c, x0, y0, x1, y1, color, head, lw) {
      var a = Math.atan2(y1 - y0, x1 - x0), hd = head || 5;
      c.strokeStyle = color; c.fillStyle = color; c.lineWidth = lw || 1.25;
      c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1 - Math.cos(a) * hd * 0.8, y1 - Math.sin(a) * hd * 0.8); c.stroke();
      c.beginPath(); c.moveTo(x1, y1);
      c.lineTo(x1 - hd * Math.cos(a - 0.42), y1 - hd * Math.sin(a - 0.42));
      c.lineTo(x1 - hd * Math.cos(a + 0.42), y1 - hd * Math.sin(a + 0.42));
      c.closePath(); c.fill();
    }
    // Spin arrow of length L centred on (x, y).
    function spin(c, x, y, ang, L, color, lw) {
      if (L < 1.5) return;
      var dx = Math.cos(ang) * L / 2, dy = Math.sin(ang) * L / 2;
      arrow(c, x - dx, y - dy, x + dx, y + dy, color, Math.max(3, Math.min(5, L * 0.4)), lw || 1.3);
    }
    function glow(c, x, y, r, color, a) {
      for (var i = 3; i >= 1; i--) { c.beginPath(); c.arc(x, y, r * i / 3, 0, TAU); c.fillStyle = stAlpha(color, a * 0.3); c.fill(); }
    }
    function guard(fn) {
      return function (c, C, W, H, t) {
        c.save();
        c.lineCap = 'butt'; c.lineJoin = 'round'; c.setLineDash([]); c.globalAlpha = 1;
        try { fn(c, C, W, H, t || 0); } finally { c.restore(); }
      };
    }
    // Legend column on the right: rows of { text, sw(x, y), on (0..1) }.
    function legendWidth(c, C, rows) {
      var w = 0;
      rows.forEach(function (r) { w = Math.max(w, textW(c, C, r.text, 11)); });
      return Math.ceil(w) + 20;
    }
    function legendDraw(c, C, x, yMid, rows, gap) {
      var y0 = yMid - (rows.length - 1) * gap / 2;
      rows.forEach(function (r, i) {
        var y = y0 + i * gap, on = r.on === undefined ? 1 : r.on;
        c.globalAlpha = 0.45 + 0.55 * on;
        if (r.sw) r.sw(x + 6, y);
        var o = { size: 11, base: 'middle', color: on > 0.5 ? C.ink : C.ink2, weight: on > 0.5 ? '600' : '400' };
        if (r.parts) stSym(c, C, r.parts, x + 18, y + 0.5, o); else label(c, C, r.text, x + 18, y + 0.5, o);
        c.globalAlpha = 1;
      });
    }
    // Square-lattice window: n columns that fit between x0 and x1 with spacing s, rows centred on yMid.
    function grid(x0, x1, s, nr, yMid, minC, maxC) {
      var nc = Math.max(minC || 4, Math.min(maxC || 12, Math.floor((x1 - x0) / s) + 1));
      return { nc: nc, nr: nr, s: s, ox: x0 + (x1 - x0 - (nc - 1) * s) / 2, oy: yMid - (nr - 1) * s / 2,
        x: function (i) { return this.ox + i * s; }, y: function (j) { return this.oy + j * s; } };
    }
    function neel(i, j) { return (i + j) % 2 ? DOWN : UP; }
    function warmTag(c, C, text, x, y, a) {
      c.globalAlpha = a;
      stTag(c, C, text, x, y, { size: 10, pad: 4, bg: stAlpha(C.warm, 0.16), ring: C.warm, color: C.ink });
      c.globalAlpha = 1;
    }

    /* 1. Mott insulator and the Hubbard model: hopping onto an occupied site costs U; a doped hole
       moves and leaves the spins it shifts on the wrong sublattice (a string of frustrated bonds). */
    function mottState(G, tt) {
      // hole path (column, row) inside the window, five hops out, then the same five hops back
      var nc = G.nc, path = [[nc - 2, 1], [nc - 3, 1], [nc - 3, 2], [nc - 4, 2], [nc - 4, 1], [nc - 5, 1]];
      var hops = [];
      for (var k = 0; k < 5; k++) hops.push({ a: path[k], b: path[k + 1], t0: 4.8 + 0.8 * k, d: 0.55 });
      for (k = 0; k < 5; k++) hops.push({ a: path[5 - k], b: path[4 - k], t0: 9.4 + 0.5 * k, d: 0.38 });
      var sp = [], i, j;
      for (i = 0; i < G.nc; i++) { sp.push([]); for (j = 0; j < G.nr; j++) sp[i].push(neel(i, j)); }
      var hole = tt >= 4.0 && tt < 12.6 ? path[0] : null, moving = null;
      if (hole) {
        for (k = 0; k < hops.length; k++) {
          var hp = hops[k];
          if (tt < hp.t0) break;
          var f = stSpan(tt, hp.t0, hp.t0 + hp.d);
          if (f >= 1) { sp[hp.a[0]][hp.a[1]] = sp[hp.b[0]][hp.b[1]]; hole = hp.b; }
          else { moving = { from: hp.b, to: hp.a, f: f, ang: sp[hp.b[0]][hp.b[1]] }; break; }
        }
      }
      return { sp: sp, hole: hole, moving: moving, appear: stSpan(tt, 4.0, 4.6) * (1 - stSpan(tt, 12.0, 12.6)) };
    }
    function drawMott(c, C, W, H, t) {
      var P = 13, tt = md(t, P), m = 10;
      var tryOn = 0, a;
      for (a = 0; a < 2; a++) tryOn = Math.max(tryOn, Math.sin(Math.PI * stClamp((tt - 0.5 - 1.8 * a) / 1.3)));
      var rows = [
        { text: 'one electron per site', sw: function (x, y) { spin(c, x, y, UP, 12, C.accent, 1.4); }, on: tt < 4 ? 1 : 0 },
        { text: 'U: no double occupancy', sw: function (x, y) { label(c, C, 'U', x, y + 0.5, { size: 11, weight: '700', align: 'center', base: 'middle', color: C.warm }); }, on: tryOn > 0.3 ? 1 : 0 },
        { text: 'hole and its spin trail', sw: function (x, y) { ring(c, x, y, 4, C.warm, 1.5); }, on: tt >= 4 ? 1 : 0 }
      ];
      var lw = legendWidth(c, C, rows), G = grid(m + 4, W - m - lw - 12, 20, 4, H / 2, 5, 9);
      var S = mottState(G, tt), i, j;
      // frustrated bonds: neighbours whose spins are parallel
      c.setLineDash([3, 2]); c.lineWidth = 1.6; c.strokeStyle = stAlpha(C.warm, 0.85);
      for (i = 0; i < G.nc; i++) for (j = 0; j < G.nr; j++) {
        var here = !(S.hole && S.hole[0] === i && S.hole[1] === j) && !(S.moving && ((S.moving.from[0] === i && S.moving.from[1] === j) || (S.moving.to[0] === i && S.moving.to[1] === j)));
        if (!here) continue;
        [[1, 0], [0, 1]].forEach(function (d) {
          var i2 = i + d[0], j2 = j + d[1];
          if (i2 >= G.nc || j2 >= G.nr) return;
          if (S.hole && S.hole[0] === i2 && S.hole[1] === j2) return;
          if (S.moving && ((S.moving.from[0] === i2 && S.moving.from[1] === j2) || (S.moving.to[0] === i2 && S.moving.to[1] === j2))) return;
          if (S.sp[i][j] === S.sp[i2][j2]) seg(c, G.x(i) + d[0] * 6, G.y(j) + d[1] * 6, G.x(i2) - d[0] * 6, G.y(j2) - d[1] * 6);
        });
      }
      c.setLineDash([]);
      // sites and spins
      c.beginPath();
      for (i = 0; i < G.nc; i++) for (j = 0; j < G.nr; j++) { c.moveTo(G.x(i) + 1.6, G.y(j)); c.arc(G.x(i), G.y(j), 1.6, 0, TAU); }
      c.fillStyle = stAlpha(C.muted, 0.6); c.fill();
      var tryI = 1, tryJ = 1, push = tryOn * 0.42 * G.s;
      for (i = 0; i < G.nc; i++) for (j = 0; j < G.nr; j++) {
        if (S.moving && ((S.moving.from[0] === i && S.moving.from[1] === j) || (S.moving.to[0] === i && S.moving.to[1] === j))) continue;
        if (S.hole && S.hole[0] === i && S.hole[1] === j) {
          if (S.appear < 1) { c.globalAlpha = 1 - S.appear; spin(c, G.x(i), G.y(j), S.sp[i][j], 13, C.accent, 1.4); c.globalAlpha = 1; }
          continue;
        }
        var dx = tt < 4 && i === tryI && j === tryJ ? push : 0;
        spin(c, G.x(i) + dx, G.y(j), S.sp[i][j], 13, C.accent, 1.4);
      }
      if (S.moving) {
        var mx = G.x(S.moving.from[0]) + (G.x(S.moving.to[0]) - G.x(S.moving.from[0])) * S.moving.f;
        var my = G.y(S.moving.from[1]) + (G.y(S.moving.to[1]) - G.y(S.moving.from[1])) * S.moving.f;
        spin(c, mx, my, S.moving.ang, 13, C.accent, 1.4);
      }
      // the hole
      if (S.hole && S.appear > 0) {
        var hx = G.x(S.hole[0]), hy = G.y(S.hole[1]);
        if (S.moving) { hx = G.x(S.moving.to[0]) + (G.x(S.moving.from[0]) - G.x(S.moving.to[0])) * S.moving.f; hy = G.y(S.moving.to[1]) + (G.y(S.moving.from[1]) - G.y(S.moving.to[1])) * S.moving.f; }
        c.globalAlpha = S.appear; glow(c, hx, hy, 9, C.warm, 0.5); ring(c, hx, hy, 5, C.warm, 1.8, C.surface2); c.globalAlpha = 1;
      }
      // the blocked hop
      if (tt < 4 && tryOn > 0.55) warmTag(c, C, 'U', G.x(tryI) + G.s * 0.62, G.y(tryJ) - 12, stClamp((tryOn - 0.55) / 0.3));
      legendDraw(c, C, W - m - lw, H / 2, rows, 24);
    }

    /* 2. Resonating valence bonds: singlet bonds flip between horizontal and vertical pairs in each
       plaquette (resonance); doped holes then move as a pair as the singlets hop two sites into them. */
    var RVB_PH = (function () { var r = stRng(23), a = []; for (var i = 0; i < 40; i++) a.push(r()); return a; })();
    function drawRvb(c, C, W, H, t) {
      var P = 13, tt = md(t, P), m = 10;
      var doped = stSpan(tt, 6.2, 6.8) * (1 - stSpan(tt, 12.2, 12.8));
      function bond(x0, y0, x1, y1, a, color) {
        if (a <= 0.01) return;
        c.lineCap = 'round';
        c.lineWidth = 10; c.strokeStyle = stAlpha(color || C.accent, 0.2 * a); seg(c, x0, y0, x1, y1);
        c.lineWidth = 2; c.strokeStyle = stAlpha(color || C.accent, 0.85 * a); seg(c, x0, y0, x1, y1);
        c.lineCap = 'butt';
      }
      var rows = [
        { text: 'singlet (valence bond)', sw: function (x, y) { bond(x - 3, y, x + 3, y, 1); } },
        { text: 'bonds resonate', sw: function (x, y) { bond(x - 4, y - 3, x - 4, y + 3, 0.6); bond(x + 1, y, x + 6, y, 0.6); }, on: doped < 0.5 ? 1 : 0.4 },
        { text: 'holes move as a pair', sw: function (x, y) { ring(c, x - 3, y, 3, C.warm, 1.4); ring(c, x + 5, y, 3, C.warm, 1.4); }, on: doped }
      ];
      var lw = legendWidth(c, C, rows), right = W - m - lw - 14;
      var G = grid(m + 6, right, 20, 4, H / 2, 4, 10);
      if (G.nc % 2) G = grid(m + 6, right - 20, 20, 4, H / 2, 4, 10);
      var nPairs = G.nc / 2, i, j, b;
      // resonance weight per 2 x 2 plaquette: 0 = horizontal pair of bonds, 1 = vertical pair
      var top = stSpan(tt, 0.6, 1.2) * (1 - stSpan(tt, 5.6, 6.2));   // the top plaquette row stops flipping while the holes move in it
      function wOf(bi, bj) {
        var u = md(tt / 3.2 + RVB_PH[(bi * 5 + bj * 3) % RVB_PH.length], 1);
        var w = stSpan(u, 0.25, 0.4) - stSpan(u, 0.75, 0.9);
        return bj === 0 ? w * top : w;
      }
      // the hole pair in row 1 starts at the right end; singlets hop right into it one after another
      var hops = nPairs - 1, step = hops ? 4.2 / hops : 1, holeAt = nPairs - 1, mover = -1, f = 0, k;
      if (doped > 0) {
        for (k = 0; k < hops; k++) {
          var t0 = 7.0 + k * step, t1 = t0 + Math.min(0.7, step * 0.6);
          if (tt >= t1) holeAt = nPairs - 2 - k;
          else if (tt >= t0) { mover = nPairs - 2 - k; f = stSpan(tt, t0, t1); break; }
          else break;
        }
      }
      for (var bj = 0; bj < G.nr / 2; bj++) for (var bi = 0; bi < nPairs; bi++) {
        var w = wOf(bi, bj), x0 = G.x(2 * bi), x1 = G.x(2 * bi + 1), ya = G.y(2 * bj), yb = G.y(2 * bj + 1);
        // vertical bonds
        bond(x0, ya, x0, yb, w); bond(x1, ya, x1, yb, w);
        // horizontal bonds (the lower one in the top row takes part in the hole motion)
        bond(x0, ya, x1, ya, 1 - w);
        if (bj === 0 && tt >= 6.2 && tt < 12.8) {
          if (bi === mover) bond(x0 + f * 2 * G.s, yb, x1 + f * 2 * G.s, yb, 1, C.warm);
          else if (bi === holeAt) bond(x0, yb, x1, yb, 1 - doped);
          else if (!(mover >= 0 && bi === mover + 1)) bond(x0, yb, x1, yb, 1);
        } else bond(x0, yb, x1, yb, 1 - w);
      }
      // sites
      c.beginPath();
      for (i = 0; i < G.nc; i++) for (j = 0; j < G.nr; j++) { c.moveTo(G.x(i) + 2.6, G.y(j)); c.arc(G.x(i), G.y(j), 2.6, 0, TAU); }
      c.fillStyle = C.accent; c.fill();
      if (doped > 0) {
        // while a singlet slides into the hole pair, the holes fade out there and fade in where it left
        var spots = mover >= 0 ? [[mover + 1, 1 - f], [mover, f]] : [[holeAt, 1]];
        spots.forEach(function (sp) {
          c.globalAlpha = doped * sp[1];
          for (var q = 0; q < 2; q++) ring(c, G.x(sp[0] * 2) + q * G.s, G.y(1), 4.6, C.warm, 1.8, C.surface2);
        });
        c.globalAlpha = 1;
        if (mover < 0 && holeAt === nPairs - 1 && tt < 7.0) warmTag(c, C, '2 holes', G.x(holeAt * 2) + G.s / 2, G.y(1) - 14, stSpan(tt, 6.4, 6.8));
      }
      legendDraw(c, C, W - m - lw, H / 2, rows, 24);
    }

    /* 3. Zhang–Rice singlet: a hole on the four oxygens around a copper binds with the copper spin
       into a singlet, which then hops like a single vacancy (the t–J model). */
    function drawZr(c, C, W, H, t) {
      var P = 11, tt = md(t, P), m = 10;
      var rows = [
        { text: 'Cu spin', sw: function (x, y) { spin(c, x, y, UP, 12, C.accent, 1.4); } },
        { text: 'O site', sw: function (x, y) { ring(c, x, y, 3, C.muted, 1.2, C.surface); } },
        { text: 'Zhang–Rice singlet', sw: function (x, y) { stRound(c, x - 5, y - 5, 10, 10, 3); c.fillStyle = stAlpha(C.warm, 0.25); c.fill(); c.lineWidth = 1.4; c.strokeStyle = C.warm; c.stroke(); } },
        { text: 'hops like one hole', sw: function (x, y) { arrow(c, x + 6, y, x - 6, y, C.warm, 4.5, 1.4); } }
      ];
      var lw = legendWidth(c, C, rows), G = grid(m + 10, W - m - lw - 18, 30, 3, H / 2, 3, 8);
      var appear = stSpan(tt, 0.4, 1.4) * (1 - stSpan(tt, 10.0, 10.8));
      var nh = Math.max(1, G.nc - 2), hopD = 0.7, gap = nh > 1 ? Math.min(2.0, 7.2 / nh) : 2;
      var at = G.nc - 2, f = 0, k;
      for (k = 0; k < nh - 1; k++) {
        var t0 = 2.0 + k * gap;
        if (tt >= t0 + hopD) at = G.nc - 3 - k;
        else if (tt >= t0) { f = stSpan(tt, t0, t0 + hopD); break; }
        else break;
      }
      rows[2].on = appear; rows[3].on = f > 0 ? 1 : 0.3;
      var row = 1, i, j;
      // Cu–O bonds
      c.strokeStyle = C.grid; c.lineWidth = 1.2;
      for (j = 0; j < G.nr; j++) seg(c, G.x(0) - G.s / 2, G.y(j), G.x(G.nc - 1) + G.s / 2, G.y(j));
      for (i = 0; i < G.nc; i++) seg(c, G.x(i), G.y(0) - G.s / 2, G.x(i), G.y(G.nr - 1) + G.s / 2);
      // singlet position (between plaquettes while hopping)
      var sx = G.x(at) - f * G.s, sy = G.y(row), hs = G.s / 2;
      if (appear > 0) {
        c.globalAlpha = appear;
        c.beginPath(); c.moveTo(sx - hs, sy); c.lineTo(sx, sy - hs); c.lineTo(sx + hs, sy); c.lineTo(sx, sy + hs); c.closePath();
        c.fillStyle = stAlpha(C.warm, 0.2); c.fill(); c.lineWidth = 1.6; c.strokeStyle = C.warm; c.stroke();
        c.globalAlpha = 1;
      }
      // O sites; the four around the singlet carry the hole
      for (i = -1; i < G.nc; i++) for (j = 0; j < G.nr; j++) {
        var ox = G.x(i) + G.s / 2, oy = G.y(j);
        if (i >= 0 || true) {
          var near = appear > 0 && Math.abs(ox - sx) + Math.abs(oy - sy) < hs + 2;
          ring(c, ox, oy, 3.2, near ? C.warm : C.muted, 1.2, near ? stAlpha(C.warm, 0.55 * appear + 0.0) : C.surface);
        }
      }
      for (i = 0; i < G.nc; i++) for (j = -1; j < G.nr; j++) {
        var px = G.x(i), py = G.y(j) + G.s / 2;
        var near2 = appear > 0 && Math.abs(px - sx) + Math.abs(py - sy) < hs + 2;
        ring(c, px, py, 3.2, near2 ? C.warm : C.muted, 1.2, near2 ? stAlpha(C.warm, 0.55 * appear) : C.surface);
      }
      // Cu spins: the singlet site has none; while hopping, the neighbour's spin slides the other way
      for (i = 0; i < G.nc; i++) for (j = 0; j < G.nr; j++) {
        var ang = neel(i, j), x = G.x(i), y = G.y(j), L = 14;
        if (j === row && appear > 0) {
          if (i === at) { if (f > 0) continue; L = 14 * (1 - appear); }
          if (f > 0 && i === at - 1) { x = G.x(at - 1) + f * G.s; }
          if (i > at && i <= G.nc - 2) ang = neel(i - 1, j);   // spins the singlet has passed moved one site right
          if (f > 0 && i === at - 1) ang = neel(i, j);
        }
        dot(c, x, y, 4.2, stAlpha(C.accent, 0.18));
        spin(c, x, y, ang, L, C.accent, 1.4);
      }
      if (appear > 0.6 && f === 0 && tt < 2.0) warmTag(c, C, 'spin 0', sx, sy - hs - 9, stSpan(tt, 1.0, 1.4));
      legendDraw(c, C, W - m - lw, H / 2, rows, 22);
    }

    /* 4. Spin-fluctuation pairing: repulsive on one site, attractive on neighbouring sites, so the pair
       amplitude sits on the four neighbours with + along x and − along y (d-wave). */
    var SG_PH = (function () { var r = stRng(41), a = []; for (var i = 0; i < 64; i++) a.push(r() * TAU); return a; })();
    function drawSpinglue(c, C, W, H, t) {
      var P = 10, tt = md(t, P), m = 10;
      var lobes = stSpan(tt, 1.8, 2.8) * (1 - stSpan(tt, 9.2, 9.9));
      var rows = [
        { text: 'pair amplitude +', sw: function (x, y) { dot(c, x, y, 4, stAlpha(C.accent, 0.75)); } },
        { text: 'pair amplitude −', sw: function (x, y) { dot(c, x, y, 4, stAlpha(C.warm, 0.75)); } },
        { text: 'spin-fluctuation glue', sw: function (x, y) { c.beginPath(); c.arc(x - 5, y, 7, -0.8, 0.8); c.strokeStyle = C.muted; c.lineWidth = 1.2; c.stroke(); c.beginPath(); c.arc(x - 5, y, 11, -0.6, 0.6); c.stroke(); } }
      ];
      var lw = legendWidth(c, C, rows), G = grid(m + 4, W - m - lw - 12, 20, 5, H / 2, 5, 11);
      var ci = Math.floor(G.nc / 2), cj = 2, cx = G.x(ci), cy = G.y(cj), i, j;
      // spin-fluctuation ripples from the pair
      for (var r = 0; r < 3; r++) {
        var ph = md(tt / 2.4 + r / 3, 1), rad = 10 + ph * 46;
        c.beginPath(); c.arc(cx, cy, rad, 0, TAU);
        c.strokeStyle = stAlpha(C.muted, 0.35 * (1 - ph) * lobes); c.lineWidth = 1.2; c.stroke();
      }
      // antiferromagnetic background with a travelling spin wave
      for (i = 0; i < G.nc; i++) for (j = 0; j < G.nr; j++) {
        if (i === ci && j === cj) continue;
        var nb = Math.abs(i - ci) + Math.abs(j - cj) === 1;
        var ang = neel(i, j) + 0.32 * Math.sin(TAU * (tt / 2.4) - 0.55 * Math.hypot(i - ci, j - cj) + SG_PH[(i * 7 + j * 3) % 64] * 0.2);
        c.globalAlpha = nb ? 0.35 : 0.75;
        spin(c, G.x(i), G.y(j), ang, 11, C.ink2, 1.2);
        c.globalAlpha = 1;
      }
      // d-wave lobes on the four neighbours
      var nbs = [[1, 0, 1], [0, -1, -1], [-1, 0, 1], [0, 1, -1]], hopT = Math.max(0, tt - 3.0), cur = Math.floor(hopT / 0.9) % 4;
      nbs.forEach(function (n, k) {
        var x = G.x(ci + n[0]), y = G.y(cj + n[1]), col = n[2] > 0 ? C.accent : C.warm;
        var hot = tt > 3.0 && tt < 9.2 && k === cur ? 1 : 0;
        if (lobes > 0) {
          c.beginPath(); c.ellipse(x, y, (n[0] ? 8.5 : 6.5) * lobes, (n[0] ? 6.5 : 8.5) * lobes, 0, 0, TAU);
          c.fillStyle = stAlpha(col, 0.28 + 0.3 * hot); c.fill();
          label(c, C, n[2] > 0 ? '+' : '−', x + n[0] * 0 + (n[1] ? 10 : 0), y + (n[0] ? -9 : 0) + 0.5, { size: 11, weight: '700', align: 'center', base: 'middle', color: col });
        }
        if (hot) { dot(c, x, y, 3.6, C.ink); }
      });
      // the electron in the middle, and the empty same-site slot (on-site repulsion U)
      glow(c, cx, cy, 9, C.ink2, 0.25);
      dot(c, cx, cy, 3.6, C.ink);
      if (tt > 0.3 && tt < 1.9) warmTag(c, C, 'not on one site', cx, cy - 17, stSpan(tt, 0.3, 0.7) * (1 - stSpan(tt, 1.5, 1.9)));
      legendDraw(c, C, W - m - lw, H / 2, rows, 24);
    }

    /* 5. Stripes: rivers of holes separate antiferromagnetic domains whose spin pattern flips across each
       river; the rivers meander and slide. */
    function drawStripes(c, C, W, H, t) {
      var P = 16, tt = md(t, P), m = 10;
      var rows = [
        { text: 'charge stripe (holes)', sw: function (x, y) { c.fillStyle = stAlpha(C.warm, 0.22); c.fillRect(x - 3, y - 7, 6, 14); dot(c, x, y, 2.6, C.warm); } },
        { text: 'spins flip across it', sw: function (x, y) { spin(c, x - 3, y, UP, 10, C.accent, 1.3); spin(c, x + 4, y, UP, 10, C.accent, 1.3); } },
        { text: 'strongest near p = 1/8', sw: null }
      ];
      var lw = legendWidth(c, C, rows), s = 17;
      var G = grid(m + 4, W - m - lw - 18, s, 5, H / 2, 7, 18), i, j;
      var period = 4, drift = tt / P * period;   // slide by one period per loop
      function stripeX(k, y) { return G.ox + (k * period + 1.5 + drift) * s + 0.28 * s * Math.sin(TAU * (y / 70 + tt / 4 + k * 0.37)); }
      var nk = Math.ceil(G.nc / period) + 2;
      // bands and holes
      for (var k = -1; k < nk; k++) {
        var pts = [];
        for (j = -1; j <= G.nr; j += 0.25) pts.push([stripeX(k, G.y(j)), G.y(j)]);
        c.save(); c.beginPath(); c.rect(G.ox - s * 0.45, G.oy - s * 0.7, (G.nc - 1) * s + s * 0.9, (G.nr - 1) * s + s * 1.4); c.clip();
        c.beginPath(); pts.forEach(function (p, q) { if (q) c.lineTo(p[0], p[1]); else c.moveTo(p[0], p[1]); });
        c.lineWidth = s * 0.8; c.strokeStyle = stAlpha(C.warm, 0.16); c.stroke();
        for (j = 0; j < G.nr; j++) {
          var hx = stripeX(k, G.y(j));
          if (hx > G.ox - s * 0.4 && hx < G.ox + (G.nc - 1) * s + s * 0.4) dot(c, hx, G.y(j), 2.8, stAlpha(C.warm, 0.9));
        }
        c.restore();
      }
      // spins: staggered pattern times a sign that flips across every stripe, shrinking near a stripe
      for (i = 0; i < G.nc; i++) for (j = 0; j < G.nr; j++) {
        var x = G.x(i), y = G.y(j), mag = 1;
        for (var k2 = -1; k2 < nk; k2++) mag *= Math.tanh((x - stripeX(k2, y)) / (0.42 * s));
        var sgn = mag >= 0 ? 1 : -1, L = 13 * Math.pow(Math.abs(mag), 0.8);
        var ang = neel(i, j) === UP ? (sgn > 0 ? UP : DOWN) : (sgn > 0 ? DOWN : UP);
        spin(c, x, y, ang, L, C.accent, 1.3);
      }
      legendDraw(c, C, W - m - lw, H / 2, rows, 24);
    }

    /* 6. Phase fluctuations: as the sample cools, pairs form below T* with random phases, and the phases
       lock together only below Tc. */
    var PH = (function () { var r = stRng(77), a = []; for (var i = 0; i < 48; i++) a.push({ th: r() * TAU, w: (r() - 0.5) * 2.4, ex: r() * TAU, ey: r() * TAU, sp: 0.6 + r() }); return a; })();
    function phaseTemp(tt) {   // temperature in units where Tc = 1 and T* = 2.4
      var k = [[0, 3.4], [2.2, 3.4], [3.6, 1.7], [6.6, 1.7], [7.8, 0.45], [11.2, 0.45], [13.6, 3.4], [14, 3.4]];
      for (var i = 0; i < k.length - 1; i++) if (tt <= k[i + 1][0]) return k[i][1] + (k[i + 1][1] - k[i][1]) * stEase((tt - k[i][0]) / (k[i + 1][0] - k[i][0]));
      return 3.4;
    }
    function drawPhase(c, C, W, H, t) {
      var P = 14, tt = md(t, P), m = 10, T = phaseTemp(tt);
      var paired = stClamp((2.4 - T) / 0.35 + 0.5), order = stClamp((1 - T) / 0.25 + 0.5);
      var state = T > 2.4 ? 'no pairs yet' : T > 1 ? 'pairs, random phases' : 'phases lock: superconductor';
      // thermometer column
      var tw = 52, tx = W - m - tw + 10, ty0 = 16, ty1 = H - 16;
      function TY(v) { return ty1 - v / 3.6 * (ty1 - ty0); }
      stRound(c, tx - 3, ty0, 6, ty1 - ty0, 3); c.fillStyle = C.surface; c.fill(); c.lineWidth = 1; c.strokeStyle = C.axis; c.stroke();
      c.fillStyle = stAlpha(T > 1 ? C.warm : C.accent, 0.7); c.fillRect(tx - 1.5, TY(T), 3, ty1 - TY(T));
      [[2.4, 'pair'], [1, 'c']].forEach(function (q) {
        c.strokeStyle = C.ink2; c.lineWidth = 1; seg(c, tx + 4, TY(q[0]), tx + 8, TY(q[0]));
        stSym(c, C, [['T'], [q[1], 1]], tx + 11, TY(q[0]) + 4, { size: 11, color: C.ink2 });
      });
      dot(c, tx, TY(T), 4, T > 1 ? C.warm : C.accent, C.surface2);
      // pairs on a grid
      var x0 = m + 6, x1 = tx - 22, s = 30, nr = 3;
      var nc = Math.max(3, Math.min(10, Math.floor((x1 - x0) / s) + 1)), ox = x0 + (x1 - x0 - (nc - 1) * s) / 2, oy = 22;
      for (var i = 0; i < nc; i++) for (var j = 0; j < nr; j++) {
        var p = PH[(i * 5 + j * 11) % PH.length], cx = ox + i * s, cy = oy + j * 28;
        // two electrons: wander apart when unpaired, bind into a dumbbell when paired
        var wob = 1 - paired, jx = 7 * wob * Math.sin(tt * 2.1 * p.sp + p.ex), jy = 6 * wob * Math.cos(tt * 1.7 * p.sp + p.ey);
        var th = p.th + p.w * tt, ux = Math.cos(th), uy = Math.sin(th);
        var vx = (1 - order) * ux, vy = (1 - order) * uy - order, vl = Math.hypot(vx, vy) || 1;
        vx /= vl; vy /= vl;
        var ax = -vy * 4.2, ay = vx * 4.2;   // dumbbell perpendicular to the phase arrow
        var e1x = cx + ax * paired + (1 - paired) * (-6 + jx), e1y = cy + ay * paired + (1 - paired) * (jy - 3);
        var e2x = cx - ax * paired + (1 - paired) * (6 - jy), e2y = cy - ay * paired + (1 - paired) * (jx * 0.6 + 3);
        if (paired > 0.05) { c.globalAlpha = paired; c.strokeStyle = stAlpha(C.ink2, 0.6); c.lineWidth = 1.2; seg(c, e1x, e1y, e2x, e2y); c.globalAlpha = 1; }
        dot(c, e1x, e1y, 2.6, C.ink2); dot(c, e2x, e2y, 2.6, C.ink2);
        if (paired > 0.05) { c.globalAlpha = paired; arrow(c, cx - vx * 2, cy - vy * 2, cx + vx * 11, cy + vy * 11, order > 0.5 ? C.accent : C.warm, 4.5, 1.5); c.globalAlpha = 1; }
      }
      stTag(c, C, state, (x0 + x1) / 2, H - 12, { size: 10.5, pad: 6, bg: C.surface, ring: order > 0.5 ? C.accent : paired > 0.5 ? C.warm : C.axis, color: C.ink });
    }

    /* 7. Bipolarons: each electron pulls the nearby ions in (a polaron); two electrons then share one
       distortion and travel together as a bound pair. */
    function drawBipolaron(c, C, W, H, t) {
      var P = 12, tt = md(t, P), m = 10;
      var bind = stSpan(tt, 3.6, 5.6) * (1 - stSpan(tt, 11.0, 11.9));
      var rows = [
        { text: 'ions pulled in', sw: function (x, y) { dot(c, x - 4, y, 2.4, C.muted); arrow(c, x - 1, y, x + 7, y, C.ink2, 3.5, 1.1); } },
        { text: 'polaron: e + its dent', sw: function (x, y) { glow(c, x, y, 7, C.accent, 0.5); dot(c, x, y, 2.8, C.accent); }, on: 1 - bind },
        { text: 'bipolaron: one dent', sw: function (x, y) { ring(c, x, y, 7, C.warm, 1.4); dot(c, x - 3, y, 2.4, C.accent); dot(c, x + 3, y, 2.4, C.accent); }, on: bind }
      ];
      var lw = legendWidth(c, C, rows), x0 = m + 6, x1 = W - m - lw - 12, s = 17;
      var G = grid(x0, x1, s, 5, H / 2, 6, 16), wide = (G.nc - 1) * s;
      // electron paths: slow and apart, then together, then moving as one
      var mid = G.ox + wide * (0.5 + 0.18 * Math.sin(TAU * tt / P)), apart = wide * 0.34 * (1 - bind) + 5.5 * bind;
      var cy = G.y(2) + 0.5 * s * Math.sin(TAU * tt / 6);
      var drift = bind > 0.99 ? wide * 0.12 * Math.sin(TAU * (tt - 5.6) / 5.4) : 0;
      var es = [[mid - apart + drift, cy + (1 - bind) * 0.6 * s * Math.sin(tt * 1.3)], [mid + apart + drift, cy - (1 - bind) * 0.6 * s * Math.sin(tt * 1.1 + 1)]];
      // dents
      es.forEach(function (e) { glow(c, e[0], e[1], 15, C.accent, 0.32 * (1 - 0.7 * bind)); });
      var close = stClamp((bind - 0.55) / 0.35);
      if (close > 0) glow(c, (es[0][0] + es[1][0]) / 2, (es[0][1] + es[1][1]) / 2, 22, C.accent, 0.38 * close);
      // ions, displaced toward the electrons
      c.beginPath();
      for (var i = 0; i < G.nc; i++) for (var j = 0; j < G.nr; j++) {
        var x = G.x(i), y = G.y(j), dx = 0, dy = 0;
        es.forEach(function (e) {
          var rx = e[0] - x, ry = e[1] - y, r2 = rx * rx + ry * ry, r = Math.sqrt(r2) || 1, pull = (3.4 + 1.6 * bind) * Math.exp(-r2 / (2 * 15 * 15)) * stClamp((r - 5) / 9);
          dx += rx / r * pull; dy += ry / r * pull;
        });
        c.moveTo(x + dx + 2.4, y + dy); c.arc(x + dx, y + dy, 2.4, 0, TAU);
      }
      c.fillStyle = C.muted; c.fill();
      if (close > 0) { c.globalAlpha = close; ring(c, (es[0][0] + es[1][0]) / 2, (es[0][1] + es[1][1]) / 2, 12, C.warm, 1.6); c.globalAlpha = 1; }
      es.forEach(function (e) { dot(c, e[0], e[1], 3.4, C.accent); });
      legendDraw(c, C, W - m - lw, H / 2, rows, 24);
    }

    /* 8. Strange metal: resistivity linear in T down to Tc (and extrapolating to zero at T = 0), against
       the T² of an ordinary metal; superconductivity takes over below Tc. */
    function drawStrange(c, C, W, H, t) {
      var P = 10, tt = md(t, P), m = 10;
      var rows = [
        { text: 'strange metal: ρ ∝ T', sw: function (x, y) { c.strokeStyle = C.warm; c.lineWidth = 2; seg(c, x - 6, y + 3, x + 6, y - 3); } },
        { text: 'Fermi liquid: ρ ∝ T²', sw: function (x, y) { c.strokeStyle = C.ink2; c.lineWidth = 1.4; c.setLineDash([3, 2]); c.beginPath(); c.moveTo(x - 6, y + 3); c.quadraticCurveTo(x + 2, y + 3, x + 6, y - 4); c.stroke(); c.setLineDash([]); } },
        { text: 'scattering ħ/τ ≈ kT', parts: [['scattering ħ/τ ≈ k'], ['B', 1], [' T']], sw: null }
      ];
      var lw = legendWidth(c, C, rows), px0 = m + 16, px1 = W - m - lw - 12, py0 = 14, py1 = H - 22, Tc = 90;
      function X(T) { return px0 + T / 300 * (px1 - px0); }
      function Y(r) { return py1 - r * (py1 - py0); }
      c.strokeStyle = C.axis; c.lineWidth = 1; seg(c, px0, py0, px0, py1); seg(c, px0, py1, px1, py1);
      label(c, C, 'ρ', px0 - 6, py0 + 6, { size: 11, align: 'right', color: C.muted });
      label(c, C, 'T', px1, py1 + 14, { size: 11, align: 'right', color: C.muted });
      stSym(c, C, [['T'], ['c', 1]], X(Tc), py1 + 14, { size: 11, align: 'center', color: C.ink2 });
      c.setLineDash([2, 3]); c.strokeStyle = C.grid; seg(c, X(Tc), py0 + 6, X(Tc), py1); c.setLineDash([]);
      // ordinary metal for comparison
      c.beginPath();
      for (var i = 0; i <= 40; i++) { var T1 = 300 * i / 40, r1 = 0.05 + 0.85 * Math.pow(T1 / 300, 2); if (i) c.lineTo(X(T1), Y(r1)); else c.moveTo(X(T1), Y(r1)); }
      c.strokeStyle = C.ink2; c.lineWidth = 1.3; c.setLineDash([3, 2]); c.stroke(); c.setLineDash([]);
      // strange metal: linear, with the extrapolation to zero below Tc dotted
      c.strokeStyle = stAlpha(C.warm, 0.5); c.lineWidth = 1.2; c.setLineDash([1.5, 3]); seg(c, X(0), Y(0), X(Tc), Y(0.9 * Tc / 300)); c.setLineDash([]);
      c.strokeStyle = C.warm; c.lineWidth = 2;
      c.beginPath(); c.moveTo(X(0), Y(0)); c.lineTo(X(Tc - 4), Y(0)); c.lineTo(X(Tc + 2), Y(0.9 * (Tc + 2) / 300)); c.lineTo(X(300), Y(0.9)); c.stroke();
      // a probe sweeping down in temperature and back
      var T = 300 - 280 * (0.5 - 0.5 * Math.cos(TAU * tt / P)), r = T < Tc - 2 ? 0 : 0.9 * T / 300;
      dot(c, X(T), Y(r), 4.2, C.warm, C.surface2);
      if (T < Tc - 2) stTag(c, C, 'ρ = 0', X(T), Y(0) - 15, { size: 10, pad: 4, bg: stAlpha(C.accent, 0.16), ring: C.accent, color: C.ink });
      legendDraw(c, C, W - m - lw, H / 2, rows, 24);
    }

    /* 9. Overview: the cuprate phase diagram (schematic), with a doping probe that names the idea
       that addresses each region. Drawn on a taller canvas. */
    var CU = [
      [0.03, 'Mott insulator', 'Hubbard model, t–J'],
      [0.10, 'Pseudogap', 'RVB, preformed pairs'],
      [0.14, 'Stripes near p = 1/8', 'intertwined orders'],
      [0.20, 'd-wave dome', 'spin fluctuations'],
      [0.25, 'Strange metal', 'quantum criticality'],
      [0.31, 'Fermi liquid', 'ordinary metal']
    ];
    function cuTc(p) { var v = 95 * (1 - 82.6 * (p - 0.16) * (p - 0.16)); return v > 0 ? v : 0; }
    function cuTN(p) { var v = 330 * (1 - Math.pow(p / 0.027, 2)); return v > 0 ? v : 0; }
    function cuTs(p) { return p < 0.19 ? 360 * (1 - p / 0.19) : 0; }
    function cuCO(p) { var v = 150 * (1 - Math.pow((p - 0.12) / 0.045, 2)); return v > 0 ? Math.min(v, cuTs(p)) : 0; }
    function cuFL(p) { return p > 0.19 ? 1500 * (p - 0.19) : 0; }
    function drawCuprate(c, C, W, H, t) {
      var P = 26, tt = md(t, P), m = 10;
      var x0 = m + 30, x1 = W - m - 6, y0 = 46, y1 = H - 38;
      function X(p) { return x0 + p / 0.3 * (x1 - x0); }
      function Y(T) { return y1 - T / 400 * (y1 - y0); }
      function area(f, color, a, from, to) {
        c.beginPath(); c.moveTo(X(from), Y(0));
        for (var i = 0; i <= 120; i++) { var p = from + (to - from) * i / 120; c.lineTo(X(p), Y(f(p))); }
        c.lineTo(X(to), Y(0)); c.closePath(); c.fillStyle = stAlpha(color, a); c.fill();
      }
      // probe position: dwell at the centre of each region
      var stops = [0.012, 0.07, 0.12, 0.165, 0.225, 0.28], dwell = P / stops.length, k = Math.floor(tt / dwell), f = stSpan(tt - k * dwell, dwell * 0.72, dwell);
      var pm = stops[k] + (stops[(k + 1) % stops.length] - stops[k]) * f, reg = 0;
      while (reg < CU.length - 1 && pm > CU[reg][0]) reg++;
      c.save(); c.beginPath(); c.rect(x0, y0 - 4, x1 - x0, y1 - y0 + 4); c.clip();
      // strange metal: the fan above T* and the Fermi-liquid crossover, narrowing to the critical point
      c.beginPath(); c.moveTo(X(0.19), Y(0)); c.lineTo(X(0), Y(360)); c.lineTo(X(0), Y(420)); c.lineTo(X(0.3), Y(420)); c.lineTo(X(0.3), Y(cuFL(0.3)));
      c.closePath(); c.fillStyle = stAlpha(C.warm, reg === 4 ? 0.2 : 0.09); c.fill();
      // pseudogap: under T* and above the other phases
      area(cuTs, C.muted, reg === 1 ? 0.26 : 0.13, 0, 0.19);
      area(cuTN, C.ink2, reg === 0 ? 0.5 : 0.3, 0, 0.027);
      area(cuCO, C.gold || C.warm, reg === 2 ? 0.5 : 0.28, 0.075, 0.165);
      area(cuTc, C.accent, reg === 3 ? 0.55 : 0.36, 0.05, 0.27);
      // lines: T* and the Fermi-liquid crossover
      c.setLineDash([4, 3]); c.lineWidth = 1.2; c.strokeStyle = C.ink2;
      c.beginPath(); c.moveTo(X(0.0), Y(360)); c.lineTo(X(0.19), Y(0)); c.stroke();
      c.beginPath(); c.moveTo(X(0.19), Y(0)); c.lineTo(X(0.3), Y(cuFL(0.3))); c.stroke();
      c.setLineDash([]);
      c.restore();
      dot(c, X(0.19), Y(0), 3, C.ink2);
      // axes
      c.strokeStyle = C.axis; c.lineWidth = 1; seg(c, x0, y0, x0, y1); seg(c, x0, y1, x1, y1);
      [0, 0.1, 0.2, 0.3].forEach(function (p) { seg(c, X(p), y1, X(p), y1 + 3); label(c, C, String(p), X(p), y1 + 14, { size: 10.5, align: 'center', color: C.muted }); });
      [100, 200, 300].forEach(function (T) { seg(c, x0 - 3, Y(T), x0, Y(T)); label(c, C, String(T), x0 - 5, Y(T) + 3.5, { size: 10.5, align: 'right', color: C.muted }); });
      label(c, C, 'T (K)', x0 - 5, y0 - 8, { size: 10.5, align: 'right', color: C.muted });
      label(c, C, 'holes per Cu, p', x1, y1 + 28, { size: 10.5, align: 'right', color: C.muted });
      // region labels (only where they fit)
      var narrow = W < 380;
      function rl(text, p, T, align, on) { label(c, C, text, X(p), Y(T), { size: 10.5, align: align || 'center', weight: on ? '600' : '400', color: on ? C.ink : C.ink2 }); }
      rl('AF', 0.012, 215, 'center', reg === 0);
      rl('pseudogap', narrow ? 0.085 : 0.09, 205, 'center', reg === 1);
      rl(narrow ? 'stripes' : 'stripes, charge order', 0.12, 110, 'center', reg === 2);
      rl('d-wave SC', 0.16, 36, 'center', reg === 3);
      rl('strange metal', 0.2, 330, 'center', reg === 4);
      rl(narrow ? 'Fermi liq.' : 'Fermi liquid', 0.298, 50, 'right', reg === 5);
      label(c, C, 'QCP?', X(0.19) + 5, Y(0) - 5, { size: 10, color: C.muted });
      // the probe
      c.strokeStyle = stAlpha(C.ink, 0.55); c.lineWidth = 1.2; c.setLineDash([2, 2]); seg(c, X(pm), y0 + 2, X(pm), y1); c.setLineDash([]);
      dot(c, X(pm), y1, 4, C.ink, C.surface2);
      var cap = CU[reg][1] + ' · ' + CU[reg][2];
      if (textW(c, C, cap, 11.5, '600') > W - 2 * m - 16) cap = CU[reg][1];
      stTag(c, C, cap, m + 2, 14, { align: 'left', size: 11.5, pad: 7, bg: C.surface, ring: C.axis, color: C.ink });
    }

    MINI_DRAW.mott = guard(drawMott); MINI_DRAW.rvb = guard(drawRvb); MINI_DRAW.zr = guard(drawZr);
    MINI_DRAW.spinglue = guard(drawSpinglue); MINI_DRAW.stripes = guard(drawStripes); MINI_DRAW.phase = guard(drawPhase);
    MINI_DRAW.bipolaron = guard(drawBipolaron); MINI_DRAW.strange = guard(drawStrange); MINI_DRAW.cupratepd = guard(drawCuprate);
    MINI_STATIC.mott = 7.1; MINI_STATIC.rvb = 1.0; MINI_STATIC.zr = 1.9; MINI_STATIC.spinglue = 3.4; MINI_STATIC.stripes = 2.0;
    MINI_STATIC.phase = 5.5; MINI_STATIC.bipolaron = 7.0; MINI_STATIC.strange = 3.0; MINI_STATIC.cupratepd = 13.5;
    MINI_ALT.mott = 'A square lattice of alternating up and down spins, one electron per site. An electron tries to hop onto an occupied neighbour and is pushed back by the repulsion U. Then a doped hole moves through the lattice, and the spins it shifts end up on the wrong sublattice, leaving a trail of frustrated bonds that heals as the hole retraces its path.';
    MINI_ALT.rvb = 'Neighbouring spins form singlet bonds that flip between a horizontal and a vertical arrangement, a resonating valence bond state. Two doped holes then appear in one row, and the singlets hop two sites at a time into them, so the hole pair moves along the row as a charged pair.';
    MINI_ALT.zr = 'A copper–oxygen plane with copper spins on a square lattice and oxygen sites between them. A doped hole spreads over the four oxygens around one copper and binds with its spin into a Zhang–Rice singlet of spin zero, which then hops from plaquette to plaquette while the neighbouring copper spin moves the other way, like a single hole in the t–J model.';
    MINI_ALT.spinglue = 'An electron sits on one site of a fluctuating antiferromagnet, with ripples of spin fluctuations spreading out. Its partner cannot share the site; instead the pair amplitude sits on the four neighbours, positive to the left and right and negative above and below, and the partner visits them in turn: d-wave pairing.';
    MINI_ALT.stripes = 'Vertical rivers of holes meander and slide through a square lattice of antiferromagnetic spins. Across each river the spin pattern flips, and spins next to a river shrink, the stripe order strongest near one-eighth doping.';
    MINI_ALT.phase = 'The preformed-pair picture: a thermometer cools and warms a grid of electrons. Above a pairing temperature the electrons wander alone. Between Tc and that temperature they bind into pairs whose phase arrows point every which way. Below Tc all the phase arrows line up and the sample superconducts.';
    MINI_ALT.bipolaron = 'Two electrons move through a lattice of ions, each pulling nearby ions inward into a dent of its own. They then fall into one shared dent and travel together as a bound pair, a bipolaron.';
    MINI_ALT.strange = 'Resistivity against temperature: the strange metal is a straight line all the way down to Tc that would extrapolate to zero at zero temperature, while a Fermi-liquid metal bends over as T squared at low temperature. A probe sweeps down in temperature and the resistivity drops to zero at Tc.';
    MINI_ALT.cupratepd = 'A schematic cuprate phase diagram of temperature against hole doping, with the antiferromagnetic Mott insulator near zero doping, the pseudogap under the T* line, a small charge-stripe dome near one-eighth, the d-wave superconducting dome, a strange-metal fan above a possible quantum critical point near p = 0.19, and the Fermi liquid at high doping. A probe moves across and names the idea that addresses each region.';
  })();

};
