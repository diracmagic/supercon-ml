'use strict';
// storm-current-demo: shared lexical function definitions; no startup side effects.

  const stormLatest = function stormLatest() {
    var am = state.data && state.data.ai_model, ens = stormEns();
    if (!am || !ens) return null;
    var vs = list(am.versions).filter(function (v) { return v && v.spec && v.scores; });
    var cur = vs.filter(function (v) { return v.version === am.current; })[0] || vs[0];
    if (!cur) return null;
    var unc = stormUnc(), cal = stormCal(), name = am.name || 'Storm';
    return { am: am, ens: ens, unc: unc, cal: cal, trees: cur, versions: vs, name: name, version: unc ? unc.version : ens.version,
      info: { am: am, v: cur, versions: vs, name: name } };
  };

  const stormLatestTitle = function stormLatestTitle(L) { return L.name + ' ' + L.version; };

  const stormRounds = function stormRounds(L) {
    var rows = [];
    L.versions.forEach(function (v) {
      var pv = v.scores.previous;
      var ok = v.status === 'adopted';
      rows.push({ round: v.round, name: L.name + ' ' + v.version, ok: ok, result: fmtVal(v.scores.tc_mae) + ' K',
        what: lcFirst(String(v.summary || '').replace(/^Hand-made \+ /, '')), why: ok ? '' : 'not released' + (pv ? ', better than ' + pv.name + ' in ' + pv.folds_better + ' of ' + list(pv.folds).length + ' folds' : '') });
    });
    if (L.cal) rows.push({ round: L.cal.round || 3, name: L.name + ' ' + L.cal.version, what: 'calibrated to measured Tc', ok: true, result: fmtVal(L.cal.scores.mae) + ' K measured' });
    rows.push({ round: L.ens.round || 4, name: L.name + ' ' + L.ens.version, what: 'trees and a crystal-graph network', ok: true, result: fmtVal(L.ens.scores.tc_mae) + ' K' });
    if (L.unc) rows.push({ round: L.unc.round || 5, name: L.name + ' ' + L.unc.version, what: 'a 90% range for every prediction', ok: true, result: (100 * L.unc.scores.coverage).toFixed(1) + '% held' });
    return rows.sort(function (a, b) { return a.round - b.round; });
  };


  const stormLatestCaption = function stormLatestCaption(si, L) {
    var ens = L.ens, sc = ens.scores, cal = ens.calibration || {}, unc = L.unc, rows = stormRounds(L), name = stormLatestTitle(L);
    var sp = L.trees.spec, n = 0;
    list(sp.inputs).forEach(function (i) { n += i.n || 0; });
    var notRel = rows.filter(function (r) { return !r.ok; }).map(function (r) { return 'round ' + r.round; });
    switch (si) {
      case 0:
        return name + ' is the Storm in use. An AI agent (Claude) built it over ' + rows.length + ' rounds, and a round was released only if it beat the version in use on held-out materials' +
          (notRel.length ? ' (' + notRel.join(' and ') + ' did not)' : '') + ': ' + rows.filter(function (r) { return r.ok; }).map(function (r) { return r.name + ', ' + r.what + (r.round === (L.ens.round || 4) ? ' together' : ''); }).join('; ') +
          '. Storm predicts Tc for conventional, phonon-mediated superconductors; ' + (radInfo() && radInfo().rd.current ? radTitle(radInfo()) : 'Radar') + ' sends cuprates, iron-based, heavy-fermion compounds and other unconventional superconductors to ' + (hurInfo() ? hurTitle(hurInfo()) : 'Hurricane') + '.';
      case 1:
        return 'Two kinds of input. The boosted trees read ' + n + ' numbers per material: ' + list(sp.inputs).map(function (i) { return i.n + ' ' + lcFirst(i.label); }).join(', ') +
          '. The physics features encode rules of thumb such as Matthias’s valence-electron peaks and the M^−½ scale of phonon frequencies. The crystal-graph network reads the crystal itself: every atom is a node joined to its 12 nearest neighbours.';
      case 2:
        var Lr = sp.learner || {};
        return 'Two learners. ' + fmtInt(Lr.trees) + ' gradient-boosted trees, each fixing what the trees before it got wrong (up to ' + Lr.leaves + ' leaves, learning rate ' + Lr.learning_rate + '), and the ' +
          (ens.gnn && ens.gnn.design ? ens.gnn.design : 'crystal-graph network') + ', which passes messages between neighbouring atoms in three layers and predicts Tc, λ and ω_log together.';
      case 3:
        return 'Three routes to Tc: the trees, the network, and the network’s λ and ω_log through the Allen–Dynes formula. Their average is off by ' + fmtVal(sc.tc_mae) + ' K for materials Storm never saw' +
          (typeof cal.mae === 'number' ? '; round 3’s calibration maps it to experiment, ' + fmtVal(cal.mae) + ' K off against measured Tc' : '') +
          (unc ? '; and every prediction gets a 90% range, which held the computed Tc ' + (100 * unc.scores.coverage).toFixed(1) + '% of the time' : '') + '. The Predict Tc demo walks through these steps for real materials.';
      case 4:
        return 'Five-fold cross-validation grouped by chemical system, so no test material shares its elements with training data. ' + name + ' is off by ' + fmtVal(sc.tc_mae) + ' K against ' +
          fmtVal(sc.reference_mae) + ' K for Storm 1.0’s trees alone, better in ' + sc.folds_better + ' of ' + list(sc.folds).length + ' folds' +
          (typeof cal.mae === 'number' ? '; calibrated, it is ' + fmtVal(cal.mae) + ' K off against measured Tc' + (typeof cal.mae_storm3 === 'number' ? ', against ' + fmtVal(cal.mae_storm3) + ' K for Storm 3.0' : '') : '') +
          (unc ? '; its ranges held ' + (100 * unc.scores.coverage).toFixed(1) + '% of held-out materials and ' + (100 * unc.scores.tail_coverage).toFixed(1) + '% of the tenth with the highest Tc' : '') +
          '. The locked JARVIS test set checks it once, at the end.';
      default:
        if (unc) return 'New in ' + name + ' (round 5): a 90% range around every prediction, set by conformal prediction from the errors on held-out folds. One width on log(1 + Tc) makes ranges wider where Tc is higher: half are narrower than ' +
          fmtVal(unc.scores.median_width) + ' K, and they held ' + (100 * unc.scores.tail_coverage).toFixed(1) + '% of the highest-Tc tenth, where one width for every material held ' + (100 * unc.scores.reference_tail_coverage).toFixed(1) + '%. A range is for the computed Tc that Storm learns; measured Tc can lie further away, as for MgB₂.';
        return 'New in ' + name + ' (round 4): Storm 1.0’s trees and the crystal-graph network together, ' + fmtVal(sc.tc_mae) + ' K against ' + fmtVal(sc.reference_mae) + ' K for the trees alone.';
    }
  };


  const drawStormLatest = function drawStormLatest(c, C, B, t, narrow, si, L) {
    [drawStormRounds, drawStormInputsLatest, drawStormLearners, drawStormCombine, drawStormCheckLatest, drawStormNewLatest][si](c, C, B, t, narrow, L);
  };

  /* 0 · the rounds that built the Storm in use */
  const drawStormRounds = function drawStormRounds(c, C, B, t, narrow, L) {
    var rows = stormRounds(L);
    stormHeader(c, C, B, 'How ' + stormLatestTitle(L) + ' was built', narrow ? '' : 'each round released only if it beat the version in use');
    var rh = Math.min(narrow ? 56 : 56, (B.h - 30) / Math.max(1, rows.length)), y0 = B.y + 30;
    rows.forEach(function (r, i) {
      var a = stSpan(t, 0.3 + 0.7 * i, 0.8 + 0.7 * i);
      if (a <= 0) return;
      var y = y0 + i * rh, last = i === rows.length - 1, cy = y + (narrow ? 14 : rh / 2);
      c.globalAlpha = a;
      if (last && t > 0.8 + 0.7 * i) { stRound(c, B.x - 6, y + 2, B.w + 12, rh - 4, 8); c.fillStyle = stAlpha(C.accent, 0.1); c.fill(); }
      stTag(c, C, 'R' + r.round, B.x + 14, cy, { size: 10.5, bg: r.ok ? C.accent : C.surface, ring: r.ok ? null : C.grid, color: r.ok ? '#ffffff' : C.ink2 });
      label(c, C, r.name, B.x + 36, cy + 4, { size: narrow ? 12 : 13, weight: '600', color: r.ok ? C.ink : C.muted });
      stFont(c, C, narrow ? 12 : 13, '600');
      var nameW = c.measureText(r.name).width;
      if (last && t > 1.2 + 0.7 * i) stTag(c, C, 'in use', B.x + 36 + nameW + 8, cy, { align: 'left', size: 10.5, bg: C.track, color: C.ink });
      var wx = narrow ? B.x + 36 : B.x + 196, wy = narrow ? cy + 19 : cy + 4, ww = narrow ? B.w - 40 : B.w - 196 - 120;
      var full = r.what + (r.why ? ' · ' + r.why : ''), what = full;
      stFont(c, C, narrow ? 11.5 : 12);
      while (what.length > 8 && c.measureText(what + '…').width > ww) what = what.slice(0, -1).replace(/[\s,·]+$/, '');
      stText(c, C, what + (what !== full ? '…' : ''), wx, wy, { size: narrow ? 11.5 : 12, color: r.ok ? C.ink2 : C.muted });
      label(c, C, r.result, B.x + B.w, cy + 4, { align: 'right', size: narrow ? 11 : 12, weight: '600', color: r.ok ? C.accent : C.muted });
      c.globalAlpha = 1;
    });
  };

  /* 1 · the trees' inputs (the network's input is the crystal itself, drawn in the next step) */
  const drawStormInputsLatest = function drawStormInputsLatest(c, C, B, t, narrow, L) { drawStormInputs(c, C, B, t, narrow, L.info); };

  /* 2 · two learners: boosted trees and the crystal-graph network */
  const drawStormLearners = function drawStormLearners(c, C, B, t, narrow, L) {
    var Lr = L.trees.spec.learner || {}, half = narrow ? { x: B.x, y: B.y + 26, w: B.w, h: (B.h - 40) / 2 } : { x: B.x, y: B.y + 26, w: B.w * 0.48, h: B.h - 30 };
    var other = narrow ? { x: B.x, y: half.y + half.h + 14, w: B.w, h: half.h } : { x: B.x + B.w * 0.52, y: half.y, w: B.w * 0.48, h: half.h };
    label(c, C, fmtInt(Lr.trees) + ' boosted trees', half.x, half.y + 10, { size: 12.5, weight: '600', color: C.ink });
    var shown = narrow ? 5 : 6, gw = half.w / shown, grown = Math.min(shown, Math.floor(t / 0.5) + 1), th = Math.min(narrow ? 60 : 100, half.h - 46);
    for (var i = 0; i < shown; i++) {
      c.globalAlpha = i < grown ? 1 : 0.2;
      drawTreeGlyph(c, C, half.x + gw * (i + 0.5), half.y + 26, gw * 0.8, th, 4, i === grown - 1 && t < shown * 0.5 ? C.warm : C.accent);
    }
    c.globalAlpha = 1;
    label(c, C, 'each tree fixes what the trees before it got wrong', half.x, half.y + 26 + th + 18, { size: 11, color: C.muted });
    // the network: atoms joined to their neighbours, messages flowing in three layers
    label(c, C, L.ens.gnn && L.ens.gnn.version ? 'Crystal-graph network ' + L.ens.gnn.version : 'Crystal-graph network', other.x, other.y + 10, { size: 12.5, weight: '600', color: C.ink });
    var cx = other.x + other.w * 0.42, cy = other.y + 26 + (other.h - 46) / 2, R = Math.min(other.w * 0.3, (other.h - 56) / 2), pts = [];
    for (var q = 0; q < 8; q++) pts.push([cx + R * Math.cos(q * Math.PI / 4), cy + R * 0.8 * Math.sin(q * Math.PI / 4)]);
    pts.push([cx, cy]);
    c.lineWidth = 1; c.strokeStyle = C.grid;
    pts.forEach(function (p, a) { pts.forEach(function (o, b) { if (b > a && Math.hypot(p[0] - o[0], p[1] - o[1]) < R * 0.95) { c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(o[0], o[1]); c.stroke(); } }); });
    var ph = (t % 1.2) / 1.2, layer = Math.floor(t / 1.2) % 3;
    pts.forEach(function (p, a) { if (a < 8) dot(c, p[0] + (cx - p[0]) * ph, p[1] + (cy - p[1]) * ph, 2.4, C.warm); });
    pts.forEach(function (p, a) { dot(c, p[0], p[1], a === 8 ? 8 : 6, a === 8 ? C.accent : mix(C.accent, C.surface, 0.45)); });
    var ox = other.x + other.w * 0.8;
    ['Tc', 'λ', 'ω_log'].forEach(function (s, k) { stTag(c, C, s, ox, cy - 26 + k * 26, { size: 11.5, bg: C.track, color: C.ink, rich: true }); });
    stArrow(c, cx + R + 8, cy, ox - 26, cy, C.axis, 6);
    label(c, C, 'message passing, layer ' + (layer + 1) + ' of 3', other.x, other.y + other.h - 2, { size: 11, color: C.muted });
  };

  /* 3 · three routes, averaged, calibrated and given a range */
  const drawStormCombine = function drawStormCombine(c, C, B, t, narrow, L) {
    var sc = L.ens.scores, cal = L.ens.calibration || {}, unc = L.unc, gn = L.ens.gnn || {};
    stormHeader(c, C, B, 'Three routes to Tc, one prediction', narrow ? '' : 'errors on held-out materials');
    var gAll = state.data && state.data.gnn, adMae = gAll && typeof gAll.tc_via_allen_dynes_mae === 'number' ? fmtVal(gAll.tc_via_allen_dynes_mae) + ' K' : '';
    var srcs = [['trees', fmtVal(sc.reference_mae) + ' K'], ['network', typeof gn.tc_mae === 'number' ? fmtVal(gn.tc_mae) + ' K' : ''], [narrow ? 'Allen–Dynes' : 'λ, ω_log → Allen–Dynes', adMae]];
    var exW = typeof predStormExamples === 'function' ? predStormExamples()[0] : null;
    // one material through the same chain, with the numbers Storm computed for it (out of fold)
    function example(y, w) {
      if (!exW || t < 3.6) return;
      c.globalAlpha = stSpan(t, 3.6, 4.2);
      var txt = 'For ' + hurSub(exW.name) + ': (' + exW.trees.toFixed(1) + ' + ' + exW.gnn.toFixed(1) + ' + ' + exW.gnn_ad.toFixed(1) + ') / 3 = ' + exW.storm4.toFixed(1) + ' K' +
        (typeof exW.calibrated === 'number' ? ', calibrated ' + exW.calibrated.toFixed(1) + ' K' : '') + ', 90% range ' + exW.lo.toFixed(1) + '–' + exW.hi.toFixed(1) + ' K; measured ' + exW.tc_exp.toFixed(1) + ' K.';
      stParaRich(c, C, txt, B.x, y, w, 18, { size: narrow ? 12 : 12.5, color: C.ink2 });
      c.globalAlpha = 1;
    }
    var bw = narrow ? (B.w - 16) / 3 : Math.min(190, B.w * 0.24), bh = 40, y0 = B.y + 44;
    function box(x, y, w, text, sub, col, a) {
      c.globalAlpha = a;
      stRound(c, x, y, w, bh, 8); c.fillStyle = stAlpha(col, 0.14); c.fill(); c.lineWidth = 1; c.strokeStyle = col; c.stroke();
      stText(c, C, text, x + w / 2, y + (sub ? 16 : 24), { align: 'center', size: narrow ? 10.5 : 12, weight: '600', color: C.ink });
      if (sub) label(c, C, sub, x + w / 2, y + 32, { align: 'center', size: 10.5, color: C.muted });
      c.globalAlpha = 1;
    }
    if (narrow) {
      srcs.forEach(function (s, i) { box(B.x + i * (bw + 8), y0, bw, s[0], s[1], i === 2 ? C.warm : C.accent, stSpan(t, 0.2 + 0.3 * i, 0.6 + 0.3 * i)); });
      var steps = [['average', fmtVal(sc.tc_mae) + ' K'], ['calibrated to experiment', typeof cal.mae === 'number' ? fmtVal(cal.mae) + ' K measured' : '']];
      if (unc) steps.push(['90% range', (100 * unc.scores.coverage).toFixed(1) + '% held']);
      steps.forEach(function (s, i) {
        var a = stSpan(t, 1.4 + 0.8 * i, 1.9 + 0.8 * i), y = y0 + 70 + i * 62;
        if (a <= 0) return;
        c.globalAlpha = a; stArrow(c, B.x + B.w / 2, y - 24, B.x + B.w / 2, y - 4, C.axis, 6); c.globalAlpha = 1;
        box(B.x + B.w * 0.15, y, B.w * 0.7, s[0], s[1], C.accent, a);
      });
      example(y0 + 70 + steps.length * 62 + 4, B.w);
      return;
    }
    var xs = B.x, gap = 26;
    srcs.forEach(function (s, i) { box(xs, y0 + i * 56, bw, s[0], s[1], i === 2 ? C.warm : C.accent, stSpan(t, 0.2 + 0.3 * i, 0.6 + 0.3 * i)); });
    var chain = [['average', fmtVal(sc.tc_mae) + ' K'], ['calibrated to experiment', typeof cal.mae === 'number' ? fmtVal(cal.mae) + ' K measured' : '']];
    if (unc) chain.push(['90% range', (100 * unc.scores.coverage).toFixed(1) + '% held']);
    var cw = Math.min(180, (B.w - bw - gap * (chain.length + 1)) / chain.length), cy = y0 + 56;
    chain.forEach(function (s, i) {
      var a = stSpan(t, 1.4 + 0.8 * i, 1.9 + 0.8 * i), x = xs + bw + gap + i * (cw + gap);
      if (a <= 0) return;
      c.globalAlpha = a;
      if (i === 0) [0, 1, 2].forEach(function (k) { stArrow(c, xs + bw + 3, y0 + k * 56 + bh / 2, x - 3, cy + bh / 2, C.axis, 6); });
      else stArrow(c, x - gap + 3, cy + bh / 2, x - 3, cy + bh / 2, C.axis, 6);
      c.globalAlpha = 1;
      box(x, cy, cw, s[0], s[1], C.accent, a);
    });
    example(y0 + 3 * 56 + 30, Math.min(B.w, 760));
  };

  /* 4 · fold by fold against Storm 1.0, plus the measured-Tc and range checks */
  const drawStormCheckLatest = function drawStormCheckLatest(c, C, B, t, narrow, L) {
    var sc = L.ens.scores, f = list(sc.folds), r = list(sc.reference_folds), n = f.length, cal = L.ens.calibration || {}, unc = L.unc;
    stormHeader(c, C, B, 'Better than Storm 1.0 in ' + sc.folds_better + ' of ' + n + ' folds', narrow ? '' : 'Tc error per test fold (K)');
    var P = { x: B.x + 34, y: B.y + 34, w: B.w - 34 - (narrow ? 4 : 220), h: B.h - (narrow ? 150 : 74) };
    var top = 0;
    f.concat(r).forEach(function (v) { top = Math.max(top, v); });
    var tstep = niceStep(top * 1.1 || 1, 3);
    top = Math.ceil(top * 1.1 / tstep) * tstep;
    function Y(v) { return P.y + P.h - v / top * P.h; }
    c.lineWidth = 1;
    for (var g = 0; g <= top + 1e-9; g += tstep) {
      var yy = Math.round(Y(g)) + 0.5;
      c.strokeStyle = g ? C.grid : C.axis; c.beginPath(); c.moveTo(P.x, yy); c.lineTo(P.x + P.w, yy); c.stroke();
      label(c, C, fmtTick(g), P.x - 6, yy + 4, { align: 'right', size: 10.5, color: C.muted });
    }
    var gw = P.w / n, bw = Math.min(26, gw * 0.3);
    for (var i = 0; i < n; i++) {
      var gx = P.x + gw * (i + 0.5), hr = (P.y + P.h - Y(r[i])) * stSpan(t, 0.3 + 0.5 * i, 0.9 + 0.5 * i), hf = (P.y + P.h - Y(f[i])) * stSpan(t, 0.6 + 0.5 * i, 1.2 + 0.5 * i);
      c.fillStyle = C.axis; c.fillRect(gx - bw - 1, P.y + P.h - hr, bw, hr);
      c.fillStyle = C.accent; c.fillRect(gx + 1, P.y + P.h - hf, bw, hf);
      label(c, C, 'fold ' + (i + 1), gx, P.y + P.h + 15, { align: 'center', size: 10.5, color: C.muted });
      if (t > 1.2 + 0.5 * i && f[i] < r[i]) label(c, C, '✓', gx + 1 + bw / 2, P.y + P.h - hf - 6, { align: 'center', size: 11, weight: '600', color: C.accent });
    }
    var items = [['Storm 1.0’s trees', fmtVal(sc.reference_mae) + ' K', C.axis], [stormLatestTitle(L), fmtVal(sc.tc_mae) + ' K', C.accent]];
    var extra = [];
    if (typeof cal.mae === 'number') extra.push('measured Tc: ' + fmtVal(cal.mae) + ' K' + (typeof cal.mae_storm3 === 'number' ? ' (Storm 3.0 ' + fmtVal(cal.mae_storm3) + ')' : ''));
    if (unc) extra.push('90% ranges held ' + (100 * unc.scores.coverage).toFixed(1) + '%');
    if (narrow) {
      var ky = P.y + P.h + 40;
      items.forEach(function (it, k) { c.fillStyle = it[2]; c.fillRect(B.x, ky + k * 19 - 8, 10, 10); label(c, C, it[0] + ' ' + it[1], B.x + 14, ky + k * 19 + 1, { size: 11.5, weight: k ? '600' : '400', color: k ? C.accent : C.ink2 }); });
      if (t > 3) { c.globalAlpha = stSpan(t, 3, 3.5); var ext = extra.join('; ') + '.'; stParaRich(c, C, ext.charAt(0).toUpperCase() + ext.slice(1), B.x, ky + 44, B.w, 16, { size: 11.5, color: C.ink2 }); c.globalAlpha = 1; }
      return;
    }
    var kx = P.x + P.w + 26, ky2 = P.y + 10;
    items.forEach(function (it, k) {
      c.fillStyle = it[2]; c.fillRect(kx, ky2 + k * 44 - 8, 10, 10);
      label(c, C, it[0], kx + 16, ky2 + k * 44 + 1, { size: 11.5, color: k ? C.accent : C.ink2 });
      label(c, C, it[1], kx + 16, ky2 + k * 44 + 19, { size: 13, weight: '600', color: k ? C.accent : C.ink2 });
    });
    extra.forEach(function (e, k) {
      c.globalAlpha = stSpan(t, 3 + 0.5 * k, 3.5 + 0.5 * k);
      stTag(c, C, e, kx, ky2 + 104 + k * 30, { align: 'left', size: 11.5, bg: C.track, color: C.ink, rich: true });
      c.globalAlpha = 1;
    });
  };

  /* 5 · what the newest round added: the 90% range, shown for the worked examples */
  const drawStormNewLatest = function drawStormNewLatest(c, C, B, t, narrow, L) {
    var unc = L.unc;
    if (!unc) { drawStormCombine(c, C, B, t, narrow, L); return; }
    stormHeader(c, C, B, narrow ? 'New in ' + stormLatestTitle(L) + ': a 90% range' : 'New in ' + stormLatestTitle(L) + ' (round 5): a 90% range for every prediction', '');
    var ex = typeof predStormExamples === 'function' ? predStormExamples() : [];
    if (!ex.length) ex = list(unc.worked).slice(0, narrow ? 4 : 5);
    if (!ex.length) ex = list(unc.examples).slice(0, narrow ? 4 : 5).map(function (e) { return { name: e.name, storm4: e.pred, lo: e.lo, hi: e.hi, dft_tc: e.tc }; });
    var vmax = 0;
    ex.forEach(function (e) { vmax = Math.max(vmax, e.hi, e.dft_tc || 0, e.tc_exp || 0); });
    vmax = vmax * 1.08 || 1;
    var nameW = narrow ? 64 : 90, x0 = B.x + nameW, x1 = B.x + B.w - 16, rh = Math.min(narrow ? 46 : 50, (B.h - 70) / Math.max(1, ex.length));
    function X(v) { return x0 + Math.max(0, Math.min(1, v / vmax)) * (x1 - x0); }
    var axisY = B.y + 40 + ex.length * rh;
    ex.forEach(function (e, i) {
      var a = stSpan(t, 0.4 + 0.7 * i, 0.9 + 0.7 * i);
      if (a <= 0) return;
      var y = B.y + 40 + i * rh + rh / 2;
      c.globalAlpha = a;
      stText(c, C, hurSub(e.name), B.x, y + 4, { size: 12.5, weight: '600', color: C.ink });
      c.fillStyle = stAlpha(C.accent, 0.2); stRound(c, X(e.lo), y - 6, Math.max(3, (X(e.hi) - X(e.lo)) * stSpan(t, 0.6 + 0.7 * i, 1.4 + 0.7 * i)), 12, 6); c.fill();
      dot(c, X(e.storm4), y, 5, C.accent);
      if (typeof e.dft_tc === 'number') { c.fillStyle = C.ink2; c.beginPath(); c.moveTo(X(e.dft_tc), y - 6); c.lineTo(X(e.dft_tc) + 5, y); c.lineTo(X(e.dft_tc), y + 6); c.lineTo(X(e.dft_tc) - 5, y); c.closePath(); c.fill(); }
      if (typeof e.tc_exp === 'number' && e.tc_exp <= vmax) {
        var sx = X(e.tc_exp); c.fillStyle = C.warm; c.beginPath();
        for (var q = 0; q < 10; q++) { var rr = q % 2 ? 3 : 7, an = -Math.PI / 2 + q * Math.PI / 5; c.lineTo(sx + Math.cos(an) * rr, y + Math.sin(an) * rr); }
        c.closePath(); c.fill();
      }
      c.globalAlpha = 1;
    });
    c.lineWidth = 1; c.strokeStyle = C.axis; c.beginPath(); c.moveTo(x0, axisY + 0.5); c.lineTo(x1, axisY + 0.5); c.stroke();
    var stp = niceStep(vmax, 4);
    for (var g = 0; g <= vmax + 1e-9; g += stp) label(c, C, fmtTick(g), X(g), axisY + 15, { align: 'center', size: 10.5, color: C.muted });
    label(c, C, 'K', x1 + 4, axisY + 15, { size: 10.5, color: C.muted });
    var ly = axisY + (narrow ? 34 : 36), lx = B.x;
    c.globalAlpha = stSpan(t, 1, 1.5);
    c.fillStyle = stAlpha(C.accent, 0.2); stRound(c, lx, ly - 9, 22, 10, 5); c.fill(); label(c, C, '90% range', lx + 28, ly, { size: 11, color: C.ink2 });
    dot(c, lx + (narrow ? 104 : 116), ly - 4, 4.5, C.accent); label(c, C, 'Storm', lx + (narrow ? 112 : 124), ly, { size: 11, color: C.ink2 });
    var dx = lx + (narrow ? 5 : 190);
    if (narrow) ly += 20;
    c.fillStyle = C.ink2; c.beginPath(); c.moveTo(dx, ly - 10); c.lineTo(dx + 5, ly - 4); c.lineTo(dx, ly + 2); c.lineTo(dx - 5, ly - 4); c.closePath(); c.fill();
    label(c, C, 'DFT', dx + 9, ly, { size: 11, color: C.ink2 });
    if (ex.some(function (e) { return typeof e.tc_exp === 'number'; })) {
      var mx = dx + 52; c.fillStyle = C.warm; c.beginPath();
      for (var q2 = 0; q2 < 10; q2++) { var r2 = q2 % 2 ? 3 : 6, a2 = -Math.PI / 2 + q2 * Math.PI / 5; c.lineTo(mx + Math.cos(a2) * r2, ly - 4 + Math.sin(a2) * r2); }
      c.closePath(); c.fill(); label(c, C, 'measured', mx + 9, ly, { size: 11, color: C.ink2 });
    }
    c.globalAlpha = 1;
  };
