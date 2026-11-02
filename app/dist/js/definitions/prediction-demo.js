'use strict';
// prediction-demo: shared lexical function definitions; no startup side effects.

  // a stable sort: by key, then by the original order
  const predSortBy = function predSortBy(arr, key) {
    return arr.map(function (x, i) { return { x: x, i: i, k: key(x) }; }).sort(function (a, b) { return a.k - b.k || a.i - b.i; }).map(function (o) { return o.x; });
  };

  const predNum = function predNum(v) { return typeof v === 'number' && isFinite(v); };

  // Storm's examples: one crystal structure per composition first (so every number belongs to one crystal), and the ones
  // whose computed Tc falls inside the range before the ones it misses, which are shown too
  const predStormExamples = function predStormExamples() {
    var u = state.data && state.data.ai_model && state.data.ai_model.uncertainty;
    var ok = list(u && u.worked).filter(function (w) {
      return w && ['trees', 'gnn', 'gnn_lambda', 'gnn_wlog', 'gnn_ad', 'storm4', 'lo', 'hi', 'tc_exp'].every(function (k) { return predNum(w[k]); });
    });
    return predSortBy(ok, function (w) { return (w.n_structures > 1 ? 2 : 0) + (predNum(w.dft_tc) && (w.dft_tc < w.lo || w.dft_tc > w.hi) ? 1 : 0); }).slice(0, 4);
  };

  // Hurricane's examples: scored anchors, one per family first (cuprates, heavy-fermion, iron-based, other oxides)
  const predHurExamples = function predHurExamples() {
    var hi = hurInfo(), an = hi && hi.v.anchors, rank = { 'cuprate': 0, 'heavy-fermion': 1, 'iron-based': 2, 'other oxide': 3 };
    var ok = predSortBy(list(an && an.table).filter(function (r) {
      return r && r.use === 'score' && r.unknown !== true && ['pred', 'tc_sc', 'p_sc', 'tc_exp'].every(function (k) { return predNum(r[k]); });
    }), function (r) { return rank[r.family] === undefined ? 9 : rank[r.family]; });
    var seen = {}, first = [], rest = [];
    ok.forEach(function (r) { if (seen[r.family]) rest.push(r); else { seen[r.family] = 1; first.push(r); } });
    return first.concat(rest).slice(0, 3);
  };

  // Storm 1.0's trees, from its own spec: how many trees and how many input numbers
  const predTreeSpec = function predTreeSpec() {
    var am = state.data && state.data.ai_model, vs = am ? list(am.versions).filter(function (v) { return v && v.spec; }) : [];
    var v = vs.filter(function (x) { return x.version === am.current; })[0] || vs[0], n = 0;
    if (!v) return null;
    list(v.spec.inputs).forEach(function (i) { n += i.n || 0; });
    return { trees: (v.spec.learner || {}).trees, n: n, name: (am.name || 'Storm') + ' ' + v.version };
  };

  // a probability as text; Radar's are rounded to two decimals, so 0 and 1 mean below 0.01 and above 0.99
  const predP = function predP(p) { return p < 0.005 ? 'below 0.01' : p > 0.995 ? 'above 0.99' : p.toFixed(2); };

  const predPShort = function predPShort(p) { return p < 0.005 ? '< 0.01' : p > 0.995 ? '> 0.99' : '= ' + p.toFixed(2); };

  const predExamples = function predExamples(mode) { return mode === 'storm' ? predStormExamples() : mode === 'hurricane' ? predHurExamples() : []; };

  const predExample = function predExample() {
    var ex = predExamples(demo.predMode);
    return ex.length ? ex[demo.predEx % ex.length] : null;
  };

  const predK = function predK(v) { return typeof v === 'number' ? (Math.abs(v) >= 100 ? Math.round(v) : v.toFixed(1)) + ' K' : '—'; };

  // Radar's own call for a graded material, when Radar has scored it (progress.json "radar", known materials)
  const predRadar = function predRadar(name) {
    var ri = radInfo(), k = ri ? list(ri.v.known).filter(function (x) { return x.name === name; })[0] : null;
    return k && typeof k.p_unconventional === 'number' ? k : null;
  };

  const stormSteps = function stormSteps(w) {
    var rd = predRadar(w.name), steps = [];
    steps.push({ id: 'radar', d: 2, text: rd ? radTitle(radInfo()) + ' sends it to Storm: the probability of an unconventional family is ' + predP(rd.p_unconventional) + '.'
      : 'A conventional, phonon-mediated superconductor, so it goes to Storm.' });
    var ts = predTreeSpec();
    steps.push({ id: 'trees', d: 2.6, text: (ts && ts.trees ? ts.name + '’s ' + fmtInt(ts.trees) + ' boosted trees read ' + ts.n + ' numbers about the material' : 'Storm’s boosted trees read numbers about the material’s composition, structure and physics') +
      ', and each tree adds a small correction: Tc = ' + predK(w.trees) + '.' });
    steps.push({ id: 'graph', d: 3, text: 'The crystal-graph network passes messages between each atom and its 12 nearest neighbours: Tc = ' + predK(w.gnn) + ', with λ = ' + w.gnn_lambda.toFixed(2) + ' and ω_log = ' + Math.round(w.gnn_wlog) + ' K.' });
    steps.push({ id: 'ad', d: 2.6, text: 'The Allen–Dynes formula with μ* = ' + (w.mu_star || 0.1).toFixed(2) + ' turns that λ and ω_log into Tc = ' + predK(w.gnn_ad) + '.' });
    steps.push({ id: 'avg', d: 2.4, text: 'Storm averages the three: (' + w.trees.toFixed(1) + ' + ' + w.gnn.toFixed(1) + ' + ' + w.gnn_ad.toFixed(1) + ') / 3 = ' + predK(w.storm4) + '. The full DFT calculation gives ' + predK(w.dft_tc) + '.' });
    if (typeof w.calibrated === 'number') steps.push({ id: 'cal', d: 2.2, text: 'Calibrated to experiment by round 3’s map: ' + predK(w.calibrated) + ', against ' + predK(w.tc_exp) + ' measured.' });
    var dft = predNum(w.dft_tc), inR = dft && w.dft_tc >= w.lo && w.dft_tc <= w.hi;
    var rt = (stormUnc() ? 'Storm ' + stormUnc().version + '’s' : 'The') + ' 90% range for the computed Tc: ' + w.lo.toFixed(1) + '–' + predK(w.hi) +
      (!dft ? '.' : inR ? ', which holds the DFT value.' : '. The DFT value, ' + predK(w.dft_tc) + ', lies outside it, as it may for one material in ten.');
    if (typeof w.calibrated !== 'number') {
      rt += ' Measured: ' + predK(w.tc_exp) + '.';
      if (dft && w.tc_exp > 2 * Math.max(w.dft_tc, w.hi)) rt += ' Here the DFT calculation that Storm learns from is itself far below the measurement.';
    }
    steps.push({ id: 'range', d: 2.6, text: rt });
    return steps;
  };

  const hurSteps = function hurSteps(r) {
    var rd = predRadar(r.name), ph = r.physics || {}, steps = [], bits = [];
    steps.push({ id: 'radar', d: 2, text: rd ? radTitle(radInfo()) + ' sends it to Hurricane: the probability of an unconventional family is ' + predP(rd.p_unconventional) + '.'
      : 'One of Hurricane’s four unconventional families, so it goes to Hurricane.' });
    if (typeof ph.p_cu === 'number') bits.push('nominal charge-balance estimate p = ' + ph.p_cu.toFixed(2) + (typeof ph.dome !== 'number' ? '' : ', giving a heuristic dome feature of ' + Math.round(100 * ph.dome) + '%'));
    if (typeof ph.cu_layers === 'number') bits.push('Cu-count proxy = ' + ph.cu_layers + ' (formula coefficient capped at 6, not a measured layer count)');
    if (typeof ph.tm_d === 'number' && typeof ph.p_cu !== 'number') bits.push('nominal d-count estimate ' + ph.tm_d.toFixed(1) + ' per transition-metal atom');
    if (typeof ph.f_share === 'number' && ph.f_share > 0) bits.push(Math.round(100 * ph.f_share) + '% f-electron atoms');
    var types = list(r.types).map(function (k) { return featLabel(k); });
    if (types.length) bits.push('structure type ' + types.join(', '));
    steps.push({ id: 'physics', d: 3.2, text: bits.length ? 'Physics read from the formula: ' + bits.join('; ') + '.' : 'Composition statistics, measurable structure and the physics features are read from the formula.' });
    steps.push({ id: 'p', d: 2.4, text: 'Part 1, a classifier: model score P = ' + r.p_sc.toFixed(2) + '. It learns catalog labels and weak background labels; this is not an experimentally calibrated probability for a new material.' });
    steps.push({ id: 'tc', d: 2.4, text: 'Part 2, a regressor trained only on superconductors: Tc if it does = ' + predK(r.tc_sc) + '.' });
    steps.push({ id: 'product', d: 2.4, text: 'The prediction is their product: ' + r.p_sc.toFixed(2) + ' × ' + predK(r.tc_sc) + ' = ' + predK(r.pred) + '.' });
    var off = r.pred - r.tc_exp, near = Math.abs(off) <= Math.max(1, 0.2 * r.tc_exp), none = r.tc_exp === 0, note;
    if (near) note = none ? ', and the prediction is close to zero.' : ', close to the prediction.';
    else if (off < 0 && r.p_sc < 0.5) note = ', above the prediction: the classifier doubts that it superconducts.';
    else if (off < 0 && r.tc_sc < r.tc_exp) note = ', above the prediction: Hurricane pulls the highest Tc values toward the middle of its training data.';
    else if (off < 0) note = ', above the prediction: part 2 alone is closer, and multiplying by P pulls it down.';
    else note = none ? ', but the prediction is above zero.' : ', below the prediction.';
    steps.push({ id: 'check', d: 2.8, text: 'Measured: ' + (none ? 'not superconducting' : predK(r.tc_exp)) + ' (' + r.status + ')' + note });
    return steps;
  };

  const predSteps = function predSteps(mode, ex) { return !ex ? [] : mode === 'storm' ? stormSteps(ex) : hurSteps(ex); };

  // which step is showing at time t, and how far into it
  const predAt = function predAt(steps, t) {
    var t0 = 0;
    for (var i = 0; i < steps.length; i++) {
      if (t < t0 + steps[i].d || i === steps.length - 1) return { i: i, s: t - t0, t0: t0 };
      t0 += steps[i].d;
    }
    return { i: 0, s: 0, t0: 0 };
  };

  const predTotal = function predTotal(steps) { var s = 0; steps.forEach(function (x) { s += x.d; }); return s; };


  const predCaption = function predCaption() {
    var mode = demo.predMode, ex = predExample();
    if (mode === 'formula') return demoDef().caption;
    if (mode === 'storm') {
      var u = stormUnc(), nm = u ? 'Storm ' + u.version : stormEns() ? 'Storm ' + stormEns().version : 'Storm';
      if (!ex) return 'How ' + nm + ' turns a crystal into Tc. The worked examples load with the live progress data after Storm’s fifth training round.';
      return 'How ' + nm + ', our model for conventional superconductors, predicts Tc, with the numbers it computed for ' + hurSub(ex.name) + ' (measured ' + predK(ex.tc_exp) + ', ' + ex.status + ').' +
        ' Every value is out of fold: the material’s chemical system was held out while the models trained. Storm learns the Tc of DFT calculations, so its own error is against the calculation. The calibration estimates measured Tc; the separate 90% range applies only to the computed target, not to the experimental estimate.' +
        (ex.n_structures > 1 ? ' The database holds ' + ex.n_structures + ' structures of ' + hurSub(ex.name) + '; the one shown has the median computed Tc.' : '');
    }
    var hi = hurInfo(), hn = hi ? hurTitle(hi) : 'Hurricane';
    if (!ex) return 'No numerical anchor demonstration is available: it requires a scored anchor where ' + hn + ' has not abstained. An unknown answer is not a low probability.';
    return 'How ' + hn + ', our model for unconventional superconductors, predicts Tc for ' + hurSub(ex.name) + ', an anchor measurement excluded from training. It reads the formula and heuristic physics features, then combines a classifier score with Tc conditional on superconductivity. Their product is the model prediction. Anchors where Hurricane abstains are omitted from this numerical demonstration; an unknown answer is not a low probability.';
  };


  const drawPredict = function drawPredict(c, C) {
    if (demo.predMode === 'formula') { drawAllenDynes(c, C); return; }
    var W = demo.W, H = demo.H, narrow = W < 560, mode = demo.predMode, ex = predExample(), all = predExamples(mode);
    var title = mode === 'storm' ? 'How ' + (stormUnc() ? 'Storm ' + stormUnc().version : 'Storm') + ' predicts Tc' : 'How ' + (hurInfo() ? hurTitle(hurInfo()) : 'Hurricane') + ' predicts Tc';
    stText(c, C, title, 16, 24, { size: narrow ? 14 : 15, weight: '600', color: C.ink });
    if (!ex) {
      stParaRich(c, C, mode === 'hurricane' ? 'No scored anchor without abstention is available. Hurricane’s unknown answers are not displayed as numerical predictions.' : 'The worked examples load with the live progress data once the model’s training round has written them.', 16, 60, W - 32, 18, { size: 12.5, color: C.muted });
      $('#demo-ad-readout').textContent = '';
      return;
    }
    var steps = predSteps(mode, ex), total = predTotal(steps), t = motionOK() ? Math.min(demo.predT, total) : total, at = predAt(steps, t);
    if (!motionOK()) at = { i: steps.length - 1, s: steps[steps.length - 1].d, t0: total - steps[steps.length - 1].d };
    var chip = (mode === 'hurricane' ? hurShortName(ex.name) : hurSub(ex.name)) + (all.length > 1 ? ' · ' + (demo.predEx % all.length + 1) + ' of ' + all.length : '');
    if (narrow) stTag(c, C, chip, 16, 46, { align: 'left', size: 11.5, bg: C.track, color: C.ink, rich: true });
    else stTag(c, C, chip, W - 16, 22, { align: 'right', size: 12, bg: C.track, color: C.ink, rich: true });
    var top = narrow ? 62 : 44;
    var V = narrow ? { x: 16, y: top, w: W - 32, h: 150 } : { x: 16, y: top, w: Math.round((W - 32) * 0.4), h: H - top - 16 };
    var T = narrow ? { x: 16, y: V.y + V.h + 12, w: W - 32, h: H - V.y - V.h - 20 } : { x: V.x + V.w + 22, y: top + 2, w: W - V.x - V.w - 38, h: H - top - 18 };
    // the visual for the current step
    c.save();
    c.beginPath(); c.rect(V.x - 2, V.y - 2, V.w + 4, V.h + 4); c.clip();
    if (mode === 'storm') drawPredStormVisual(c, C, V, ex, steps[at.i].id, at.s, narrow);
    else drawPredHurVisual(c, C, V, ex, steps[at.i].id, at.s, narrow);
    c.restore();
    // the trace: one line per step so far; on small screens only the latest ones that fit
    var size = narrow ? 11.5 : 12.5, lh = narrow ? 15 : 17, gap = narrow ? 7 : 9;
    var shown = [];
    for (var i = 0; i <= at.i; i++) shown.push(i);
    function heightOf(i) { stFont(c, C, size); return predLines(c, C, steps[i].text, T.w - 22, size) * lh + gap; }
    var hsum = 0, first = shown.length;
    for (var j = shown.length - 1; j >= 0; j--) { var hh = heightOf(shown[j]); if (hsum + hh > T.h && j < shown.length - 1) break; hsum += hh; first = j; }
    var y = T.y + 12;
    for (var k = first; k < shown.length; k++) {
      var si = shown[k], cur = si === at.i, a = cur ? stSpan(at.s, 0, 0.45) : 1;
      c.globalAlpha = a;
      dot(c, T.x + 6, y - 4, cur ? 5 : 3.5, cur ? C.accent : C.axis);
      var n = stParaRich(c, C, steps[si].text, T.x + 20, y, T.w - 22, lh, { size: size, color: cur ? C.ink : C.ink2, weight: cur ? '600' : '400' });
      y += n * lh + gap;
      c.globalAlpha = 1;
    }
    $('#demo-ad-readout').textContent = (mode === 'hurricane' ? hurShortName(ex.name) : hurSub(ex.name)) + ' · step ' + (at.i + 1) + ' of ' + steps.length;
    demo.canvas.setAttribute('aria-label', title + ' for ' + ex.name + ': ' + steps.map(function (s) { return s.text; }).join(' '));
  };

  const predLines = function predLines(c, C, text, maxW, size) {
    var words = String(text).split(' '), lines = 1, lw = 0;
    stFont(c, C, size);
    var sp = c.measureText(' ').width;
    words.forEach(function (w) {
      var ww = stSymWidth(c, C, symParts(w), size);
      if (lw && lw + sp + ww > maxW) { lines++; lw = ww; } else lw += (lw ? sp : 0) + ww;
    });
    return lines;
  };


  /* the visuals */
  const predRadarGlyph = function predRadarGlyph(c, C, V, s, toStorm, p) {
    var cx = V.x + V.w / 2, cy = V.y + V.h * 0.42, r = Math.min(V.w, V.h) * 0.26;
    c.lineWidth = 1; c.strokeStyle = C.grid;
    [1, 0.62, 0.3].forEach(function (k) { c.beginPath(); c.arc(cx, cy, r * k, 0, Math.PI * 2); c.stroke(); });
    var a = -Math.PI / 2 + s * 2.4;
    c.strokeStyle = C.accent; c.lineWidth = 2;
    c.beginPath(); c.moveTo(cx, cy); c.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r); c.stroke();
    dot(c, cx, cy, 3.5, C.accent);
    var bx = toStorm ? V.x + V.w * 0.22 : V.x + V.w * 0.78, by = V.y + V.h - 18;
    stTag(c, C, 'Storm', V.x + V.w * 0.22, by, { size: 12, bg: toStorm ? C.accent : C.surface, ring: toStorm ? null : C.grid, color: toStorm ? '#ffffff' : C.ink2 });
    stTag(c, C, 'Hurricane', V.x + V.w * 0.78, by, { size: 12, bg: toStorm ? C.surface : C.accent, ring: toStorm ? C.grid : null, color: toStorm ? C.ink2 : '#ffffff' });
    if (s > 0.6) { c.globalAlpha = stSpan(s, 0.6, 1.1); stArrow(c, cx, cy + r + 4, bx, by - 14, C.accent, 7); c.globalAlpha = 1; }
    if (typeof p === 'number') label(c, C, 'p ' + predPShort(p), cx + r + 8, cy - r + 10, { size: 11.5, color: C.muted });
  };

  // a horizontal Tc axis with labelled markers; vals: [{v, label, kind: 'bar'|'dot'|'diamond'|'star', color}], range [lo, hi]
  const predAxis = function predAxis(c, C, V, vmax, vals, range, y) {
    var x0 = V.x + 8, x1 = V.x + V.w - 12;
    function X(v) { return x0 + Math.max(0, Math.min(1, v / vmax)) * (x1 - x0); }
    c.lineWidth = 1; c.strokeStyle = C.axis;
    c.beginPath(); c.moveTo(x0, y + 0.5); c.lineTo(x1, y + 0.5); c.stroke();
    var stp = niceStep(vmax, 4), ticks = [];
    for (var g = 0; g <= vmax + 1e-9; g += stp) ticks.push(g);
    ticks.forEach(function (g, i) {
      var gx = Math.round(X(g)) + 0.5, last = i === ticks.length - 1, txt = fmtTick(g) + (last ? ' K' : '');
      c.beginPath(); c.moveTo(gx, y); c.lineTo(gx, y + 4); c.stroke();
      stFont(c, C, 10.5);
      var right = last && gx + c.measureText(txt).width / 2 > V.x + V.w;
      label(c, C, txt, right ? V.x + V.w : gx, y + 16, { align: right ? 'right' : 'center', size: 10.5, color: C.muted });
    });
    if (range) {
      c.fillStyle = stAlpha(C.accent, 0.18); stRound(c, X(range[0]), y - 13, Math.max(2, X(range[1]) - X(range[0])), 10, 5); c.fill();
      c.strokeStyle = C.accent; c.lineWidth = 1.5;
      c.beginPath(); c.moveTo(X(range[0]), y - 15); c.lineTo(X(range[0]), y - 1); c.moveTo(X(range[1]), y - 15); c.lineTo(X(range[1]), y - 1); c.stroke();
    }
    vals.forEach(function (m, i) {
      var x = X(m.v), yy = y - 8;
      if (m.kind === 'diamond') {
        c.fillStyle = m.color; c.beginPath(); c.moveTo(x, yy - 6); c.lineTo(x + 5, yy); c.lineTo(x, yy + 6); c.lineTo(x - 5, yy); c.closePath(); c.fill();
      } else if (m.kind === 'star') {
        c.fillStyle = m.color; c.beginPath();
        for (var q = 0; q < 10; q++) { var rr = q % 2 ? 3 : 7, an = -Math.PI / 2 + q * Math.PI / 5; c.lineTo(x + Math.cos(an) * rr, yy + Math.sin(an) * rr); }
        c.closePath(); c.fill();
      } else dot(c, x, yy, 5, m.color);
      if (m.label) label(c, C, m.label, x, yy - 12 - (m.lift || 0), { align: x > x1 - 60 ? 'right' : x < x0 + 60 ? 'left' : 'center', size: 11, weight: '600', color: m.color });
    });
  };

  const predBar = function predBar(c, C, V, y, v, vmax, text, color, a) {
    var x0 = V.x + 8, w = (V.w - 70) * Math.max(0, Math.min(1, v / vmax)) * (a === undefined ? 1 : a);
    stRound(c, x0, y - 8, Math.max(2, w), 16, 5); c.fillStyle = color; c.fill();
    stFont(c, C, 12, '600');
    var tw = stSymWidth(c, C, symParts(text), 12, '600');
    // the label goes after the bar; when the bar is too long for that, just above it
    if (x0 + w + 8 + tw <= V.x + V.w) stSym(c, C, symParts(text), x0 + w + 8, y + 4, { size: 12, weight: '600', color: C.ink });
    else stSym(c, C, symParts(text), x0, y - 13, { size: 12, weight: '600', color: C.ink });
  };

  const drawPredStormVisual = function drawPredStormVisual(c, C, V, w, id, s, narrow) {
    var vmax = Math.max(w.trees, w.gnn, w.gnn_ad, w.storm4, w.dft_tc, w.hi, w.tc_exp, typeof w.calibrated === 'number' ? w.calibrated : 0) * 1.1 || 1;
    if (id === 'radar') { var rd = predRadar(w.name); predRadarGlyph(c, C, V, s, true, rd ? rd.p_unconventional : null); return; }
    if (id === 'trees') {
      var n = narrow ? 5 : 6, gw = V.w / n, grown = Math.min(n, Math.floor(s / 0.35) + 1);
      for (var i = 0; i < n; i++) { c.globalAlpha = i < grown ? 1 : 0.18; drawTreeGlyph(c, C, V.x + gw * (i + 0.5), V.y + 10, gw * 0.8, narrow ? 54 : 74, 4, i === grown - 1 ? C.warm : C.accent); }
      c.globalAlpha = 1;
      var tsv = predTreeSpec();
      if (tsv && tsv.trees) label(c, C, '… ' + fmtInt(tsv.trees) + ' trees', V.x + V.w - 4, V.y + (narrow ? 82 : 104), { align: 'right', size: 11, color: C.muted });
      // the running sum climbs to the trees' prediction (the steps are schematic, the end point is Storm's number)
      var k = stEase(Math.min(1, s / 2.2)), cur = w.trees * (1 - Math.pow(1 - k, 3));
      predBar(c, C, V, V.y + (narrow ? 112 : 150), cur, vmax, 'trees: ' + predK(cur), C.accent);
      return;
    }
    if (id === 'graph') {
      var cx = V.x + V.w * (narrow ? 0.32 : 0.5), cy = V.y + (narrow ? 64 : V.h * 0.36), R = narrow ? 48 : Math.min(V.w, V.h) * 0.24, pts = [];
      for (var q = 0; q < 6; q++) pts.push([cx + R * Math.cos(q * Math.PI / 3), cy + R * Math.sin(q * Math.PI / 3)]);
      pts.push([cx, cy]);
      c.lineWidth = 1; c.strokeStyle = C.grid;
      pts.forEach(function (p, a) { pts.forEach(function (o, b) { if (b > a && Math.hypot(p[0] - o[0], p[1] - o[1]) < R * 1.05) { c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(o[0], o[1]); c.stroke(); } }); });
      var layer = Math.min(2, Math.floor(s / 0.9)), ph = (s % 0.9) / 0.9;
      pts.forEach(function (p, a) {
        if (a === 6) return;
        var x = p[0] + (cx - p[0]) * ph, y = p[1] + (cy - p[1]) * ph;
        dot(c, x, y, 2.6, C.warm);
      });
      pts.forEach(function (p, a) { dot(c, p[0], p[1], a === 6 ? 9 : 7, a === 6 ? C.accent : mix(C.accent, C.surface, 0.45)); });
      label(c, C, 'message passing, layer ' + (layer + 1) + ' of 3', cx, cy + R + 22, { align: 'center', size: 11, color: C.muted });
      if (s > 2.2) {
        c.globalAlpha = stSpan(s, 2.2, 2.7);
        var ox = narrow ? V.x + V.w * 0.66 : V.x + 8, oy = narrow ? V.y + 30 : V.y + V.h - 48;
        stText(c, C, 'Tc = ' + predK(w.gnn), ox, oy, { size: 13, weight: '700', color: C.accent });
        stText(c, C, 'λ = ' + w.gnn_lambda.toFixed(2) + ',  ω_log = ' + Math.round(w.gnn_wlog) + ' K', ox, oy + 20, { size: 12, color: C.ink2 });
        c.globalAlpha = 1;
      }
      return;
    }
    if (id === 'ad') {
      var lam = w.gnn_lambda, wl = w.gnn_wlog, mu = w.mu_star || 0.1, dd = lam - mu * (1 + 0.62 * lam), big = narrow ? 12.5 : 13.5;
      stSym(c, C, [['T'], ['c', 1], [' = (ω'], ['log', 1], [' / 1.2) ×']], V.x + 4, V.y + 26, { size: big, weight: '600' });
      stSym(c, C, [['exp[ −1.04 (1 + λ) / (λ − μ*(1 + 0.62 λ)) ]']], V.x + 4, V.y + 48, { size: big - 1, weight: '600' });
      if (s > 0.8) {
        c.globalAlpha = stSpan(s, 0.8, 1.3);
        stPara(c, C, '= (' + Math.round(wl) + ' / 1.2) × exp[ −1.04 × ' + (1 + lam).toFixed(2) + ' / ' + dd.toFixed(3) + ' ]', V.x + 4, V.y + 78, V.w - 8, 17, { size: 12, color: C.ink2 });
        c.globalAlpha = 1;
      }
      if (s > 1.6) { c.globalAlpha = stSpan(s, 1.6, 2.1); stText(c, C, 'Tc = ' + predK(w.gnn_ad), V.x + 4, V.y + (narrow ? 130 : 128), { size: narrow ? 20 : 24, weight: '700', color: C.warm }); c.globalAlpha = 1; }
      return;
    }
    if (id === 'avg') {
      var rows = [['trees', w.trees, C.accent], ['network', w.gnn, mix(C.accent, C.surface, 0.35)], ['Allen–Dynes', w.gnn_ad, C.warm]], rh = narrow ? 24 : 30;
      rows.forEach(function (r, i) { predBar(c, C, V, V.y + 14 + i * rh, r[1], vmax, r[0] + ' ' + predK(r[1]), r[2], stSpan(s, 0.1 * i, 0.4 + 0.1 * i)); });
      if (s > 0.9) {
        c.globalAlpha = stSpan(s, 0.9, 1.4);
        predAxis(c, C, { x: V.x, y: V.y, w: V.w, h: V.h }, vmax, [{ v: w.dft_tc, label: 'DFT ' + predK(w.dft_tc), kind: 'diamond', color: C.ink2, lift: 10 }, { v: w.storm4, label: 'Storm ' + predK(w.storm4), kind: 'dot', color: C.accent }], null, V.y + V.h - 22);
        c.globalAlpha = 1;
      }
      return;
    }
    // calibration and range share one axis
    var marks = [{ v: w.storm4, label: id === 'range' ? '' : 'Storm ' + predK(w.storm4), kind: 'dot', color: C.accent }];
    if (id === 'cal' && typeof w.calibrated === 'number') marks.push({ v: w.calibrated, label: 'calibrated ' + predK(w.calibrated), kind: 'dot', color: C.warm, lift: 14 });
    marks.push({ v: w.tc_exp, label: 'measured ' + predK(w.tc_exp), kind: 'star', color: C.ink, lift: id === 'cal' ? 28 : 0 });
    if (id === 'range') marks.push({ v: w.dft_tc, label: 'DFT ' + predK(w.dft_tc), kind: 'diamond', color: C.ink2, lift: 14 });
    predAxis(c, C, V, vmax, marks, id === 'range' ? [w.lo, w.lo + (w.hi - w.lo) * stSpan(s, 0, 1)] : null, V.y + V.h * 0.6);
    if (id === 'cal' && typeof w.calibrated === 'number' && s > 0.3) {
      var x0 = V.x + 8, x1 = V.x + V.w - 12, ax = x0 + w.storm4 / vmax * (x1 - x0), bx = x0 + w.calibrated / vmax * (x1 - x0), yy = V.y + V.h * 0.6 + 30;
      c.globalAlpha = stSpan(s, 0.3, 0.8); stArrow(c, ax, yy, ax + (bx - ax) * stSpan(s, 0.3, 1.2), yy, C.warm, 7); c.globalAlpha = 1;
    }
    if (id === 'range') label(c, C, '90% range ' + w.lo.toFixed(1) + '–' + predK(w.hi), V.x + 8, V.y + V.h * 0.6 + 40, { size: 12, weight: '600', color: C.accent });
  };

  const drawPredHurVisual = function drawPredHurVisual(c, C, V, r, id, s, narrow) {
    var vmax = Math.max(r.tc_sc, r.pred, r.tc_exp) * 1.15 || 1, ph = r.physics || {};
    if (id === 'radar') { var rd = predRadar(r.name); predRadarGlyph(c, C, V, s, false, rd ? rd.p_unconventional : null); return; }
    if (id === 'physics') {
      if (typeof ph.p_cu === 'number') {
        // the empirical cuprate dome Tc / Tc,max = 1 − 82.6 (p − 0.16)² (Presland and Tallon), with this compound's p
        var x0 = V.x + 30, x1 = V.x + V.w - 10, y0 = V.y + 16, y1 = V.y + V.h - 34;
        var X = function (p) { return x0 + (p - 0.03) / 0.27 * (x1 - x0); };
        var Y = function (f) { return y1 - f * (y1 - y0); };
        c.strokeStyle = C.axis; c.lineWidth = 1; c.beginPath(); c.moveTo(x0, y0); c.lineTo(x0, y1); c.lineTo(x1, y1); c.stroke();
        c.strokeStyle = C.accent; c.lineWidth = 2; c.beginPath();
        for (var q = 0; q <= 60; q++) { var p = 0.05 + 0.22 * q / 60, f = Math.max(0, 1 - 82.6 * (p - 0.16) * (p - 0.16)); if (q) c.lineTo(X(p), Y(f)); else c.moveTo(X(p), Y(f)); }
        c.stroke();
        [0.05, 0.16, 0.27].forEach(function (p) { label(c, C, p.toFixed(2), X(p), y1 + 14, { align: 'center', size: 10.5, color: C.muted }); });
        label(c, C, 'holes per Cu, p', (x0 + x1) / 2, y1 + 28, { align: 'center', size: 11, color: C.muted });
        label(c, C, 'Tc / top', x0 - 4, y0 + 4, { align: 'right', size: 10.5, color: C.muted });
        if (s > 0.5) {
          var pp = Math.max(0.03, Math.min(0.3, ph.p_cu)), fd = Math.max(0, 1 - 82.6 * (pp - 0.16) * (pp - 0.16));
          c.globalAlpha = stSpan(s, 0.5, 1); dot(c, X(pp), Y(fd), 6, C.warm);
          label(c, C, 'p = ' + ph.p_cu.toFixed(2), X(pp) + 9, Y(fd) - 6, { size: 11.5, weight: '600', color: C.warm }); c.globalAlpha = 1;
        }
      } else {
        var chips = list(r.types).map(function (k) { return featLabel(k); });
        if (typeof ph.f_share === 'number') chips.push(Math.round(100 * ph.f_share) + '% f-electron atoms');
        if (typeof ph.tm_d === 'number') chips.push('d count ' + ph.tm_d.toFixed(1));
        if (!chips.length) chips = ['composition', 'structure', 'physics'];
        chips.forEach(function (t2, i) { c.globalAlpha = stSpan(s, 0.3 * i, 0.3 * i + 0.4); stTag(c, C, t2, V.x, V.y + 24 + i * 30, { align: 'left', size: 12, bg: C.track, color: C.ink }); });
        c.globalAlpha = 1;
      }
      return;
    }
    if (id === 'p') {
      var gx = V.x + 8, gw2 = V.w - 24, gy = V.y + V.h * 0.42, fill = r.p_sc * stSpan(s, 0.2, 1.2);
      stRound(c, gx, gy - 10, gw2, 20, 10); c.fillStyle = C.surface2; c.fill(); c.strokeStyle = C.grid; c.lineWidth = 1; c.stroke();
      stRound(c, gx, gy - 10, Math.max(4, gw2 * fill), 20, 10); c.fillStyle = C.accent; c.fill();
      label(c, C, '0', gx, gy + 28, { size: 10.5, color: C.muted }); label(c, C, '1', gx + gw2, gy + 28, { align: 'right', size: 10.5, color: C.muted });
      label(c, C, 'Classifier score = ' + fill.toFixed(2), gx, gy - 20, { size: 13, weight: '700', color: C.accent });
      return;
    }
    var rows = [];
    if (id === 'tc' || id === 'product' || id === 'check') rows.push(['Tc if it superconducts', r.tc_sc, mix(C.accent, C.surface, 0.35)]);
    if (id === 'product' || id === 'check') rows.push(['P × Tc', id === 'product' ? r.tc_sc + (r.pred - r.tc_sc) * stSpan(s, 0.3, 1.6) : r.pred, C.accent]);
    rows.forEach(function (row, i) { predBar(c, C, V, V.y + 26 + i * 38, row[1], vmax, row[0] + ': ' + predK(row[1]), row[2], id === 'tc' ? stSpan(s, 0.2, 1) : 1); });
    if (id === 'check') predAxis(c, C, V, vmax, [{ v: r.pred, label: 'predicted ' + predK(r.pred), kind: 'dot', color: C.accent }, { v: r.tc_exp, label: r.tc_exp === 0 ? 'not superconducting' : 'measured ' + predK(r.tc_exp), kind: 'star', color: C.ink, lift: 14 }], null, V.y + V.h - 22);
  };

  const setPredMode = function setPredMode(m) {
    demo.predMode = m; demo.predT = 0; demo.predEx = 0;
    store.set('pred', m);
    if (motionOK()) demo.predPlay = true;
    syncControls(); kick();
  };

  const predNext = function predNext() {
    if (!motionOK()) { demo.predEx += 1; demo.predT = 0; syncControls(); kick(); return; }
    var steps = predSteps(demo.predMode, predExample()), at = predAt(steps, demo.predT);
    if (at.i < steps.length - 1) demo.predT = at.t0 + steps[at.i].d + 0.001;
    else { demo.predEx += 1; demo.predT = 0; }
    syncControls(); kick();
  };
