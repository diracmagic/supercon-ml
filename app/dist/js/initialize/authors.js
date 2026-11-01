'use strict';
// authors: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconAuthors = function initializeSuperconAuthors() {


  /* ---------- Authors: the people behind the project. progress.json can list more ("authors") without a new app release ---------- */
  // who the authors are stays hidden for now: none are built in, and progress.json "authors" can list them again later
  AUTHORS = [];

  EMAIL_OK = /^[^\s@<>()"',;:\\]+@[^\s@<>()"',;:\\]+\.[A-Za-z]{2,}$/;


  // Every author gets a pencil sketch of a tree, grown from a seed (their name unless progress.json picks one). It is drawn
  // stroke by stroke: construction lines, ground, trunk, branches, canopy and shading. Then the tree sways in a breeze and an
  // autumn leaf falls now and then. Coordinates are on a 100 × 100 sheet.
  makeTree = (function () {
    function plen(P) { var L = 0; for (var i = 1; i < P.length; i++) L += Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]); return L; }
    function mk(pts, a, w) { var L = plen(pts); return { pts: pts, len: L, a: a, w: w, ph: (pts.length * 0.37 + L) % 6.28 }; }
    function quad(x0, y0, cx, cy, x1, y1, n) {
      var P = [];
      for (var k = 0; k <= n; k++) { var u = k / n, v = 1 - u; P.push([v * v * x0 + 2 * v * u * cx + u * u * x1, v * v * y0 + 2 * v * u * cy + u * u * y1]); }
      return P;
    }
    function wob(st, i, pass) {
      return [0.26 * Math.sin(i * 0.83 + st.ph + pass * 2.3) + pass * 0.36, 0.26 * Math.cos(i * 0.61 + st.ph * 1.7 + pass * 1.1) + pass * 0.24];
    }
    // Draw the first `prog` (0–1) of a stroke in two pencil passes through the map M(x, y) -> [px, py]; returns the pencil tip.
    function draw(c, st, prog, M, S, ink, alpha) {
      if (prog <= 0 || st.len <= 0) return null;
      var P = st.pts, target = Math.min(1, prog) * st.len, tip = null;
      for (var pass = 0; pass < 2; pass++) {
        var acc = 0;
        c.beginPath();
        for (var i = 0; i < P.length; i++) {
          var p = P[i];
          if (i) {
            var q = P[i - 1], seg = Math.hypot(p[0] - q[0], p[1] - q[1]);
            if (acc + seg >= target) { var f = seg ? (target - acc) / seg : 0; p = [q[0] + (p[0] - q[0]) * f, q[1] + (p[1] - q[1]) * f]; acc = target; }
            else acc += seg;
          }
          var o = wob(st, i, pass), m = M(p[0] + o[0], p[1] + o[1]);
          if (i) c.lineTo(m[0], m[1]); else c.moveTo(m[0], m[1]);
          if (!pass) tip = m;
          if (i && acc >= target) break;
        }
        c.strokeStyle = stAlpha(ink, st.a * alpha * (pass ? 0.38 : 0.92));
        c.lineWidth = S * st.w * (pass ? 0.7 : 1.05);
        c.stroke();
      }
      return tip;
    }
    function pencil(c, C, x, y, S, a) {
      if (a <= 0) return;
      c.save();
      c.globalAlpha *= a;
      c.translate(x, y); c.rotate(-0.95);
      var u = S * 1.15;
      c.beginPath(); c.moveTo(0, 0); c.lineTo(3.4 * u, -1.35 * u); c.lineTo(3.4 * u, 1.35 * u); c.closePath(); c.fillStyle = mix(C.warm, '#ffffff', 0.6); c.fill();
      c.beginPath(); c.moveTo(0, 0); c.lineTo(1.2 * u, -0.48 * u); c.lineTo(1.2 * u, 0.48 * u); c.closePath(); c.fillStyle = C.ink; c.fill();
      c.fillStyle = C.warm; c.fillRect(3.4 * u, -1.35 * u, 11 * u, 2.7 * u);
      c.fillStyle = C.muted; c.fillRect(14.4 * u, -1.35 * u, 2 * u, 2.7 * u);
      c.fillStyle = mix(C.warm, '#ffffff', 0.35); c.fillRect(16.4 * u, -1.35 * u, 1.6 * u, 2.7 * u);
      c.restore();
    }
    function inside(P, x, y) {
      var a = false;
      for (var i = 0, j = P.length - 1; i < P.length; j = i++) {
        if ((P[i][1] > y) !== (P[j][1] > y) && x < (P[j][0] - P[i][0]) * (y - P[i][1]) / (P[j][1] - P[i][1]) + P[i][0]) a = !a;
      }
      return a;
    }
    function path(c, P, M) { P.forEach(function (p, k) { var m = M(p[0], p[1]); if (k) c.lineTo(m[0], m[1]); else c.moveTo(m[0], m[1]); }); c.closePath(); }

    return function (seed) {
      var rng = stRng(seed * 7919 + 13), i, j;
      var GROUND = 87, base = [50 + (rng() - 0.5) * 2.4, GROUND], fork = [base[0] + (rng() - 0.5) * 3, 65 + rng() * 2];
      // canopy: a rounded crown of leaf masses
      var ccx = 50 + (rng() - 0.5) * 3, ccy = 33 + (rng() - 0.5) * 2, rx = 25 + rng() * 3, ry = 20.5 + rng() * 2.5;
      var CL = [[ccx, ccy + 1, 12.5]], nRing = 11, a0 = rng() * 6.28;
      for (i = 0; i < nRing; i++) {
        var aa = a0 + i / nRing * Math.PI * 2 + (rng() - 0.5) * 0.25, rr = 0.7 + rng() * 0.1;
        CL.push([ccx + Math.cos(aa) * rx * rr, ccy + Math.sin(aa) * ry * rr, 7.2 + rng() * 2.6]);
      }
      for (i = 0; i < 4; i++) { var ai = rng() * 6.28, ri = 0.35 + rng() * 0.2; CL.push([ccx + Math.cos(ai) * rx * ri, ccy + Math.sin(ai) * ry * ri, 8 + rng() * 2]); }
      function inCanopy(x, y) { for (var k = 0; k < CL.length; k++) { var dx = x - CL[k][0], dy = y - CL[k][1]; if (dx * dx + dy * dy < CL[k][2] * CL[k][2]) return true; } return false; }
      var CAN = [], R0 = [], TH = [], ph = rng() * 6.28;
      for (i = 0; i < 180; i++) {
        var th = -Math.PI / 2 + i / 180 * Math.PI * 2, r = 46;
        while (r > 2 && !inCanopy(ccx + Math.cos(th) * r, ccy + Math.sin(th) * r)) r -= 0.2;
        TH.push(th); R0.push(r);
        r += 0.45 * Math.abs(Math.sin(th * 17 + ph)) - 0.2;
        CAN.push([ccx + Math.cos(th) * r, ccy + Math.sin(th) * r]);
      }
      CAN.push(CAN[0].slice());
      var CANOPY = mk(CAN, 0.9, 1.05);
      // the leafy edge as the wind passes: the small scallops shift a little
      function rustle(w) {
        for (var k = 0; k < 180; k++) {
          var r1 = R0[k] + 0.45 * Math.abs(Math.sin(TH[k] * 17 + ph + w * Math.sin(TH[k] * 3 + w))) - 0.2;
          CANOPY.pts[k][0] = ccx + Math.cos(TH[k]) * r1; CANOPY.pts[k][1] = ccy + Math.sin(TH[k]) * r1;
        }
        CANOPY.pts[180][0] = CANOPY.pts[0][0]; CANOPY.pts[180][1] = CANOPY.pts[0][1];
      }
      var bottom = 0; CAN.forEach(function (q) { if (Math.abs(q[0] - ccx) < 6) bottom = Math.max(bottom, q[1]); });
      // trunk: two tapering edges, a little root flare and some bark
      var bend = (rng() - 0.5) * 2.6, cx0 = (base[0] + fork[0]) / 2 + bend, cy0 = (GROUND + fork[1]) / 2;
      var TRUNK = [
        mk(quad(base[0] - 3.4, GROUND, cx0 - 2.6, cy0, fork[0] - 2.1, fork[1], 10), 0.92, 1.1),
        mk(quad(base[0] + 3.4, GROUND, cx0 + 2.6, cy0, fork[0] + 2.1, fork[1], 10), 0.92, 1.1),
        mk(quad(base[0] - 3.4, GROUND, base[0] - 4.6, GROUND - 0.2, base[0] - 6.4, GROUND + 0.6, 6), 0.8, 1),
        mk(quad(base[0] + 3.4, GROUND, base[0] + 4.6, GROUND - 0.2, base[0] + 6.6, GROUND + 0.6, 6), 0.8, 1)
      ];
      var BARK = [];
      for (i = 0; i < 4; i++) {
        var bx = base[0] - 1.5 + i * 1.05 + (rng() - 0.5) * 0.5, by0 = GROUND - 2.5 - rng() * 6, by1 = by0 - 4 - rng() * 6;
        BARK.push(mk(quad(bx, by0, bx + (rng() - 0.5) * 1.2, (by0 + by1) / 2, bx + (rng() - 0.5) * 0.7, by1, 6), 0.32, 0.8));
      }
      // limbs: from the fork into the crown, with a twig or two; most of them end up behind the leaves
      var BR = [];
      [[-0.62, 1.9], [0.05, 2.1], [0.6, 1.8]].forEach(function (L) {
        var ang = -Math.PI / 2 + L[0] + (rng() - 0.5) * 0.2, len = (fork[1] - ccy) * (L[0] ? 0.78 : 0.9) + rng() * 3;
        var x1 = fork[0] + Math.cos(ang) * len, y1 = fork[1] + Math.sin(ang) * len, bb = (rng() - 0.5) * 3;
        var st = mk(quad(fork[0] + L[0] * 1.6, fork[1], (fork[0] + x1) / 2 + bb, (fork[1] + y1) / 2, x1, y1, 10), 0.9, L[1]); st.d = 0; BR.push(st);
        for (var k = 0; k < 2; k++) {
          var f = 0.45 + k * 0.25, sx = fork[0] + (x1 - fork[0]) * f, sy = fork[1] + (y1 - fork[1]) * f, sa = ang + (k ? 1 : -1) * (0.55 + rng() * 0.3), sl = len * (0.32 + rng() * 0.12);
          // twigs end inside the crown, never as bare sticks beside it
          while (sl > 1.5 && !inside(CAN, sx + Math.cos(sa) * sl, sy + Math.sin(sa) * sl)) sl *= 0.85;
          if (sl <= 1.5) continue;
          var tw = mk(quad(sx, sy, sx + Math.cos(sa) * sl * 0.5 + (rng() - 0.5), sy + Math.sin(sa) * sl * 0.5, sx + Math.cos(sa) * sl, sy + Math.sin(sa) * sl, 6), 0.8, L[1] * 0.55); tw.d = 1; BR.push(tw);
        }
      });
      BR.sort(function (p1, p2) { return p1.d - p2.d; });
      var bTotal = 0;
      BR.forEach(function (st) { st.t0 = bTotal; bTotal += st.len; });
      // a few inner contours that separate leaf masses, on the shaded lower right
      var CLUMPS = [];
      CL.slice(1, 1 + nRing).filter(function (q) { return q[1] > ccy - 4 || q[0] > ccx + 4; }).slice(0, 4).forEach(function (q) {
        var P = [];
        for (var k = 0; k <= 12; k++) {
          var an = 0.15 + k / 12 * 2.2, x = q[0] + Math.cos(an) * q[2] * 0.78, y = q[1] + Math.sin(an) * q[2] * 0.78;
          if (inside(CAN, x, y)) P.push([x + 0.3 * Math.sin(k * 2.1), y]); else if (P.length) break;
        }
        if (P.length > 5) CLUMPS.push(mk(P, 0.4, 0.85));
      });
      // shading, light from the upper left: hatching that gets denser toward the lower right of the crown
      var HATCH = [];
      for (j = 0; j * 2.1 < 2 * ry + 12; j++) {
        for (i = 0; i * 1.5 < 2 * rx + 14; i++) {
          var x0 = ccx - rx - 7 + i * 1.5 + (j % 2) * 0.75 + (rng() - 0.5) * 0.5, y0 = ccy - ry - 6 + j * 2.1 + (rng() - 0.5) * 0.5;
          var sh = (x0 - ccx) / rx * 0.5 + (y0 - ccy) / ry * 0.75;
          if (sh < 0.08 || rng() > Math.min(0.95, 0.25 + sh * 0.9) || !inside(CAN, x0, y0)) continue;
          var L2 = 1.3 + 2.2 * Math.min(1, sh);
          if (inside(CAN, x0 - 0.55 * L2, y0 + 0.8 * L2)) HATCH.push(mk([[x0, y0], [x0 - 0.55 * L2, y0 + 0.8 * L2]], 0.14 + 0.14 * Math.min(1, sh), 0.72));
        }
      }
      HATCH.sort(function (h1, h2) { return (h1.pts[0][1] - h2.pts[0][1]) || (h1.pts[0][0] - h2.pts[0][0]); });
      var NH = HATCH.length;
      for (i = 0; i < 5; i++) HATCH.push(mk([[fork[0] + 0.5 + i * 0.4, fork[1] + 2.5 + i * 4.6], [fork[0] + 2 + i * 0.35, fork[1] + 5.9 + i * 4.6]], 0.26, 0.8));
      for (i = 0; i < 7; i++) HATCH.push(mk([[base[0] + 4 + i * 2.6, GROUND + 2.4], [base[0] + 6.6 + i * 2.6, GROUND - 0.2]], 0.18, 0.8));
      // ground and grass
      var GR = [mk(quad(8, GROUND + 0.4, 50, GROUND - 1.2, 92, GROUND + 0.6, 18), 0.6, 0.95)];
      for (i = 0; i < 11; i++) {
        var gx = 12 + i * 7.6 + (rng() - 0.5) * 3;
        if (Math.abs(gx - base[0]) < 7) continue;
        GR.push(mk([[gx - 1.1, GROUND], [gx - 0.2, GROUND - 2.4 - rng() * 1.2]], 0.45, 0.8));
        GR.push(mk([[gx + 0.2, GROUND], [gx + 1.2, GROUND - 1.8 - rng() * 1.2]], 0.45, 0.8));
      }
      var GUIDE = [
        mk(quad(ccx - rx - 3, ccy, ccx, ccy - 2 * ry - 6, ccx + rx + 3, ccy, 16).concat(quad(ccx + rx + 3, ccy, ccx, ccy + 2 * ry + 6, ccx - rx - 3, ccy, 16).slice(1)), 0.1, 0.8),
        mk([[fork[0], fork[1] - 4], [base[0], GROUND + 3]], 0.09, 0.8), mk([[6, GROUND], [94, GROUND]], 0.09, 0.8)
      ];
      // the storm: two low clouds (union of puffs, flat underneath), rain, wind and now and then lightning
      var CLOUDS = [], CSH = [];
      [[33 + (rng() - 0.5) * 3, 15.5, 16], [67 + (rng() - 0.5) * 3, 13.5, 14.5]].forEach(function (cd) {
        var puffs = [];
        for (var k = 0; k < 6; k++) puffs.push([cd[0] - cd[2] * 0.8 + k * cd[2] * 0.32 + (rng() - 0.5) * 2, cd[1] + (rng() - 0.5) * 1.5 - (k > 0 && k < 5 ? 2 : 0), 4 + rng() * 2.4 + (k > 1 && k < 4 ? 2 : 0)]);
        var P = [];
        for (var q = 0; q < 90; q++) {
          var th = -Math.PI / 2 + q / 90 * Math.PI * 2, r = 30;
          while (r > 1) {
            var x = cd[0] + Math.cos(th) * r, y = cd[1] + Math.sin(th) * r * 0.62, hit = false;
            for (var m = 0; m < puffs.length && !hit; m++) { var dx = x - puffs[m][0], dy = y - puffs[m][1]; hit = dx * dx + dy * dy < puffs[m][2] * puffs[m][2]; }
            if (hit) break;
            r -= 0.3;
          }
          P.push([cd[0] + Math.cos(th) * r, Math.min(cd[1] + 3.6, cd[1] + Math.sin(th) * r * 0.62)]);
        }
        P.push(P[0].slice());
        var cl = mk(P, 0.85, 1); cl.cx = cd[0]; cl.cy = cd[1]; CLOUDS.push(cl);
        for (k = 0; k < 9; k++) CSH.push(mk([[cd[0] - cd[2] * 0.6 + k * cd[2] * 0.15, cd[1] - 0.6], [cd[0] - cd[2] * 0.6 + k * cd[2] * 0.15 - 1.8, cd[1] + 3]], 0.32, 0.75));
      });
      var DROPS = [];
      for (i = 0; i < 46; i++) DROPS.push([rng() * 120 - 10, rng(), 0.75 + rng() * 0.5]);
      var LOW = CAN.filter(function (p) { return p[1] > ccy + 4; });
      var T0 = 0.5, T1 = 0.6, T2 = 1.3, T3 = 1.2, T4 = 0.9, T5 = 0.9, TT = T0 + T1 + T2 + T3 + T4, TD = TT + T5;
      var REST = CSH[CSH.length - 1].pts[1], K = 0.78;

      return function (c, C, W, H, t) {
        var side = Math.min(W, H), S = side / 100, ox = (W - side) / 2, oy = (H - side) / 2, ink = C.ink;
        // wind from the left: the tree leans with it, shakes, and bends further in the gusts
        var on = stClamp((t - TD) / 1.5), gust = Math.pow(Math.max(0, Math.sin(Math.PI * 2 * (t + seed % 7) / 6.5)), 3);
        var sw = on * (2.2 + 3.2 * gust + (1.1 + 0.9 * gust) * Math.sin(2.3 * t + seed) + 0.4 * Math.sin(5.7 * t));
        if (on > 0) rustle(on * (1.6 * t + 3 * gust));
        function M(x, y) { var hgt = stClamp((fork[1] + 8 - y) / 56); return [ox + (50 + (x + sw * hgt * hgt - 50) * K) * S, oy + (GROUND + (y - GROUND) * K) * S]; }
        function N(x, y) { return [ox + x * S, oy + y * S]; }
        var dark = C.dark ? '#000000' : ink;
        if (on > 0) { c.fillStyle = stAlpha(dark, 0.05 * on); c.fillRect(0, 0, W, H); }
        c.lineCap = 'round'; c.lineJoin = 'round';
        var tip = null;
        function run(list, from, dur, alpha) {
          var tot = 0; list.forEach(function (st) { tot += st.len; });
          var reach = stClamp((t - from) / dur) * tot, acc = 0;
          list.forEach(function (st) {
            var p = (reach - acc) / st.len; acc += st.len;
            if (p <= 0) return;
            var tp = draw(c, st, p, M, S, ink, alpha);
            if (p < 1 && tp) tip = tp;
          });
        }
        var erase = 1 - 0.6 * stClamp((t - T0 - T1 - T2 - T3) / T4);
        run(GUIDE, 0, T0, erase);
        run([GR[0]].concat(TRUNK), T0, T1, 1);
        var reach = stClamp((t - T0 - T1) / T2) * bTotal;
        BR.forEach(function (st) {
          var p = (reach - st.t0) / st.len;
          if (p <= 0) return;
          var tp = draw(c, st, p, M, S, ink, 1);
          if (p < 1 && tp) tip = tp;
        });
        // the leaves cover the inner branches as the canopy is drawn
        var cp = stClamp((t - T0 - T1 - T2) / T3);
        if (cp > 0) {
          c.beginPath(); path(c, CAN, M); c.fillStyle = stAlpha(C.surface2, 0.93 * stClamp(cp * 1.6)); c.fill();
          var tp = draw(c, CANOPY, cp, M, S, ink, 1);
          if (cp < 1 && tp) tip = tp;
        }
        var hp = (t - T0 - T1 - T2 - T3) / T4;
        if (hp > 0) {
          c.save(); c.beginPath(); path(c, CAN, M); c.clip();
          CLUMPS.concat(HATCH.slice(0, NH)).forEach(function (st, k, all) {
            var p = stClamp((hp - k * 0.45 / all.length) / 0.12), tp = draw(c, st, p, M, S, ink, 1);
            if (p > 0 && p < 1 && tp) tip = tp;
          });
          c.restore();
          BARK.concat(HATCH.slice(NH), GR.slice(1)).forEach(function (st, k, all) {
            var p = stClamp((hp - 0.5 - k * 0.42 / all.length) / 0.08), tp = draw(c, st, p, M, S, ink, 1);
            if (p > 0 && p < 1 && tp) tip = tp;
          });
        }
        // storm clouds roll in
        var kp = stClamp((t - TT) / T5);
        if (kp > 0) {
          var drift = on * 1.5 * Math.sin(t * 0.4);
          var NC = function (x, y) { return N(x + drift, y); };
          CLOUDS.forEach(function (cl, k) {
            var p = stClamp(kp * 2 - k * 0.6);
            if (p <= 0) return;
            c.beginPath(); path(c, cl.pts, NC); c.fillStyle = stAlpha(C.surface2, 0.95 * stClamp(p * 2)); c.fill();
            var tp = draw(c, cl, p, NC, S, ink, 1);
            if (p < 1 && tp) tip = tp;
          });
          CSH.forEach(function (st, k) {
            var p = stClamp((kp - 0.5 - k * 0.025) / 0.06), tp = draw(c, st, p, NC, S, ink, 1);
            if (p > 0 && p < 1 && tp) tip = tp;
          });
        }
        // rain, slanted by the wind, with splashes on the ground
        var rain = stClamp((t - TD - 0.2) / 1.2);
        if (rain > 0) {
          var slant = 0.38 + 0.3 * gust, L = 4.2;
          c.lineWidth = S * 0.62;
          DROPS.forEach(function (d) {
            var y = 20 + ((d[1] * 77 + t * 62 * d[2]) % 77), x = ((d[0] + (y - 20) * slant) % 120 + 120) % 120 - 10;
            if (y > GROUND) {
              var sa = rain * (1 - (y - GROUND) / 9);
              if (sa > 0) {
                c.strokeStyle = stAlpha(ink, 0.35 * sa);
                c.beginPath(); var s0 = N(x - 1.1, GROUND - 0.9), s1 = N(x, GROUND), s2 = N(x + 1.1, GROUND - 0.9);
                c.moveTo(s0[0], s0[1]); c.lineTo(s1[0], s1[1]); c.lineTo(s2[0], s2[1]); c.stroke();
              }
              return;
            }
            var a1 = N(x - L * slant, y - L), a2 = N(x, y);
            c.strokeStyle = stAlpha(ink, 0.3 * rain); c.beginPath(); c.moveTo(a1[0], a1[1]); c.lineTo(a2[0], a2[1]); c.stroke();
          });
        }
        // lightning every few seconds, beside the tree; a brief flash only while animating
        var lt = t - TD - 2.4;
        if (lt > 0) {
          var bk = Math.floor(lt / 7), age = lt - bk * 7;
          if (age < 0.42) {
            var left = (bk + seed) % 2 === 0, bx = left ? 23 : 78, by = CLOUDS[left ? 0 : 1].cy + 3.4, pts = [[bx, by]];
            for (var q = 1; q <= 6; q++) pts.push([bx + (q % 2 ? 1 : -1) * (2 + ((bk * 3 + q) % 3) * 0.7) + (left ? -q * 0.5 : q * 0.4), by + q * 6.6]);
            var la = age < 0.3 ? 1 : 1 - (age - 0.3) / 0.12;
            [[2.4, stAlpha('#ffd84a', 0.9 * la)], [0.9, stAlpha('#ffffff', la)]].forEach(function (pen) {
              c.beginPath(); pts.forEach(function (q, k) { var m = N(q[0], q[1]); if (k) c.lineTo(m[0], m[1]); else c.moveTo(m[0], m[1]); });
              c.strokeStyle = pen[1]; c.lineWidth = S * pen[0]; c.stroke();
            });
            if (age < 0.09) { c.fillStyle = stAlpha('#ffffff', C.dark ? 0.16 : 0.24); c.fillRect(0, 0, W, H); }
          }
        }
        // leaves torn off by the wind
        if (t > TD + 0.6 && LOW.length) {
          for (var lf = 0; lf < 3; lf++) {
            var per = 2.4, tt = t - TD - 0.6 - lf * 0.8;
            if (tt < 0) continue;
            var k = Math.floor(tt / per), u = (tt - k * per) / 2.2;
            if (u > 1.4) continue;
            var rr = Math.abs(Math.sin((k + 1) * 12.9898 + lf * 7.1 + seed) * 43758.5453) % 1, st0 = LOW[Math.floor(rr * LOW.length)];
            var fall = Math.min(1, u), y = st0[1] + (GROUND - 1.2 - st0[1]) * (1 - (1 - fall) * (1 - fall)), x = st0[0] + 2 * Math.sin(7 * fall + rr * 6) * fall + (12 + 10 * gust) * fall;
            var a = stClamp(u / 0.15) * (u > 1 ? 1 - (u - 1) / 0.45 : 1), m = M(x, y);
            c.save(); c.translate(m[0], m[1]); c.rotate(u > 1 ? 0.3 : 2.2 * Math.sin(5 * fall + rr * 3));
            c.beginPath(); c.moveTo(-2.1 * S, 0); c.quadraticCurveTo(0, -1.5 * S, 2.1 * S, 0); c.quadraticCurveTo(0, 1.5 * S, -2.1 * S, 0);
            c.fillStyle = stAlpha(C.warm, 0.88 * a); c.fill();
            c.beginPath(); c.moveTo(-2.1 * S, 0); c.lineTo(1.8 * S, 0); c.strokeStyle = stAlpha(mix(C.warm, '#000000', 0.35), 0.7 * a); c.lineWidth = S * 0.35; c.stroke();
            c.restore();
          }
        }
        // the pencil follows the line while drawing, then lifts off where it finished
        var done = t - TD;
        if (done > 0 && done < 0.45) {
          var lift = done / 0.45, mr = N(REST[0] + 7 * lift, REST[1] - 7 * lift);
          pencil(c, C, mr[0], mr[1], S, 1 - lift);
        } else if (tip && done <= 0) pencil(c, C, tip[0], tip[1], S, 1);
      };
    };
  })();

};
