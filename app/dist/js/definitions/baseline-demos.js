'use strict';
// baseline-demos: shared lexical function definitions; no startup side effects.

  const pct1 = function pct1(x) { return (100 * x).toFixed(1) + '%'; };

  const baseK1 = function baseK1(x) { return x.toFixed(1); };

  const modelTitle = function modelTitle(variant, si) { var st = MODEL_STAGES[variant][si]; return st.titleFn ? st.titleFn() : st.title; };


  // The Storm in use, for the comparison under Storm's two baselines
  const baseStormLine = function baseStormLine(variant) {
    var L = typeof stormLatest === 'function' ? stormLatest() : null, sc = modelScores(variant);
    if (!L) return '';
    return (sc.tc !== null ? (variant === 'foundation' ? 'The foundation model' : 'This baseline') + ' is off by ' + fmtVal(sc.tc) + ' K for Tc; ' + stormLatestTitle(L) + ', our AI-designed model, by '
      : stormLatestTitle(L) + ', our AI-designed model, is off by ') + fmtVal(L.ens.scores.tc_mae) + ' K with the same grouped cross-validation';
  };

  const modelCaption = function modelCaption(variant, si) {
    var st = MODEL_STAGES[variant][si], hi = hurInfo(), ri = radInfo();
    if (variant === 'baseline' || variant === 'foundation') {
      var sl = si === MODEL_STAGES[variant].length - 1 ? baseStormLine(variant) : '';
      return st.text + (sl ? ' ' + sl + '.' : '');
    }
    if (variant === 'hurricane') {
      if (!hi) return 'Hurricane’s baseline loads with the live progress data.';
      var dd = hi.data, sc = hi.v.scores, fam = dd.families || {}, cu = (sc.by_family || {}).cuprate;
      switch (si) {
        case 0: return 'Hurricane’s data: ' + fmtInt(dd.n) + ' cuprates, iron- and nickel-based compounds, heavy-fermion compounds and other oxides with measured Tc from SuperCon, matched to Materials Project crystal structures by 3DSC. ' +
          fmtInt(dd.n_sc) + ' of them superconduct; the other ' + fmtInt(dd.n - dd.n_sc) + ' were measured and did not. The baseline sees only the chemical formula.';
        case 1: return 'The baseline describes each compound by 33 numbers from its formula alone: the number of elements, and the mean, spread, minimum and maximum of eight element properties (atomic number, mass, electronegativity, row, group, radius, Mendeleev number, valence). No crystal structure and no physics features.';
        case 2: return 'Histogram gradient boosting adds up to 800 small decision trees (learning rate 0.04, at most 31 leaves per tree). It learns log(1 + Tc), so the many low-Tc compounds do not dominate; a compound that does not superconduct counts as Tc = 0.';
        default: return 'Five-fold cross-validation grouped by parent compound, so no test compound shares its parent with the training data. The baseline is off by ' + baseK1(sc.reference_mae) + ' K on average, ' + hurTitle(hi) + ', our AI-designed model, by ' + baseK1(sc.tc_mae) + ' K, better in ' + sc.folds_better + ' of ' + list(sc.folds).length + ' folds' +
          (cu ? '. Cuprates are hardest: ' + baseK1(cu.mae_ref) + ' K for the baseline, ' + baseK1(cu.mae) + ' K for ' + hurTitle(hi) : '') + '.';
      }
    }
    if (!ri) return 'Radar’s baseline loads with the live progress data.';
    var rd = ri.data, rs = ri.v.scores, cl = rd.classes || {};
    switch (si) {
      case 0: return 'Radar’s data: ' + fmtInt(rd.n) + ' SuperCon entries in 3DSC, ' + fmtInt(rd.n_unconventional) + ' from the four unconventional families (cuprates, iron- and nickel-based, heavy-fermion, other oxides) and ' + fmtInt(rd.n_conventional) + ' conventional ones' +
        (typeof cl.Chevrel === 'number' ? ', among them ' + fmtInt(cl.Chevrel) + ' Chevrel phases and ' + fmtInt(cl.Carbon || 0) + ' carbon-based superconductors' : '') + '. The baseline sees only the chemical formula.';
      case 1: return 'The same 33 numbers from the formula as Hurricane’s baseline: the number of elements, and the mean, spread, minimum and maximum of eight element properties. No crystal structure and no physics features.';
      case 2: return 'A gradient-boosted classifier (up to 400 trees, learning rate 0.05, at most 31 leaves per tree) gives the probability that a material belongs to an unconventional family. At 0.5 or more it goes to Hurricane, otherwise to Storm.';
      default: return 'Five-fold cross-validation grouped by parent compound. The baseline’s log loss is ' + rs.reference_log_loss.toFixed(3) + ', ' + radTitle(ri) + '’s ' + rs.log_loss.toFixed(3) + ' (lower is better), better in ' + rs.folds_better + ' of ' + list(rs.folds).length + ' folds; it picks the right model ' +
        pct1(rs.reference_balanced_accuracy) + ' of the time against ' + pct1(rs.balanced_accuracy) + ' for ' + radTitle(ri) + ' (balanced accuracy).';
    }
  };


  /* 0 · the data: families (Hurricane) or classes (Radar) */
  const drawBaseData = function drawBaseData(c, C, D, t, narrow, variant) {
    var rows = [], hi = hurInfo(), ri = radInfo(), vmax = 1, i;
    if (variant === 'hurricane' && hi) {
      hurFamilies(hi).forEach(function (f) { rows.push({ label: HUR_FAM_SHORT[f.id] || f.label, n: f.n, sc: f.n_sc, note: 'up to ' + Math.round(f.max_tc) + ' K', col: hurColor(C, f.id) }); });
    } else if (variant === 'radar' && ri) {
      var cl = ri.data.classes || {};
      RAD_UNCONV.concat(RAD_CONV).forEach(function (k) { if (typeof cl[k] === 'number') rows.push({ label: RAD_SHORT[k] || k, n: cl[k], to: RAD_UNCONV.indexOf(k) >= 0 ? 'Hurricane' : 'Storm' }); });
    }
    if (!rows.length) { label(c, C, 'The data load with the live progress data.', D.x, D.y + 30, { size: 13, color: C.muted }); return; }
    rows.forEach(function (r) { vmax = Math.max(vmax, r.n); });
    var nameW = narrow ? 92 : 130, x0 = D.x + nameW, x1 = D.x + D.w - (narrow ? 70 : 150), rh = Math.min(narrow ? 34 : 38, (D.h - 40) / rows.length);
    for (i = 0; i < rows.length; i++) {
      var r = rows[i], y = D.y + 18 + i * rh, a = stSpan(t, 0.3 + 0.25 * i, 0.8 + 0.25 * i);
      if (a <= 0) continue;
      c.globalAlpha = a;
      label(c, C, r.label, D.x, y + 5, { size: narrow ? 11.5 : 12.5, weight: '600', color: C.ink });
      var w = (x1 - x0) * Math.sqrt(r.n / vmax) * a;
      if (variant === 'hurricane') {
        var wsc = w * r.sc / r.n;
        stRound(c, x0, y - 7, Math.max(2, w), 14, 4); c.fillStyle = stAlpha(r.col, 0.25); c.fill();
        stRound(c, x0, y - 7, Math.max(2, wsc), 14, 4); c.fillStyle = r.col; c.fill();
        label(c, C, fmtInt(r.n) + (narrow ? '' : ' · ' + r.note), x0 + w + 8, y + 4, { size: 11.5, weight: '600', color: C.ink2 });
      } else {
        var col = r.to === 'Hurricane' ? C.accent : C.warm;
        stRound(c, x0, y - 7, Math.max(2, w), 14, 4); c.fillStyle = col; c.fill();
        label(c, C, fmtInt(r.n) + (narrow ? '' : ' → ' + r.to), x0 + w + 8, y + 4, { size: 11.5, weight: '600', color: C.ink2 });
      }
      c.globalAlpha = 1;
    }
    var ly = D.y + 18 + rows.length * rh + 12;
    c.globalAlpha = stSpan(t, 1.6, 2.1);
    if (variant === 'hurricane') {
      c.fillStyle = C.accent; c.fillRect(D.x, ly - 8, 10, 10); label(c, C, 'superconducts', D.x + 14, ly + 1, { size: 11, color: C.ink2 });
      c.fillStyle = stAlpha(C.accent, 0.25); c.fillRect(D.x + 110, ly - 8, 10, 10); label(c, C, 'measured, not superconducting', D.x + 124, ly + 1, { size: 11, color: C.ink2 });
    } else {
      c.fillStyle = C.accent; c.fillRect(D.x, ly - 8, 10, 10); label(c, C, 'unconventional → Hurricane', D.x + 14, ly + 1, { size: 11, color: C.ink2 });
      c.fillStyle = C.warm; c.fillRect(D.x + (narrow ? 0 : 190), ly - 8 + (narrow ? 18 : 0), 10, 10); label(c, C, 'conventional → Storm', D.x + (narrow ? 14 : 204), ly + 1 + (narrow ? 18 : 0), { size: 11, color: C.ink2 });
    }
    c.globalAlpha = 1;
  };


  /* 1 · 33 numbers from the formula (the composition block of Storm's baseline, without structure) */
  const drawBaseFeatures = function drawBaseFeatures(c, C, D, t, narrow) {
    drawModelFeatures(c, C, D, t, narrow, COMP_GROUPS, [['Composition · 33 numbers', 'Composition · 33', C.accent]]);
  };


  /* 2 · boosted trees, ending in Tc (Hurricane) or in a probability and a route (Radar) */
  const drawBaseTrees = function drawBaseTrees(c, C, D, t, narrow, variant) {
    var nShow = narrow ? 5 : 9, s = narrow ? 16 : 20, slotW = (D.w - 40) / (nShow + 1), total = variant === 'radar' ? 400 : 800;
    for (var i = 0; i < nShow; i++) {
      var x = D.x + 20 + slotW * (i + 0.5), y = D.y + 14, a = stSpan(t, 0.4 + i * (2.4 / nShow), 0.7 + i * (2.4 / nShow));
      if (a <= 0) continue;
      c.globalAlpha = a;
      treeGlyph(c, C, x, y, s, C.accent);
      if (i > 0) label(c, C, '+', x - slotW / 2, y + s * 0.8, { align: 'center', base: 'middle', size: 14, weight: '600', color: C.ink2 });
    }
    c.globalAlpha = stSpan(t, 2.8, 3.2);
    label(c, C, '… ' + total, D.x + 20 + slotW * (nShow + 0.5), D.y + 14 + s * 0.85, { align: 'center', base: 'middle', size: 13, weight: '600', color: C.ink2 });
    c.globalAlpha = stSpan(t, 3.2, 3.8);
    var by = D.y + D.h * (narrow ? 0.5 : 0.45), bx = D.x + (narrow ? 0 : D.w * 0.12), bw = narrow ? D.w : D.w * 0.76;
    if (variant === 'radar') {
      // the probability bar with the 0.5 cut between Storm and Hurricane
      stRound(c, bx, by, bw, 18, 9); c.fillStyle = C.surface2; c.fill(); c.strokeStyle = C.grid; c.lineWidth = 1; c.stroke();
      var g = c.createLinearGradient(bx, 0, bx + bw, 0); g.addColorStop(0, C.warm); g.addColorStop(1, C.accent);
      stRound(c, bx, by, bw, 18, 9); c.fillStyle = g; c.globalAlpha *= 0.85; c.fill(); c.globalAlpha = stSpan(t, 3.2, 3.8);
      var cx = bx + bw / 2;
      c.strokeStyle = C.ink; c.lineWidth = 2; c.beginPath(); c.moveTo(cx, by - 8); c.lineTo(cx, by + 26); c.stroke();
      label(c, C, '0', bx, by + 36, { size: 11, color: C.muted }); label(c, C, '1', bx + bw, by + 36, { align: 'right', size: 11, color: C.muted });
      label(c, C, '0.5', cx, by + 36, { align: 'center', size: 11, weight: '600', color: C.ink });
      label(c, C, '← Storm', bx + bw * 0.25, by - 10, { align: 'center', size: 12, weight: '600', color: C.warm });
      label(c, C, 'Hurricane →', bx + bw * 0.75, by - 10, { align: 'center', size: 12, weight: '600', color: C.accent });
      stSym(c, C, symParts('probability of an unconventional family'), bx, by + 58, { size: 12, color: C.ink2 });
    } else {
      stSym(c, C, symParts('trees add up to log(1 + Tc)  →  Tc'), bx, by + 6, { size: narrow ? 13 : 15, weight: '600', color: C.ink });
      stParaRich(c, C, 'A compound that does not superconduct counts as Tc = 0.', bx, by + 32, bw, 17, { size: 12, color: C.ink2 });
    }
    c.globalAlpha = 1;
  };


  /* 3 · fold by fold against the model in use */
  const drawBaseScore = function drawBaseScore(c, C, D, t, narrow, variant) {
    var hi = hurInfo(), ri = radInfo(), f, r, unit, name, refMean, mean, fmt, extra = [];
    if (variant === 'hurricane' && hi) {
      var sc = hi.v.scores; f = list(sc.folds); r = list(sc.reference_folds); refMean = sc.reference_mae; mean = sc.tc_mae; name = hurTitle(hi); unit = ' K'; fmt = baseK1;
      var bf = sc.by_family || {};
      HUR_FAMS.forEach(function (k) { if (bf[k] && typeof bf[k].mae_ref === 'number') extra.push((HUR_FAM_SHORT[k] || k) + ': ' + baseK1(bf[k].mae_ref) + ' → ' + baseK1(bf[k].mae) + ' K'); });
    } else if (variant === 'radar' && ri) {
      var rs = ri.v.scores; f = list(rs.folds); r = list(rs.reference_folds); refMean = rs.reference_log_loss; mean = rs.log_loss; name = radTitle(ri); unit = ''; fmt = function (v) { return v.toFixed(3); };
      extra.push('right model: ' + pct1(rs.reference_balanced_accuracy) + ' → ' + pct1(rs.balanced_accuracy));
    }
    if (!f || !f.length || f.length !== r.length) { label(c, C, 'Scores load with the live progress data.', D.x, D.y + 30, { size: 13, color: C.muted }); return; }
    var n = f.length, better = 0;
    for (var q = 0; q < n; q++) if (f[q] < r[q]) better++;
    label(c, C, variant === 'radar' ? 'Log loss per test fold (lower is better)' : 'Tc error per test fold (K)', D.x, D.y + 8, { size: 12, weight: '600', color: C.ink2 });
    var P = { x: D.x + 36, y: D.y + 24, w: D.w - 36 - (narrow ? 4 : 250), h: D.h - (narrow ? 150 : 50) };
    var top = 0;
    f.concat(r).forEach(function (v) { top = Math.max(top, v); });
    var tstep = niceStep(top * 1.1 || 1, 3);
    top = Math.ceil(top * 1.1 / tstep) * tstep;
    function Y(v) { return P.y + P.h - v / top * P.h; }
    c.lineWidth = 1;
    for (var gv = 0; gv <= top + 1e-9; gv += tstep) {
      var yy = Math.round(Y(gv)) + 0.5;
      c.strokeStyle = gv ? C.grid : C.axis; c.beginPath(); c.moveTo(P.x, yy); c.lineTo(P.x + P.w, yy); c.stroke();
      label(c, C, variant === 'radar' ? gv.toFixed(2) : fmtTick(gv), P.x - 6, yy + 4, { align: 'right', size: 10.5, color: C.muted });
    }
    var gw = P.w / n, bw = Math.min(26, gw * 0.3);
    for (var i = 0; i < n; i++) {
      var gx = P.x + gw * (i + 0.5), hr = (P.y + P.h - Y(r[i])) * stSpan(t, 0.3 + 0.4 * i, 0.8 + 0.4 * i), hf = (P.y + P.h - Y(f[i])) * stSpan(t, 0.5 + 0.4 * i, 1.0 + 0.4 * i);
      c.fillStyle = C.axis; c.fillRect(gx - bw - 1, P.y + P.h - hr, bw, hr);
      c.fillStyle = C.accent; c.fillRect(gx + 1, P.y + P.h - hf, bw, hf);
      label(c, C, 'fold ' + (i + 1), gx, P.y + P.h + 15, { align: 'center', size: 10.5, color: C.muted });
      if (t > 1.0 + 0.4 * i && f[i] < r[i]) label(c, C, '✓', gx + 1 + bw / 2, P.y + P.h - hf - 6, { align: 'center', size: 11, weight: '600', color: C.accent });
    }
    var items = [['baseline', fmt(refMean) + unit, C.axis], [name, fmt(mean) + unit, C.accent]];
    var head = name + ' better in ' + better + ' of ' + n + ' folds';
    if (narrow) {
      var ky = P.y + P.h + 40;
      items.forEach(function (it, k) { c.fillStyle = it[2]; c.fillRect(D.x, ky + k * 19 - 8, 10, 10); label(c, C, it[0] + ' ' + it[1], D.x + 14, ky + k * 19 + 1, { size: 11.5, weight: k ? '600' : '400', color: k ? C.accent : C.ink2 }); });
      c.globalAlpha = stSpan(t, 3, 3.5);
      label(c, C, head, D.x, ky + 44, { size: 11.5, weight: '600', color: C.ink });
      if (extra.length) stParaRich(c, C, extra.join('; '), D.x, ky + 62, D.w, 16, { size: 11, color: C.ink2 });
      c.globalAlpha = 1;
      return;
    }
    var kx = P.x + P.w + 30, ky2 = P.y + 10;
    items.forEach(function (it, k) {
      c.fillStyle = it[2]; c.fillRect(kx, ky2 + k * 44 - 8, 10, 10);
      label(c, C, it[0], kx + 16, ky2 + k * 44 + 1, { size: 11.5, color: k ? C.accent : C.ink2 });
      label(c, C, it[1], kx + 16, ky2 + k * 44 + 19, { size: 13, weight: '600', color: k ? C.accent : C.ink2 });
    });
    c.globalAlpha = stSpan(t, 3, 3.5);
    label(c, C, head, kx, ky2 + 100, { size: 12, weight: '600', color: C.ink });
    extra.forEach(function (e, k) { stText(c, C, e, kx, ky2 + 124 + k * 20, { size: 11.5, color: C.ink2 }); });
    c.globalAlpha = 1;
  };
