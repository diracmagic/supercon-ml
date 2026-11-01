'use strict';
// radar-demo: shared lexical function definitions; no startup side effects.


  const radInfo = function radInfo() {
    var rd = state.data && state.data.radar;
    var vs = rd ? list(rd.versions).filter(function (v) { return v && v.scores; }) : [];
    if (!vs.length) return null;
    var v = vs.filter(function (x) { return x.version === rd.current; })[0] || vs[vs.length - 1];
    return { rd: rd, v: v, name: rd.name || 'Radar', data: rd.data || {}, versions: vs };
  };

  const radTitle = function radTitle(info) { return info.name + ' ' + info.v.version; };

  // one decimal from 90% up, so 99.5% and 99.0% read as different numbers; never rounds up to 100% or down to 0%
  const radPct = function radPct(x) {
    if (typeof x !== 'number' || !isFinite(x)) return '—';
    if (x >= 0.9 && x < 1) { var s = (100 * x).toFixed(1); return (s === '100.0' ? '>99.9' : s) + '%'; }
    if (x > 0 && x < 0.005) return '<1%';
    return String(Math.round(100 * x)) + '%';
  };

  const radColor = function radColor(C, k) { return RAD_UNCONV.indexOf(k) >= 0 ? hurColor(C, k) : k === 'Chevrel' ? mix(C.warm, C.ink2, 0.3) : k === 'Carbon' ? mix(C.warm, C.surface2, 0.4) : C.warm; };

  const radAnd = function radAnd(a) { return a.length > 1 ? a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1] : a.join(''); };


  const radCaption = function radCaption(si) {
    var info = radInfo();
    if (!info) return 'Radar decides whether a material goes to Storm or to Hurricane. Its data and scores load with the live progress data.';
    var v = info.v, sc = v.scores || {}, dd = info.data, name = radTitle(info), nf = list(sc.folds).length, ok = v.status === 'adopted';
    switch (si) {
      case 0:
        return 'Radar decides which of our two models to ask. It learns from ' + fmtInt(dd.n) + ' SuperCon entries in 3DSC, each labelled with its chemical class: ' +
          fmtInt(dd.n_unconventional) + ' in Hurricane’s four unconventional families (cuprates, iron- and nickel-based, heavy-fermion and other oxides) and ' +
          fmtInt(dd.n_conventional) + ' conventional ones for Storm. It gives the probability that a material belongs to an unconventional family and sends it to Hurricane when that probability is at least one half.';
      case 1:
        var sr = v.search || {};
        return 'An AI agent (Claude) proposed ' + (sr.candidates || 'several') + ' designs in round ' + v.round + ': which inputs to use (Hurricane’s physics features, the crystal structure, element shares), balanced classes, a seed average and calibrated probabilities. ' +
          'Each was scored with five-fold cross-validation that holds out whole parent compounds, using the log loss, which punishes confident mistakes. ' +
          (ok ? 'The best beat the composition-only baseline in ' + sc.folds_better + ' of ' + nf + ' folds and became ' + name + '.'
            : 'A design is released only if it beats the baseline on average and in at least 4 of 5 folds; none did, so ' + name + ' stays experimental.');
      case 2:
        var kn = list(v.known), kag = kn.filter(function (k) { return k.family === 'kagome'; });
        var pref = function (k) { var m = [/Hg-1223\)$/, /UTe2/, /CeRh2As2/, /thin film/].map(function (re) { return re.test(k.name); }).indexOf(true); return m < 0 ? 9 : m; };
        var nm = function (k) { return /thin film/.test(k.name) ? 'nickelate films' : hurShortName(k.name); };
        var toH = kn.filter(function (k) { return k.model === 'Hurricane' && pref(k) < 9; }).sort(function (a, b) { return pref(a) - pref(b); });
        var conv = kn.filter(function (k) { return k.list === 'experiments' && k.family !== 'kagome'; });
        var toS = conv.filter(function (k) { return k.model === 'Storm'; }), oddS = conv.filter(function (k) { return k.model !== 'Storm'; });
        // unconventional anchors that Radar sends to Storm (the kagome metals are discussed on their own)
        var oddH = kn.filter(function (k) { return k.list === 'anchors' && k.family !== 'kagome' && k.family !== 'conventional' && k.family !== 'hydride' && k.model === 'Storm'; });
        var ends = ['Al', 'MgB2', 'Nb3Sn'].every(function (n) { return toS.some(function (k) { return k.name === n; }); });
        var hyd = toS.some(function (k) { return k.family === 'hydride'; });
        var kagM = kag.length && kag.every(function (k) { return k.model === kag[0].model; }) ? kag[0].model : '';
        return 'Graded materials, each with its probability of an unconventional family from a Radar that never saw it' +
          (kn.some(function (k) { return k.in_training; }) ? ' (those also in its training data are scored out of fold, with their parent compound held out)' : '') + '. ' +
          (toH.length ? 'It sends ' + radAnd(toH.slice(0, 4).map(nm)) + ' to Hurricane' : '') +
          (toS.length ? (toH.length ? ', and ' : 'It sends ') + toS.length + ' graded conventional superconductors' + (hyd ? ' and hydrides' : '') + (ends ? ', from aluminium to MgB₂ and Nb₃Sn,' : '') + ' to Storm' : '') + '. ' +
          (oddS.length ? radAnd(oddS.map(nm)) + (oddS.length > 1 ? ' go' : ' goes') + ' to Hurricane instead. ' : '') +
          (oddH.length ? radAnd(oddH.map(nm)) + (oddH.length > 1 ? ' go' : ' goes') + ' to Storm instead. ' : '') +
          (kagM ? 'The kagome metals ' + radAnd(kag.map(function (k) { return hurShortName(k.name); })) + ' go to ' + kagM + (kagM === 'Storm' && toS.length ? ' too' : '') +
            '; whether their pairing is unconventional is still debated, which makes them a test case for comparing what the two models predict.' :
            kag.length ? 'The kagome metals split: ' + radAnd(kag.map(function (k) { return hurShortName(k.name) + ' to ' + k.model; })) + '; whether their pairing is unconventional is still debated.' : '');
      case 3:
        return 'For parent compounds it never saw, ' + name + ' picks the right model ' + radPct(sc.balanced_accuracy) + ' of the time (balanced accuracy), against ' +
          radPct(sc.reference_balanced_accuracy) + ' for gradient boosting on the composition alone. It sends ' + radPct(sc.to_hurricane) + ' of unconventional entries to Hurricane and ' +
          radPct(sc.to_storm) + ' of conventional ones to Storm' + (typeof sc.ece === 'number' ? ', and its probabilities are well calibrated: when it says 90%, it is right about 90% of the time (calibration error ' + (100 * sc.ece).toFixed(1) + ' points)' : '') + '.';
      default:
        var lo = list(v.lofo), by = {};
        lo.forEach(function (r) { by[r.family] = r; });
        var cu = by['cuprate'], hf = by['heavy-fermion'], fe = by['iron-based'];
        return 'The real test is a whole family Radar has never seen. ' +
          (cu ? 'Trained without any cuprate, it still sends ' + radPct(cu.right) + ' of cuprates to Hurricane: copper oxides look unconventional even to a model that never met one. ' : '') +
          (hf && hf.right < 0.5 ? 'Heavy-fermion compounds are the opposite: without them in training, only ' + radPct(hf.right) + ' go to Hurricane, because f-electron intermetallics look like ordinary intermetallics' + (fe && fe.right < 0.5 ? ', and iron-based compounds (' + radPct(fe.right) + ') fall in between' : '') + '. Both families surprised physicists when they were found, in 1979 and 2008: little in their chemistry announced unconventional pairing. ' : '') +
          'So Radar can route a new material of a known kind, but a new family needs physics, not only a classifier.';
    }
  };


  const hitRadNode = function hitRadNode(p) {
    var nodes = demo.radNodes || [];
    for (var i = 0; i < nodes.length; i++) {
      var b = nodes[i];
      if (p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h) return i;
    }
    return -1;
  };


  const drawRadar = function drawRadar(c, C) {
    var W = demo.W, H = demo.H, narrow = W < 560;
    var si = demo.radStage, t = motionOK() ? demo.radT : RAD_DUR;
    var n = RAD_STAGES.length, gap = narrow ? 6 : 18, nodeW = (W - 32 - gap * (n - 1)) / n, nodeH = narrow ? 34 : 40, ny = 12;
    demo.radNodes = [];
    for (var i = 0; i < n; i++) {
      var x = 16 + i * (nodeW + gap), on = i === si;
      demo.radNodes.push({ x: x, y: ny, w: nodeW, h: nodeH });
      stRound(c, x, ny, nodeW, nodeH, 9);
      c.fillStyle = on ? C.accent : C.surface2; c.fill();
      if (!on) { c.lineWidth = 1; c.strokeStyle = C.grid; c.stroke(); }
      label(c, C, narrow ? RAD_STAGES[i].short : RAD_STAGES[i].node, x + nodeW / 2, ny + nodeH / 2 + 0.5,
        { align: 'center', base: 'middle', size: narrow ? 10.5 : 12, weight: '600', color: on ? '#ffffff' : C.ink2 });
      if (i < n - 1 && !narrow) stArrow(c, x + nodeW + 3, ny + nodeH / 2, x + nodeW + gap - 3, ny + nodeH / 2, C.axis, 5);
    }
    if (motionOK()) {
      var px = demo.radNodes[si];
      c.fillStyle = stAlpha(C.accent, 0.25);
      c.fillRect(px.x + 6, ny + nodeH - 3, (px.w - 12) * Math.min(1, t / RAD_DUR), 2);
    }
    var B = { x: 16, y: ny + nodeH + 16, w: W - 32, h: H - ny - nodeH - 28 };
    var info = radInfo();
    if (!info) {
      label(c, C, 'Radar’s results load with the live progress data.', W / 2, B.y + B.h / 2, { align: 'center', base: 'middle', size: 13, color: C.muted });
      return;
    }
    [drawRadData, drawRadDesign, drawRadRoute, drawRadCheck, drawRadFamily][si](c, C, B, t, narrow, info);
    c.globalAlpha = 1;
    c.setLineDash([]);
  };


  /* 0 · the labelled classes, and which model each one goes to */
  const drawRadData = function drawRadData(c, C, B, t, narrow, info) {
    var dd = info.data, cl = dd.classes || {};
    stormHeader(c, C, B, fmtInt(dd.n) + ' labelled SuperCon entries', narrow ? '' : '3DSC: every class goes to one model');
    var cols = [['Hurricane', RAD_UNCONV, C.accent, dd.n_unconventional], ['Storm', RAD_CONV, C.warm, dd.n_conventional]];
    var mx = 1;
    RAD_UNCONV.concat(RAD_CONV).forEach(function (k) { mx = Math.max(mx, cl[k] || 0); });
    var colW = narrow ? B.w : (B.w - 40) / 2;
    cols.forEach(function (col, j) {
      var X = narrow ? B.x : B.x + j * (colW + 40), Y = narrow ? B.y + 30 + j * (B.h * 0.5) : B.y + 34;
      var a = stSpan(t, 0.2 + 1.6 * j, 0.8 + 1.6 * j);
      if (a <= 0) return;
      c.globalAlpha = a;
      stRound(c, X, Y, narrow ? 96 : 112, 28, 8); c.fillStyle = col[2]; c.fill();
      label(c, C, 'to ' + col[0], X + (narrow ? 48 : 56), Y + 14.5, { align: 'center', base: 'middle', size: 12, weight: '600', color: '#ffffff' });
      label(c, C, fmtInt(col[3]) + (j ? ' conventional' : ' unconventional'), X + (narrow ? 106 : 124), Y + 18, { size: 12, color: C.ink2 });
      var rh = narrow ? 34 : 44;
      col[1].forEach(function (k, i) {
        var g = stSpan(t, 0.5 + 1.6 * j + 0.3 * i, 1.4 + 1.6 * j + 0.3 * i);
        if (g <= 0 || !cl[k]) return;
        var y = Y + 40 + i * rh, nmW = narrow ? 112 : 150, bw = Math.max(2, (colW - nmW - 56) * cl[k] / mx * g);
        c.globalAlpha = a * Math.min(1, g * 1.5);
        dot(c, X + 5, y + 7, 4.5, radColor(C, k));
        label(c, C, hurFit(c, C, narrow ? RAD_SHORT[k] : RAD_LABEL[k], nmW - 16, 12, '600'), X + 15, y + 11, { size: 12, weight: '600', color: C.ink });
        c.fillStyle = radColor(C, k); c.fillRect(X + nmW, y + 2, bw, 10);
        label(c, C, fmtInt(Math.round(cl[k] * g)), X + nmW + bw + 6, y + 11, { size: 11, color: C.ink2 });
      });
    });
    c.globalAlpha = 1;
  };


  /* 1 · the design loop and the leaderboard of the round (log loss) */
  const drawRadDesign = function drawRadDesign(c, C, B, t, narrow, info) {
    var v = info.v, sr = v.search || {}, rows = list(sr.leaderboard);
    var winner = rows.filter(function (r) { return stormRowName(r) === v.summary || r.name === v.summary; })[0] || rows[0];
    stormHeader(c, C, B, 'Search round ' + v.round + ': ' + rows.length + ' designs', narrow ? '' : 'log loss in grouped CV (lower is better)');
    if (!rows.length) return;
    var T = { x: B.x, y: B.y + 28, w: B.w, h: B.h - 28 };
    var rh = Math.min(30, (T.h - 50) / rows.length), lo = Infinity, hi = -Infinity;
    rows.forEach(function (r) { lo = Math.min(lo, r.log_loss); hi = Math.max(hi, r.log_loss); });
    var span = Math.max(0.005, hi - lo), step = niceStep(span * 1.2, 4);
    var a0v = Math.max(0, Math.floor((lo - span * 0.1) / step) * step), a1v = Math.ceil((hi + span * 0.1) / step) * step;
    // on a phone the names give way to the plot: the tag and the first words are enough there
    var nameW = narrow ? Math.min(150, T.w * 0.44) : Math.min(380, T.w * 0.5), bx = T.x + nameW + 10, bw = T.w - nameW - (narrow ? 50 : 60);
    var refId = sr.reference_id || 'R0', base = rows.filter(function (r) { return r.id === refId; })[0];
    function BX(x) { return bx + (x - a0v) / (a1v - a0v) * bw; }
    var axisY = T.y + rows.length * rh + 4;
    c.lineWidth = 1;
    // label every tick only when the labels have room (about 36 px each)
    var every = Math.max(1, Math.ceil(36 / Math.max(1, bw / ((a1v - a0v) / step)))), ti = 0;
    for (var tv = a0v; tv <= a1v + 1e-9; tv += step, ti++) {
      var gx = Math.round(BX(tv)) + 0.5;
      c.strokeStyle = C.grid; c.beginPath(); c.moveTo(gx, T.y); c.lineTo(gx, axisY); c.stroke();
      if (ti % every === 0) label(c, C, fmtTick(tv), gx, axisY + 13, { align: 'center', size: 10.5, color: C.muted });
    }
    rows.forEach(function (r, i) {
      var a = stSpan(t, 0.4 + 0.32 * i, 0.8 + 0.32 * i);
      if (a <= 0) return;
      var y = T.y + i * rh, isW = r === winner && t > 4.2, isB = r.id === refId, cy2 = y + rh / 2;
      c.globalAlpha = a;
      if (isW) { stRound(c, T.x - 6, y + 1, T.w + 6, rh - 2, 7); c.fillStyle = stAlpha(C.accent, 0.1); c.fill(); }
      stTag(c, C, r.id, T.x + 13, cy2, { size: 10.5, bg: isW ? C.accent : C.surface, ring: C.grid, color: isW ? '#ffffff' : C.ink2 });
      var full = (isB ? 'Composition only (baseline)' : r.name.replace(/^Composition \+ /, '+ ')) + (r.settings && r.settings !== 'default' ? ', ' + r.settings : '');
      var size = narrow ? 11 : 12;
      label(c, C, hurFit(c, C, full, nameW - 32, size, isW ? '600' : '400'), T.x + 30, cy2 + 4, { size: size, color: isB ? C.ink2 : C.ink, weight: isW ? '600' : '400' });
      var x = BX(r.log_loss), col = isW ? C.accent : isB ? C.ink2 : mix(C.accent, C.surface2, 0.35);
      dot(c, x, cy2, isW ? 5.5 : 4.5, col);
      label(c, C, r.log_loss.toFixed(3), x + 9, cy2 + 4, { size: 11, weight: isW ? '600' : '400', color: isW ? C.accent : C.ink2 });
      c.globalAlpha = 1;
    });
    if (base && t > 0.6) {
      var xb = Math.round(BX(base.log_loss)) + 0.5;
      c.setLineDash([3, 3]); c.strokeStyle = C.ink2; c.lineWidth = 1;
      c.beginPath(); c.moveTo(xb, T.y); c.lineTo(xb, axisY); c.stroke(); c.setLineDash([]);
    }
    if (t > 4.6) {
      c.globalAlpha = stSpan(t, 4.6, 5.2);
      var ok = v.status === 'adopted';
      stTag(c, C, ok ? 'Released as ' + radTitle(info) : radTitle(info) + ' stays experimental', T.x + T.w, axisY + 32, { align: 'right', size: 12, bg: ok ? C.accent : C.surface, ring: ok ? null : C.grid, color: ok ? '#ffffff' : C.ink });
      c.globalAlpha = 1;
    }
  };


  /* 2 · materials it never trained on: the probability meter and where each one goes */
  const drawRadRoute = function drawRadRoute(c, C, B, t, narrow, info) {
    var kn = list(info.v.known);
    stormHeader(c, C, B, 'Where new materials go', narrow ? '' : 'probability of an unconventional family');
    if (!kn.length) return;
    var M = { x: B.x + (narrow ? 8 : 60), y: B.y + 54, w: B.w - (narrow ? 16 : 120) };
    var a0 = stSpan(t, 0.2, 0.8);
    c.globalAlpha = a0;
    var grad = c.createLinearGradient(M.x, 0, M.x + M.w, 0);
    grad.addColorStop(0, stAlpha(C.warm, 0.85)); grad.addColorStop(0.5, stAlpha(C.surface2, 1)); grad.addColorStop(1, stAlpha(C.accent, 0.85));
    stRound(c, M.x, M.y - 5, M.w, 10, 5); c.fillStyle = grad; c.fill();
    var mid = Math.round(M.x + M.w / 2) + 0.5;
    c.setLineDash([3, 3]); c.strokeStyle = C.ink2; c.lineWidth = 1; c.beginPath(); c.moveTo(mid, M.y - 16); c.lineTo(mid, M.y + 16); c.stroke(); c.setLineDash([]);
    label(c, C, '0', M.x, M.y + 22, { align: 'center', size: 10.5, color: C.muted });
    label(c, C, '½', mid, M.y + 28, { align: 'center', size: 11, color: C.ink2 });
    label(c, C, '1', M.x + M.w, M.y + 22, { align: 'center', size: 10.5, color: C.muted });
    label(c, C, '← Storm', M.x, M.y - 14, { size: 12, weight: '600', color: C.warm });
    label(c, C, 'Hurricane →', M.x + M.w, M.y - 14, { align: 'right', size: 12, weight: '600', color: C.accent });
    // a few named materials drop onto the meter; the rest are counted
    // each group has its own quota, so the conventional side is not crowded out on a phone
    var pick = [], seen = {};
    function take(f, n) { var got = 0; kn.filter(f).forEach(function (k) { if (got < n && !seen[k.name]) { seen[k.name] = 1; pick.push(k); got++; } }); }
    take(function (k) { return k.list === 'anchors' && k.model === 'Hurricane' && /Hg-1223\)$|UTe2|CeRh2As2|thin film/.test(k.name); }, 4);
    take(function (k) { return k.family === 'kagome'; }, 2);
    take(function (k) { return /^(MgB2|Nb3Sn|H3S|NbSe2|Pb)$/.test(k.name); }, 3);
    pick.sort(function (p, q) { return p.p_unconventional - q.p_unconventional; });
    var left = pick.filter(function (k) { return k.model === 'Storm'; }), right = pick.filter(function (k) { return k.model !== 'Storm'; });
    var LY = M.y + 50, rh = narrow ? 22 : 24, room = M.w / 2 - 14;
    [[left, M.x, 'left'], [right, M.x + M.w, 'right']].forEach(function (grp) {
      var y = LY;
      grp[0].forEach(function (k, i) {
        var o = grp[2] === 'left' ? i : i + left.length, g = stSpan(t, 1.0 + 0.35 * o, 1.6 + 0.35 * o);
        var note = k.family === 'kagome' ? 'kagome metal' : /thin film/.test(k.name) ? 'thin film' : '';
        var nm = /thin film/.test(k.name) ? hurSub(k.name.split(',')[0]) : hurShortName(k.name), pv = k.p_unconventional.toFixed(2);
        // a long name keeps its probability on the second line instead of losing it to an ellipsis
        var full = nm + ' · ' + pv, fits = hurFit(c, C, full, room, 12, '600') === full;
        var sub = fits ? note : pv + (note ? ' · ' + note : '');
        if (g > 0) {
          c.globalAlpha = g;
          var px2 = M.x + M.w * Math.max(0, Math.min(1, k.p_unconventional)), col = k.model === 'Storm' ? C.warm : C.accent;
          dot(c, px2, M.y, 5, col, C.surface);
          label(c, C, fits ? full : hurFit(c, C, nm, room, 12, '600'), grp[1], y, { align: grp[2], size: 12, weight: '600', color: C.ink });
          if (sub && g > 0.9) label(c, C, sub, grp[1], y + 13, { align: grp[2], size: 10.5, color: fits ? C.muted : C.ink2 });
        }
        y += rh + (sub ? 12 : 0);
      });
    });
    var rest = kn.length - pick.length, ca = stSpan(t, 4.6, 5.2);
    if (ca > 0 && rest > 0) {
      c.globalAlpha = ca;
      var nS = kn.filter(function (k) { return k.model === 'Storm' && !seen[k.name]; }).length, nH = rest - nS;
      label(c, C, '+ ' + nS + ' more to Storm' + (nH ? ', ' + nH + ' more to Hurricane' : ''), B.x + B.w / 2, B.y + B.h - 6, { align: 'center', size: 11.5, color: C.ink2 });
    }
    c.globalAlpha = 1;
  };


  /* 3 · how often each class goes to the right model */
  const drawRadCheck = function drawRadCheck(c, C, B, t, narrow, info) {
    var sc = info.v.scores || {}, bc = sc.by_class || {};
    stormHeader(c, C, B, 'Right model ' + radPct(sc.balanced_accuracy) + ' of the time', narrow ? '' : 'parent compounds held out; composition only: ' + radPct(sc.reference_balanced_accuracy));
    var keys = RAD_UNCONV.concat(RAD_CONV).filter(function (k) { return bc[k]; });
    var rh = Math.min(narrow ? 40 : 44, (B.h - 60) / Math.max(1, keys.length)), nameW = narrow ? 118 : 200, bx = B.x + nameW, bw = B.w - nameW - 70, y0 = B.y + 32;
    keys.forEach(function (k, i) {
      var a = stSpan(t, 0.3 + 0.4 * i, 0.9 + 0.4 * i);
      if (a <= 0) return;
      var e = bc[k], y = y0 + i * rh, col = radColor(C, k);
      c.globalAlpha = a;
      dot(c, B.x + 5, y + 8, 4.5, col);
      label(c, C, hurFit(c, C, narrow ? RAD_SHORT[k] : RAD_LABEL[k], nameW - 20, 12, '600'), B.x + 15, y + 12, { size: 12, weight: '600', color: C.ink });
      if (!narrow) label(c, C, fmtInt(e.n) + ' entries → ' + e.model, B.x + 15, y + 27, { size: 10.5, color: C.muted });
      c.fillStyle = C.track || C.surface2; c.fillRect(bx, y + 3, bw, 10);
      c.fillStyle = col; c.fillRect(bx, y + 3, bw * e.right * a, 10);
      label(c, C, radPct(e.right), bx + bw + 8, y + 12, { size: 11.5, weight: '600', color: C.ink });
    });
    c.globalAlpha = 1;
  };


  /* 4 · leave one family out: how much of a never-seen family goes to the right model */
  const drawRadFamily = function drawRadFamily(c, C, B, t, narrow, info) {
    var lo = list(info.v.lofo), bc = (info.v.scores || {}).by_class || {};
    stormHeader(c, C, B, 'Trained without a whole family', narrow ? '' : 'share sent to the right model');
    if (!lo.length) return;
    var rh = Math.min(narrow ? 48 : 54, (B.h - 70) / lo.length), nameW = narrow ? 120 : 210, bx = B.x + nameW, bw = B.w - nameW - 70, y0 = B.y + 32;
    lo.forEach(function (r, i) {
      var a = stSpan(t, 0.3 + 0.5 * i, 0.9 + 0.5 * i);
      if (a <= 0) return;
      var y = y0 + i * rh, col = radColor(C, r.family), inCv = bc[r.family] ? bc[r.family].right : null;
      c.globalAlpha = a;
      dot(c, B.x + 5, y + 8, 4.5, col);
      label(c, C, hurFit(c, C, narrow ? (RAD_SHORT[r.family] || r.label) : (r.label || RAD_LABEL[r.family]), nameW - 20, 12, '600'), B.x + 15, y + 12, { size: 12, weight: '600', color: C.ink });
      label(c, C, hurFit(c, C, (narrow ? '→ ' : 'should go to ') + r.model, nameW - 22, 10.5, '400'), B.x + 15, y + 27, { size: 10.5, color: C.muted });
      var g = stSpan(t, 0.6 + 0.5 * i, 1.4 + 0.5 * i);
      if (typeof inCv === 'number') { c.fillStyle = stAlpha(col, 0.22); c.fillRect(bx, y + 2, bw * inCv, 8); }
      c.fillStyle = col; c.fillRect(bx, y + 12, Math.max(2, bw * r.right * g), 10);
      if (g > 0.85) label(c, C, radPct(r.right), bx + Math.max(2, bw * r.right) + 6, y + 21, { size: 11.5, weight: '600', color: r.right < 0.5 ? C.warm : C.ink });
    });
    var la = stSpan(t, 3.4, 4.0);
    if (la > 0) {
      c.globalAlpha = la;
      var ly = y0 + lo.length * rh + 10;
      c.fillStyle = stAlpha(C.ink2, 0.22); c.fillRect(B.x, ly - 8, 12, 8);
      label(c, C, 'with the family in training', B.x + 18, ly, { size: 11, color: C.ink2 });
      c.fillStyle = C.ink2; c.fillRect(B.x + (narrow ? 0 : 210), ly + (narrow ? 8 : -8), 12, 10);
      label(c, C, 'family left out', B.x + (narrow ? 18 : 228), ly + (narrow ? 17 : 1), { size: 11, weight: '600', color: C.ink });
    }
    c.globalAlpha = 1;
  };
