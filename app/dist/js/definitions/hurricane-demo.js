'use strict';
// hurricane-demo: shared lexical function definitions; no startup side effects.

  const hurFamText = function hurFamText(f) { return HUR_FAM_TEXT[f] || lcFirst(famLabel(f)); };


  const hurInfo = function hurInfo() {
    var hu = state.data && state.data.hurricane;
    var vs = hu ? list(hu.versions).filter(function (v) { return v && v.scores && v.spec; }) : [];
    if (!vs.length) return null;
    var v = vs.filter(function (x) { return x.version === hu.current; })[0] || vs[vs.length - 1];
    return { hu: hu, v: v, name: hu.name || 'Hurricane', data: hu.data || {}, versions: vs };
  };

  const hurTitle = function hurTitle(info) { return info.name + ' ' + info.v.version; };

  const hurColor = function hurColor(C, f) { return { 'cuprate': C.accent, 'iron-based': C.warm, 'heavy-fermion': C.aqua || C.accent, 'other oxide': C.gold || C.ink2 }[f] || C.muted; };

  const hurFamilies = function hurFamilies(info) {
    var fam = info.data.families || {}, out = [];
    HUR_FAMS.concat(Object.keys(fam).filter(function (k) { return HUR_FAMS.indexOf(k) < 0; })).forEach(function (k) {
      var f = fam[k];
      if (f && typeof f.n === 'number') out.push({ id: k, label: f.label || famLabel(k), n: f.n, n_sc: f.n_sc || 0, max_tc: f.max_tc || 0 });
    });
    return out;
  };

  const hurK = function hurK(v) { return typeof v === 'number' ? (Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2)) : '—'; };

  const hurSub = function hurSub(s) {
    return String(s || '').replace(/([A-Za-z\)])(\d+(?:\.\d+)?)/g, function (m, a, d) {
      return a + d.replace(/[0-9]/g, function (ch) { return '₀₁₂₃₄₅₆₇₈₉'.charAt(+ch); });
    });
  };

  // "HgBa2Ca2Cu3O8+δ (Hg-1223)" → "Hg-1223"; "LK-99 (Cu-doped lead apatite)" → "LK-99"
  const hurShortName = function hurShortName(name) {
    var m = /^(.*\S)\s*\(([^()]+)\)$/.exec(String(name || ''));
    var s = m ? (m[2].length < m[1].length ? m[2] : m[1]) : String(name || '');
    return hurSub(s);
  };

  const hurFit = function hurFit(c, C, text, maxW, size, weight) {
    stFont(c, C, size, weight);
    if (c.measureText(text).width <= maxW) return text;
    while (text.length > 4 && c.measureText(text + '…').width > maxW) text = text.slice(0, -1);
    return text.replace(/[ ,]+$/, '') + '…';
  };

  const hurGroupOf = function hurGroupOf(info) {
    var map = {};
    list(info.v.spec.inputs).forEach(function (g) { list(g.items).forEach(function (it) { map[it.name] = g.group; }); });
    return function (name) {
      if (map[name]) return map[name];
      if (/^x_[A-Z]/.test(name)) return 'elements';
      if (/^(cs|ct)_/.test(name)) return 'structure';
      return 'composition';
    };
  };

  const hurGroupColor = function hurGroupColor(C, g) { return g === 'physics' ? C.warm : g === 'structure' ? (C.aqua || C.accent) : g === 'elements' ? (C.gold || C.ink2) : C.accent; };

  const hurFeatName = function hurFeatName(n) { return HUR_FEAT[n] || featLabel(n); };


  const hurCaption = function hurCaption(si) {
    var info = hurInfo();
    if (!info) return 'Hurricane is our AI-designed model for unconventional superconductors. Its data and scores load with the live progress data.';
    var v = info.v, sc = v.scores || {}, dd = info.data, name = hurTitle(info), nf = list(sc.folds).length, ok = v.status === 'adopted';
    var non = (dd.n || 0) - (dd.n_sc || 0), rl = hurRel(v), bgn = rl && rl.background && typeof rl.background.n === 'number' ? rl.background.n : 0;
    switch (si) {
      case 0:
        return 'No first-principles theory gives Tc for cuprates, iron-based or heavy-fermion superconductors, so Hurricane learns from measurements: ' +
          fmtInt(dd.n) + ' measured Tc values from 3DSC, which pairs the SuperCon database of measured Tc with Materials Project crystal structures' +
          (dd.n_groups ? ', from ' + fmtInt(dd.n_groups) + ' parent compounds' : '') + '. ' + fmtInt(non) +
          ' of them were reported as not superconducting down to the lowest temperature measured; they teach the model where Tc falls to zero.' +
          (bgn ? ' Its classifier also learns from ' + fmtInt(typeof rl.background.n_used === 'number' ? rl.background.n_used : bgn) + ' compounds that no one has reported as superconducting, counted as probably not superconducting, so that it does not call ordinary compounds likely superconductors.' : '') +
          (hur4(rl) && rl.abstain ? ' Far from everything it learned from, it answers “not known” instead of giving a chance.' : '');
      case 1:
        var sr = v.search || {}, pv = v.previous && typeof v.previous.tc_mae === 'number' ? v.previous : null;
        if (pv && hur4(rl)) {   // round 4: "not known" far from the training data, released for calling fewer of a new family unlikely
          var nNew4 = typeof sr.candidates === 'number' ? sr.candidates - (sr.reference_id ? 1 : 0) - (sr.previous_id ? 1 : 0) - (sr.version_reference_id ? 1 : 0) : 0;
          return 'In round ' + v.round + ' an AI agent (Claude) proposed ' + (nNew4 > 0 ? nNew4 : 'several') + ' new designs built on Hurricane ' + pv.version +
            ': each gives a chance only near its training data and answers “not known” further away, some of them also keeping only the background compounds nearby. Each was asked about whole families it never learned from. ' +
            (ok ? 'The best one calls ' + radPct(rl.dismissed) + ' of such a family’s superconductors unlikely, against ' + radPct(rl.dismissed_previous) + ' for Hurricane ' + pv.version +
              (rl.reference_version ? ' and ' + radPct(rl.dismissed_reference) + ' for Hurricane ' + rl.reference_version : '') + ', with ' + (rl.false_alarms === 0 ? 'no false alarms' : radPct(rl.false_alarms) + ' false alarms') + ', and became ' + name + '.' +
              (typeof hurLofoAvg(v, 'unknown') === 'number' && typeof hurLofoAvg(v, 'found') === 'number' ? ' For ' + radPct(hurLofoAvg(v, 'unknown')) + ' of them it answers “not known”, and it gives ' + radPct(hurLofoAvg(v, 'found')) +
                ' at least an even chance' + (typeof hurLofoAvg(v, 'found_reference') === 'number' && rl.reference_version ? ' (Hurricane ' + rl.reference_version + ': ' + radPct(hurLofoAvg(v, 'found_reference')) + ')' : '') +
                (hurLofoAvg(v, 'found') <= 0.2 ? ': it would not recognize a new family either.' : '.') : '')
              : 'None passed every test of the release rule, so Hurricane ' + pv.version + ' stays in use.');
        }
        if (pv && rl) {   // round 3: the same model with background compounds, released for fewer false alarms outside the training data
          var nNew3 = typeof sr.candidates === 'number' ? sr.candidates - (sr.reference_id ? 1 : 0) - (sr.previous_id ? 1 : 0) : 0;
          return 'In round ' + v.round + ' an AI agent (Claude) proposed ' + (nNew3 > 0 ? nNew3 : 'several') + ' new designs built on Hurricane ' + pv.version +
            ': the same model, with compounds that have no superconductivity record added as not superconducting, at different weights. Each was scored on compounds it never learned from. ' +
            (ok ? 'The best one cut the false alarms, compounds with no record given at least an even chance, from ' + radPct(rl.false_alarms_previous) + ' to ' + (rl.false_alarms === 0 ? 'none' : radPct(rl.false_alarms)) +
              ', with a measured-Tc error of ' + kPair(sc.tc_mae, pv.tc_mae)[0] + ' against ' + kPair(sc.tc_mae, pv.tc_mae)[1] + ', and became ' + name + '.'
              : 'None passed every test of the release rule, so Hurricane ' + pv.version + ' stays in use.');
        }
        if (pv) {   // round 2 and later: new designs built on the version in use, which is retrained on the same folds as the yardstick
          var nNew = typeof sr.candidates === 'number' ? sr.candidates - (sr.reference_id ? 1 : 0) - (sr.previous_id ? 1 : 0) : 0;
          return 'In round ' + v.round + ' an AI agent (Claude) proposed ' + (nNew > 0 ? nNew : 'several') + ' new designs built on Hurricane ' + pv.version +
            ', which was retrained on the same folds as the yardstick; Model details on the Progress view lists them. ' +
            (ok ? 'The best one beat Hurricane ' + pv.version + ' on average and in ' + pv.folds_better + ' of ' + list(pv.folds).length + ' folds and became ' + name + '.'
              : 'A design is released only if it beats Hurricane ' + pv.version + ' on average and in at least 4 of 5 folds; none did this round, so Hurricane ' + pv.version + ' stays in use.');
        }
        return 'An AI agent (Claude) proposed ' + (sr.candidates || 'several') + ' designs in round ' + v.round +
          ': which inputs to use, physics features, the objective and how to weight noisy entries. Each was trained and scored with five-fold cross-validation that holds out whole parent compounds, so no test compound has a close relative in training. ' +
          (ok ? 'The best one beat the composition-only baseline on average and in ' + sc.folds_better + ' of ' + nf + ' folds and became ' + name + '.'
            : 'A design is released only if it beats the baseline on average and in at least 4 of 5 folds; none did this round, so ' + name + ' stays experimental.');
      case 2:
        var ins = list(v.spec.inputs), total = 0, top = list(v.importance).slice(0, 3).map(function (i) { return hurFeatName(i.name); });
        ins.forEach(function (g) { total += g.n || 0; });
        return name + ' reads ' + total + ' numbers per compound: ' + ins.map(function (g) { return g.n + ' ' + lcFirst(g.label); }).join(', ').replace(/, ([^,]*)$/, ' and $1') +
          '. The physics features carry what is known about these families. Charge balance gives the holes per copper, p, and cuprate Tc rises and falls with p along the empirical dome 1 − 82.6 (p − 0.16)², highest at p = 0.16; it also gives the d-electron count of the metal layer (Cu²⁺ is d⁹, Fe²⁺ d⁶).' +
          (top.length ? ' Shuffling one input at a time and measuring how much the error grows shows what the model relies on most: ' + top.join(', ') + '.' : '') +
          // Hurricane 2.0 and later can predict in two parts (spec.learner.two_part says how)
          (v.spec.learner && typeof v.spec.learner.two_part === 'string' ? ' It predicts in two parts: ' + v.spec.learner.two_part.replace(/\.$/, '') + '.' : '');
      case 3:
        var fam = sc.by_family || {}, parts = [];
        HUR_FAMS.forEach(function (k) { if (fam[k]) parts.push(hurFamText(k) + ' ' + hurK(fam[k].mae) + ' K'); });
        var pv3 = v.previous && typeof v.previous.tc_mae === 'number' ? v.previous : null;
        return name + ' is off by ' + hurK(sc.tc_mae) + ' K on average for compounds whose parent it never saw, against ' + hurK(sc.reference_mae) +
          ' K for gradient boosting on the composition alone, and better in ' + sc.folds_better + ' of ' + nf + ' folds.' +
          (pv3 ? ' Hurricane ' + pv3.version + ', retrained on the same folds, is off by ' + hurK(pv3.tc_mae) + ' K.' : '') +
          (typeof sc.sc_mae === 'number' ? ' For superconductors alone the error is ' + hurK(sc.sc_mae) + ' K.' : '') +
          (parts.length ? ' By family: ' + parts.join(', ') + '. Cuprate Tc spans 0 to over 130 K, so their errors are the largest.' : '');
      case 4:
        var lo = list(v.lofo), cu = lo.filter(function (r) { return r.family === 'cuprate'; })[0];
        var flat = lo.filter(function (r) { return r.mae >= 0.9 * r.mae_median; }).map(function (r) { return hurFamText(r.family); });
        var good = lo.filter(function (r) { return r.mae < 0.5 * r.mae_median; });
        var cu4 = cu && hur4(hurRel(v)) && typeof cu.dismissed === 'number' ? cu : null;
        return 'Leaving out a whole family is a much harder test. ' +
          (cu ? 'Trained without any cuprate, ' + name + ' never predicts more than ' + hurK(cu.max_pred) + ' K for one, while cuprates reach ' + Math.round(cu.max_tc) + ' K. ' : '') +
          (cu4 ? 'It calls ' + radPct(cu4.dismissed) + ' of the cuprate superconductors unlikely and gives ' + radPct(cu4.unknown) + ' of them no chance at all' + (typeof cu4.dismissed_previous === 'number' ? ', where Hurricane ' + (v.previous && v.previous.version || 'before') + ' called ' + radPct(cu4.dismissed_previous) + ' unlikely' : '') + '. ' : '') +
          (flat.length ? 'For ' + flat.join(', ').replace(/, ([^,]*)$/, ' and $1') + ', the error is no better than always guessing the median Tc of the other families. ' : '') +
          (good.length ? good.map(function (r) { var x = hurFamText(r.family); return x.charAt(0).toUpperCase() + x.slice(1); }).join(' and ') + (good.length > 1 ? ' are' : ' are') + ' the exception: their Tc is low across the board, and a model that predicts low values does well (' + good.map(function (r) { return hurK(r.mae) + ' K'; }).join(', ') + '). ' : '') +
          'A model that has only seen other families does not discover a new one; finding a new high-Tc family needs physics that these correlations do not contain.';
      default:
        var an = v.anchors || {}, rows = list(an.table), hg = rows.filter(function (r) { return /Hg-1223\)?$/.test(r.name) && r.use === 'score'; })[0];
        var shown = rows.filter(function (r) { return r.use === 'show'; }).length, out = rows.filter(function (r) { return r.use === 'exclude'; });
        return 'Compounds Hurricane never trained on, most reported after the 2018 SuperCon snapshot that 3DSC is built on, each graded by reliability. Only replicated, ambient-pressure, bulk measurements in its four families are scored' +
          (typeof an.mae === 'number' ? ': ' + an.n_scored + ' so far, off by ' + hurK(an.mae) + ' K on average' + (an.scored_as_check ? '' : ', too few to count as a check yet') : '') + '. ' +
          (hg && typeof hg.pred === 'number' ? 'Hg-1223, the ambient-pressure record of ' + hg.tc_exp + ' K since 1993, is predicted at ' + Math.round(hg.pred) + ' K. ' : '') +
          (shown ? shown + ' more, such as thin films, pressure-quenched samples and kagome metals, are shown but not scored' : '') +
          (out.length ? (shown ? ', and ' : '') + out.map(function (r) { return hurShortName(r.name); }).join(', ') + ' is left out because it was ' + (out[0].status || 'refuted') : '') + '.';
    }
  };


  const hitHurNode = function hitHurNode(p) {
    var nodes = demo.hurNodes || [];
    for (var i = 0; i < nodes.length; i++) {
      var b = nodes[i];
      if (p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h) return i;
    }
    return -1;
  };


  const drawHurricane = function drawHurricane(c, C) {
    var W = demo.W, H = demo.H, narrow = W < 560;
    var si = demo.hurStage, t = motionOK() ? demo.hurT : HUR_DUR;
    var n = HUR_STAGES.length, gap = narrow ? 6 : 18, nodeW = (W - 32 - gap * (n - 1)) / n, nodeH = narrow ? 34 : 40, ny = 12;
    demo.hurNodes = [];
    for (var i = 0; i < n; i++) {
      var x = 16 + i * (nodeW + gap), on = i === si;
      demo.hurNodes.push({ x: x, y: ny, w: nodeW, h: nodeH });
      stRound(c, x, ny, nodeW, nodeH, 9);
      c.fillStyle = on ? C.accent : C.surface2; c.fill();
      if (!on) { c.lineWidth = 1; c.strokeStyle = C.grid; c.stroke(); }
      label(c, C, narrow ? HUR_STAGES[i].short : HUR_STAGES[i].node, x + nodeW / 2, ny + nodeH / 2 + 0.5,
        { align: 'center', base: 'middle', size: narrow ? 10.5 : 12, weight: '600', color: on ? '#ffffff' : C.ink2 });
      if (i < n - 1 && !narrow) stArrow(c, x + nodeW + 3, ny + nodeH / 2, x + nodeW + gap - 3, ny + nodeH / 2, C.axis, 5);
    }
    if (motionOK()) {
      var px = demo.hurNodes[si];
      c.fillStyle = stAlpha(C.accent, 0.25);
      c.fillRect(px.x + 6, ny + nodeH - 3, (px.w - 12) * Math.min(1, t / HUR_DUR), 2);
    }
    var B = { x: 16, y: ny + nodeH + 16, w: W - 32, h: H - ny - nodeH - 28 };
    var info = hurInfo();
    if (!info) {
      label(c, C, 'Hurricane’s results load with the live progress data.', W / 2, B.y + B.h / 2, { align: 'center', base: 'middle', size: 13, color: C.muted });
      return;
    }
    [drawHurData, drawHurDesign, drawHurPhysics, drawHurCheck, drawHurFamily, drawHurLater][si](c, C, B, t, narrow, info);
    c.globalAlpha = 1;
    c.setLineDash([]);
  };


  /* 0 · the measured data, family by family */
  const drawHurData = function drawHurData(c, C, B, t, narrow, info) {
    var dd = info.data, fams = hurFamilies(info);
    stormHeader(c, C, B, fmtInt(dd.n) + ' measured Tc values', narrow ? '' : '3DSC: SuperCon Tc with Materials Project structures');
    if (!fams.length) return;
    var L = narrow ? { x: B.x, y: B.y + 30, w: B.w, h: Math.min(190, B.h * 0.48) } : { x: B.x, y: B.y + 34, w: Math.round(B.w * 0.55), h: B.h - 34 };
    var R = narrow ? { x: B.x, y: L.y + L.h + 10, w: B.w, h: B.y + B.h - (L.y + L.h + 10) } : { x: L.x + L.w + 34, y: B.y + 34, w: B.w - L.w - 34, h: B.h - 34 };
    var maxN = 1;
    fams.forEach(function (f) { maxN = Math.max(maxN, f.n); });
    var rh = Math.min(narrow ? 46 : 64, L.h / fams.length);
    fams.forEach(function (f, i) {
      var a = stSpan(t, 0.2 + 0.4 * i, 0.8 + 0.4 * i);
      if (a <= 0) return;
      var y = L.y + i * rh, col = hurColor(C, f.id), g = stSpan(t, 0.4 + 0.4 * i, 1.6 + 0.4 * i);
      c.globalAlpha = a;
      dot(c, L.x + 5, y + 9, 5, col);
      label(c, C, f.label, L.x + 16, y + 13, { size: narrow ? 12 : 12.5, weight: '600', color: C.ink });
      label(c, C, fmtInt(Math.round(f.n * g)), L.x + L.w, y + 13, { align: 'right', size: 12, weight: '600', color: C.ink2 });
      var bw = (L.w - 16) * f.n / maxN, sw = f.n ? bw * f.n_sc / f.n : 0;
      c.fillStyle = stAlpha(col, 0.22); c.fillRect(L.x + 16, y + 20, bw * g, 10);
      c.fillStyle = col; c.fillRect(L.x + 16, y + 20, sw * g, 10);
      if (g > 0.85) {
        c.globalAlpha = a * stSpan(g, 0.85, 1);
        label(c, C, fmtInt(f.n_sc) + ' superconducting, up to ' + (f.max_tc >= 10 ? Math.round(f.max_tc) : f.max_tc.toFixed(1)) + ' K', L.x + 16, y + 43, { size: 11, color: C.muted });
      }
    });
    c.globalAlpha = 1;
    // the highest Tc in each family, against liquid nitrogen
    var ra = stSpan(t, 2.2, 2.8);
    if (ra <= 0) return;
    c.globalAlpha = ra;
    stText(c, C, 'Highest Tc in each family', R.x, R.y + 4, { size: 12, weight: '600', color: C.ink });
    var P = { x: R.x + 30, y: R.y + 22, w: R.w - 34, h: R.h - 22 - (narrow ? 28 : 34) };
    var topV = 0;
    fams.forEach(function (f) { topV = Math.max(topV, f.max_tc); });
    topV = Math.max(topV, 80);
    var step = niceStep(topV * 1.05, 3);
    topV = Math.ceil(topV * 1.05 / step) * step;
    function Y(v) { return P.y + P.h - v / topV * P.h; }
    c.lineWidth = 1;
    for (var gv = 0; gv <= topV + 1e-9; gv += step) {
      var yy = Math.round(Y(gv)) + 0.5;
      c.strokeStyle = gv ? C.grid : C.axis; c.beginPath(); c.moveTo(P.x, yy); c.lineTo(P.x + P.w, yy); c.stroke();
      label(c, C, fmtTick(gv), P.x - 6, yy + 4, { align: 'right', size: 10.5, color: C.muted });
    }
    var y77 = Math.round(Y(77)) + 0.5;
    c.setLineDash([4, 4]); c.strokeStyle = C.ink2; c.beginPath(); c.moveTo(P.x, y77); c.lineTo(P.x + P.w, y77); c.stroke(); c.setLineDash([]);
    label(c, C, 'liquid nitrogen, 77 K', P.x + P.w, y77 - 5, { align: 'right', size: 10.5, color: C.ink2 });
    var cw = P.w / fams.length, bwid = Math.min(34, cw * 0.46);
    fams.forEach(function (f, i) {
      var g = stSpan(t, 2.5 + 0.3 * i, 3.5 + 0.3 * i), x = P.x + cw * (i + 0.5), hgt = (P.y + P.h - Y(f.max_tc)) * g;
      c.fillStyle = hurColor(C, f.id); c.fillRect(x - bwid / 2, P.y + P.h - hgt, bwid, hgt);
      if (g > 0.9) label(c, C, (f.max_tc >= 10 ? Math.round(f.max_tc) : f.max_tc.toFixed(1)) + ' K', x, P.y + P.h - hgt - 6, { align: 'center', size: 11, weight: '600', color: C.ink });
      var short = cw < 80 ? ({ 'cuprate': 'Cuprates', 'iron-based': 'Fe, Ni', 'heavy-fermion': 'Heavy f.', 'other oxide': 'Oxides' }[f.id]) : HUR_FAM_SHORT[f.id];
      label(c, C, hurFit(c, C, short || f.label, cw - 4, 10.5), x, P.y + P.h + 14, { align: 'center', size: 10.5, color: C.ink2 });
    });
    if (!narrow && t > 4) {
      c.globalAlpha = stSpan(t, 4, 4.6);
      stParaRich(c, C, 'Pale: compounds reported as not superconducting. They show the model where Tc falls to zero.', L.x, L.y + fams.length * rh + 6, L.w, 16, { size: 11.5, color: C.muted });
    }
    c.globalAlpha = 1;
  };


  /* 1 · the design loop and the leaderboard of the round */
  const drawHurDesign = function drawHurDesign(c, C, B, t, narrow, info) {
    // round 3 on, the designs are compared by their false alarms outside the training data; before, by their Tc error
    var v = info.v, sr = v.search || {}, rl = hurRel(v);
    var r4 = hur4(rl), M = r4 ? function (r) { return r.dismissed; } : rl ? function (r) { return r.false_alarms; } : function (r) { return r.tc_mae; };
    var rows = list(sr.leaderboard).filter(function (r) { return typeof M(r) === 'number'; });
    var winner = rows.filter(function (r) { return stormRowName(r) === v.summary; })[0] || rows[0];
    stormHeader(c, C, B, 'Search round ' + v.round + ': ' + rows.length + ' designs', narrow ? '' : r4 ? 'superconductors of a left-out family called unlikely' : rl ? 'false alarms on compounds with no record' : 'Tc error in grouped CV (K)');
    var L = narrow ? { x: B.x, y: B.y + 26, w: B.w, h: 64 } : { x: B.x, y: B.y + 30, w: Math.round(B.w * 0.28), h: B.h - 36 };
    var steps = ['propose', 'train', 'score'], k = Math.floor(t * 1.4) % 3;
    if (narrow) {
      stRound(c, L.x, L.y, 104, 34, 8); c.fillStyle = C.accent; c.fill();
      label(c, C, 'AI agent', L.x + 52, L.y + 17.5, { align: 'center', base: 'middle', size: 12, weight: '600', color: '#ffffff' });
      var sx = L.x + 116, room = L.x + L.w - sx, ws = [], tot = 0, fs = 11;
      stFont(c, C, fs, '600');
      steps.forEach(function (s) { var w = c.measureText(s).width + 14; ws.push(w); tot += w; });
      var gapA = Math.max(4, (room - tot) / 2);
      steps.forEach(function (s, i) {
        stTag(c, C, s, sx, L.y + 17, { align: 'left', size: fs, bg: i === k ? C.track : C.surface, ring: C.grid, color: C.ink });
        if (i < 2 && gapA >= 14) stArrow(c, sx + ws[i] + 3, L.y + 17, sx + ws[i] + gapA - 3, L.y + 17, C.axis, 5);
        sx += ws[i] + gapA;
      });
      label(c, C, '(Claude)', L.x + 52, L.y + 48, { align: 'center', size: 10.5, color: C.muted });
    } else {
      var cx = L.x + L.w / 2, cy = L.y + L.h / 2 - 6, r = Math.min(L.w, L.h) * 0.3;
      c.lineWidth = 1.5; c.strokeStyle = C.grid;
      c.beginPath(); c.arc(cx, cy, r, 0, Math.PI * 2); c.stroke();
      steps.forEach(function (s, i) {
        var a = -Math.PI / 2 + i * 2 * Math.PI / 3;
        stTag(c, C, s, cx + Math.cos(a) * r, cy + Math.sin(a) * r, { size: 11.5, bg: i === k ? C.track : C.surface, ring: C.grid, color: C.ink });
      });
      var a2 = -Math.PI / 2 + (t * 1.4 % 3) * 2 * Math.PI / 3;
      dot(c, cx + Math.cos(a2) * r, cy + Math.sin(a2) * r, 3.5, C.warm);
      stRound(c, cx - 46, cy - 15, 92, 30, 8); c.fillStyle = C.accent; c.fill();
      label(c, C, 'AI agent', cx, cy + 0.5, { align: 'center', base: 'middle', size: 12, weight: '600', color: '#ffffff' });
      label(c, C, 'Claude proposes each design', cx, L.y + L.h - 4, { align: 'center', size: 11, color: C.muted });
    }
    var T = narrow ? { x: B.x, y: L.y + L.h + 6, w: B.w, h: B.y + B.h - (L.y + L.h + 6) } : { x: L.x + L.w + 24, y: B.y + 26, w: B.w - L.w - 24, h: B.h - 26 };
    if (!rows.length) return;
    var rh = Math.min(30, (T.h - 40) / rows.length), lo = Infinity, hi = -Infinity;
    rows.forEach(function (r) { lo = Math.min(lo, M(r)); hi = Math.max(hi, M(r)); });
    if (rl) lo = 0;   // shares start at zero
    var span = Math.max(rl ? 0.05 : 0.1, hi - lo), step = niceStep(span * 1.2, 4);
    var a0v = rl ? 0 : Math.floor((lo - span * 0.08) / step) * step, a1v = Math.ceil((hi + span * 0.08) / step) * step;
    var nameW = narrow ? Math.min(rl ? 190 : 170, T.w * (rl ? 0.6 : 0.56)) : Math.min(300, T.w * 0.55), bx = T.x + nameW + 10, bw = T.w - nameW - 52;
    var refId = r4 ? sr.version_reference_id || 'H12' : rl ? sr.previous_id || 'H12' : sr.reference_id || 'H0', base = rows.filter(function (r) { return r.id === refId; })[0];
    function BX(x) { return bx + (x - a0v) / (a1v - a0v) * bw; }
    var axisY = T.y + rows.length * rh + 4;
    c.lineWidth = 1;
    var every = bw / ((a1v - a0v) / step) < 24 ? 2 : 1, ti = 0;
    for (var tv = a0v; tv <= a1v + 1e-9; tv += step, ti++) {
      var gx = Math.round(BX(tv)) + 0.5;
      c.strokeStyle = C.grid; c.beginPath(); c.moveTo(gx, T.y); c.lineTo(gx, axisY); c.stroke();
      if (ti % every === 0) label(c, C, rl ? Math.round(100 * tv) + '%' : fmtTick(tv), gx, axisY + 13, { align: 'center', size: 10.5, color: C.muted });
    }
    rows.forEach(function (r, i) {
      var a = stSpan(t, 0.4 + 0.32 * i, 0.8 + 0.32 * i);
      if (a <= 0) return;
      var y = T.y + i * rh, isW = r === winner && t > 4.2, isB = r.id === refId, cy2 = y + rh / 2;
      c.globalAlpha = a;
      if (isW) { stRound(c, T.x - 6, y + 1, T.w + 6, rh - 2, 7); c.fillStyle = stAlpha(C.accent, 0.1); c.fill(); }
      stTag(c, C, r.id, T.x + 13, cy2, { size: 10.5, bg: isW ? C.accent : C.surface, ring: C.grid, color: isW ? '#ffffff' : C.ink2 });
      var full = (isB && rl) || (r4 && r.id === sr.previous_id) ? r.name + ', retrained' : (isB ? 'Composition only (baseline)' : r.name.replace(/^Composition \+ /, '+ ').replace(/^Hurricane [\d.]+ \+ /, '+ ').replace(/ compounds as non-superconducting$/, '').replace(/ \+ not known outside the training data$/, ' + not known')) + (r.settings && r.settings !== 'default' ? ', ' + r.settings : '');
      var size = narrow ? 11 : 12;
      label(c, C, hurFit(c, C, full, nameW - 32, size, isW ? '600' : '400'), T.x + 30, cy2 + 4, { size: size, color: isB ? C.ink2 : C.ink, weight: isW ? '600' : '400' });
      var x = BX(M(r)), col = isW ? C.accent : isB ? C.ink2 : mix(C.accent, C.surface2, 0.35);
      dot(c, x, cy2, isW ? 5.5 : 4.5, col);
      label(c, C, rl ? radPct(M(r)) : fmtVal(M(r)), x + 9, cy2 + 4, { size: 11, weight: isW ? '600' : '400', color: isW ? C.accent : C.ink2 });
      c.globalAlpha = 1;
    });
    if (base && t > 0.6) {
      var xb = Math.round(BX(M(base))) + 0.5;
      c.setLineDash([3, 3]); c.strokeStyle = C.ink2; c.lineWidth = 1;
      c.beginPath(); c.moveTo(xb, T.y); c.lineTo(xb, axisY); c.stroke(); c.setLineDash([]);
    }
    if (t > 4.6) {
      c.globalAlpha = stSpan(t, 4.6, 5.2);
      var ok = v.status === 'adopted';
      stTag(c, C, ok ? 'Released as ' + hurTitle(info) : hurTitle(info) + ' stays experimental', T.x + T.w, axisY + 32, { align: 'right', size: 12, bg: ok ? C.accent : C.surface, ring: ok ? null : C.grid, color: ok ? '#ffffff' : C.ink });
      c.globalAlpha = 1;
    }
  };


  /* 2 · what goes in, the cuprate dome behind the most useful input, and what the model relies on */
  const hurDome = function hurDome(p) { return Math.max(0, 1 - 82.6 * (p - 0.16) * (p - 0.16)); };

  const drawHurPhysics = function drawHurPhysics(c, C, B, t, narrow, info) {
    var ins = list(info.v.spec.inputs), total = 0;
    ins.forEach(function (g) { total += g.n || 0; });
    stormHeader(c, C, B, total + ' numbers describe each compound', narrow ? '' : 'orange: physics features the AI proposed');
    var sy = B.y + 26, x = B.x;
    ins.forEach(function (g, i) {
      var a = stSpan(t, 0.2 + 0.3 * i, 0.7 + 0.3 * i);
      var w = B.w * (g.n || 0) / (total || 1), col = hurGroupColor(C, g.group);
      if (a > 0) {
        c.globalAlpha = a;
        c.fillStyle = g.group === 'physics' ? col : stAlpha(col, 0.5);
        c.fillRect(x + 1, sy, Math.max(0, w - 2), 12);
        var names = { composition: 'composition', structure: 'structure', physics: 'physics', elements: 'element shares' };
        var txt = g.n + ' ' + (names[g.group] || lcFirst(g.label));
        stFont(c, C, 11, '600');
        if (c.measureText(txt).width > w - 4) txt = String(g.n);
        label(c, C, txt, x + 2, sy + 27, { size: 11, weight: '600', color: g.group === 'physics' ? C.warm : C.ink2 });
      }
      x += w;
    });
    c.globalAlpha = 1;
    var top = sy + 44;
    var D = narrow ? { x: B.x, y: top, w: B.w, h: Math.min(176, (B.y + B.h - top) * 0.47) } : { x: B.x, y: top, w: Math.round(B.w * 0.47), h: B.y + B.h - top };
    var I = narrow ? { x: B.x, y: D.y + D.h + 16, w: B.w, h: B.y + B.h - (D.y + D.h + 16) } : { x: D.x + D.w + 34, y: top, w: B.w - D.w - 34, h: B.y + B.h - top };
    drawHurDomePanel(c, C, D, t, 1.2, narrow);
    drawHurImportance(c, C, I, t, narrow, info);
  };

  // The empirical cuprate dome (Presland and Tallon): Tc / Tc,max = 1 − 82.6 (p − 0.16)²
  const drawHurDomePanel = function drawHurDomePanel(c, C, D, t, s0, narrow) {
    var a = stSpan(t, s0, s0 + 0.6);
    if (a <= 0) return;
    c.globalAlpha = a;
    stText(c, C, 'Cuprate Tc against holes per Cu', D.x, D.y + 4, { size: 12, weight: '600', color: C.ink });
    var P = { x: D.x + 30, y: D.y + 20, w: D.w - 40, h: D.h - 20 - 44 };
    if (P.h < 40 || P.w < 80) return;
    var PMAX = 0.3;
    function X(p) { return P.x + p / PMAX * P.w; }
    function Y(v) { return P.y + P.h - v * P.h * 0.92; }
    c.lineWidth = 1;
    [0, 0.1, 0.2, 0.3].forEach(function (p) {
      var gx = Math.round(X(p)) + 0.5;
      c.strokeStyle = p ? C.grid : C.axis; c.beginPath(); c.moveTo(gx, P.y); c.lineTo(gx, P.y + P.h); c.stroke();
      label(c, C, p ? p.toFixed(1) : '0', gx, P.y + P.h + 13, { align: 'center', size: 10.5, color: C.muted });
    });
    c.strokeStyle = C.axis; c.beginPath(); c.moveTo(P.x, Math.round(P.y + P.h) + 0.5); c.lineTo(P.x + P.w, Math.round(P.y + P.h) + 0.5); c.stroke();
    stText(c, C, 'Tc', P.x - 6, Y(1) + 4, { align: 'right', size: 11, color: C.muted });
    var g = stSpan(t, s0 + 0.3, s0 + 1.7), p0 = 0.05, p1 = 0.05 + (0.27 - 0.05) * g;
    if (g > 0) {
      c.beginPath(); c.moveTo(X(p0), Y(0));
      for (var p = p0; p <= p1 + 1e-9; p += 0.0025) c.lineTo(X(p), Y(hurDome(p)));
      c.lineTo(X(p1), Y(0)); c.closePath();
      c.fillStyle = stAlpha(C.accent, 0.14); c.fill();
      c.beginPath();
      for (var q = p0; q <= p1 + 1e-9; q += 0.0025) { if (q === p0) c.moveTo(X(q), Y(hurDome(q))); else c.lineTo(X(q), Y(hurDome(q))); }
      c.lineWidth = 2; c.strokeStyle = C.accent; c.stroke();
    }
    if (g >= 1) {
      var xo = Math.round(X(0.16)) + 0.5;
      c.setLineDash([3, 3]); c.lineWidth = 1; c.strokeStyle = C.ink2;
      c.beginPath(); c.moveTo(xo, Y(1) - 4); c.lineTo(xo, P.y + P.h); c.stroke(); c.setLineDash([]);
      if (!narrow || D.w > 260) {
        label(c, C, 'underdoped', X(0.085), Y(0.18), { align: 'center', size: 10.5, color: C.muted });
        label(c, C, 'overdoped', X(0.24), Y(0.18), { align: 'center', size: 10.5, color: C.muted });
      }
      // a sample sweeping the doping: Tc follows the dome
      var ph = motionOK() ? (t - s0 - 1.7) : 1.2, pp = 0.16 + 0.095 * Math.sin(ph * 0.9 - Math.PI / 2), tv = hurDome(pp);
      dot(c, X(pp), Y(tv), 5.5, C.warm, C.surface);
      label(c, C, 'p = ' + pp.toFixed(2) + (Math.abs(pp - 0.16) < 0.012 ? ', optimal' : ''), X(0.16), Y(1) - 10, { align: 'center', size: 11, weight: '600', color: C.ink });
    }
    var na = stSpan(t, s0 + 1.8, s0 + 2.4);
    if (na > 0) {
      c.globalAlpha = a * na;
      stParaRich(c, C, 'p comes from charge balance: in La₂₋ₓSrₓCuO₄ each Sr²⁺ for La³⁺ adds one hole, so p = x.', D.x, P.y + P.h + 30, D.w, 15, { size: 11, color: C.ink2 });
    }
    c.globalAlpha = 1;
  };

  const drawHurImportance = function drawHurImportance(c, C, I, t, narrow, info) {
    var imp = list(info.v.importance).slice(0, narrow ? 6 : 8);
    var a = stSpan(t, 2.4, 3.0);
    if (!imp.length || a <= 0) return;
    c.globalAlpha = a;
    label(c, C, 'What it relies on most', I.x, I.y + 4, { size: 12, weight: '600', color: C.ink });
    if (!narrow) label(c, C, 'error growth when shuffled', I.x + I.w, I.y + 4, { align: 'right', size: 11, color: C.muted });
    var groupOf = hurGroupOf(info), maxG = 0, used = {};
    imp.forEach(function (f) { maxG = Math.max(maxG, +f.gain || 0); });
    var rh = Math.min(28, (I.h - 46) / imp.length), nameW = Math.min(narrow ? 140 : 180, I.w * 0.52), bx = I.x + nameW + 8, bwMax = I.w - nameW - 62;
    imp.forEach(function (f, i) {
      var b = stSpan(t, 2.7 + 0.22 * i, 3.3 + 0.22 * i);
      if (b <= 0) return;
      var y = I.y + 16 + i * rh, grp = groupOf(f.name), col = hurGroupColor(C, grp), cy2 = y + rh / 2;
      used[grp] = 1;
      c.globalAlpha = a * b;
      label(c, C, hurFit(c, C, hurFeatName(f.name), nameW, 11.5, grp === 'physics' ? '600' : '400'), I.x, cy2 + 4, { size: 11.5, weight: grp === 'physics' ? '600' : '400', color: grp === 'physics' ? C.ink : C.ink2 });
      var w = Math.max(2, bwMax * (+f.gain || 0) / (maxG || 1) * b);
      c.fillStyle = col; c.fillRect(bx, cy2 - 5, w, 10);
      label(c, C, '+' + (+f.gain).toFixed(2) + ' K', bx + w + 6, cy2 + 4, { size: 11, color: C.ink2 });
    });
    var la = stSpan(t, 4.6, 5.2);
    if (la > 0) {
      c.globalAlpha = a * la;
      var lx = I.x, ly = I.y + 16 + imp.length * rh + 14;
      [['physics', 'physics (AI)'], ['structure', 'structure'], ['elements', 'element share'], ['composition', 'composition']].forEach(function (k) {
        if (!used[k[0]]) return;
        stFont(c, C, 11);
        var w = c.measureText(k[1]).width + 26;
        if (lx + w > I.x + I.w) { lx = I.x; ly += 17; }
        c.fillStyle = hurGroupColor(C, k[0]); c.fillRect(lx, ly - 8, 10, 10);
        label(c, C, k[1], lx + 14, ly + 1, { size: 11, color: C.ink2 });
        lx += w;
      });
    }
    c.globalAlpha = 1;
  };


  /* 3 · fold by fold against the composition-only baseline, and family by family */
  const drawHurCheck = function drawHurCheck(c, C, B, t, narrow, info) {
    var sc = info.v.scores, f = list(sc.folds), r = list(sc.reference_folds), n = f.length;
    stormHeader(c, C, B, (narrow ? 'Better in ' : 'Better than composition only in ') + sc.folds_better + ' of ' + n + ' folds', narrow ? '' : 'error for compounds whose parent it never saw');
    var F = narrow ? { x: B.x, y: B.y + 28, w: B.w, h: Math.min(200, B.h * 0.47) } : { x: B.x, y: B.y + 30, w: Math.round(B.w * 0.5), h: B.h - 30 };
    var G = narrow ? { x: B.x, y: F.y + F.h + 18, w: B.w, h: B.y + B.h - (F.y + F.h + 18) } : { x: F.x + F.w + 36, y: B.y + 30, w: B.w - F.w - 36, h: B.h - 30 };
    var P = { x: F.x + 30, y: F.y + 8, w: F.w - 34, h: F.h - 8 - 46 };
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
    var gw = P.w / Math.max(1, n), bw = Math.min(24, gw * 0.3);
    for (var i = 0; i < n; i++) {
      var a = stSpan(t, 0.3 + 0.45 * i, 0.9 + 0.45 * i), gx = P.x + gw * (i + 0.5);
      var hr = (P.y + P.h - Y(r[i])) * a, hf = (P.y + P.h - Y(f[i])) * stSpan(t, 0.6 + 0.45 * i, 1.2 + 0.45 * i);
      c.fillStyle = C.axis; c.fillRect(gx - bw - 1, P.y + P.h - hr, bw, hr);
      c.fillStyle = C.accent; c.fillRect(gx + 1, P.y + P.h - hf, bw, hf);
      label(c, C, 'fold ' + (i + 1), gx, P.y + P.h + 15, { align: 'center', size: 10.5, color: C.muted });
      if (t > 1.2 + 0.45 * i && f[i] < r[i]) label(c, C, '✓', gx + 1 + bw / 2, P.y + P.h - hf - 6, { align: 'center', size: 11, weight: '600', color: C.accent });
    }
    var ky = P.y + P.h + 36, t1 = 'composition only ' + hurK(sc.reference_mae) + ' K', t2 = hurTitle(info) + ' ' + hurK(sc.tc_mae) + ' K';
    stFont(c, C, 11);
    var w1 = c.measureText(t1).width, w2 = c.measureText(t2).width, two = 14 + w1 + 18 + 14 + w2 > F.w;
    c.fillStyle = C.axis; c.fillRect(F.x, ky - 8, 10, 10);
    label(c, C, t1, F.x + 14, ky + 1, { size: 11, color: C.ink2 });
    var kx = two ? F.x : F.x + 14 + w1 + 18, ky2 = two ? ky + 16 : ky;
    c.fillStyle = C.accent; c.fillRect(kx, ky2 - 8, 10, 10);
    label(c, C, t2, kx + 14, ky2 + 1, { size: 11, weight: '600', color: C.accent });
    // by family
    var fam = sc.by_family || {}, keys = HUR_FAMS.filter(function (k) { return fam[k]; });
    var ga = stSpan(t, 3.0, 3.6);
    if (!keys.length || ga <= 0) return;
    c.globalAlpha = ga;
    label(c, C, 'By family', G.x, G.y + 4, { size: 12, weight: '600', color: C.ink });
    var mx = 0;
    keys.forEach(function (k) { mx = Math.max(mx, fam[k].mae || 0, fam[k].mae_ref || 0); });
    var rh = Math.min(narrow ? 44 : 60, (G.h - 20) / keys.length), nameW = narrow ? 0 : Math.min(176, G.w * 0.42), bx = G.x + nameW, bwMax = G.w - nameW - 58;
    keys.forEach(function (k, j) {
      var b = stSpan(t, 3.3 + 0.35 * j, 4.0 + 0.35 * j);
      if (b <= 0) return;
      var y = G.y + 18 + j * rh, e = fam[k];
      c.globalAlpha = ga * b;
      if (narrow) label(c, C, famLabel(k) + ' · ' + fmtInt(e.n), G.x, y + 10, { size: 11.5, weight: '600', color: C.ink });
      else {
        label(c, C, hurFit(c, C, famLabel(k), nameW - 8, 12, '600'), G.x, y + 14, { size: 12, weight: '600', color: C.ink });
        label(c, C, fmtInt(e.n) + ' compounds', G.x, y + 29, { size: 10.5, color: C.muted });
      }
      var by = narrow ? y + 16 : y + 6;
      var w1 = Math.max(2, bwMax * (e.mae || 0) / (mx || 1) * b), w2 = Math.max(2, bwMax * (e.mae_ref || 0) / (mx || 1) * b);
      c.fillStyle = C.accent; c.fillRect(bx, by, w1, 9);
      label(c, C, hurK(e.mae) + ' K', bx + w1 + 6, by + 8, { size: 11, weight: '600', color: C.accent });
      c.fillStyle = C.axis; c.fillRect(bx, by + 12, w2, 9);
      label(c, C, hurK(e.mae_ref) + ' K', bx + w2 + 6, by + 20, { size: 11, color: C.ink2 });
    });
    c.globalAlpha = 1;
  };


  /* 4 · leave one family out */
  const drawHurFamily = function drawHurFamily(c, C, B, t, narrow, info) {
    var lo = list(info.v.lofo);
    stormHeader(c, C, B, 'Trained without a whole family', narrow ? '' : 'error for the family left out (K)');
    if (!lo.length) return;
    var Rw = narrow ? 0 : Math.min(230, Math.round(B.w * 0.3));
    var L = narrow ? { x: B.x, y: B.y + 30, w: B.w, h: Math.min(268, B.h * 0.62) } : { x: B.x, y: B.y + 30, w: B.w - Rw - 36, h: B.h - 30 - 30 };
    var mx = 0;
    lo.forEach(function (r) { mx = Math.max(mx, r.mae || 0, r.mae_median || 0, r.mae_cv || 0); });
    var rh = Math.min(narrow ? 58 : 70, L.h / lo.length), nameW = narrow ? 0 : Math.min(176, L.w * 0.33), bx = L.x + nameW, bwMax = L.w - nameW - 60;
    var kinds = [['mae_cv', 'with the family in training', C.accent], ['mae', 'family left out', C.warm], ['mae_median', 'guessing the median of the rest', C.axis]];
    lo.forEach(function (r, i) {
      var a = stSpan(t, 0.3 + 0.5 * i, 0.9 + 0.5 * i);
      if (a <= 0) return;
      var y = L.y + i * rh, col = hurColor(C, r.family);
      c.globalAlpha = a;
      dot(c, L.x + 5, y + 9, 4.5, col);
      label(c, C, narrow ? famLabel(r.family) : hurFit(c, C, famLabel(r.family), nameW - 22, 12, '600'), L.x + 15, y + 13, { size: 12, weight: '600', color: C.ink });
      var by = narrow ? y + 20 : y + 4;
      if (!narrow) label(c, C, fmtInt(r.n) + ' compounds', L.x + 15, y + 28, { size: 10.5, color: C.muted });
      kinds.forEach(function (kd, j) {
        var g = stSpan(t, 0.6 + 0.5 * i + 0.15 * j, 1.3 + 0.5 * i + 0.15 * j), val = r[kd[0]];
        if (typeof val !== 'number') return;
        var w = Math.max(2, bwMax * val / (mx || 1) * g);
        c.fillStyle = kd[2]; c.fillRect(bx, by + j * 12, w, 9);
        if (g > 0.8) label(c, C, hurK(val) + ' K', bx + w + 6, by + j * 12 + 8, { size: 10.5, weight: j === 1 ? '600' : '400', color: j === 1 ? C.warm : C.ink2 });
      });
    });
    c.globalAlpha = 1;
    var la = stSpan(t, 2.6, 3.2), lx = L.x, ly = L.y + lo.length * rh + 12;
    c.globalAlpha = la;
    kinds.forEach(function (kd) {
      stFont(c, C, 11);
      var w = c.measureText(kd[1]).width + 28;
      if (lx + w > L.x + L.w) { lx = L.x; ly += 17; }
      if (la > 0) { c.fillStyle = kd[2]; c.fillRect(lx, ly - 8, 10, 10); label(c, C, kd[1], lx + 14, ly + 1, { size: 11, color: C.ink2 }); }
      lx += w;
    });
    c.globalAlpha = 1;
    // the highest family: what it is, and what a model trained without it predicts
    var hi = lo.slice().sort(function (p, q) { return (q.max_tc || 0) - (p.max_tc || 0); })[0];
    var ca = stSpan(t, 3.6, 4.2);
    if (!hi || ca <= 0) return;
    c.globalAlpha = ca;
    var R = narrow ? { x: B.x, y: ly + 18, w: B.w, h: B.y + B.h - (ly + 18) } : { x: B.x + B.w - Rw, y: B.y + 30, w: Rw, h: B.h - 30 };
    if (R.h < 70) { c.globalAlpha = 1; return; }
    stParaRich(c, C, 'Trained without ' + hurFamText(hi.family), R.x, R.y + 6, R.w, 16, { size: 12, weight: '600', color: C.ink });
    var P = narrow ? { x: R.x + 8, y: R.y + 20, w: R.w - 16, h: R.h - 24 } : { x: R.x + 10, y: R.y + 46, w: R.w - 20, h: R.h - 78 };
    if (narrow) {
      // horizontal: measured range against the highest prediction
      var X = function (v) { return P.x + 92 + v / (hi.max_tc || 1) * (P.w - 150); };
      var g1 = stSpan(t, 3.9, 4.9), g2 = stSpan(t, 4.6, 5.4), y1 = P.y + 12, y2 = P.y + 34;
      label(c, C, 'measured', P.x, y1 + 4, { size: 11, color: C.ink2 });
      c.fillStyle = hurColor(C, hi.family); c.fillRect(X(0), y1 - 5, (X(hi.max_tc) - X(0)) * g1, 10);
      if (g1 > 0.9) label(c, C, 'up to ' + Math.round(hi.max_tc) + ' K', X(hi.max_tc) + 6, y1 + 4, { size: 11, weight: '600', color: C.ink });
      label(c, C, 'predicted', P.x, y2 + 4, { size: 11, color: C.ink2 });
      c.fillStyle = C.warm; c.fillRect(X(0), y2 - 5, Math.max(2, (X(hi.max_pred) - X(0)) * g2), 10);
      if (g2 > 0.9) label(c, C, 'at most ' + hurK(hi.max_pred) + ' K', X(hi.max_pred) + 6, y2 + 4, { size: 11, weight: '600', color: C.warm });
    } else {
      var Yv = function (v) { return P.y + P.h - v / (hi.max_tc || 1) * P.h; };
      var cw = P.w / 2, bw2 = Math.min(40, cw * 0.45), h1 = (P.y + P.h - Yv(hi.max_tc)) * stSpan(t, 3.9, 5.0), h2 = (P.y + P.h - Yv(hi.max_pred)) * stSpan(t, 4.8, 5.6);
      c.strokeStyle = C.axis; c.lineWidth = 1; c.beginPath(); c.moveTo(P.x, Math.round(P.y + P.h) + 0.5); c.lineTo(P.x + P.w, Math.round(P.y + P.h) + 0.5); c.stroke();
      c.fillStyle = hurColor(C, hi.family); c.fillRect(P.x + cw * 0.5 - bw2 / 2, P.y + P.h - h1, bw2, h1);
      c.fillStyle = C.warm; c.fillRect(P.x + cw * 1.5 - bw2 / 2, P.y + P.h - h2, bw2, Math.max(2, h2));
      if (t > 5) label(c, C, Math.round(hi.max_tc) + ' K', P.x + cw * 0.5, P.y + P.h - h1 - 6, { align: 'center', size: 12, weight: '600', color: C.ink });
      if (t > 5.6) label(c, C, hurK(hi.max_pred) + ' K', P.x + cw * 1.5, P.y + P.h - h2 - 6, { align: 'center', size: 12, weight: '600', color: C.warm });
      label(c, C, 'highest measured', P.x + cw * 0.5, P.y + P.h + 15, { align: 'center', size: 10.5, color: C.ink2 });
      label(c, C, 'highest predicted', P.x + cw * 1.5, P.y + P.h + 15, { align: 'center', size: 10.5, color: C.ink2 });
    }
    c.globalAlpha = 1;
  };


  /* 5 · materials it never trained on, mostly found after its data were collected */
  const drawHurLater = function drawHurLater(c, C, B, t, narrow, info) {
    var an = info.v.anchors || {}, rows = list(an.table);
    stormHeader(c, C, B, 'Materials it never trained on', narrow ? '' : 'measured and predicted Tc, square-root scale');
    if (!rows.length) return;
    var nameW = narrow ? Math.min(112, B.w * 0.36) : Math.min(240, B.w * 0.3), gradeW = narrow ? 56 : 104;
    var P = { x: B.x + nameW + 10, y: B.y + 34, w: B.w - nameW - 10 - gradeW - 12, h: B.h - 34 - (narrow ? 66 : 48) };
    var vmax = 0;
    rows.forEach(function (r) { vmax = Math.max(vmax, typeof r.tc_exp === 'number' ? r.tc_exp : 0, typeof r.pred === 'number' ? r.pred : 0); });
    vmax = Math.max(20, Math.ceil(vmax * 1.05 / 20) * 20);
    function X(v) { return P.x + Math.sqrt(Math.max(0, Math.min(v, vmax)) / vmax) * P.w; }
    var rh = Math.min(30, P.h / rows.length), axisY = P.y + rows.length * rh + 2;
    c.lineWidth = 1;
    [0, 1, 5, 20, 50, 100, 150, 200].filter(function (v) { return v <= vmax; }).forEach(function (v) {
      var gx = Math.round(X(v)) + 0.5;
      c.strokeStyle = v ? C.grid : C.axis; c.beginPath(); c.moveTo(gx, P.y - 4); c.lineTo(gx, axisY); c.stroke();
      if (!narrow || v === 0 || v === 5 || v === 50 || v === 150) label(c, C, String(v), gx, axisY + 13, { align: 'center', size: 10.5, color: C.muted });
    });
    label(c, C, 'K', P.x + P.w + 4, axisY + 13, { size: 10.5, color: C.muted });
    rows.forEach(function (r, i) {
      var a = stSpan(t, 0.3 + 0.35 * i, 0.8 + 0.35 * i);
      if (a <= 0) return;
      var cy2 = P.y + i * rh + rh / 2, scored = r.use === 'score', col = hurColor(C, r.family);
      c.globalAlpha = a * (scored ? 1 : 0.85);
      var nm = hurFit(c, C, hurShortName(r.name), nameW - 4, narrow ? 11 : 12, scored ? '600' : '400');
      label(c, C, nm, B.x, cy2 + 4, { size: narrow ? 11 : 12, weight: scored ? '600' : '400', color: scored ? C.ink : C.ink2 });
      var hasM = typeof r.tc_exp === 'number', hasP = typeof r.pred === 'number', g = stSpan(t, 0.6 + 0.35 * i, 1.3 + 0.35 * i);
      if (hasM && hasP && g > 0) {
        var xm = X(r.tc_exp), xp = xm + (X(r.pred) - xm) * g;
        c.strokeStyle = stAlpha(C.ink2, 0.5); c.lineWidth = 2; c.beginPath(); c.moveTo(xm, cy2); c.lineTo(xp, cy2); c.stroke();
        dot(c, xp, cy2, 4.5, C.surface, C.accent);
      }
      if (hasM) dot(c, X(r.tc_exp), cy2, 4.5, HUR_FAMS.indexOf(r.family) >= 0 ? col : C.ink2);
      else {
        if (hasP && g > 0) dot(c, X(r.pred), cy2, 4.5, C.surface, C.accent);
        label(c, C, r.status || 'no Tc', P.x + (hasP && X(r.pred) < P.x + 70 ? 16 + (X(r.pred) - P.x) : 4), cy2 + 4, { size: 11, color: C.warm, weight: '600' });
      }
      var use = scored ? 'scored' : r.use === 'exclude' ? 'left out' : 'shown';
      stTag(c, C, narrow ? use : use + ' · ' + (r.status === 'single report' ? 'single' : r.status), B.x + B.w, cy2, { align: 'right', size: 10.5, bg: scored ? C.track : C.surface, ring: scored ? null : C.grid, color: scored ? C.ink : C.ink2 });
    });
    c.globalAlpha = 1;
    var la = stSpan(t, 0.6 + 0.35 * rows.length, 1.2 + 0.35 * rows.length);
    if (la > 0) {
      c.globalAlpha = la;
      var ly = axisY + 34;
      dot(c, B.x + 5, ly - 4, 4.5, C.ink2);
      label(c, C, 'measured', B.x + 14, ly, { size: 11, color: C.ink2 });
      dot(c, B.x + 86, ly - 4, 4.5, C.surface, C.accent);
      label(c, C, hurTitle(info), B.x + 95, ly, { size: 11, color: C.ink2 });
      if (typeof an.mae === 'number') {
        var msg = an.n_scored + ' scored · average error ' + hurK(an.mae) + ' K' + (an.scored_as_check ? '' : (narrow ? '' : ' · too few for a check yet'));
        if (narrow) label(c, C, msg, B.x, ly + 18, { size: 11, weight: '600', color: C.ink });
        else label(c, C, msg, B.x + B.w, ly, { align: 'right', size: 11, weight: '600', color: C.ink });
      }
      c.globalAlpha = 1;
    }
  };
