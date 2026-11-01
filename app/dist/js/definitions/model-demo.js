'use strict';
// model-demo: shared lexical function definitions; no startup side effects.


  const symParts = function symParts(s) {
    var out = [];
    String(s).split(/(ω_log|Tc)/).forEach(function (p) {
      if (!p) return;
      if (p === 'ω_log') { out.push(['ω']); out.push(['log', 1]); }
      else if (p === 'Tc') { out.push(['T']); out.push(['c', 1]); }
      else out.push([p]);
    });
    return out;
  };

  const modelScores = function modelScores(variant) {
    var d = state.data, out = { tc: null, tcVia: null, lam: null, wlog: null };
    if (!d) return out;
    list(d.results).forEach(function (r) {
      if (!r || typeof r.mae !== 'number') return;
      var tag = String(r.tag || '') + ' ' + L(r.model);
      var isF = /foundation|mace/i.test(tag);
      if ((variant === 'foundation') !== isF) return;
      if (r.target === 'Tc') {
        if (/allen/i.test(L(r.model))) out.tcVia = r.mae; else out.tc = out.tc === null ? r.mae : Math.min(out.tc, r.mae);
      } else if (r.target === 'lambda') out.lam = r.mae;
      else if (r.target === 'omega_log') out.wlog = r.mae;
    });
    return out;
  };


  const drawModel = function drawModel(c, C) {
    var W = demo.W, H = demo.H, narrow = W < 560;
    var variant = demo.modelVariant, stages = MODEL_STAGES[variant], n = stages.length;
    var si = demo.modelStage, t = motionOK() ? demo.modelT : MODEL_STAGE_DUR;
    var gapA = narrow ? 10 : 26, nodeW = (W - 32 - gapA * (n - 1)) / n, nodeH = narrow ? 38 : 44, ny = 14;
    demo.modelNodes = [];
    for (var i = 0; i < n; i++) {
      var x = 16 + i * (nodeW + gapA), on = i === si;
      demo.modelNodes.push({ x: x, y: ny, w: nodeW, h: nodeH });
      stRound(c, x, ny, nodeW, nodeH, 10);
      c.fillStyle = on ? mix(C.surface, C.accent, 0.14) : C.surface2; c.fill();
      c.lineWidth = on ? 2 : 1; c.strokeStyle = on ? C.accent : C.axis; c.stroke();
      stSym(c, C, symParts(narrow ? stages[i].short : stages[i].node), x + nodeW / 2, ny + nodeH / 2 + 4, { size: narrow ? 11 : 12.5, weight: '600', align: 'center', color: on ? C.ink : C.ink2 });
      if (i < n - 1) stArrow(c, x + nodeW + 3, ny + nodeH / 2, x + nodeW + gapA - 3, ny + nodeH / 2, i < si ? C.accent : C.axis, 6);
    }
    if (si > 0 && t < 0.8 && motionOK()) {
      var k = stEase(t / 0.8), xa = 16 + (si - 1) * (nodeW + gapA) + nodeW, xb = xa + gapA;
      dot(c, xa + (xb - xa) * k, ny + nodeH / 2, 4, C.accent);
    }
    var ty = ny + nodeH + 30;
    stSym(c, C, symParts('Step ' + (si + 1) + ' of ' + n + ' · ' + modelTitle(variant, si)), 16, ty, { size: narrow ? 14 : 16, weight: '600' });
    if (!narrow) label(c, C, MODEL_LABEL[variant] || 'Baseline', W - 16, ty, { align: 'right', size: 12, weight: '600', color: C.accent });
    var D = { x: 16, y: ty + 16, w: W - 32, h: H - ty - 30 };
    c.save();
    c.globalAlpha = stSpan(t, 0, 0.4);
    var draw = {
      baseline: [drawModelCrystal, drawModelFeatures, drawModelBoost, drawModelTc, drawModelScore],
      foundation: [drawModelCrystal, drawModelMace, drawModelBags, drawModelTc, drawModelScore],
      hurricane: [drawBaseData, drawBaseFeatures, drawBaseTrees, drawBaseScore],
      radar: [drawBaseData, drawBaseFeatures, drawBaseTrees, drawBaseScore]
    }[variant];
    draw[si](c, C, D, t, narrow, variant);
    c.restore();
    c.globalAlpha = 1;
  };


  const drawModelCrystal = function drawModelCrystal(c, C, D, t, narrow) {
    var cx = narrow ? D.x + D.w / 2 : D.x + D.w * 0.3, cy = narrow ? D.y + D.h * 0.36 : D.y + D.h * 0.5;
    var s = Math.min(narrow ? D.h * 0.26 : D.h * 0.36, 120);
    var ang = (motionOK() ? t : 1.2) * 0.45 + 0.5, tilt = 0.42;
    function P(p) {
      var x = p[0] - 0.5, y = p[1] - 0.5, z = p[2] - 0.5;
      var x1 = x * Math.cos(ang) + z * Math.sin(ang), z1 = -x * Math.sin(ang) + z * Math.cos(ang);
      var y2 = y * Math.cos(tilt) - z1 * Math.sin(tilt), z2 = y * Math.sin(tilt) + z1 * Math.cos(tilt);
      return [cx + x1 * s * 1.6, cy + y2 * s * 1.6, z2];
    }
    var corners = [];
    for (var i = 0; i < 8; i++) corners.push([i & 1, (i >> 1) & 1, (i >> 2) & 1]);
    c.strokeStyle = C.axis; c.lineWidth = 1.2;
    for (var a = 0; a < 8; a++) for (var b = a + 1; b < 8; b++) {
      var dd = Math.abs(corners[a][0] - corners[b][0]) + Math.abs(corners[a][1] - corners[b][1]) + Math.abs(corners[a][2] - corners[b][2]);
      if (dd !== 1) continue;
      var pa = P(corners[a]), pb = P(corners[b]);
      c.beginPath(); c.moveTo(pa[0], pa[1]); c.lineTo(pb[0], pb[1]); c.stroke();
    }
    var atoms = corners.map(function (p) { return [p, 'Sn']; }).concat([[[0.5, 0.5, 0.5], 'Sn']]);
    [[0.25, 0, 0.5], [0.75, 0, 0.5], [0.25, 1, 0.5], [0.75, 1, 0.5], [0.5, 0.25, 0], [0.5, 0.75, 0], [0.5, 0.25, 1], [0.5, 0.75, 1], [0, 0.5, 0.25], [0, 0.5, 0.75], [1, 0.5, 0.25], [1, 0.5, 0.75]].forEach(function (p) { atoms.push([p, 'Nb']); });
    var proj = atoms.map(function (a2) { var q = P(a2[0]); return { x: q[0], y: q[1], z: q[2], k: a2[1] }; }).sort(function (p, q) { return p.z - q.z; });
    proj.forEach(function (p) {
      var r = (p.k === 'Sn' ? 9 : 7) * (1 + 0.18 * p.z) * Math.max(0.7, s / 110);
      dot(c, p.x, p.y, r, p.k === 'Sn' ? C.warm : C.accent, C.surface);
    });
    var lx = narrow ? D.x + D.w / 2 : cx, ly = cy + s * 1.25 + 18;
    var leg = 'Example: Nb₃Sn, A15 structure';
    if (narrow) label(c, C, leg, lx, ly, { align: 'center', size: 12, weight: '600', color: C.ink });
    else label(c, C, leg, lx, Math.min(ly, D.y + D.h - 4), { align: 'center', size: 12, weight: '600', color: C.ink });
    var lg2 = narrow ? ly + 18 : Math.min(ly, D.y + D.h - 4) + 18;
    if (lg2 < D.y + D.h + 10) {
      dot(c, lx - 52, lg2 - 4, 4.5, C.accent); label(c, C, 'Nb', lx - 44, lg2, { size: 11.5, color: C.ink2 });
      dot(c, lx + 18, lg2 - 4, 5, C.warm); label(c, C, 'Sn', lx + 26, lg2, { size: 11.5, color: C.ink2 });
    }
    var stats = [['7,582', 'crystals'], ['4,288', 'chemical systems'], ['0.02–3.27', 'range of λ'], ['41–1,104 K', 'range of ω_log'], ['0–36 K', 'range of Tc']];
    c.globalAlpha = stSpan(t, 0.8, 1.4);
    if (!narrow) {
      var x0 = D.x + D.w * 0.58, y0 = D.y + 18;
      label(c, C, 'Training data (Alexandria)', x0, y0, { size: 12.5, weight: '600', color: C.ink });
      stats.forEach(function (st, i2) {
        var yy = y0 + 34 + i2 * 36;
        label(c, C, st[0], x0, yy, { size: 18, weight: '700', color: C.ink });
        stFont(c, C, 18, '700');
        stSym(c, C, symParts(st[1]), x0 + c.measureText(st[0]).width + 10, yy, { size: 12.5, color: C.ink2 });
      });
    } else {
      var y1 = lg2 + 30;
      stats.forEach(function (st, i2) {
        var col = i2 % 2, row = Math.floor(i2 / 2), xx = D.x + col * D.w / 2, yy = y1 + row * 34;
        if (yy > D.y + D.h + 6) return;
        label(c, C, st[0], xx, yy, { size: 14, weight: '700', color: C.ink });
        stSym(c, C, symParts(st[1]), xx, yy + 15, { size: 11, color: C.ink2 });
      });
    }
  };


  // groups: [name, count] in order; brackets: [text, text on phones, colour] each spanning a run of groups (default: Storm's baseline)
  const drawModelFeatures = function drawModelFeatures(c, C, D, t, narrow, groups, brackets) {
    var custom = Array.isArray(groups);
    groups = custom ? groups : FEATURE_GROUPS;
    var rng = stRng(7), vals = [], total = 0;
    groups.forEach(function (g) { total += g[1]; });
    for (var i = 0; i < total; i++) vals.push(0.15 + 0.85 * rng());
    var groupGap = narrow ? 2 : 10, gaps = groups.length - 1;
    var bx0 = D.x + 6, bw = D.w - 12, slot = (bw - gaps * groupGap) / total;
    var baseY = D.y + D.h * (narrow ? 0.6 : 0.66), maxH = D.h * (narrow ? 0.46 : 0.5);
    var k = 0, x = bx0, groupX = [];
    groups.forEach(function (g, gi) {
      var gx0 = x;
      for (var j = 0; j < g[1]; j++, k++) {
        var a = stSpan(t, 0.3 + k * 0.06, 0.6 + k * 0.06);
        if (a > 0) {
          var hh = vals[k] * maxH * a;
          stRound(c, x + slot * 0.15, baseY - hh, slot * 0.7, hh, Math.min(3, slot * 0.3));
          c.fillStyle = !custom && gi >= 9 ? C.warm : C.accent; c.fill();
        }
        x += slot;
      }
      groupX.push([gx0, x, g[0]]);
      x += groupGap;
    });
    c.strokeStyle = C.axis; c.lineWidth = 1;
    c.beginPath(); c.moveTo(bx0, Math.round(baseY) + 0.5); c.lineTo(bx0 + bw, Math.round(baseY) + 0.5); c.stroke();
    c.globalAlpha = stSpan(t, 1.0, 1.6);
    if (!narrow) {
      groupX.forEach(function (g) { label(c, C, g[2], (g[0] + g[1]) / 2, baseY + 16, { align: 'center', size: 11, color: C.muted }); });
    }
    var by = baseY + (narrow ? 18 : 40);
    function bracket(x0, x1, text, color) {
      c.strokeStyle = color; c.lineWidth = 1.5;
      c.beginPath(); c.moveTo(x0, by - 6); c.lineTo(x0, by); c.lineTo(x1, by); c.lineTo(x1, by - 6); c.stroke();
      label(c, C, text, (x0 + x1) / 2, by + 16, { align: 'center', size: 12, weight: '600', color: C.ink });
    }
    if (custom) (brackets || []).forEach(function (b) { bracket(bx0, bx0 + bw, narrow ? b[1] : b[0], b[2]); });
    else {
      bracket(bx0, groupX[8][1], narrow ? 'Composition · 34' : 'Composition · 34 numbers', C.accent);
      bracket(groupX[9][0], bx0 + bw, narrow ? 'Structure · 9' : 'Structure · 9', C.warm);
    }
    c.globalAlpha = 1;
    label(c, C, 'Example values, scaled', D.x + D.w, D.y + 10, { align: 'right', size: 11, color: C.muted });
  };


  const drawModelMace = function drawModelMace(c, C, D, t, narrow) {
    var cx = narrow ? D.x + D.w / 2 : D.x + D.w * 0.3, cy = D.y + D.h * (narrow ? 0.34 : 0.46);
    var R = Math.min(narrow ? D.h * 0.2 : D.h * 0.3, 92);
    var pts = [[0, 0]];
    for (var i = 0; i < 6; i++) { var an = i * Math.PI / 3 + 0.3; pts.push([R * 0.62 * Math.cos(an), R * 0.62 * Math.sin(an)]); }
    pts.push([R * 1.15, -R * 0.2]); pts.push([-R * 1.1, R * 0.35]);
    var bonds = [];
    for (var a = 0; a < pts.length; a++) for (var b = a + 1; b < pts.length; b++) {
      if (Math.hypot(pts[a][0] - pts[b][0], pts[a][1] - pts[b][1]) < R * 0.75) bonds.push([a, b]);
    }
    c.setLineDash([4, 4]); c.strokeStyle = C.muted; c.lineWidth = 1;
    c.beginPath(); c.arc(cx, cy, R * 0.75, 0, Math.PI * 2); c.stroke(); c.setLineDash([]);
    label(c, C, 'cutoff 6 Å', cx + R * 0.53, cy - R * 0.62, { size: 11, color: C.muted });
    c.strokeStyle = C.axis; c.lineWidth = 1.6;
    bonds.forEach(function (bd) { c.beginPath(); c.moveTo(cx + pts[bd[0]][0], cy + pts[bd[0]][1]); c.lineTo(cx + pts[bd[1]][0], cy + pts[bd[1]][1]); c.stroke(); });
    var layer = t < 1.8 ? 1 : 2, wave = stClamp(((t - 0.4) % 1.4) / 1.4);
    if (t > 0.4 && t < 3.2) {
      bonds.forEach(function (bd, k) {
        var dir = (k + layer) % 2, p = pts[bd[dir]], q = pts[bd[1 - dir]];
        c.globalAlpha = Math.sin(wave * Math.PI);
        dot(c, cx + p[0] + (q[0] - p[0]) * wave, cy + p[1] + (q[1] - p[1]) * wave, 3, C.accent);
      });
      c.globalAlpha = 1;
      label(c, C, 'message passing · layer ' + layer + ' of 2', cx, cy + R * 0.75 + 24, { align: 'center', size: 11.5, weight: '600', color: C.ink2 });
    }
    var fill = stSpan(t, 0.5, 3.0), cells = 6, cw = narrow ? 5 : 6, ch = narrow ? 4 : 5;
    pts.forEach(function (p, i2) {
      dot(c, cx + p[0], cy + p[1], i2 === 0 ? 9 : 8, i2 % 3 === 0 ? C.warm : C.accent, C.surface);
      if (fill > 0 && t < 3.6) {
        var nshow = Math.ceil(fill * cells);
        for (var q = 0; q < nshow; q++) {
          c.fillStyle = stRgb(rampColor(((i2 * 7 + q * 3) % 10) / 10, C.dark));
          c.fillRect(cx + p[0] + 11, cy + p[1] - cells * ch / 2 + q * ch, cw, ch - 1);
        }
      }
    });
    var poolA = stSpan(t, 3.4, 4.2);
    if (poolA > 0) {
      c.globalAlpha = poolA;
      var names = ['mean', 'std', 'max'];
      var px0 = narrow ? D.x + 10 : D.x + D.w * 0.58, py0 = narrow ? D.y + D.h * 0.7 : D.y + D.h * 0.26;
      var bw2 = narrow ? (D.w - 20 - 16) / 3 : Math.min(120, D.w * 0.11), gap2 = 8;
      names.forEach(function (nm, j) {
        var x = px0 + j * (bw2 + gap2);
        stRound(c, x, py0, bw2, 46, 8); c.fillStyle = C.surface2; c.fill(); c.lineWidth = 1; c.strokeStyle = C.axis; c.stroke();
        for (var q = 0; q < 8; q++) { c.fillStyle = stRgb(rampColor(((j * 3 + q * 5) % 10) / 10, C.dark)); c.fillRect(x + 8 + q * ((bw2 - 16) / 8), py0 + 10, (bw2 - 16) / 8 - 1, 12); }
        label(c, C, nm, x + bw2 / 2, py0 + 38, { align: 'center', size: 11.5, weight: '600', color: C.ink2 });
      });
      label(c, C, 'pooled over all atoms', px0, py0 - 10, { size: 12, weight: '600', color: C.ink });
      var fy = py0 + 70;
      c.globalAlpha = stSpan(t, 4.4, 5.0);
      label(c, C, '→ one fingerprint per crystal', px0, fy, { size: 12.5, weight: '600', color: C.ink });
      for (var q2 = 0; q2 < 24; q2++) { c.fillStyle = stRgb(rampColor(((q2 * 7) % 11) / 11, C.dark)); c.fillRect(px0 + q2 * ((narrow ? D.w - 20 : 3 * bw2 + 16) / 24), fy + 10, (narrow ? D.w - 20 : 3 * bw2 + 16) / 24 - 1, 10); }
    }
  };


  const treeGlyph = function treeGlyph(c, C, x, y, s, color) {
    var nodes = [[0, 0], [-0.5, 0.7], [0.5, 0.7], [-0.75, 1.4], [-0.25, 1.4], [0.25, 1.4], [0.75, 1.4]];
    c.strokeStyle = C.axis; c.lineWidth = 1;
    [[0, 1], [0, 2], [1, 3], [1, 4], [2, 5], [2, 6]].forEach(function (e) {
      c.beginPath(); c.moveTo(x + nodes[e[0]][0] * s, y + nodes[e[0]][1] * s); c.lineTo(x + nodes[e[1]][0] * s, y + nodes[e[1]][1] * s); c.stroke();
    });
    nodes.forEach(function (p, i) { dot(c, x + p[0] * s, y + p[1] * s, i < 3 ? s * 0.16 : s * 0.13, i < 3 ? color : C.surface, color); });
  };


  const drawModelBoost = function drawModelBoost(c, C, D, t, narrow) {
    var nShow = narrow ? 5 : 11, s = narrow ? 16 : 20, slotW = (D.w - 40) / (nShow + 1);
    var grow = stClamp((t - 0.5) / 3.5), shown = Math.floor(grow * nShow + 0.0001);
    for (var i = 0; i < nShow; i++) {
      var x = D.x + 20 + slotW * (i + 0.5), y = D.y + 14;
      var a = stSpan(t, 0.5 + i * (3.5 / nShow), 0.8 + i * (3.5 / nShow));
      if (a <= 0) continue;
      c.globalAlpha = a;
      treeGlyph(c, C, x, y, s, C.accent);
      label(c, C, String(i + 1), x, y + s * 1.4 + 18, { align: 'center', size: 11, color: C.muted });
      if (i > 0) label(c, C, '+', x - slotW / 2, y + s * 0.8, { align: 'center', base: 'middle', size: 14, weight: '600', color: C.ink2 });
    }
    c.globalAlpha = stSpan(t, 4.0, 4.4);
    var lastX = D.x + 20 + slotW * (nShow + 0.5);
    label(c, C, '… 800', lastX, D.y + 14 + s * 0.85, { align: 'center', base: 'middle', size: 13, weight: '600', color: C.ink2 });
    c.globalAlpha = 1;
    var ly = D.y + D.h * (narrow ? 0.62 : 0.7), lx0 = D.x + 40, lx1 = D.x + D.w - 40;
    function X(v) { return lx0 + (v / 1.0) * (lx1 - lx0); }
    c.strokeStyle = C.axis; c.lineWidth = 1;
    c.beginPath(); c.moveTo(lx0, ly); c.lineTo(lx1, ly); c.stroke();
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      c.beginPath(); c.moveTo(X(v), ly - 4); c.lineTo(X(v), ly + 4); c.stroke();
      label(c, C, String(v), X(v), ly + 18, { align: 'center', size: 11, color: C.muted });
    });
    label(c, C, 'λ for one example material', lx0, ly + 36, { size: 11.5, color: C.ink2 });
    var target = 0.62, start = 0.42;
    var trees = Math.round(800 * Math.pow(grow, 2.2));
    var pred = target - (target - start) * Math.pow(0.96, trees);
    c.setLineDash([3, 3]); c.strokeStyle = C.warm; c.lineWidth = 1.5;
    c.beginPath(); c.moveTo(X(target), ly - 26); c.lineTo(X(target), ly + 6); c.stroke(); c.setLineDash([]);
    label(c, C, 'full calculation 0.62', X(target) + 6, ly - 30, { size: 11.5, weight: '600', color: C.ink2 });
    dot(c, X(start), ly, 3, C.muted);
    label(c, C, 'start: average 0.42', X(start) - 6, ly - 12, { align: 'right', size: 11, color: C.muted });
    dot(c, X(pred), ly, 6, C.accent, C.surface);
    label(c, C, trees + (trees === 1 ? ' tree' : ' trees') + ' → λ ≈ ' + pred.toFixed(3), X(pred), ly - (narrow ? 46 : 50), { align: 'center', size: 12.5, weight: '700', color: C.ink });
  };


  const drawModelBags = function drawModelBags(c, C, D, t, narrow) {
    var preds = [0.58, 0.66, 0.61], rows = 3, rh = narrow ? 44 : 50;
    var stripX = D.x + (narrow ? 4 : 10), stripW = narrow ? D.w * 0.46 : D.w * 0.42, ndots = narrow ? 14 : 24;
    var rng = stRng(5);
    for (var b = 0; b < rows; b++) {
      var y = D.y + 18 + b * rh, a = stSpan(t, 0.3 + b * 0.5, 0.8 + b * 0.5);
      if (a <= 0) continue;
      c.globalAlpha = a;
      label(c, C, 'Model ' + (b + 1), stripX, y - 2, { size: 11.5, weight: '600', color: C.ink2 });
      var counts = [];
      for (var q = 0; q < ndots; q++) counts.push(0);
      for (var q2 = 0; q2 < ndots; q2++) counts[Math.floor(rng() * ndots)]++;
      counts.forEach(function (n2, q) {
        var x = stripX + (q + 0.5) * stripW / ndots;
        if (n2 === 0) dot(c, x, y + 12, 3.5, C.surface, C.axis);
        for (var m = 0; m < Math.min(n2, 3); m++) dot(c, x, y + 12 - m * 5, 3.5, C.accent);
      });
      var tx = stripX + stripW + (narrow ? 18 : 40);
      stArrow(c, stripX + stripW + 4, y + 10, tx - 6, y + 10, C.axis, 6);
      treeGlyph(c, C, tx + 10, y - 2, narrow ? 10 : 12, C.accent);
      treeGlyph(c, C, tx + (narrow ? 26 : 30), y - 2, narrow ? 10 : 12, C.accent);
      label(c, C, 'λ ≈ ' + preds[b].toFixed(2), tx + (narrow ? 48 : 58), y + 12, { size: 12.5, weight: '600', color: C.ink });
    }
    c.globalAlpha = 1;
    label(c, C, narrow ? 'bootstrap resamples' : 'each model trains on a bootstrap resample (dots picked with repeats)', stripX, D.y + 18 + rows * rh + 4, { size: 11, color: C.muted });
    var ly = D.y + D.h * (narrow ? 0.8 : 0.82), lx0 = D.x + 40, lx1 = D.x + D.w - 40;
    function X(v) { return lx0 + ((v - 0.4) / 0.4) * (lx1 - lx0); }
    c.strokeStyle = C.axis; c.lineWidth = 1;
    c.beginPath(); c.moveTo(lx0, ly); c.lineTo(lx1, ly); c.stroke();
    [0.4, 0.5, 0.6, 0.7, 0.8].forEach(function (v) { label(c, C, v.toFixed(1), X(v), ly + 18, { align: 'center', size: 11, color: C.muted }); });
    var mean = (preds[0] + preds[1] + preds[2]) / 3;
    var sd = Math.sqrt(preds.reduce(function (s2, p) { return s2 + (p - mean) * (p - mean); }, 0) / 3);
    var merge = stSpan(t, 3.4, 4.4);
    preds.forEach(function (p, i) {
      if (t < 1.0 + i * 0.5) return;
      var x = X(p) + (X(mean) - X(p)) * merge;
      dot(c, x, ly, 5, C.accent, C.surface);
    });
    if (merge > 0) {
      c.globalAlpha = merge;
      c.strokeStyle = C.ink; c.lineWidth = 2;
      c.beginPath(); c.moveTo(X(mean - sd), ly - 14); c.lineTo(X(mean + sd), ly - 14);
      c.moveTo(X(mean - sd), ly - 19); c.lineTo(X(mean - sd), ly - 9); c.moveTo(X(mean + sd), ly - 19); c.lineTo(X(mean + sd), ly - 9); c.stroke();
      label(c, C, 'λ = ' + mean.toFixed(2) + ' ± ' + sd.toFixed(2), X(mean), ly - 28, { align: 'center', size: 13, weight: '700', color: C.ink });
    }
  };


  const drawModelTc = function drawModelTc(c, C, D, t, narrow, variant) {
    var lam = 0.62, wl = 240, f = variant === 'foundation';
    var tc = allenDynes(lam, wl, 0.10), lo = allenDynes(lam - 0.05, wl - 9, 0.10), hi = allenDynes(lam + 0.05, wl + 9, 0.10);
    var y0 = D.y + 22;
    var cards = [[[['λ = 0.62' + (f ? ' ± 0.05' : '')]], 0.3], [[['ω'], ['log', 1], [' = 240 K' + (f ? ' ± 9 K' : '')]], 0.6]];
    cards.forEach(function (cd, i) {
      c.globalAlpha = stSpan(t, cd[1], cd[1] + 0.4);
      var x = D.x + (narrow ? i * D.w / 2 : 0), y = narrow ? y0 : y0 + i * 40;
      stSym(c, C, cd[0], x, y, { size: narrow ? 14 : 16, weight: '700' });
    });
    c.globalAlpha = stSpan(t, 1.2, 1.7);
    var fx = narrow ? D.x : D.x + D.w * 0.3, fy = narrow ? y0 + 44 : y0 + 2;
    label(c, C, 'Allen–Dynes formula', fx, fy - 2, { size: 11.5, color: C.muted });
    var big = narrow ? 13.5 : 16;
    var f1 = [['T'], ['c', 1], [' = (ω'], ['log', 1], [' / 1.2) · exp[ −1.04 (1 + λ) / (λ − μ*(1 + 0.62 λ)) ]']];
    if (narrow) {
      stSym(c, C, [['T'], ['c', 1], [' = (ω'], ['log', 1], [' / 1.2) ×']], fx, fy + 22, { size: big, weight: '600' });
      stSym(c, C, [['exp[ −1.04 (1+λ) / (λ − μ*(1+0.62λ)) ]']], fx, fy + 44, { size: big, weight: '600' });
    } else stSym(c, C, f1, fx, fy + 26, { size: big, weight: '600' });
    c.globalAlpha = stSpan(t, 2.4, 2.9);
    var d2 = lam - 0.1 * (1 + 0.62 * lam);
    var sub = '= (240 / 1.2) · exp[ −1.04 × ' + (1 + lam).toFixed(2) + ' / ' + d2.toFixed(3) + ' ],  μ* = 0.10';
    stPara(c, C, sub, fx, fy + (narrow ? 68 : 54), narrow ? D.w : D.w * 0.68, 18, { size: narrow ? 12 : 13, color: C.ink2 });
    c.globalAlpha = stSpan(t, 3.4, 3.9);
    var ry = narrow ? fy + 122 : fy + 108;
    stSym(c, C, [['T'], ['c', 1], [' ≈ ' + tc.toFixed(1) + ' K']], fx, ry, { size: narrow ? 24 : 30, weight: '700' });
    if (f) label(c, C, 'range ' + lo.toFixed(1) + '–' + hi.toFixed(1) + ' K from the three models', fx, ry + 24, { size: 12.5, weight: '600', color: C.accent });
    c.globalAlpha = stSpan(t, 4.2, 4.8);
    var sc = modelScores(variant), ny2 = ry + (f ? 54 : 34);
    var noteTxt;
    if (sc.tc !== null && sc.tcVia !== null) noteTxt = 'Average error: ' + sc.tc.toFixed(2) + ' K predicting Tc directly, ' + sc.tcVia.toFixed(2) + ' K via λ and ω_log.';
    else if (sc.tc !== null) noteTxt = 'Average Tc error so far: ' + sc.tc.toFixed(2) + ' K.';
    else noteTxt = f ? 'Scores appear here when the foundation-model run finishes.' : '';
    if (noteTxt && ny2 < D.y + D.h + 4) stPara(c, C, noteTxt, fx, ny2, narrow ? D.w : D.w * 0.66, 17, { size: 12, color: C.ink2 });
  };


  const drawModelScore = function drawModelScore(c, C, D, t, narrow, variant) {
    var folds = 5, colW = D.w / folds, chipH = narrow ? 18 : 22, per = 4;
    var cur = motionOK() ? Math.min(folds - 1, Math.floor(Math.max(0, t - 0.4) / 0.9)) : folds - 1;
    var showAll = t > 0.4 + folds * 0.9;
    for (var f = 0; f < folds; f++) {
      var x = D.x + f * colW, test = !showAll && f === cur;
      label(c, C, 'Fold ' + (f + 1), x + colW / 2, D.y + 12, { align: 'center', size: 12, weight: '600', color: test ? C.accent : C.ink2 });
      label(c, C, showAll ? 'held out once' : test ? 'test' : 'train', x + colW / 2, D.y + 28, { align: 'center', size: 11, color: test ? C.accent : C.muted });
      for (var k = 0; k < per; k++) {
        var name = CHEMSYS[f * per + k];
        var cx = narrow ? x + colW / 2 : x + colW / 2 + (k % 2 === 0 ? -colW * 0.22 : colW * 0.22);
        var cy = narrow ? D.y + 48 + k * (chipH + 6) : D.y + 50 + Math.floor(k / 2) * (chipH + 8);
        stTag(c, C, name, cx, cy, { size: narrow ? 10 : 11.5, weight: '600', bg: test ? mix(C.surface, C.accent, 0.18) : C.surface2, ring: test ? C.accent : null, color: test ? C.ink : C.ink2, pad: narrow ? 4 : 7 });
      }
    }
    var sy = D.y + (narrow ? 48 + per * (chipH + 6) + 26 : 50 + 2 * (chipH + 8) + 34);
    c.globalAlpha = stSpan(t, 4.8, 5.3);
    var sc = modelScores(variant), live = stLive();
    label(c, C, variant === 'baseline' ? 'Average error over the five held-out folds' : 'Foundation model scores', D.x, sy, { size: 12.5, weight: '600', color: C.ink });
    var items = [];
    if (sc.tc !== null) items.push([[['T'], ['c', 1]], sc.tc.toFixed(2) + ' K']);
    if (sc.lam !== null) items.push([[['λ']], sc.lam.toFixed(3)]);
    if (sc.wlog !== null) items.push([[['ω'], ['log', 1]], sc.wlog.toFixed(1) + ' K']);
    if (!items.length) {
      var msg = variant === 'foundation' ? (live.foundation === 'active' ? 'Training now: results will appear here when the run finishes.' : 'Next up: results will appear here after the first run.') : 'Results load with the live progress data.';
      stPara(c, C, msg, D.x, sy + 24, D.w, 17, { size: 12.5, color: C.ink2 });
      return;
    }
    var colw = narrow ? D.w / 3 : 170;
    items.forEach(function (it, i) {
      var x = D.x + i * colw;
      stSym(c, C, it[0], x, sy + 26, { size: 12.5, color: C.ink2 });
      label(c, C, it[1], x, sy + 54, { size: narrow ? 18 : 22, weight: '700', color: C.ink });
    });
    var L = typeof stormLatest === 'function' ? stormLatest() : null;
    if (L && sc.tc !== null && sy + 84 < D.y + D.h + 8) {
      c.globalAlpha = stSpan(t, 5.3, 5.8);
      stSym(c, C, symParts(stormLatestTitle(L) + ', our AI-designed model: Tc off by ' + fmtVal(L.ens.scores.tc_mae) + ' K'), D.x, sy + 84, { size: 12.5, weight: '600', color: C.accent });
      c.globalAlpha = 1;
    }
  };
