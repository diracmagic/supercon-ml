'use strict';
// storm-demo: shared lexical function definitions; no startup side effects.


  const stormInfo = function stormInfo() {
    var d = state.data, am = d && d.ai_model;
    var vs = am ? list(am.versions).filter(function (v) { return v && v.spec && v.scores; }) : [];
    if (!vs.length) return null;
    var v = vs.filter(function (x) { return x.version === demo.stormVer; })[0] ||
      vs.filter(function (x) { return x.version === am.current; })[0] || vs[vs.length - 1];
    return { am: am, v: v, versions: vs, name: am.name || 'Storm' };
  };

  // The design this version is compared with: the previous version, or the hand-made baseline for the first one.
  const stormPrev = function stormPrev(info) {
    var i = info.versions.indexOf(info.v), pv = i > 0 ? info.versions[i - 1] : null;
    if (pv && pv.spec) return { inputs: list(pv.spec.inputs), learner: pv.spec.learner || STORM_BASE, label: info.name + ' ' + pv.version };
    return { inputs: [{ group: 'composition' }, { group: 'structure' }], learner: STORM_BASE, label: 'the baseline' };
  };

  const stormTitle = function stormTitle(info) { return info.name + ' ' + info.v.version; };

  // From round 2 on, a version must beat the current release (scores.previous); the baseline stays as a second yardstick.
  const stormPrevScores = function stormPrevScores(info) { var p = info.v.scores && info.v.scores.previous; return p && list(p.folds).length ? p : null; };

  const stormRowName = function stormRowName(r) { return r.name + (r.settings && r.settings !== 'default' ? ', ' + r.settings : ''); };

  // Short label for the leaderboard: what the design adds to the baseline, plus its setting.
  const stormShortName = function stormShortName(r) {
    if (/baseline/i.test(r.name)) return 'Baseline (hand-made features)';
    var n = r.name.replace(/^Hand-made \+ /, '+ ').replace(/ features$/, '').replace('MACE-MP-0 descriptors', 'MACE fingerprint')
      .replace('MACE principal components', 'MACE components');
    return n + (r.settings && r.settings !== 'default' ? ', ' + r.settings : '');
  };

  const prettyMath = function prettyMath(s) { return String(s).replace(/M\^-1\/2/g, 'M^−½'); };

  const stormFmtDate = function stormFmtDate(s) {
    var p = String(s || '').split('-');
    var m = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][(+p[1] || 1) - 1];
    return p.length >= 3 ? (+p[2]) + ' ' + m + ' ' + p[0] : s;
  };

  // The stages of the demo: the Storm in use (built over several rounds) once Storm 4.0 is released, else one version's spec.
  const stormStages = function stormStages() { return stormLatest() ? STORM_LATEST_STAGES : STORM_STAGES; };

  const stormCaption = function stormCaption(si) {
    var Lt = stormLatest();
    if (Lt) return stormLatestCaption(si, Lt);
    var info = stormInfo();
    if (!info) return 'Storm is the AI-designed model. Its structure and scores load with the live progress data.';
    var v = info.v, sc = v.scores, sp = v.spec, L0 = sp.learner || {}, n = 0;
    list(sp.inputs).forEach(function (i) { n += i.n || 0; });
    var name = stormTitle(info);
    var better = sc.folds_better + ' of ' + list(sc.folds).length;
    switch (si) {
      case 0:
        var ref = stormPrevScores(info) ? stormPrevScores(info).name : 'the baseline';
        return 'An AI agent (Claude) proposed ' + (v.search ? v.search.candidates : 'several') + ' designs in search round ' + v.round +
        ': new feature sets, physics features and settings. Each was trained and scored with the same composition-grouped cross-validation. ' +
        (v.status === 'adopted' ? 'The best one beat ' + ref + ' on average and in at least 4 of 5 folds, and became ' + name + '.'
          : 'A design is released only if it beats ' + ref + ' on average and in at least 4 of 5 folds. None did this round, so the best one, ' + name + ', stays experimental and ' + ref + ' remains in use.') +
        ' Storm predicts Tc for conventional, phonon-mediated superconductors; cuprates, nickelates, iron-based and other unconventional superconductors go to our second AI-designed model, Hurricane, which learns from measured Tc, and a third, ' +
          (radInfo() && radInfo().rd.current ? radTitle(radInfo()) + ', decides' : 'Radar, will decide') + ' which model each material goes to.' + (stormIsCurrent(info) ? stormEnsSentence() : '');
      case 1: return name + ' reads ' + n + ' numbers per material: ' + list(sp.inputs).map(function (i) {
          return i.group === 'stage' ? i.n + ' from the ' + i.label + ' (its predicted λ and ω_log and the Allen–Dynes Tc from them)' : i.n + ' ' + lcFirst(i.label);
        }).join(', ') + '. The physics features encode rules of thumb such as Matthias’s valence-electron peaks and the M^−½ scale of phonon frequencies.';
      case 2: return 'Gradient-boosted decision trees: ' + fmtInt(L0.trees) + ' small trees, each fixing what the previous ones got wrong, with up to ' + L0.leaves + ' leaves per tree and learning rate ' + L0.learning_rate + '. Predicting log(1 + Tc) compresses the largest temperatures and emphasizes relative differences at low Tc.';
      case 3: return 'Two routes to Tc: directly (error ' + fmtVal(sc.tc_mae) + ' K), or by predicting λ (error ' + fmtVal(sc.lambda_mae) + ') and ω_log (error ' + fmtVal(sc.omega_log_mae) + ' K) and putting them into the Allen–Dynes formula (error ' + fmtVal(sc.tc_via_lambda_wlog_mae) + ' K).';
      case 4:
        var pv = stormPrevScores(info);
        return 'Five-fold cross-validation grouped by chemical system, so no test material has the same complete set of elements as a training material. Individual elements can occur in both sets. ' + name + ' averages ' + fmtVal(sc.tc_mae) + ' K against ' +
          (pv ? fmtVal(pv.tc_mae) + ' K for ' + pv.name + ' and ' : '') + fmtVal(sc.reference_mae) + ' K for the baseline, and is better than ' +
          (pv ? pv.name + ' in ' + pv.folds_better + ' of ' + list(pv.folds).length : 'the baseline in ' + better) + ' folds. It was picked on these folds, so the locked JARVIS test set will check it once at the end.' + stormExpSentence(info);
      default:
        var cal = stormCal(), calTxt = cal && stormIsCurrent(info) ? ' Round 3 added a calibration to measured Tc on top of ' + name + ': that is Storm ' + cal.version + ', off by ' + fmtVal(cal.scores.mae) + ' K against experiment.' : '';
        return name + ' (' + stormFmtDate(v.date) + ', status: ' + v.status + '): ' + prettyMath(list(v.changes).join('; ')) + '.' + calTxt + (stormIsCurrent(info) ? stormEnsSentence() : '') + ' Every new version draws this animation from its own spec.';
    }
  };

  // The measured-Tc check (from round 2 on): how far the model and its own DFT training labels are from replicated experiments.
  const stormExpSentence = function stormExpSentence(info) {
    var ex = info.v.experiments, pv = stormPrevScores(info);
    if (!ex || !ex.n_scored || typeof ex.mae !== 'number') return '';
    return ' Against ' + ex.n_scored + ' replicated Tc measurements, ' + stormTitle(info) + ' is off by ' + fmtVal(ex.mae) + ' K on average' +
      (pv && typeof ex.mae_previous === 'number' ? ' (' + pv.name + ': ' + fmtVal(ex.mae_previous) + ' K)' : '') +
      (typeof ex.dft_mae === 'number' ? ', and the DFT labels it learns from miss by ' + fmtVal(ex.dft_mae) + ' K: most of the gap to experiment comes from the labels, not the model' + stormCalSentence() : '.');
  };

  // Storm 3.0 and later: the version in use calibrated to measured Tc (ai_model.calibration), when released.
  const stormCal = function stormCal() {
    var am = state.data && state.data.ai_model, c = am && am.calibration;
    return c && c.status === 'adopted' && c.version && c.scores && typeof c.scores.mae === 'number' ? c : null;
  };

  // Storm 4.0 and later: Storm 1.0's trees and the crystal-graph network together, calibrated (ai_model.ensemble), when released.
  const stormEns = function stormEns() {
    var am = state.data && state.data.ai_model, e = am && am.ensemble;
    return e && e.status === 'adopted' && e.version && e.scores && typeof e.scores.tc_mae === 'number' && e.calibration && typeof e.calibration.mae === 'number' ? e : null;
  };

  const stormEnsSentence = function stormEnsSentence() {
    var e = stormEns();
    return e ? ' Round 4 combined it with a crystal-graph network: that is Storm ' + e.version + ', ' + e.scores.tc_mae.toFixed(2) + ' K off against computed Tc and ' + e.calibration.mae.toFixed(2) + ' K against experiment once calibrated.' + stormUncSentence() : '';
  };

  // Storm 5.0 and later: a 90% range around Storm 4.0's prediction (ai_model.uncertainty), when released.
  const stormUnc = function stormUnc() {
    var am = state.data && state.data.ai_model, u = am && am.uncertainty;
    return stormEns() && u && u.status === 'adopted' && u.version && u.scores && typeof u.scores.coverage === 'number' ? u : null;
  };

  const stormUncSentence = function stormUncSentence() {
    var u = stormUnc();
    return u ? ' Round 5 gave every prediction a 90% range, which makes it Storm ' + u.version + ': for materials it never saw, the range held the computed Tc ' + Math.round(100 * u.scores.coverage) + '% of the time.' : '';
  };

  // The name of the Storm in use, from the newest release round.
  const stormVersionInUse = function stormVersionInUse() { var u = stormUnc(), e = stormEns(), c = stormCal(); return u ? u.version : e ? e.version : c ? c.version : null; };

  // True when the version shown is the one in use, so the calibrated name applies to it.
  const stormIsCurrent = function stormIsCurrent(info) { return !!info && info.v.status === 'adopted' && info.v.version === (info.am.current || info.v.version); };

  // Round 3: Storm calibrated to measured Tc (ai_model.calibration), if it has run.
  const stormCalSentence = function stormCalSentence() {
    var cal = state.data && state.data.ai_model && state.data.ai_model.calibration, sc = cal && cal.scores, dd = (cal && cal.data) || {};
    if (!sc || typeof sc.mae !== 'number') return ', so the next round calibrates Storm against graded measurements.';
    return '. Round 3 therefore calibrated Storm against measured Tc: on ' + (dd.n_matched || 'the') + ' conventional materials from 3DSC, ' +
      (cal.status === 'adopted' ? 'Storm ' + cal.version + ' is off by ' + fmtVal(sc.mae) + ' K against ' + fmtVal(sc.mae_raw) + ' K uncalibrated.'
        : 'the best calibration is off by ' + fmtVal(sc.mae) + ' K against ' + fmtVal(sc.mae_raw) + ' K uncalibrated, but it was not released.');
  };

  // Lower-case the first letter of a label for use mid-sentence, but keep acronyms and names (AI, MACE, Storm, Allen–Dynes).
  const lcFirst = function lcFirst(str) {
    str = String(str || '');
    return /^[A-Z][a-z]/.test(str) && !/^(Storm|Hurricane|Radar|Allen|Matthias|MACE|Alexandria|JARVIS|Debye|McMillan|Eliashberg)\b/.test(str) ? str.charAt(0).toLowerCase() + str.slice(1) : str;
  };

  const fmtInt = function fmtInt(n) { return typeof n === 'number' ? n.toLocaleString('en-US') : String(n || ''); };


  const hitStormNode = function hitStormNode(p) {
    var nodes = demo.stormNodes || [];
    for (var i = 0; i < nodes.length; i++) {
      var b = nodes[i];
      if (p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h) return i;
    }
    return -1;
  };

  const setStormVersion = function setStormVersion(ver) {
    demo.stormVer = ver; demo.stormStage = 0; demo.stormT = 0;
    syncControls(); kick();
  };

  const renderStormSeg = function renderStormSeg() {
    var el = $('#storm-seg');
    if (!el) return;
    clear(el);
    // the demo shows only the Storm in use, so there is no version to pick
    el.hidden = !!stormLatest();
    if (el.hidden) return;
    var info = stormInfo();
    if (!info) { el.appendChild(h('button', { type: 'button', 'aria-pressed': 'true', disabled: true }, 'Storm')); return; }
    info.versions.forEach(function (v) {
      el.appendChild(h('button', { type: 'button', 'aria-pressed': v === info.v ? 'true' : 'false', onclick: function () { setStormVersion(v.version); } }, info.name + ' ' + v.version));
    });
  };


  const drawStorm = function drawStorm(c, C) {
    var W = demo.W, H = demo.H, narrow = W < 560;
    var si = demo.stormStage, t = motionOK() ? demo.stormT : STORM_DUR, Lt = stormLatest(), ST = Lt ? STORM_LATEST_STAGES : STORM_STAGES;
    var n = ST.length, gap = narrow ? 6 : 18, nodeW = (W - 32 - gap * (n - 1)) / n, nodeH = narrow ? 34 : 40, ny = 12;
    demo.stormNodes = [];
    for (var i = 0; i < n; i++) {
      var x = 16 + i * (nodeW + gap), on = i === si;
      demo.stormNodes.push({ x: x, y: ny, w: nodeW, h: nodeH });
      stRound(c, x, ny, nodeW, nodeH, 9);
      c.fillStyle = on ? C.accent : C.surface2; c.fill();
      if (!on) { c.lineWidth = 1; c.strokeStyle = C.grid; c.stroke(); }
      label(c, C, narrow ? ST[i].short : ST[i].node, x + nodeW / 2, ny + nodeH / 2 + 0.5,
        { align: 'center', base: 'middle', size: narrow ? 10.5 : 12, weight: '600', color: on ? '#ffffff' : C.ink2 });
      if (i < n - 1 && !narrow) stArrow(c, x + nodeW + 3, ny + nodeH / 2, x + nodeW + gap - 3, ny + nodeH / 2, C.axis, 5);
    }
    if (motionOK()) {
      var px = demo.stormNodes[si];
      c.fillStyle = stAlpha(C.accent, 0.25);
      c.fillRect(px.x + 6, ny + nodeH - 3, (px.w - 12) * Math.min(1, t / STORM_DUR), 2);
    }
    var B = { x: 16, y: ny + nodeH + 16, w: W - 32, h: H - ny - nodeH - 28 };
    if (Lt) { drawStormLatest(c, C, B, t, narrow, si, Lt); return; }
    var info = stormInfo();
    if (!info) {
      label(c, C, 'Storm’s structure loads with the live progress data.', W / 2, B.y + B.h / 2, { align: 'center', base: 'middle', size: 13, color: C.muted });
      return;
    }
    [drawStormDesign, drawStormInputs, drawStormLearner, drawStormPredict, drawStormCheck, drawStormNew][si](c, C, B, t, narrow, info);
  };


  const stormHeader = function stormHeader(c, C, B, text, sub) {
    label(c, C, text, B.x, B.y + 12, { size: 13, weight: '600', color: C.ink });
    if (sub) label(c, C, sub, B.x + B.w, B.y + 12, { size: 11.5, color: C.muted, align: 'right' });
  };


  /* 0 · the design loop and the leaderboard of the round */
  const drawStormDesign = function drawStormDesign(c, C, B, t, narrow, info) {
    var v = info.v, rows = v.search ? list(v.search.leaderboard) : [];
    var winner = rows.filter(function (r) { return stormRowName(r) === v.summary; })[0] || rows[0];
    stormHeader(c, C, B, 'Search round ' + v.round + ': ' + rows.length + ' designs', narrow ? '' : 'Tc error in grouped CV (K)');
    // the loop: propose → train → score
    var L = narrow ? { x: B.x, y: B.y + 26, w: B.w, h: 64 } : { x: B.x, y: B.y + 30, w: Math.round(B.w * 0.3), h: B.h - 36 };
    var steps = ['propose', 'train', 'score'], k = Math.floor(t * 1.4) % 3;
    if (narrow) {
      stRound(c, L.x, L.y, 104, 34, 8); c.fillStyle = C.accent; c.fill();
      label(c, C, 'AI agent', L.x + 52, L.y + 17.5, { align: 'center', base: 'middle', size: 12, weight: '600', color: '#ffffff' });
      steps.forEach(function (s, i) {
        var sx = L.x + 124 + i * ((L.w - 124) / 3);
        stTag(c, C, s, sx, L.y + 17, { align: 'left', size: 11, bg: i === k ? C.track : C.surface, ring: C.grid, color: C.ink });
        if (i < 2) stArrow(c, sx + 56, L.y + 17, sx + (L.w - 124) / 3 - 6, L.y + 17, C.axis, 5);
      });
      label(c, C, '(Claude)', L.x + 52, L.y + 48, { align: 'center', size: 10.5, color: C.muted });
    } else {
      var cx = L.x + L.w / 2, cy = L.y + L.h / 2 - 6, r = Math.min(L.w, L.h) * 0.3;
      c.lineWidth = 1.5; c.strokeStyle = C.grid;
      c.beginPath(); c.arc(cx, cy, r, 0, Math.PI * 2); c.stroke();
      steps.forEach(function (s, i) {
        var a = -Math.PI / 2 + i * 2 * Math.PI / 3, sx = cx + Math.cos(a) * r, sy = cy + Math.sin(a) * r;
        stTag(c, C, s, sx, sy, { size: 11.5, bg: i === k ? C.track : C.surface, ring: C.grid, color: C.ink });
      });
      var a2 = -Math.PI / 2 + (t * 1.4 % 3) * 2 * Math.PI / 3;
      dot(c, cx + Math.cos(a2) * r, cy + Math.sin(a2) * r, 3.5, C.warm);
      stRound(c, cx - 46, cy - 15, 92, 30, 8); c.fillStyle = C.accent; c.fill();
      label(c, C, 'AI agent', cx, cy + 0.5, { align: 'center', base: 'middle', size: 12, weight: '600', color: '#ffffff' });
      label(c, C, 'Claude proposes each design', cx, L.y + L.h - 4, { align: 'center', size: 11, color: C.muted });
    }
    // leaderboard
    var T = narrow ? { x: B.x, y: L.y + L.h + 6, w: B.w, h: B.y + B.h - (L.y + L.h + 6) } : { x: L.x + L.w + 24, y: B.y + 26, w: B.w - L.w - 24, h: B.h - 26 };
    if (!rows.length) return;
    var rh = Math.min(32, (T.h - 22) / rows.length), lo = Infinity, hi = -Infinity;
    rows.forEach(function (r) { lo = Math.min(lo, r.tc_mae); hi = Math.max(hi, r.tc_mae); });
    var step = 0.05, a0v = Math.floor((lo - 0.01) / step) * step, a1v = Math.ceil((hi + 0.01) / step) * step;
    var nameW = narrow ? Math.min(170, T.w * 0.56) : Math.min(290, T.w * 0.52), bx = T.x + nameW + 10, bw = T.w - nameW - 50;
    var refId = (v.search && v.search.reference_id) || 'A', base = rows.filter(function (r) { return r.id === refId; })[0];
    function BX(v) { return bx + (v - a0v) / (a1v - a0v) * bw; }
    var axisY = T.y + rows.length * rh + 4;
    c.lineWidth = 1;
    for (var tv = a0v; tv <= a1v + 1e-9; tv += step) {
      var gx = Math.round(BX(tv)) + 0.5;
      c.strokeStyle = C.grid; c.beginPath(); c.moveTo(gx, T.y); c.lineTo(gx, axisY); c.stroke();
      label(c, C, tv.toFixed(2), gx, axisY + 13, { align: 'center', size: 10.5, color: C.muted });
    }
    rows.forEach(function (r, i) {
      var a = stSpan(t, 0.4 + 0.35 * i, 0.8 + 0.35 * i);
      if (a <= 0) return;
      var y = T.y + i * rh, isW = r === winner && t > 4.2, isB = r.id === refId, cy = y + rh / 2;
      c.globalAlpha = a;
      if (isW) { stRound(c, T.x - 6, y + 1, T.w + 6, rh - 2, 7); c.fillStyle = stAlpha(C.accent, 0.1); c.fill(); }
      stTag(c, C, r.id, T.x + 13, cy, { size: 10.5, bg: isW ? C.accent : C.surface, ring: C.grid, color: isW ? '#ffffff' : C.ink2 });
      var full = stormShortName(r), nm = full, size = narrow ? 11 : 12;
      stFont(c, C, size);
      while (nm.length > 8 && c.measureText(nm + '…').width > nameW - 32) nm = nm.slice(0, -1);
      if (nm !== full) nm = nm.replace(/[ ,]+$/, '') + '…';
      label(c, C, nm, T.x + 30, cy + 4, { size: size, color: isB ? C.ink2 : C.ink, weight: isW ? '600' : '400' });
      var x = BX(r.tc_mae), col = isW ? C.accent : isB ? C.ink2 : mix(C.accent, C.surface2, 0.35);
      dot(c, x, cy, isW ? 5.5 : 4.5, col);
      label(c, C, fmtVal(r.tc_mae), x + 9, cy + 4, { size: 11, weight: isW ? '600' : '400', color: isW ? C.accent : C.ink2 });
      c.globalAlpha = 1;
    });
    if (base && t > 0.6) {
      var xb = Math.round(BX(base.tc_mae)) + 0.5;
      c.setLineDash([3, 3]); c.strokeStyle = C.ink2; c.lineWidth = 1;
      c.beginPath(); c.moveTo(xb, T.y); c.lineTo(xb, axisY); c.stroke(); c.setLineDash([]);
    }
    if (t > 4.6) {
      c.globalAlpha = stSpan(t, 4.6, 5.2);
      var ok = v.status === 'adopted';
      var msg = ok ? 'Released as ' + stormTitle(info) : stormTitle(info) + ' stays experimental';
      stTag(c, C, msg, T.x + T.w, axisY + 30, { align: 'right', size: 12, bg: ok ? C.accent : C.surface, ring: ok ? null : C.grid, color: ok ? '#ffffff' : C.ink });
      c.globalAlpha = 1;
    }
  };


  /* 1 · the inputs, group by group */
  const drawStormInputs = function drawStormInputs(c, C, B, t, narrow, info) {
    var sp = info.v.spec, ins = list(sp.inputs), total = 0;
    ins.forEach(function (i) { total += i.n || 0; });
    var prev = stormPrev(info), had = {};
    prev.inputs.forEach(function (g) { had[g.group] = 1; });
    stormHeader(c, C, B, total + ' numbers describe each material', narrow ? '' : 'orange: new since ' + prev.label);
    var y0 = B.y + 30, colW = narrow ? B.w : Math.round(B.w * 0.5), rowH = narrow ? 44 : Math.min(58, (B.h - 40) / Math.max(1, ins.length));
    var maxN = 1;
    ins.forEach(function (i) { maxN = Math.max(maxN, i.n_in || i.n || 1); });
    ins.forEach(function (g, i) {
      var a = stSpan(t, 0.3 + 0.6 * i, 0.9 + 0.6 * i);
      if (a <= 0) return;
      var y = y0 + i * rowH, isNew = !had[g.group], col = isNew ? C.warm : C.accent;
      c.globalAlpha = a;
      label(c, C, g.label, B.x, y + 12, { size: 12, weight: '600', color: C.ink });
      var bw = colW - 70, full = Math.max(8, bw * Math.sqrt((g.n || 1) / maxN));
      if (g.n_in) {
        // a wide block squeezed down to its principal components
        var sq = stSpan(t, 1 + 0.6 * i, 2.4 + 0.6 * i), wide = Math.max(8, bw * Math.sqrt(g.n_in / maxN));
        var cur = wide + (full - wide) * sq;
        c.fillStyle = stAlpha(col, 0.25 + 0.6 * sq); c.fillRect(B.x, y + 20, cur, 12);
        label(c, C, (sq < 0.5 ? g.n_in : g.n) + (sq < 0.5 ? '' : ' (PCA)'), B.x + cur + 8, y + 30, { size: 11.5, weight: '600', color: col });
      } else {
        c.fillStyle = col; c.fillRect(B.x, y + 20, full * a, 12);
        label(c, C, String(g.n), B.x + full * a + 8, y + 30, { size: 11.5, weight: '600', color: col });
      }
      c.globalAlpha = 1;
    });
    var withItems = ins.filter(function (g) { return list(g.items).length; });
    var phys = withItems.filter(function (g) { return !had[g.group]; })[0] || withItems.filter(function (g) { return g.group === 'physics'; })[0];
    if (!phys) return;
    var P = narrow ? { x: B.x, y: y0 + ins.length * rowH + 6, w: B.w } : { x: B.x + colW + 16, y: y0 - 4, w: B.w - colW - 16 };
    var items = list(phys.items), lh = narrow ? 21 : 23;
    // on phones one column when the list fits, so no label is cut short; the bar above already names the group
    var cols = narrow ? (P.y + 26 + items.length * lh <= B.y + B.h - 4 ? 1 : 2) : (P.w > 360 ? 2 : 1), cw = P.w / cols;
    label(c, C, narrow && phys.group === 'physics' ? 'The ' + items.length + ' physics features' : phys.group === 'physics' ? 'Physics features proposed by the AI' : phys.label, P.x, P.y + 10, { size: 12, weight: '600', color: had[phys.group] ? C.ink : C.warm });
    items.forEach(function (it, j) {
      var a = stSpan(t, 1.2 + 0.25 * j, 1.6 + 0.25 * j);
      if (a <= 0) return;
      var cx = P.x + (j % cols) * cw, cy = P.y + 26 + Math.floor(j / cols) * lh;
      if (cy > B.y + B.h - 4) return;
      c.globalAlpha = a;
      dot(c, cx + 4, cy + 4, 3, C.warm);
      stFont(c, C, 11.5);
      var txt = PHYS_LABELS[it.name] || it.name;
      while (txt.length > 6 && c.measureText(txt).width > cw - 18) txt = txt.slice(0, -2);
      label(c, C, txt + (txt !== (PHYS_LABELS[it.name] || it.name) ? '…' : ''), cx + 12, cy + 8, { size: 11.5, color: C.ink2 });
      c.globalAlpha = 1;
    });
  };


  /* 2 · boosted trees with this version's settings */
  const drawStormLearner = function drawStormLearner(c, C, B, t, narrow, info) {
    var Lr = info.v.spec.learner || {}, Lb = stormPrev(info).learner, depth = Math.max(2, Math.min(6, Math.round(Math.log(Lr.leaves || 31) / Math.LN2)));
    stormHeader(c, C, B, 'Gradient-boosted trees', narrow ? '' : 'each tree fixes the errors left by the trees before it');
    var shown = narrow ? 5 : 8, gapx = (B.w - 20) / shown, th = narrow ? 92 : 112, ty = B.y + 34;
    var grown = Math.min(shown, Math.floor(t / 0.55) + 1);
    for (var i = 0; i < shown; i++) {
      var a = i < grown ? 1 : 0.18, cx = B.x + 10 + gapx * (i + 0.5), w = gapx * 0.8;
      c.globalAlpha = a;
      drawTreeGlyph(c, C, cx, ty, w, th, depth, i === grown - 1 && t < shown * 0.55 ? C.warm : C.accent);
      label(c, C, i === shown - 1 ? '… ' + fmtInt(Lr.trees) : '#' + (i + 1), cx, ty + th + 14, { align: 'center', size: 10.5, color: C.muted });
      c.globalAlpha = 1;
    }
    // settings, with changes against the baseline highlighted
    var sy = ty + th + 34, items = [
      ['trees', fmtInt(Lr.trees), Lr.trees !== Lb.trees ? fmtInt(Lb.trees) : null],
      ['leaves per tree', 'up to ' + Lr.leaves, Lr.leaves !== Lb.leaves ? String(Lb.leaves) : null],
      ['materials per leaf', 'at least ' + Lr.min_leaf, Lr.min_leaf !== Lb.min_leaf ? String(Lb.min_leaf) : null],
      ['learning rate', String(Lr.learning_rate), Lr.learning_rate !== Lb.learning_rate ? String(Lb.learning_rate) : null],
      ['features per split', Lr.features_per_split >= 1 ? 'all' : Math.round(Lr.features_per_split * 100) + '%', Lr.features_per_split !== Lb.features_per_split ? (Lb.features_per_split >= 1 ? 'all' : Math.round(Lb.features_per_split * 100) + '%') : null]
    ];
    var lossA = Lr.loss || 'squared error', lossB = Lb.loss || 'squared error', ensA = Lr.ensemble || 1, ensB = Lb.ensemble || 1;
    if (Lr.loss || Lb.loss) items.push(['objective', lossA === 'absolute error' ? 'median (absolute error)' : 'mean (squared error)', lossA !== lossB ? (lossB === 'absolute error' ? 'median' : 'mean') : null]);
    if (ensA > 1 || ensB > 1) items.push(['models averaged', String(ensA), ensA !== ensB ? String(ensB) : null]);
    var stg = info.v.spec.stage;
    if (stg && t > 0.8) stTag(c, C, stg.label || 'Allen–Dynes stage', B.x + B.w, B.y + 8, { align: 'right', size: 11, bg: stAlpha(C.warm, 0.16), ring: C.warm, color: C.ink });
    var cols = narrow ? 2 : 5, cw = B.w / cols;
    items.forEach(function (it, j) {
      var x = B.x + (j % cols) * cw, y = sy + Math.floor(j / cols) * 42;
      if (y + 30 > B.y + B.h + 6) return;
      var changed = !!it[2];
      label(c, C, it[0], x, y + 10, { size: 11, color: C.muted });
      label(c, C, it[1], x, y + 28, { size: 13, weight: '600', color: changed ? C.warm : C.ink });
      if (changed) { stFont(c, C, 13, '600'); label(c, C, ' (was ' + it[2] + ')', x + c.measureText(it[1]).width, y + 28, { size: 11, color: C.muted }); }
    });
  };

  const drawTreeGlyph = function drawTreeGlyph(c, C, cx, y, w, hgt, depth, col) {
    var levels = depth, dy = hgt / (levels + 0.5);
    c.lineWidth = 1; c.strokeStyle = stAlpha(col, 0.7);
    function node(x, yy, half, lev) {
      if (lev >= levels) { dot(c, x, yy, 2, col); return; }
      var ny = yy + dy, sp = half / 2;
      c.beginPath(); c.moveTo(x, yy); c.lineTo(x - sp, ny); c.moveTo(x, yy); c.lineTo(x + sp, ny); c.stroke();
      node(x - sp, ny, sp, lev + 1); node(x + sp, ny, sp, lev + 1);
    }
    dot(c, cx, y, 2.6, col);
    node(cx, y, w / 2, 1);
  };


  /* 3 · the two routes to Tc */
  const drawStormPredict = function drawStormPredict(c, C, B, t, narrow, info) {
    var sc = info.v.scores;
    stormHeader(c, C, B, 'Two routes to Tc', '');
    var rowY = narrow ? [B.y + 54, B.y + 200] : [B.y + 70, B.y + 190], bw = narrow ? (B.w - 24) / 3 : 120;
    function box(x, y, w, text, col, a) {
      c.globalAlpha = a;
      stRound(c, x, y - 17, w, 34, 8); c.fillStyle = col === C.surface ? C.surface : stAlpha(col, 0.14); c.fill();
      c.lineWidth = 1; c.strokeStyle = col === C.surface ? C.grid : col; c.stroke();
      stText(c, C, text, x + w / 2, y + 0.5, { align: 'center', base: 'middle', size: narrow ? 11 : 12, weight: '600', color: C.ink });
      c.globalAlpha = 1;
    }
    var xs = narrow ? [B.x, B.x + bw + 12, B.x + 2 * (bw + 12)] : [B.x, B.x + B.w * 0.28, B.x + B.w * 0.56];
    var bwN = narrow ? bw : Math.min(170, B.w * 0.22);
    // direct route
    var a1 = stSpan(t, 0.2, 0.8), a2 = stSpan(t, 0.9, 1.5), a3 = stSpan(t, 1.6, 2.2);
    box(xs[0], rowY[0], bwN, info.name + ' features', C.surface, a1);
    box(xs[1], rowY[0], bwN, 'log(1 + Tc)', C.accent, a2);
    box(xs[2], rowY[0], bwN, 'Tc', C.accent, a3);
    if (a2 > 0) stArrow(c, xs[0] + bwN + 3, rowY[0], xs[1] - 3, rowY[0], C.axis, 5);
    if (a3 > 0) stArrow(c, xs[1] + bwN + 3, rowY[0], xs[2] - 3, rowY[0], C.axis, 5);
    if (t > 2.2) {
      c.globalAlpha = stSpan(t, 2.2, 2.7);
      stText(c, C, 'error ' + fmtVal(sc.tc_mae) + ' K', narrow ? xs[2] + bwN / 2 : xs[2] + bwN + 14, narrow ? rowY[0] + 34 : rowY[0] + 4,
        { align: narrow ? 'center' : 'left', size: 12.5, weight: '600', color: C.accent });
      c.globalAlpha = 1;
    }
    // via λ and ω_log
    var b1 = stSpan(t, 2.8, 3.4), b2 = stSpan(t, 3.5, 4.1), b3 = stSpan(t, 4.2, 4.8);
    box(xs[0], rowY[1], bwN, info.name + ' features', C.surface, b1);
    box(xs[1], rowY[1] - 26, bwN, 'λ', C.aqua || C.accent, b2);
    box(xs[1], rowY[1] + 26, bwN, 'ω_log', C.aqua || C.accent, b2);
    box(xs[2], rowY[1], bwN, 'Allen–Dynes Tc', C.warm, b3);
    if (b2 > 0) { stArrow(c, xs[0] + bwN + 3, rowY[1], xs[1] - 3, rowY[1] - 26, C.axis, 5); stArrow(c, xs[0] + bwN + 3, rowY[1], xs[1] - 3, rowY[1] + 26, C.axis, 5); }
    if (b3 > 0) { stArrow(c, xs[1] + bwN + 3, rowY[1] - 26, xs[2] - 3, rowY[1], C.axis, 5); stArrow(c, xs[1] + bwN + 3, rowY[1] + 26, xs[2] - 3, rowY[1], C.axis, 5); }
    if (t > 4.8) {
      c.globalAlpha = stSpan(t, 4.8, 5.3);
      if (narrow) {
        stText(c, C, 'λ ± ' + fmtVal(sc.lambda_mae) + ' · ω_log ± ' + fmtVal(sc.omega_log_mae) + ' K', B.x, rowY[1] + 66, { size: 11.5, color: C.ink2 });
        stText(c, C, 'Tc error ' + fmtVal(sc.tc_via_lambda_wlog_mae) + ' K', xs[2] + bwN / 2, rowY[1] + 34, { align: 'center', size: 12.5, weight: '600', color: C.warm });
      } else {
        stText(c, C, 'error ± ' + fmtVal(sc.lambda_mae), xs[1] + bwN + 10, rowY[1] - 46, { size: 11, color: C.ink2 });
        stText(c, C, 'error ± ' + fmtVal(sc.omega_log_mae) + ' K', xs[1] + bwN + 10, rowY[1] + 50, { size: 11, color: C.ink2 });
        stText(c, C, 'error ' + fmtVal(sc.tc_via_lambda_wlog_mae) + ' K', xs[2] + bwN + 14, rowY[1] + 4, { size: 12.5, weight: '600', color: C.warm });
      }
      c.globalAlpha = 1;
    }
  };


  /* 4 · fold-by-fold check against the baseline */
  const drawStormCheck = function drawStormCheck(c, C, B, t, narrow, info) {
    var sc = info.v.scores, f = list(sc.folds), r = list(sc.reference_folds), n = f.length, pv = stormPrevScores(info), q = pv ? list(pv.folds) : [];
    stormHeader(c, C, B, pv ? 'Better than ' + pv.name + ' in ' + pv.folds_better + ' of ' + n + ' folds' : 'Better in ' + sc.folds_better + ' of ' + n + ' folds', narrow ? '' : 'Tc error per test fold (K)');
    var P = { x: B.x + 34, y: B.y + 34, w: B.w - 34 - (narrow ? 4 : 190), h: B.h - 74 };
    var top = 0;
    f.concat(r, q).forEach(function (v) { top = Math.max(top, v); });
    var tstep = niceStep(top * 1.1 || 1, 3);
    top = Math.ceil(top * 1.1 / tstep) * tstep;
    function Y(v) { return P.y + P.h - v / top * P.h; }
    c.lineWidth = 1;
    for (var g = 0; g <= top + 1e-9; g += tstep) {
      var yy = Math.round(Y(g)) + 0.5;
      c.strokeStyle = g ? C.grid : C.axis; c.beginPath(); c.moveTo(P.x, yy); c.lineTo(P.x + P.w, yy); c.stroke();
      label(c, C, fmtTick(g), P.x - 6, yy + 4, { align: 'right', size: 10.5, color: C.muted });
    }
    var gw = P.w / n, bw = Math.min(pv ? 18 : 26, gw * (pv ? 0.24 : 0.3));
    for (var i = 0; i < n; i++) {
      var a = stSpan(t, 0.3 + 0.5 * i, 0.9 + 0.5 * i), gx = P.x + gw * (i + 0.5);
      var hr = (P.y + P.h - Y(r[i])) * a, hf = (P.y + P.h - Y(f[i])) * stSpan(t, 0.6 + 0.5 * i, 1.2 + 0.5 * i);
      var x0 = pv ? gx - 1.5 * bw - 2 : gx - bw - 1, xf = pv ? gx + 0.5 * bw + 2 : gx + 1;
      c.fillStyle = C.axis; c.fillRect(x0, P.y + P.h - hr, bw, hr);
      if (pv) { var hq = (P.y + P.h - Y(q[i])) * stSpan(t, 0.45 + 0.5 * i, 1.05 + 0.5 * i); c.fillStyle = stAlpha(C.accent, 0.4); c.fillRect(gx - 0.5 * bw, P.y + P.h - hq, bw, hq); }
      c.fillStyle = C.accent; c.fillRect(xf, P.y + P.h - hf, bw, hf);
      label(c, C, 'fold ' + (i + 1), gx, P.y + P.h + 15, { align: 'center', size: 10.5, color: C.muted });
      if (t > 1.2 + 0.5 * i && f[i] < (pv ? q[i] : r[i])) label(c, C, '✓', xf + bw / 2, P.y + P.h - hf - 6, { align: 'center', size: 11, weight: '600', color: C.accent });
    }
    var kx = narrow ? B.x : P.x + P.w + 26, ky = narrow ? B.y + B.h - 6 : P.y + 10;
    if (narrow && pv) {
      var w3 = B.w / 3;
      c.fillStyle = C.axis; c.fillRect(kx, ky - 8, 10, 10); label(c, C, 'baseline ' + fmtVal(sc.reference_mae), kx + 14, ky + 1, { size: 11, color: C.ink2 });
      c.fillStyle = stAlpha(C.accent, 0.4); c.fillRect(kx + w3, ky - 8, 10, 10); label(c, C, pv.name.replace(info.name + ' ', 'v') + ' ' + fmtVal(pv.tc_mae), kx + w3 + 14, ky + 1, { size: 11, color: C.ink2 });
      c.fillStyle = C.accent; c.fillRect(kx + 2 * w3, ky - 8, 10, 10); label(c, C, 'v' + info.v.version + ' ' + fmtVal(sc.tc_mae) + ' K', kx + 2 * w3 + 14, ky + 1, { size: 11, weight: '600', color: C.accent });
    } else if (narrow) {
      c.fillStyle = C.axis; c.fillRect(kx, ky - 8, 10, 10); label(c, C, 'baseline ' + fmtVal(sc.reference_mae) + ' K', kx + 14, ky + 1, { size: 11, color: C.ink2 });
      c.fillStyle = C.accent; c.fillRect(kx + B.w / 2, ky - 8, 10, 10); label(c, C, info.name + ' ' + fmtVal(sc.tc_mae) + ' K', kx + B.w / 2 + 14, ky + 1, { size: 11, weight: '600', color: C.accent });
    } else if (pv) {
      c.fillStyle = C.axis; c.fillRect(kx, ky - 8, 10, 10); label(c, C, 'baseline', kx + 16, ky + 1, { size: 11.5, color: C.ink2 });
      label(c, C, fmtVal(sc.reference_mae) + ' K', kx + 16, ky + 19, { size: 13, weight: '600', color: C.ink2 });
      c.fillStyle = stAlpha(C.accent, 0.4); c.fillRect(kx, ky + 34, 10, 10); label(c, C, pv.name, kx + 16, ky + 43, { size: 11.5, color: C.ink2 });
      label(c, C, fmtVal(pv.tc_mae) + ' K', kx + 16, ky + 61, { size: 13, weight: '600', color: C.ink2 });
      c.fillStyle = C.accent; c.fillRect(kx, ky + 76, 10, 10); label(c, C, stormTitle(info), kx + 16, ky + 85, { size: 11.5, color: C.accent });
      label(c, C, fmtVal(sc.tc_mae) + ' K', kx + 16, ky + 103, { size: 13, weight: '600', color: C.accent });
      if (pv.tc_mae > 0) {
        var g2 = Math.round((1 - sc.tc_mae / pv.tc_mae) * 100);
        if (g2 > 0 && t > 3) stTag(c, C, g2 + '% lower than ' + pv.name.replace(info.name + ' ', 'v'), kx, ky + 128, { align: 'left', size: 11.5, bg: C.track, color: C.ink });
      }
    } else {
      c.fillStyle = C.axis; c.fillRect(kx, ky - 8, 10, 10); label(c, C, 'baseline', kx + 16, ky + 1, { size: 11.5, color: C.ink2 });
      label(c, C, fmtVal(sc.reference_mae) + ' K', kx + 16, ky + 19, { size: 13, weight: '600', color: C.ink2 });
      c.fillStyle = C.accent; c.fillRect(kx, ky + 38, 10, 10); label(c, C, stormTitle(info), kx + 16, ky + 47, { size: 11.5, color: C.accent });
      label(c, C, fmtVal(sc.tc_mae) + ' K', kx + 16, ky + 65, { size: 13, weight: '600', color: C.accent });
      if (sc.reference_mae > 0) {
        var gain = Math.round((1 - sc.tc_mae / sc.reference_mae) * 100);
        if (gain > 0 && t > 3) stTag(c, C, gain + '% lower error', kx, ky + 94, { align: 'left', size: 11.5, bg: C.track, color: C.ink });
      }
    }
  };


  /* 5 · what changed in this version */
  const drawStormNew = function drawStormNew(c, C, B, t, narrow, info) {
    var v = info.v, ch = list(v.changes);
    stormHeader(c, C, B, stormTitle(info) + ' · ' + stormFmtDate(v.date) + ' · round ' + v.round, '');
    var ok = v.status === 'adopted';
    stTag(c, C, ok ? 'released' : 'experimental', B.x + B.w, B.y + 8, { align: 'right', size: 11, bg: ok ? C.accent : C.surface, ring: ok ? null : C.grid, color: ok ? '#ffffff' : C.ink });
    var y = B.y + 40, maxW = B.w - 30;
    ch.forEach(function (text, i) {
      var a = stSpan(t, 0.4 + 0.9 * i, 1.0 + 0.9 * i);
      if (a <= 0 || y > B.y + B.h - 30) return;
      c.globalAlpha = a;
      dot(c, B.x + 8, y - 4, 8, stAlpha(C.warm, 0.18));
      label(c, C, '+', B.x + 8, y, { align: 'center', size: 13, weight: '700', color: C.warm });
      var lines = stParaRich(c, C, prettyMath(text), B.x + 26, y, maxW, narrow ? 16 : 17, { size: narrow ? 11.5 : 12.5, color: C.ink });
      y += lines * (narrow ? 16 : 17) + 14;
      c.globalAlpha = 1;
    });
    if (t > 0.6 + 0.9 * ch.length) {
      c.globalAlpha = stSpan(t, 0.6 + 0.9 * ch.length, 1.2 + 0.9 * ch.length);
      stParaRich(c, C, 'This animation is drawn from the model’s own spec, so the next version of ' + info.name + ' will explain itself here.', B.x, Math.min(B.y + B.h - 8, y + 8), B.w, 16, { size: 11.5, color: C.muted });
      c.globalAlpha = 1;
    }
  };
