'use strict';
// tour: shared lexical function definitions; no startup side effects.
     // Storm 1.0, the AI-designed model, same CV (K); the live value is used when loaded
  const stormMae = function stormMae() { var info = stormInfo(); return info ? info.v.scores.tc_mae : MAE_STORM; };

  const stormName = function stormName() { var info = stormInfo(); return info ? stormTitle(info) : 'Storm 1.0'; };


  const stClamp = function stClamp(v) { return v < 0 ? 0 : v > 1 ? 1 : v; };

  const stEase = function stEase(v) { v = stClamp(v); return v * v * (3 - 2 * v); };

  const stSpan = function stSpan(t, a, b) { return stEase((t - a) / (b - a)); };

  const stRound = function stRound(c, x, y, w, hh, r) {
    c.beginPath();
    if (c.roundRect) c.roundRect(x, y, w, hh, r); else c.rect(x, y, w, hh);
  };

  const stFont = function stFont(c, C, size, weight) { c.font = (weight || '400') + ' ' + size + 'px ' + C.font; };

  const stWrap = function stWrap(c, text, maxW) {
    var words = String(text).split(' '), lines = [], line = '';
    words.forEach(function (w) {
      var test = line ? line + ' ' + w : w;
      if (line && c.measureText(test).width > maxW) { lines.push(line); line = w; } else line = test;
    });
    if (line) lines.push(line);
    return lines;
  };

  const stPara = function stPara(c, C, text, x, y, maxW, lh, opts) {
    stFont(c, C, opts.size || 12, opts.weight);
    var lines = stWrap(c, text, maxW);
    lines.forEach(function (ln, i) { label(c, C, ln, x, y + i * lh, opts); });
    return lines.length;
  };

  const stRgb = function stRgb(rgb, a) { return 'rgba(' + rgb[0] + ',' + rgb[1] + ',' + rgb[2] + ',' + (a === undefined ? 1 : a) + ')'; };

  const stAlpha = function stAlpha(hex, a) { return stRgb(hexRgb(hex), a); };

  const stRng = function stRng(seed) {
    return function () {
      seed = (seed + 0x6D2B79F5) | 0;
      var q = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      q = (q + Math.imul(q ^ (q >>> 7), 61 | q)) ^ q;
      return ((q ^ (q >>> 14)) >>> 0) / 4294967296;
    };
  };

  const stTag = function stTag(c, C, text, x, y, opts) {
    opts = opts || {};
    var size = opts.size || 12;
    stFont(c, C, size, opts.weight || '600');
    var tw = opts.rich ? stSymWidth(c, C, symParts(text), size, opts.weight || '600') : c.measureText(text).width;
    var w = tw + 2 * (opts.pad || 7), hh = size + 9;
    var x0 = opts.align === 'left' ? x : opts.align === 'right' ? x - w : x - w / 2;
    stRound(c, x0, y - hh / 2, w, hh, hh / 2);
    c.fillStyle = opts.bg || C.surface; c.fill();
    if (opts.ring) { c.lineWidth = 1; c.strokeStyle = opts.ring; c.stroke(); }
    if (opts.rich) stSym(c, C, symParts(text), x0 + w / 2, y + 0.5, { align: 'center', base: 'middle', size: size, weight: opts.weight || '600', color: opts.color || C.ink });
    else label(c, C, text, x0 + w / 2, y + 0.5, { align: 'center', base: 'middle', size: size, weight: opts.weight || '600', color: opts.color || C.ink });
    return w;
  };

  // Text with subscripts: parts = [['T'], ['c', 1], [' = 20 K']]
  const stSym = function stSym(c, C, parts, x, y, opts) {
    opts = opts || {};
    var size = opts.size || 13, ws = [], w = 0;
    parts.forEach(function (p) { stFont(c, C, p[1] ? size * 0.7 : size, opts.weight); var pw = c.measureText(p[0]).width; ws.push(pw); w += pw; });
    var x0 = opts.align === 'center' ? x - w / 2 : opts.align === 'right' ? x - w : x;
    parts.forEach(function (p, i) {
      label(c, C, p[0], x0, y + (p[1] ? size * 0.24 : 0), { size: p[1] ? size * 0.7 : size, weight: opts.weight, color: opts.color || C.ink, base: opts.base });
      x0 += ws[i];
    });
    return w;
  };

  const stSymWidth = function stSymWidth(c, C, parts, size, weight) {
    var w = 0;
    parts.forEach(function (p) { stFont(c, C, p[1] ? size * 0.7 : size, weight); w += c.measureText(p[0]).width; });
    return w;
  };

  const stText = function stText(c, C, text, x, y, opts) { return stSym(c, C, symParts(text), x, y, opts || {}); };

  const stParaRich = function stParaRich(c, C, text, x, y, maxW, lh, opts) {
    var size = opts.size || 12, words = String(text).split(' '), lines = [], line = [], lw = 0;
    stFont(c, C, size, opts.weight);
    var sp = c.measureText(' ').width;
    words.forEach(function (w) {
      var ww = stSymWidth(c, C, symParts(w), size, opts.weight);
      if (line.length && lw + sp + ww > maxW) { lines.push(line); line = [w]; lw = ww; }
      else { lw += (line.length ? sp : 0) + ww; line.push(w); }
    });
    if (line.length) lines.push(line);
    lines.forEach(function (ln, i) { stSym(c, C, symParts(ln.join(' ')), x, y + i * lh, opts); });
    return lines.length;
  };

  const stArrow = function stArrow(c, x0, y0, x1, y1, color, head) {
    var a = Math.atan2(y1 - y0, x1 - x0), hd = head || 7;
    c.strokeStyle = color; c.fillStyle = color; c.lineWidth = 1.5;
    c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1 - Math.cos(a) * hd * 0.7, y1 - Math.sin(a) * hd * 0.7); c.stroke();
    c.beginPath(); c.moveTo(x1, y1);
    c.lineTo(x1 - hd * Math.cos(a - 0.45), y1 - hd * Math.sin(a - 0.45));
    c.lineTo(x1 - hd * Math.cos(a + 0.45), y1 - hd * Math.sin(a + 0.45));
    c.closePath(); c.fill();
  };

  const stElectron = function stElectron(c, C, x, y, r) {
    dot(c, x, y, r || 6.5, C.accent, C.surface);
    c.strokeStyle = C.surface; c.lineWidth = 1.6;
    c.beginPath(); c.moveTo(x - 3, y); c.lineTo(x + 3, y); c.stroke();
  };

  const stIon = function stIon(c, C, x, y, r, w) {
    dot(c, x, y, r, mix(mix(C.muted, C.surface, 0.35), C.warm, w || 0));
    c.strokeStyle = C.surface; c.lineWidth = 1.4;
    c.beginPath(); c.moveTo(x - 2.5, y); c.lineTo(x + 2.5, y); c.moveTo(x, y - 2.5); c.lineTo(x, y + 2.5); c.stroke();
  };

  const stCube = function stCube(c, C, x, y, s) {
    var k = 0.87 * s;
    c.beginPath(); c.moveTo(x, y - s); c.lineTo(x + k, y - s / 2); c.lineTo(x, y); c.lineTo(x - k, y - s / 2); c.closePath();
    c.fillStyle = mix(C.accent, C.surface, 0.55); c.fill();
    c.beginPath(); c.moveTo(x - k, y - s / 2); c.lineTo(x, y); c.lineTo(x, y + s); c.lineTo(x - k, y + s / 2); c.closePath();
    c.fillStyle = mix(C.accent, C.surface, 0.2); c.fill();
    c.beginPath(); c.moveTo(x, y); c.lineTo(x + k, y - s / 2); c.lineTo(x + k, y + s / 2); c.lineTo(x, y + s); c.closePath();
    c.fillStyle = C.accent; c.fill();
  };

  const stLog = function stLog(v) { return Math.log(v) / Math.LN10; };

  const stTcText = function stTcText(v) { return v < 10 ? v.toFixed(1) : String(Math.round(v)); };

  const stLive = function stLive() {
    var d = state.data, out = { mae: null, now: '', release: null, foundation: '', foundationMae: null, measured: '' };
    if (!d) return out;
    var best = bestOurs(d, 'Tc');
    if (best) out.mae = best.mae;
    var st = list(d.stages), ci = currentIndex(st);
    if (ci >= 0 && st[ci]) out.now = L(st[ci].short) || L(st[ci].name);
    st.forEach(function (x) {
      if (!x) return;
      if (x.id === 'release' && x.date) out.release = parseDate(x.date);
      if (x.id === 'foundation') out.foundation = x.status || '';
      if (x.id === 'data-measured') out.measured = x.status || '';
    });
    list(d.results).forEach(function (r) {
      if (r && r.target === 'Tc' && typeof r.mae === 'number' && /foundation|mace/i.test(String(r.tag || '') + ' ' + L(r.model))) {
        if (out.foundationMae === null || r.mae < out.foundationMae) out.foundationMae = r.mae;
      }
    });
    return out;
  };

  const storyCaption = function storyCaption(i) {
    var sc = STORY[i];
    return typeof sc.caption === 'function' ? sc.caption() : sc.caption;
  };

  const storyShortcutCaption = function storyShortcutCaption() {
    var info = stormInfo(), n = 54, np = 11;
    if (info) { n = 0; list(info.v.spec.inputs).forEach(function (i) { n += i.n || 0; if (i.group === 'physics') np = i.n; }); }
    return 'We train on about 7,600 materials whose λ and ω_log have already been computed (the Alexandria superconductivity set). ' + stormName() + ', the model our AI agent designed, describes each crystal with ' + n + ' numbers: composition statistics, the crystal structure and ' + np + ' physics features the AI proposed, such as the valence-electron count that Matthias linked to Tc and the M^−½ scale of phonon frequencies. Gradient-boosted trees turn them into Tc directly, or into λ and ω_log for the Allen–Dynes formula. We also test fingerprints from the foundation model MACE-MP-0, pre-trained on about 1.6 million DFT calculations; so far they have not beaten Storm.' +
      (function () { var c = stormCal(); return c && stormIsCurrent(info) ? ' A calibration learned from measured Tc turns it into Storm ' + c.version + ', off by ' + c.scores.mae.toFixed(2) + ' K against experiment.' + stormEnsSentence() : ''; })();
  };

  const storyModelsCaption = function storyModelsCaption() {
    var live = stLive();
    var f = live.foundationMae !== null ? 'first run finished at ' + live.foundationMae.toFixed(2) + ' K' : live.foundation === 'active' ? 'training now' : 'up next';
    return 'No single model is best for every material, so we compare several: gradient boosting on 43 hand-made composition and structure features (done, ' + MAE_BASELINE.toFixed(2) + ' K average Tc error), the MACE-MP-0 foundation model with a boosted head (' + f + '), ' +
      (function () { var gi = gnnInfo(); return gi.status === 'done' && gi.mae !== null ? 'our crystal-graph network (' + gi.name + ', ' + gi.mae.toFixed(2) + ' K)' : 'graph neural networks such as ALIGNN'; })() + ', and Hurricane, our second AI-designed model, which learns the Tc of unconventional superconductors from measurements. We are also letting an AI agent design models itself: it proposes an architecture or feature set, trains it, scores it with the same grouped cross-validation, and refines the design, keeping only what beats the current best. A locked test set is used only once, at the very end, so no design can be tuned to it.' + stormStorySentence();
  };

  const stormStorySentence = function stormStorySentence() {
    var info = stormInfo();
    if (!info) return '';
    var v = info.v;
    var cal = stormIsCurrent(info) ? stormCal() : null;
    return ' Its designs are called Storm: ' + stormTitle(info) + ' (' + lcFirst(v.summary) + ') ' +
      (v.status === 'adopted' ? 'was released with ' : 'stays experimental at ') + v.scores.tc_mae.toFixed(2) + ' K average Tc error.' +
      (cal ? ' Calibrated to measured Tc, it became Storm ' + cal.version + ', off by ' + cal.scores.mae.toFixed(2) + ' K against experiment.' + stormEnsSentence() : '');
  };

  const storyAccuracyCaption = function storyAccuracyCaption() {
    // the dots are Storm 1.0's predictions; a later Storm that adds the graph network is named with its own error
    var e = stormEns(), later = e ? ' Storm ' + e.version + ', which adds our crystal-graph network, is off by ' + e.scores.tc_mae.toFixed(2) + ' K.' : '';
    return 'Each dot is one material the model did not see during training: across is its Tc from the full calculation, up is our prediction. The axes use a square-root scale so the many low-Tc materials stay visible. Guessing the average Tc for every material would be off by ' + MAE_GUESS.toFixed(2) + ' K on average; our AI-designed model ' + stormName() + ' is off by ' + stormMae().toFixed(2) + ' K, against ' + MAE_BASELINE.toFixed(2) + ' K for the hand-made baseline, tested on whole chemical systems held out from training.' + later;
  };


  const drawStory = function drawStory(c, C) {
    var W = demo.W, H = demo.H, narrow = W < 560;
    var sc = STORY[demo.scene];
    var t = motionOK() ? demo.sceneT : sc.dur;
    var n = STORY.length, gap = 4, segW = (W - 32 - gap * (n - 1)) / n;
    for (var i = 0; i < n; i++) {
      var sx = 16 + i * (segW + gap);
      stRound(c, sx, 12, segW, 3, 1.5); c.fillStyle = C.grid; c.fill();
      var f = i < demo.scene ? 1 : i > demo.scene ? 0 : stClamp(t / sc.dur);
      if (f > 0) { stRound(c, sx, 12, Math.max(3, segW * f), 3, 1.5); c.fillStyle = C.accent; c.fill(); }
    }
    var box;
    c.save();
    if (sc.bare) box = { x: 16, y: 26, w: W - 32, h: H - 40 };
    else {
      c.globalAlpha = stSpan(t, 0, 0.35);
      label(c, C, demo.scene + ' · ' + sc.title, 16, 48, { size: narrow ? 15 : 17, weight: '600', color: C.ink });
      label(c, C, 'Hello Super', W - 16, 48, { align: 'right', size: 12, weight: '600', color: C.accent });
      var lines = stParaRich(c, C, sc.sub, 16, 71, W - 32, 18, { size: narrow ? 12.5 : 13.5, color: C.ink2 });
      var top = 71 + (lines - 1) * 18 + 18;
      box = { x: 16, y: top, w: W - 32, h: H - top - 14 };
    }
    c.restore();
    c.save();
    sc.draw(c, C, box, t, narrow);
    c.restore();
    c.globalAlpha = 1;
    c.setLineDash([]);
  };


  const goScene = function goScene(i) {
    var n = STORY.length;
    demo.scene = ((i % n) + n) % n;
    demo.sceneT = 0;
    if (motionOK()) demo.storyPlay = true;
    syncControls();
    kick();
  };


  /* 0 · title card */
  const drawStoryIntro = function drawStoryIntro(c, C, B, t, narrow) {
    var cx = B.x + B.w / 2, cy = B.y + B.h * 0.4;
    var rng = stRng(11), N = narrow ? 12 : 22;
    c.save();
    stRound(c, B.x, B.y, B.w, B.h, 12); c.clip();
    for (var i = 0; i < N; i++) {
      var lane = rng(), speed = 36 + 46 * rng(), phase = rng() * 10, amp = 8 + 16 * rng(), spin = (rng() < 0.5 ? -1 : 1) * (1.2 + rng());
      var span = B.w + 80;
      var x = B.x - 40 + ((phase * 97 + t * speed) % span);
      var y = B.y + 16 + lane * (B.h - 32) + amp * Math.sin(x / 70 + phase);
      var ang = t * spin + phase, r = 7;
      var px = Math.cos(ang) * r, py = Math.sin(ang) * r;
      var fade = 0.18 + 0.5 * stClamp(Math.abs(y - cy) / (B.h * 0.22));
      c.globalAlpha = fade * stSpan(t, 0, 0.8);
      c.strokeStyle = C.accent; c.lineWidth = 1.5;
      c.beginPath(); c.moveTo(x - px, y - py); c.lineTo(x + px, y + py); c.stroke();
      dot(c, x - px, y - py, 3.2, C.accent); dot(c, x + px, y + py, 3.2, C.accent);
    }
    c.restore();
    var title = 'Hello Super', shown = Math.round(stClamp((t - 0.3) / 1.1) * title.length);
    var size = narrow ? 36 : 52;
    stFont(c, C, size, '700');
    var wHello = c.measureText('Hello ').width, wAll = c.measureText(title).width, x0 = cx - wAll / 2;
    c.globalAlpha = 1;
    var s1 = title.slice(0, Math.min(shown, 6)), s2 = shown > 6 ? title.slice(6, shown) : '';
    if (s1) label(c, C, s1, x0, cy, { size: size, weight: '700', color: C.ink, base: 'middle' });
    if (s2) label(c, C, s2, x0 + wHello, cy, { size: size, weight: '700', color: C.accent, base: 'middle' });
    if (motionOK() && t < 1.9 && Math.floor(t * 2.5) % 2 === 0) {
      stFont(c, C, size, '700');
      var cw = c.measureText(title.slice(0, shown)).width;
      c.fillStyle = C.accent; c.fillRect(x0 + cw + 4, cy - size * 0.4, 3, size * 0.8);
    }
    c.globalAlpha = stSpan(t, 1.5, 2.1);
    var tagY = cy + size * 0.95;
    var nTag = stPara(c, C, 'A machine-learning hunt for new superconductors', cx, tagY, B.w - 24, 20, { size: narrow ? 14 : 16, color: C.ink2, align: 'center' });
    var chips = ['Predict Tc', 'Screen for high Tc', 'Probe the mechanism'];
    var cy2 = tagY + (nTag - 1) * 20 + 42;
    stFont(c, C, 12.5, '600');
    var widths = chips.map(function (s) { return c.measureText(s).width + 18; });
    var total = widths.reduce(function (a, b) { return a + b; }, 0) + 10 * (chips.length - 1);
    var stack = total > B.w - 20;
    var xx = cx - total / 2;
    chips.forEach(function (s, k) {
      c.globalAlpha = stSpan(t, 2.3 + 0.25 * k, 2.7 + 0.25 * k);
      if (stack) stTag(c, C, s, cx, cy2 + k * 30, { size: 12.5, ring: C.axis, bg: C.surface });
      else { stTag(c, C, s, xx, cy2, { size: 12.5, align: 'left', ring: C.axis, bg: C.surface, pad: 9 }); xx += widths[k] + 10; }
    });
  };


  /* 1 · why it matters */
  const drawStoryWhy = function drawStoryWhy(c, C, B, t, narrow) {
    var tx = B.x + (narrow ? 84 : Math.max(180, Math.round(B.w * 0.27)));
    var yt = B.y + 12, yb = B.y + B.h - 30, TOP = stLog(400);
    function Y(T) { return yb - stLog(T) / TOP * (yb - yt); }
    var a0 = stSpan(t, 0, 0.5);
    c.globalAlpha = a0;
    stRound(c, tx - 8, yt - 6, 16, yb - yt + 14, 8);
    c.fillStyle = C.surface2; c.fill(); c.lineWidth = 1; c.strokeStyle = C.axis; c.stroke();
    c.beginPath(); c.arc(tx, yb + 14, 13, 0, Math.PI * 2); c.fillStyle = C.accent; c.fill();
    var times = WHY_ITEMS.map(function (d, i) { return 0.7 + 0.72 * i; });
    var rec = 1, lvl = 0;
    WHY_ITEMS.forEach(function (d, i) {
      if (t < times[i] || d.kind === 'pressure') return;
      var nr = Math.max(rec, d.T);
      lvl = stLog(rec) + (stLog(nr) - stLog(rec)) * stEase((t - times[i]) / 0.6);
      rec = nr;
    });
    var fy = Y(Math.pow(10, lvl));
    var gr = c.createLinearGradient(0, yb, 0, Y(300));
    gr.addColorStop(0, C.accent); gr.addColorStop(1, C.warm);
    stRound(c, tx - 4, fy, 8, yb + 8 - fy, 4); c.fillStyle = gr; c.fill();
    WHY_REFS.forEach(function (r) {
      var y = Math.round(Y(r.T)) + 0.5;
      c.setLineDash([3, 3]); c.strokeStyle = C.muted; c.lineWidth = 1;
      c.beginPath(); c.moveTo(tx - 18, y); c.lineTo(tx + 9, y); c.stroke(); c.setLineDash([]);
      if (narrow) {
        label(c, C, r.short, tx - 22, y - 2, { align: 'right', size: 11, color: C.ink2 });
        label(c, C, r.val, tx - 22, y + 11, { align: 'right', size: 11, color: C.muted });
      } else label(c, C, r.name + ' · ' + r.val, tx - 22, y + 4, { align: 'right', size: 12, color: C.ink2 });
    });
    var g = stSpan(t, 6.0, 6.6);
    if (g > 0) {
      var pulse = motionOK() ? 0.55 + 0.45 * Math.sin(t * 4) : 1;
      var gy0 = Y(295), gy1 = Y(160);
      c.globalAlpha = a0 * g * (0.45 + 0.55 * pulse);
      c.setLineDash([4, 3]); c.lineWidth = 1.6; c.strokeStyle = C.warm;
      stRound(c, tx - 10, gy0 - 3, 20, gy1 - gy0 + 6, 9); c.stroke(); c.setLineDash([]);
      c.globalAlpha = a0 * g;
      label(c, C, '?', tx, (gy0 + gy1) / 2 + 1, { align: 'center', base: 'middle', size: 13, weight: '700', color: C.warm });
    }
    var items = WHY_ITEMS.map(function (d, i) { return { d: d, i: i, y: Y(d.T) }; }).sort(function (a, b) { return a.d.T - b.d.T; });
    var gapY = narrow ? 15 : 17;
    for (var k = 1; k < items.length; k++) if (items[k].y > items[k - 1].y - gapY) items[k].y = items[k - 1].y - gapY;
    var over = (yt + 4) - items[items.length - 1].y;
    if (over > 0) items.forEach(function (it) { it.y += over; });
    var lx = tx + 32;
    items.forEach(function (it) {
      var d = it.d, a = stSpan(t, times[it.i], times[it.i] + 0.4);
      if (a <= 0) return;
      c.globalAlpha = a0 * a;
      var my = Y(d.T);
      c.strokeStyle = C.axis; c.lineWidth = 1;
      c.beginPath(); c.moveTo(tx + 21, my); c.lineTo(tx + 25, my); c.lineTo(lx - 4, it.y - 4); c.stroke();
      if (d.kind === 'pressure') dot(c, tx + 16, my, 4, C.surface, C.accent);
      else dot(c, tx + 16, my, 4.5, d.kind === 'unconv' ? C.warm : C.accent);
      var off = (1 - a) * 8, fs = narrow ? 11.5 : 12.5;
      stFont(c, C, fs, '600');
      var nw = c.measureText(d.name).width;
      label(c, C, d.name, lx + off, it.y, { size: fs, weight: '600', color: C.ink });
      var rest = d.T + ' K · ' + d.year + (d.kind === 'pressure' && !narrow ? ' · under 1.7 million atm' : '');
      label(c, C, rest, lx + off + nw + 6, it.y, { size: narrow ? 11 : 12, color: C.ink2 });
    });
    c.globalAlpha = a0 * stSpan(t, 0.3, 0.8);
    var leg = [['conv', 'Conventional (phonons)'], ['unconv', 'Unconventional'], ['pressure', 'Needs extreme pressure']];
    leg.forEach(function (e, i) {
      var y = yb - 30 + i * 15, x = tx + 30;
      if (e[0] === 'pressure') dot(c, x + 4, y - 4, 3.5, C.surface, C.accent);
      else dot(c, x + 4, y - 4, 4, e[0] === 'unconv' ? C.warm : C.accent);
      label(c, C, e[1], x + 14, y, { size: 11, color: C.muted });
    });
    if (!narrow) {
      var gx = lx + 290, gw = B.x + B.w - gx;
      if (gw > 190) {
        c.globalAlpha = a0 * stSpan(t, 6.2, 6.9);
        label(c, C, 'The goal', gx, B.y + B.h * 0.28, { size: 15, weight: '600', color: C.ink });
        stPara(c, C, 'A superconductor that works warm, at everyday pressure. It could carry electricity without loss and make MRI scanners and powerful magnets far cheaper to run.', gx, B.y + B.h * 0.28 + 24, Math.min(330, gw), 19, { size: 13, color: C.ink2 });
      }
    }
  };


  /* 2 · what sets Tc */
  const drawStoryPhysics = function drawStoryPhysics(c, C, B, t, narrow) {
    var wide = !narrow;
    var Lr = wide ? { x: B.x, y: B.y, w: Math.round(B.w * 0.56), h: B.h } : { x: B.x, y: B.y, w: B.w, h: Math.round(B.h * 0.5) };
    var P = wide ? { x: B.x + Math.round(B.w * 0.62), y: B.y + 8, w: B.w - Math.round(B.w * 0.62), h: B.h - 8 } : { x: B.x, y: Lr.y + Lr.h + 18, w: B.w, h: B.h - Lr.h - 18 };
    var a0 = stSpan(t, 0, 0.5);
    c.globalAlpha = a0;
    var d = Math.max(26, Math.min(40, Math.floor(Lr.h / 5)));
    var rows = Math.max(3, Math.floor(Lr.h / d)), cols = Math.max(5, Math.floor(Lr.w / d));
    var dx = Lr.w / cols, oy = Lr.y + (Lr.h - rows * d) / 2;
    var lane = oy + Math.floor(rows / 2) * d;
    var speed = (0.85 * Lr.w + 2 * d) / 9;
    var e1x = Lr.x - 2 * d + speed * t;
    var catchUp = stSpan(t, 0.8, 3.6);
    var e2x = e1x - (5.2 - 2.6 * catchUp) * d, e2y = lane + (1 - catchUp) * 0.4 * d * Math.sin(t * 5) + catchUp * 3 * Math.sin(t * 3);
    c.save();
    stRound(c, Lr.x, Lr.y, Lr.w, Lr.h, 12); c.fillStyle = C.surface2; c.fill(); c.clip();
    for (var r = 0; r < rows; r++) {
      for (var k = 0; k < cols; k++) {
        var x0 = Lr.x + (k + 0.5) * dx, y0 = oy + (r + 0.5) * d;
        var b = e1x - x0, v = y0 - lane;
        var A = b > -0.4 * d ? 7.5 * Math.exp(-Math.pow(b - 1.3 * d, 2) / (2 * Math.pow(1.3 * d, 2))) : 0;
        var u = A * Math.exp(-(v * v) / (2 * Math.pow(0.85 * d, 2)));
        var x = x0 + (b > 0 ? 0.25 : -0.25) * u + 0.9 * Math.sin(t * 9 + k * 1.7 + r * 2.3);
        var y = y0 - (v > 0 ? 1 : -1) * u + 0.9 * Math.cos(t * 11 + k * 2.1 + r);
        stIon(c, C, x, y, 6 + 1.4 * Math.min(1, u / 5), Math.min(1, u / 5));
      }
    }
    var tagA = stSpan(t, 1.4, 1.8) * (1 - stSpan(t, 2.7, 3.1));
    if (tagA > 0) {
      c.globalAlpha = a0 * tagA;
      stTag(c, C, 'electron', Math.max(Lr.x + 36, e1x), lane - 0.95 * d, { size: 11.5 });
      stTag(c, C, 'ions pulled in', Math.max(Lr.x + 52, e1x - 1.3 * d), lane + 1.05 * d, { size: 11.5 });
    }
    var pa = stSpan(t, 2.8, 3.5);
    if (pa > 0) {
      c.globalAlpha = a0 * pa;
      c.setLineDash([4, 5]); c.lineWidth = 1.5; c.strokeStyle = C.accent;
      var midx = (e1x + e2x) / 2, midy = lane - 0.9 * d;
      c.beginPath(); c.moveTo(e2x, e2y - 8); c.quadraticCurveTo(midx, midy, e1x, lane - 8); c.stroke(); c.setLineDash([]);
      stTag(c, C, 'Cooper pair', midx, midy - 6, { size: 12 });
    }
    c.globalAlpha = a0;
    stElectron(c, C, e2x, e2y); stElectron(c, C, e1x, lane);
    c.restore();
    var lam = 0.3 + 0.7 * stSpan(t, 1.4, 5.4), wl = 300 * stSpan(t, 0.6, 1.6);
    var tc = allenDynes(lam, 300, 0.10);
    var short = P.w < 380;
    c.globalAlpha = a0 * stSpan(t, 0.4, 0.9);
    var y1 = P.y + (wide ? 16 : 10), step = wide ? 58 : 44;
    function meter(parts, desc, valText, frac, yy) {
      var sw = stSym(c, C, parts, P.x, yy, { size: 15, weight: '700' });
      label(c, C, desc, P.x + sw + 8, yy, { size: 12, color: C.ink2 });
      label(c, C, valText, P.x + P.w, yy, { align: 'right', size: 13, weight: '600', color: C.ink });
      stRound(c, P.x, yy + 9, P.w, 8, 4); c.fillStyle = C.grid; c.fill();
      if (frac > 0) { stRound(c, P.x, yy + 9, Math.max(8, P.w * Math.min(1, frac)), 8, 4); c.fillStyle = C.accent; c.fill(); }
    }
    meter([['λ']], short ? 'coupling strength' : 'how strongly electrons tug on the lattice', lam.toFixed(2), lam / 2, y1);
    meter([['ω'], ['log', 1]], short ? 'vibration energy' : 'how fast the lattice vibrates', Math.round(wl) + ' K', wl / 800, y1 + step);
    var y3 = y1 + 2 * step + (wide ? 12 : 4);
    label(c, C, 'Allen–Dynes formula, μ* = 0.10', P.x, y3, { size: 12, color: C.muted });
    stSym(c, C, [['T'], ['c', 1], [' ≈ ' + stTcText(tc) + ' K']], P.x, y3 + (wide ? 34 : 28), { size: wide ? 28 : 22, weight: '700' });
    if (t > 5.1) {
      c.globalAlpha = a0 * stSpan(t, 5.2, 5.8);
      stSym(c, C, [['Stronger coupling → higher T'], ['c', 1]], P.x, y3 + (wide ? 62 : 50), { size: 12.5, color: C.ink2 });
    }
  };


  /* 3 · the slow way */
  const drawStorySlow = function drawStorySlow(c, C, B, t, narrow) {
    var a0 = stSpan(t, 0, 0.5);
    c.globalAlpha = a0;
    var qs = [], cs = narrow ? 9 : 11, box, qx, qy, sp, qrows = 4;
    if (!narrow) {
      qx = B.x + 16; var qw = Math.round(B.w * 0.26), qcols = 5;
      sp = Math.min(34, qw / qcols);
      qy = B.y + B.h * 0.45 - (qrows - 1) * sp / 2;
      for (var r = 0; r < qrows; r++) for (var k = 0; k < qcols; k++) qs.push([qx + k * sp + sp / 2, qy + r * sp]);
      box = { w: Math.min(300, Math.round(B.w * 0.32)), h: 150 };
      box.x = B.x + Math.round(B.w * 0.56) - box.w / 2; box.y = B.y + B.h * 0.45 - box.h / 2;
    } else {
      var n = 8, sp2 = (B.w - 20) / n;
      for (var j = 0; j < n; j++) qs.push([B.x + 10 + sp2 * (j + 0.5), B.y + 22]);
      box = { x: B.x + 8, y: B.y + 78, w: B.w - 16, h: 128 };
    }
    var front = qs[qs.length - 1];
    qs.forEach(function (p, i) { if (i === qs.length - 1 && t >= 0.9) return; stCube(c, C, p[0], p[1], cs); });
    if (!narrow) {
      label(c, C, 'Candidate crystals', qx, qy - 28, { size: 12, weight: '600', color: C.ink });
      label(c, C, '…millions more waiting', qx, qy + (qrows - 1) * sp + 34, { size: 12, color: C.ink2 });
    } else label(c, C, 'Millions of candidate crystals waiting…', B.x + B.w / 2, B.y + 54, { align: 'center', size: 12, color: C.ink2 });
    stRound(c, box.x, box.y, box.w, box.h, 12); c.fillStyle = C.surface2; c.fill(); c.lineWidth = 1; c.strokeStyle = C.axis; c.stroke();
    label(c, C, 'Quantum calculation', box.x + 16, box.y + 26, { size: 13.5, weight: '600', color: C.ink });
    label(c, C, 'DFT + phonons on a supercomputer', box.x + 16, box.y + 44, { size: 11.5, color: C.muted });
    var ck = { x: box.x + box.w - 30, y: box.y + 32, r: 14 };
    c.beginPath(); c.arc(ck.x, ck.y, ck.r, 0, Math.PI * 2); c.fillStyle = C.surface; c.fill(); c.strokeStyle = C.ink2; c.lineWidth = 1.5; c.stroke();
    var run = stClamp((t - 2.1) / 5.4), spin = Math.max(0, Math.min(t, 7.5) - 2.1);
    var ma = -Math.PI / 2 + spin * Math.PI * 2 * 1.2, ha = -Math.PI / 2 + spin * Math.PI * 2 * 0.1;
    c.lineCap = 'round';
    c.beginPath(); c.moveTo(ck.x, ck.y); c.lineTo(ck.x + Math.cos(ma) * 10, ck.y + Math.sin(ma) * 10); c.stroke();
    c.lineWidth = 2.2; c.beginPath(); c.moveTo(ck.x, ck.y); c.lineTo(ck.x + Math.cos(ha) * 6.5, ck.y + Math.sin(ha) * 6.5); c.stroke();
    c.lineCap = 'butt';
    var p = 1 - Math.pow(1 - run, 2);
    var pbx = box.x + 16, pby = box.y + box.h - 24, pbw = box.w - 32;
    stRound(c, pbx, pby, pbw, 8, 4); c.fillStyle = C.grid; c.fill();
    if (p > 0) { stRound(c, pbx, pby, Math.max(8, pbw * p), 8, 4); c.fillStyle = C.accent; c.fill(); }
    label(c, C, Math.round(p * 100) + '%', pbx + pbw, pby - 8, { align: 'right', size: 11.5, weight: '600', color: C.ink2 });
    label(c, C, run >= 1 ? 'Done: 1 material' : t > 2.1 ? 'Computing…' : 'Waiting for input', pbx, pby - 8, { size: 11.5, color: C.ink2 });
    var mv = stSpan(t, 0.9, 2.1), slot = [box.x + box.w / 2, box.y + box.h / 2 + 2];
    if (t >= 0.9 && run < 1) {
      var mx = front[0] + (slot[0] - front[0]) * mv, my = front[1] + (slot[1] - front[1]) * mv - Math.sin(mv * Math.PI) * 30;
      stCube(c, C, mx, my, cs + 3 * mv);
      if (t > 2.1) {
        c.save(); c.setLineDash([3, 4]); c.lineDashOffset = -t * 20; c.strokeStyle = C.accent; c.lineWidth = 1.5;
        c.beginPath(); c.arc(slot[0], slot[1], cs + 12, 0, Math.PI * 2); c.stroke(); c.restore();
      }
    }
    var out = stSpan(t, 7.5, 8.2);
    if (out > 0) {
      c.globalAlpha = a0 * out;
      var ox = !narrow ? box.x + box.w + 28 + 16 * (1 - out) : B.x + B.w / 2, oy = !narrow ? box.y + box.h / 2 : box.y + box.h + 30 + 8 * (1 - out);
      stTag(c, C, 'λ = 0.62 · ω_log = 240 K', ox, oy, { size: 12, align: !narrow ? 'left' : 'center', ring: C.axis, rich: true });
      label(c, C, 'one material done', !narrow ? ox + 4 : ox, oy + 26, { size: 11.5, color: C.muted, align: !narrow ? 'left' : 'center' });
    }
    c.globalAlpha = a0;
    label(c, C, 'Each material: hours to days of computing', !narrow ? box.x + box.w / 2 : B.x + B.w / 2, !narrow ? box.y + box.h + 26 : box.y + box.h + 80, { align: 'center', size: 12.5, weight: '600', color: C.ink });
  };


  /* 4 · our shortcut */
  const drawStoryShortcut = function drawStoryShortcut(c, C, B, t, narrow) {
    var a0 = stSpan(t, 0, 0.5);
    c.globalAlpha = a0;
    var wide = !narrow, x1, x2, x3, R, mw, mh, cy;
    if (wide) {
      cy = B.y + B.h * 0.32; x1 = B.x + B.w * 0.15; x2 = B.x + B.w * 0.5; x3 = B.x + B.w * 0.82;
      R = Math.min(B.w * 0.06, B.h * 0.15, 54); mw = Math.min(B.w * 0.24, 220); mh = Math.min(B.h * 0.34, 120);
    } else {
      cy = B.y + B.h * 0.2; x1 = B.x + B.w * 0.22; x2 = B.x + B.w * 0.74; x3 = B.x + B.w / 2;
      R = Math.min(36, B.h * 0.12); mw = Math.min(B.w * 0.4, 140); mh = Math.min(B.h * 0.24, 84);
    }
    var atoms = [[0, 0, 'c']];
    for (var i = 0; i < 6; i++) { var an = Math.PI / 6 + i * Math.PI / 3; atoms.push([R * Math.cos(an), R * Math.sin(an), i % 2 ? 'w' : 'a']); }
    var bonds = [];
    for (var j = 1; j <= 6; j++) { bonds.push([0, j]); bonds.push([j, j % 6 + 1]); }
    c.lineWidth = 2; c.strokeStyle = C.axis;
    bonds.forEach(function (b) { var p = atoms[b[0]], q = atoms[b[1]]; c.beginPath(); c.moveTo(x1 + p[0], cy + p[1]); c.lineTo(x1 + q[0], cy + q[1]); c.stroke(); });
    var msg = stSpan(t, 0.5, 0.9) * (1 - stSpan(t, 3.6, 4.2));
    if (msg > 0) {
      bonds.forEach(function (b, k) {
        var ph = (t * 0.9 + k * 0.37) % 1, dir = k % 2;
        var p = atoms[b[dir]], q = atoms[b[1 - dir]];
        c.globalAlpha = a0 * msg * Math.sin(ph * Math.PI);
        dot(c, x1 + p[0] + (q[0] - p[0]) * ph, cy + p[1] + (q[1] - p[1]) * ph, 3, C.accent);
      });
      c.globalAlpha = a0;
    }
    atoms.forEach(function (p, k) {
      var col = p[2] === 'a' ? C.accent : p[2] === 'w' ? C.warm : C.ink2;
      var glow = msg > 0 && motionOK() ? 0.5 + 0.5 * Math.sin(t * 6 + k) : 0;
      dot(c, x1 + p[0], cy + p[1], (k ? 8.5 : 9.5) + glow * 1.5, col, C.surface);
    });
    var fpV = [0.15, 0.8, 0.45, 0.95, 0.3, 0.65, 0.1, 0.55];
    var cellW = narrow ? 8 : 10, cellH = narrow ? 6 : 8;
    var fx0 = x1 + R + 16, fx1 = x2 - mw / 2 - 12 - cellW;
    var fpA = stSpan(t, 1.6, 1.9) * (1 - stSpan(t, 3.2, 3.6)), fpM = stSpan(t, 1.9, 3.1);
    if (fpA > 0) {
      var fx = fx0 + (fx1 - fx0) * fpM, fy = cy - fpV.length * cellH / 2;
      c.globalAlpha = a0 * fpA;
      fpV.forEach(function (v, k) { c.fillStyle = stRgb(rampColor(v, C.dark)); c.fillRect(fx, fy + k * cellH, cellW, cellH - 1); });
      c.globalAlpha = a0;
    }
    var mx0 = x2 - mw / 2, my0 = cy - mh / 2, nTree = 3;
    stRound(c, mx0, my0, mw, mh, 12); c.fillStyle = C.surface2; c.fill(); c.lineWidth = 1; c.strokeStyle = C.axis; c.stroke();
    for (var ti = 0; ti < nTree; ti++) {
      var e = stSpan(t, 3.1 + 0.4 * ti, 3.5 + 0.4 * ti), tw = mw / nTree;
      drawTreeGlyph(c, C, mx0 + tw * (ti + 0.5), my0 + mh * 0.18, tw * 0.78, mh * 0.62, narrow ? 3 : 4, e > 0 ? mix(C.axis, C.accent, e) : C.axis);
    }
    var capY = cy + Math.max(R, mh / 2) + 22, shortCap = B.w < 900;
    function caption2(x, a, b) {
      label(c, C, a, x, capY, { align: 'center', size: 12.5, weight: '600', color: C.ink });
      label(c, C, b, x, capY + 16, { align: 'center', size: 11.5, color: C.ink2 });
    }
    caption2(x1, 'Crystal → numbers', narrow ? 'numbers per material' : shortCap ? 'composition, structure, physics' : 'composition, structure and physics features');
    caption2(x2, stormName(), shortCap ? 'AI-designed trees' : 'our AI-designed model: boosted trees');
    var tcEx = allenDynes(0.92, 310, 0.10);
    if (wide) {
      if (t > 4.4) { c.globalAlpha = a0 * stSpan(t, 4.4, 4.8); stArrow(c, mx0 + mw + 10, cy, x3 - 76, cy, C.axis, 7); }
      c.globalAlpha = a0 * stSpan(t, 4.7, 5.0);
      stSym(c, C, [['λ = 0.92']], x3, cy - 22, { size: 14, weight: '600', align: 'center' });
      c.globalAlpha = a0 * stSpan(t, 5.0, 5.3);
      stSym(c, C, [['ω'], ['log', 1], [' = 310 K']], x3, cy + 2, { size: 14, weight: '600', align: 'center' });
      c.globalAlpha = a0 * stSpan(t, 5.5, 5.9);
      stSym(c, C, [['T'], ['c', 1], [' ≈ ' + Math.round(tcEx) + ' K']], x3, cy + 38, { size: 24, weight: '700', align: 'center' });
      c.globalAlpha = a0;
      caption2(x3, 'Prediction', 'example values');
    } else {
      var oy = capY + 58;
      if (t > 4.4) { c.globalAlpha = a0 * stSpan(t, 4.4, 4.8); stArrow(c, x2, capY + 24, x2, oy - 24, C.axis, 7); }
      c.globalAlpha = a0 * stSpan(t, 4.7, 5.2);
      stSym(c, C, [['λ = 0.92   ω'], ['log', 1], [' = 310 K']], x3, oy, { size: 13, weight: '600', align: 'center' });
      c.globalAlpha = a0 * stSpan(t, 5.5, 5.9);
      stSym(c, C, [['T'], ['c', 1], [' ≈ ' + Math.round(tcEx) + ' K (example)']], x3, oy + 28, { size: 19, weight: '700', align: 'center' });
    }
    var sbA = stSpan(t, 6.2, 6.6);
    if (sbA > 0) {
      c.globalAlpha = a0 * sbA;
      var by0 = B.y + B.h * (wide ? 0.78 : 0.82), lw = wide ? 170 : 104;
      var bx0 = B.x + lw, bx1 = B.x + B.w - (wide ? 110 : 84);
      label(c, C, wide ? 'Quantum calculation' : 'Quantum calc.', B.x, by0 + 4, { size: 12, color: C.ink2 });
      label(c, C, 'Our model', B.x, by0 + 30, { size: 12, color: C.ink2 });
      stRound(c, bx0, by0 - 5, bx1 - bx0, 10, 5); c.fillStyle = C.grid; c.fill();
      var grow = stClamp((t - 6.4) / 2.2);
      if (grow > 0) { stRound(c, bx0, by0 - 5, Math.max(10, (bx1 - bx0) * grow), 10, 5); c.fillStyle = C.muted; c.fill(); }
      stRound(c, bx0, by0 + 21, 6, 10, 3); c.fillStyle = C.accent; c.fill();
      label(c, C, wide ? 'hours to days' : 'hours–days', bx1 + 8, by0 + 4, { size: 11.5, color: C.ink2 });
      label(c, C, wide ? 'under a second' : '< 1 second', bx0 + 14, by0 + 30, { size: 11.5, weight: '600', color: C.ink });
    }
  };


  const hurStoryRow = function hurStoryRow(narrow, live) {
    var info = hurInfo();
    if (!info) return { name: narrow ? 'Hurricane · unconventional' : 'Hurricane · our AI model', desc: 'for unconventional superconductors, from measured Tc', status: live.measured === 'done' ? 'done' : live.measured === 'active' ? 'running' : 'planned', note: '' };
    return { name: hurTitle(info) + (narrow ? '' : ' · our AI model'), desc: 'AI-designed, unconventional; error against measured Tc', status: info.v.status === 'adopted' ? 'done' : 'exploring',
      note: hurK(info.v.scores.tc_mae) + ' K' };
  };

  const stormStoryRow = function stormStoryRow() {
    var info = stormInfo();
    if (!info) return { name: 'Storm (AI-designed)', desc: 'an agent proposes new designs', status: 'exploring', note: '' };
    var cal = stormIsCurrent(info) ? stormCal() : null, ens = stormIsCurrent(info) ? stormEns() : null;
    var unc = ens ? stormUnc() : null;
    return { name: (unc ? 'Storm ' + unc.version : ens ? 'Storm ' + ens.version : cal ? 'Storm ' + cal.version : stormTitle(info)) + ' · our AI model', desc: 'AI-designed, conventional; error against DFT Tc', status: info.v.status === 'adopted' ? 'done' : 'exploring',
      note: (ens ? ens.scores.tc_mae : info.v.scores.tc_mae).toFixed(2) + ' K' };
  };


  /* 5 · many models, and AI that designs them */
  const drawStoryModels = function drawStoryModels(c, C, B, t, narrow) {
    var a0 = stSpan(t, 0, 0.5), live = stLive();
    c.globalAlpha = a0;
    var fStatus = live.foundation === 'done' || live.foundationMae !== null ? 'done' : live.foundation === 'active' ? 'running' : 'next';
    var rows = [
      stormStoryRow(),
      { name: 'Gradient boosting', desc: '43 hand-made features', status: 'done', note: MAE_BASELINE.toFixed(2) + ' K' },
      { name: 'MACE-MP-0 + boosting', desc: 'foundation-model fingerprint', status: fStatus, note: live.foundationMae !== null ? live.foundationMae.toFixed(2) + ' K' : '' },
      (function () { var gi = gnnInfo(); return { name: gi.name, desc: 'crystal-graph network', status: gi.status === 'done' ? 'done' : gi.status === 'training' || gi.status === 'active' ? 'running' : gi.status === 'experimental' ? 'exploring' : 'planned', note: gi.mae !== null ? gi.mae.toFixed(2) + ' K' : '' }; })(),
      hurStoryRow(narrow, live)
    ];
    var Z = narrow ? { x: B.x, y: B.y + 4, w: B.w } : { x: B.x, y: B.y + 10, w: Math.round(B.w * 0.5) };
    var rh = narrow ? 27 : 36;
    label(c, C, 'Models we are trying', Z.x, Z.y + 10, { size: 12.5, weight: '600', color: C.ink });
    if (!narrow) stText(c, C, 'avg. Tc error', Z.x + Z.w - 12, Z.y + 10, { align: 'right', size: 11, color: C.muted });
    var stCol = { done: C.accent, running: C.accent, next: C.muted, planned: C.muted, exploring: C.warm };
    rows.forEach(function (r, i) {
      var a = stSpan(t, 0.5 + 0.35 * i, 0.9 + 0.35 * i);
      if (a <= 0) return;
      c.globalAlpha = a0 * a;
      var y = Z.y + 22 + i * rh;
      stRound(c, Z.x, y, Z.w, rh - 6, 8); c.fillStyle = C.surface2; c.fill();
      var midY = y + (rh - 6) / 2;
      var on = r.status === 'done' || r.status === 'running';
      if (r.status === 'running' && motionOK()) {
        c.save(); c.strokeStyle = C.accent; c.lineWidth = 2; c.beginPath(); c.arc(Z.x + 14, midY, 5, t * 5, t * 5 + 4.2); c.stroke(); c.restore();
      } else dot(c, Z.x + 14, midY, 4.5, on || r.status === 'exploring' ? stCol[r.status] : C.surface, stCol[r.status]);
      label(c, C, r.name, Z.x + 28, narrow ? midY + 4 : midY - 2, { size: narrow ? 12 : 12.5, weight: '600', color: C.ink });
      if (!narrow) label(c, C, r.desc, Z.x + 28, midY + 12, { size: 11, color: C.muted });
      var right = r.note || r.status;
      label(c, C, right, Z.x + Z.w - 12, midY + 4, { align: 'right', size: 12, weight: r.note ? '600' : '400', color: r.note ? C.ink : C.ink2 });
    });
    var Lp = narrow ? { cx: B.x + B.w / 2, cy: Z.y + 22 + 5 * rh + (B.h - (22 + 5 * rh)) / 2 + 2, R: Math.min(B.w * 0.22, (B.h - (26 + 5 * rh)) * 0.34) }
      : { cx: B.x + B.w * 0.78, cy: B.y + B.h * 0.5, R: Math.min(B.h * 0.32, B.w * 0.12) };
    var la = stSpan(t, 2.4, 3.0);
    if (la <= 0) return;
    c.globalAlpha = a0 * la;
    var steps = [['Propose', -Math.PI / 2], ['Train', 0], ['Evaluate', Math.PI / 2], ['Refine', Math.PI]];
    c.lineWidth = 1.5; c.strokeStyle = C.grid;
    c.beginPath(); c.arc(Lp.cx, Lp.cy, Lp.R, 0, Math.PI * 2); c.stroke();
    var per = 3.2, ang = -Math.PI / 2 + 2 * Math.PI * (((t - 2.4) % per) / per);
    steps.forEach(function (s) {
      var nx = Lp.cx + Lp.R * Math.cos(s[1]), ny = Lp.cy + Lp.R * Math.sin(s[1]);
      var dA = Math.abs(Math.atan2(Math.sin(ang - s[1]), Math.cos(ang - s[1])));
      var on = motionOK() ? stClamp(1 - dA / 0.7) : 0;
      dot(c, nx, ny, 5, on > 0.3 ? C.accent : C.surface, mix(C.axis, C.accent, on));
      var cosv = Math.cos(s[1]), sinv = Math.sin(s[1]);
      var tx = nx + cosv * 12, ty = ny + sinv * 12;
      label(c, C, s[0], tx, ty + (sinv < -0.5 ? -2 : sinv > 0.5 ? 2 : 0), { align: cosv > 0.5 ? 'left' : cosv < -0.5 ? 'right' : 'center', base: sinv > 0.5 ? 'top' : sinv < -0.5 ? 'alphabetic' : 'middle', size: 12, weight: '600', color: on > 0.5 ? C.accent : C.ink });
    });
    if (motionOK()) dot(c, Lp.cx + Lp.R * Math.cos(ang), Lp.cy + Lp.R * Math.sin(ang), 5, C.accent, C.surface);
    var hx = Lp.cx, hy = Lp.cy + 2, hw = 34, hh = 26;
    c.strokeStyle = C.accent; c.lineWidth = 1.5;
    c.beginPath(); c.moveTo(hx, hy - hh / 2); c.lineTo(hx, hy - hh / 2 - 8); c.stroke();
    dot(c, hx, hy - hh / 2 - 10, 3, C.accent);
    stRound(c, hx - hw / 2, hy - hh / 2, hw, hh, 8); c.fillStyle = C.surface; c.fill(); c.lineWidth = 2; c.strokeStyle = C.accent; c.stroke();
    var blink = motionOK() && (t % 3.1) < 0.12;
    if (blink) { c.fillStyle = C.accent; c.fillRect(hx - 9, hy - 1, 6, 2); c.fillRect(hx + 3, hy - 1, 6, 2); }
    else { dot(c, hx - 6, hy, 3, C.accent); dot(c, hx + 6, hy, 3, C.accent); }
    label(c, C, narrow ? 'AI designer' : 'AI designer · Storm and Hurricane', hx, hy + hh / 2 + 16, { align: 'center', size: 11.5, weight: '600', color: C.ink2 });
    if (!narrow) {
      c.globalAlpha = a0 * stSpan(t, 3.2, 3.8);
      stPara(c, C, 'Keeps a design only if it beats the current best on held-out materials in at least 4 of 5 folds.', Lp.cx, Lp.cy + Lp.R + 40, Math.min(300, B.w * 0.36), 16, { size: 11.5, color: C.muted, align: 'center' });
    }
  };


  /* 6 · how accurate? */
  const drawStoryAccuracy = function drawStoryAccuracy(c, C, B, t, narrow) {
    var a0 = stSpan(t, 0, 0.5), live = stLive();
    c.globalAlpha = a0;
    var S = !narrow ? Math.min(B.h - 48, B.w * 0.5) : Math.min(B.w - 56, B.h - 140);
    var px0 = B.x + 46, py0 = B.y + 6, VMAX = 25;
    function f(v) { return Math.sqrt(Math.max(0, Math.min(v, VMAX)) / VMAX); }
    function X(v) { return px0 + f(v) * S; }
    function Y(v) { return py0 + S - f(v) * S; }
    c.lineWidth = 1;
    [1, 4, 9, 16, 25].forEach(function (v) {
      var gx = Math.round(X(v)) + 0.5, gy = Math.round(Y(v)) + 0.5;
      c.strokeStyle = C.grid;
      c.beginPath(); c.moveTo(gx, py0); c.lineTo(gx, py0 + S); c.moveTo(px0, gy); c.lineTo(px0 + S, gy); c.stroke();
    });
    c.strokeStyle = C.axis;
    c.beginPath(); c.moveTo(px0 + 0.5, py0); c.lineTo(px0 + 0.5, py0 + S + 0.5); c.lineTo(px0 + S, py0 + S + 0.5); c.stroke();
    [0, 1, 4, 9, 16, 25].forEach(function (v) {
      label(c, C, String(v), X(v), py0 + S + 15, { align: 'center', size: 11, color: C.muted });
      label(c, C, String(v), px0 - 7, Y(v) + 4, { align: 'right', size: 11, color: C.muted });
    });
    stText(c, C, 'Tc from the full calculation (K)', px0 + S / 2, py0 + S + 32, { align: 'center', size: 11.5, color: C.ink2 });
    c.save(); c.translate(px0 - 30, py0 + S / 2); c.rotate(-Math.PI / 2);
    stText(c, C, 'Predicted Tc (K)', 0, 0, { align: 'center', base: 'middle', size: 11.5, color: C.ink2 });
    c.restore();
    c.setLineDash([5, 4]); c.strokeStyle = C.ink2; c.globalAlpha = a0 * 0.7;
    c.beginPath(); c.moveTo(X(0), Y(0)); c.lineTo(X(25), Y(25)); c.stroke(); c.setLineDash([]);
    c.globalAlpha = a0;
    c.save(); c.translate(X(13), Y(13)); c.rotate(-Math.PI / 4);
    label(c, C, 'perfect prediction', 0, -7, { align: 'center', size: 11, color: C.muted });
    c.restore();
    var meanA = 1 - stSpan(t, 2.6, 3.6);
    if (meanA > 0) {
      c.globalAlpha = a0 * meanA;
      c.setLineDash([3, 3]); c.strokeStyle = C.warm;
      c.beginPath(); c.moveTo(px0, Y(PARITY_MEAN)); c.lineTo(px0 + S, Y(PARITY_MEAN)); c.stroke(); c.setLineDash([]);
      label(c, C, 'guess the average', px0 + S - 4, Y(PARITY_MEAN) - 7, { align: 'right', size: 11.5, weight: '600', color: C.ink2 });
    }
    var n = PARITY.length / 2, appear = stSpan(t, 0.5, 1.4), fm = f(PARITY_MEAN);
    c.globalAlpha = a0 * appear * 0.6;
    c.fillStyle = C.accent;
    for (var i = 0; i < n; i++) {
      var ti = 2.0 + 2.6 * (i / n), k = stSpan(t, ti, ti + 0.8);
      var yS = fm + (f(PARITY[2 * i + 1]) - fm) * k;
      c.beginPath(); c.arc(X(PARITY[2 * i]), py0 + S - yS * S, narrow ? 2.3 : 2.8, 0, Math.PI * 2); c.fill();
    }
    c.globalAlpha = a0;
    var bestTxt = 'Hand-made baseline: ' + MAE_BASELINE.toFixed(2) + ' K';
    var note = 'Average error on whole chemical systems held out from training (5-fold cross-validation).';
    var modelA = stSpan(t, 4.6, 5.2);
    if (!narrow) {
      var x = px0 + S + 56, w = B.x + B.w - x, y = py0 + 30;
      stPara(c, C, 'Guessing the average for every material', x, y, w, 16, { size: 12, color: C.ink2 });
      label(c, C, MAE_GUESS.toFixed(2) + ' K', x, y + 40, { size: 26, weight: '700', color: C.muted });
      c.globalAlpha = a0 * modelA;
      label(c, C, 'Our AI model, ' + stormName(), x, y + 84, { size: 12, color: C.ink2 });
      label(c, C, stormMae().toFixed(2) + ' K', x, y + 120, { size: 26, weight: '700', color: C.accent });
      if (bestTxt) label(c, C, bestTxt, x, y + 146, { size: 12, weight: '600', color: C.ink });
      stPara(c, C, note, x, y + (bestTxt ? 172 : 152), Math.min(300, w), 16, { size: 11.5, color: C.muted });
    } else {
      var yy = py0 + S + 58, half = B.w / 2;
      label(c, C, 'Guess the average', B.x, yy, { size: 11.5, color: C.ink2 });
      label(c, C, MAE_GUESS.toFixed(2) + ' K', B.x, yy + 26, { size: 21, weight: '700', color: C.muted });
      c.globalAlpha = a0 * modelA;
      label(c, C, 'Our AI model, ' + stormName(), B.x + half, yy, { size: 11.5, color: C.ink2 });
      label(c, C, stormMae().toFixed(2) + ' K', B.x + half, yy + 26, { size: 21, weight: '700', color: C.accent });
      stPara(c, C, bestTxt ? bestTxt + '. ' + note : note, B.x, yy + 46, B.w, 15, { size: 11, color: C.muted });
    }
  };

  const drawStoryScreen = function drawStoryScreen(c, C, B, t, narrow) {
    var a0 = stSpan(t, 0, 0.5);
    c.globalAlpha = a0;
    var cols = narrow ? 12 : 20, rows = narrow ? 7 : 8;
    var GR = narrow ? { x: B.x, y: B.y + 22, w: B.w, h: Math.round(B.h * 0.5) } : { x: B.x, y: B.y + 24, w: Math.round(B.w * 0.62), h: B.h - 66 };
    var cell = Math.min(GR.w / cols, GR.h / rows), gap = Math.max(2, cell * 0.16);
    var gw = cell * cols, gh = cell * rows, gx0 = narrow ? GR.x + (GR.w - gw) / 2 : GR.x, gy0 = GR.y;
    var key = cols + 'x' + rows;
    if (!SCREEN_CACHE || SCREEN_CACHE.key !== key) {
      var rng = stRng(42), vals = [];
      for (var i = 0; i < cols * rows; i++) vals.push(Math.pow(rng(), 3));
      var order = vals.map(function (v, k) { return k; }).sort(function (a, b) { return vals[b] - vals[a]; });
      SCREEN_CACHE = { key: key, vals: vals, top: order.slice(0, 5) };
    }
    var vals2 = SCREEN_CACHE.vals, top = SCREEN_CACHE.top;
    label(c, C, 'Candidate crystals (illustration)', gx0, gy0 - 10, { size: 12, weight: '600', color: C.ink });
    var u = stClamp((t - 0.8) / 3.8), sx = gx0 + u * (gw + 30), base = hexRgb(C.surface2);
    for (var r = 0; r < rows; r++) {
      for (var k = 0; k < cols; k++) {
        var idx = r * cols + k, x = gx0 + k * cell, y = gy0 + r * cell;
        var lit = stClamp((sx - (x + cell / 2)) / 24);
        var rgb = rampColor(0.12 + 0.88 * Math.sqrt(vals2[idx]), C.dark);
        var col = [0, 1, 2].map(function (j) { return Math.round(base[j] + (rgb[j] - base[j]) * lit); });
        stRound(c, x + gap / 2, y + gap / 2, cell - gap, cell - gap, Math.min(4, cell * 0.2));
        c.fillStyle = stRgb(col); c.fill();
        if (lit < 1) { c.lineWidth = 1; c.strokeStyle = C.grid; c.stroke(); }
      }
    }
    if (u > 0 && u < 1 && sx <= gx0 + gw + 4) {
      c.fillStyle = stAlpha(C.accent, 0.12); c.fillRect(sx - 10, gy0 - 4, 10, gh + 8);
      c.strokeStyle = C.accent; c.lineWidth = 2; c.beginPath(); c.moveTo(sx, gy0 - 4); c.lineTo(sx, gy0 + gh + 4); c.stroke();
    }
    var ly = gy0 + gh + 18, lx0 = gx0, lw = Math.min(140, gw * 0.4);
    var lbw = stText(c, C, 'Predicted Tc', lx0, ly + 4, { size: 11, color: C.muted }) + 8;
    for (var q = 0; q <= 40; q++) { c.fillStyle = stRgb(rampColor(0.12 + 0.88 * q / 40, C.dark)); c.fillRect(lx0 + lbw + lw * q / 41, ly - 5, lw / 41 + 1, 10); }
    label(c, C, 'low', lx0 + lbw, ly + 18, { size: 10.5, color: C.muted });
    label(c, C, 'high', lx0 + lbw + lw, ly + 18, { align: 'right', size: 10.5, color: C.muted });
    var hl = stSpan(t, 4.9, 5.4);
    var V = narrow ? { x: B.x, y: ly + 34, w: B.w, h: B.y + B.h - (ly + 34) } : { x: B.x + Math.round(B.w * 0.68), y: gy0, w: B.w - Math.round(B.w * 0.68), h: Math.min(gh, 230) };
    if (hl > 0) {
      stRound(c, V.x, V.y, V.w, V.h, 12); c.fillStyle = C.surface2; c.fill(); c.lineWidth = 1; c.strokeStyle = C.axis; c.stroke();
      label(c, C, 'Verify with the full calculation', V.x + 14, V.y + 22, { size: 12.5, weight: '600', color: C.ink });
      if (!narrow) label(c, C, 'only the most promising few', V.x + 14, V.y + 39, { size: 11.5, color: C.muted });
    }
    top.forEach(function (idx, rank) {
      var r = Math.floor(idx / cols), k = idx % cols, x = gx0 + k * cell, y = gy0 + r * cell;
      if (hl > 0) {
        c.globalAlpha = a0 * hl; c.lineWidth = 2; c.strokeStyle = C.ink;
        stRound(c, x + 1, y + 1, cell - 2, cell - 2, 5); c.stroke();
      }
      var p = stSpan(t, 5.8 + 0.15 * rank, 6.6 + 0.15 * rank);
      if (p <= 0) return;
      var tx, ty;
      if (narrow) { tx = V.x + 22 + rank * ((V.w - 44) / 4); ty = V.y + 52; }
      else { tx = V.x + 26; ty = V.y + 64 + rank * 32; }
      var sx0 = x + cell / 2, sy0 = y + cell / 2;
      var px = sx0 + (tx - sx0) * p, py = sy0 + (ty - sy0) * p - Math.sin(p * Math.PI) * 40;
      var sz = (cell - gap) + (16 - (cell - gap)) * p;
      c.globalAlpha = a0;
      stRound(c, px - sz / 2, py - sz / 2, sz, sz, 4);
      c.fillStyle = stRgb(rampColor(0.12 + 0.88 * Math.sqrt(vals2[idx]), C.dark)); c.fill();
      if (p >= 1) {
        if (narrow) label(c, C, '#' + (rank + 1), tx, ty + 24, { align: 'center', size: 11.5, weight: '600', color: C.ink });
        else {
          label(c, C, 'Candidate ' + (rank + 1), tx + 18, ty + 4, { size: 12.5, weight: '600', color: C.ink });
          label(c, C, 'checking…', V.x + V.w - 40, ty + 4, { align: 'right', size: 11.5, color: C.muted });
        }
        var sa = motionOK() ? t * 4 + rank : 0;
        var spx = narrow ? tx + 14 : V.x + V.w - 24, spy = narrow ? ty - 14 : ty;
        c.save(); c.strokeStyle = C.accent; c.lineWidth = 1.8; c.beginPath(); c.arc(spx, spy, 5, sa, sa + 4.2); c.stroke(); c.restore();
      }
    });
  };


  /* 8 · beyond phonons */
  const drawStoryBeyond = function drawStoryBeyond(c, C, B, t, narrow) {
    var a0 = stSpan(t, 0, 0.5), P1, P2, bottomY;
    if (!narrow) {
      var pw = (B.w - 24) / 2, ph = B.h - 58;
      P1 = { x: B.x, y: B.y, w: pw, h: ph }; P2 = { x: B.x + pw + 24, y: B.y, w: pw, h: ph }; bottomY = B.y + ph + 34;
    } else {
      var ph2 = (B.h - 70) / 2;
      P1 = { x: B.x, y: B.y, w: B.w, h: ph2 }; P2 = { x: B.x, y: B.y + ph2 + 12, w: B.w, h: ph2 }; bottomY = B.y + 2 * ph2 + 46;
    }
    function panel(P, a, title, sub, foot) {
      c.globalAlpha = a0 * a;
      stRound(c, P.x, P.y, P.w, P.h, 12); c.fillStyle = C.surface2; c.fill();
      label(c, C, title, P.x + 14, P.y + 24, { size: 13.5, weight: '600', color: C.ink });
      label(c, C, sub, P.x + 14, P.y + 42, { size: 12, color: C.ink2 });
      stText(c, C, foot, P.x + 14, P.y + P.h - 12, { size: 11.5, color: C.muted });
    }
    var a1 = stSpan(t, 0.2, 0.8), a2 = stSpan(t, 1.6, 2.2);
    panel(P1, a1, 'Conventional', 'Glue: lattice vibrations (phonons)', 'Storm learns from computed λ and ω_log');
    if (a1 > 0) {
      var top1 = P1.y + 54, bot1 = P1.y + P1.h - 28, cyv = (top1 + bot1) / 2;
      var n1 = Math.max(6, Math.floor((P1.w - 28) / 28)), dxx = (P1.w - 28) / n1;
      c.save(); c.beginPath(); c.rect(P1.x, top1 - 6, P1.w, bot1 - top1 + 12); c.clip();
      var rsp = Math.min(44, (bot1 - top1) / 3);
      [-1, 0, 1].forEach(function (row) {
        for (var k = 0; k <= n1; k++) {
          var x = P1.x + 14 + k * dxx, ph0 = k * 0.75 - t * 3;
          var y = cyv + row * rsp + 5 * Math.sin(ph0 + row);
          stIon(c, C, x, y, 5.5, 0.5 + 0.5 * Math.sin(ph0));
        }
      });
      var ex = P1.x + 14 + ((t * 45) % (P1.w - 28));
      c.globalAlpha = a0 * a1 * 0.9; c.setLineDash([3, 4]); c.strokeStyle = C.accent; c.lineWidth = 1.4;
      var ey = cyv + rsp / 2;
      c.beginPath(); c.moveTo(ex - 34, ey); c.quadraticCurveTo(ex - 17, ey - 16, ex, ey); c.stroke(); c.setLineDash([]);
      c.globalAlpha = a0 * a1;
      stElectron(c, C, ex - 34, ey, 5.5); stElectron(c, C, ex, ey, 5.5);
      c.restore();
    }
    panel(P2, a2, 'Unconventional: cuprates, iron-based', 'Glue: still debated (spin fluctuations?)', 'Hurricane learns from measured Tc');
    if (a2 > 0) {
      var top2 = P2.y + 56, bot2 = P2.y + P2.h - 30;
      var a = Math.max(30, Math.min(56, (bot2 - top2) / 2.2));
      var nx = Math.min(8, Math.max(4, Math.floor((P2.w - 40) / a))), ny = Math.min(3, Math.max(2, Math.floor((bot2 - top2) / a) + 1));
      var gx0 = P2.x + (P2.w - (nx - 1) * a) / 2, gy0 = top2 + ((bot2 - top2) - (ny - 1) * a) / 2;
      c.globalAlpha = a0 * a2;
      for (var j = 0; j < ny; j++) for (var i = 0; i < nx; i++) {
        if (i < nx - 1) dot(c, gx0 + (i + 0.5) * a, gy0 + j * a, 3, C.muted);
        if (j < ny - 1) dot(c, gx0 + i * a, gy0 + (j + 0.5) * a, 3, C.muted);
      }
      for (var jj = 0; jj < ny; jj++) for (var ii = 0; ii < nx; ii++) {
        var x2 = gx0 + ii * a, y2 = gy0 + jj * a;
        dot(c, x2, y2, 6, C.warm);
        var up = (ii + jj) % 2 === 0, base = up ? -Math.PI / 2 : Math.PI / 2;
        var fl = motionOK() ? 0.5 * Math.sin(1.7 * t + ii * 1.3 + jj * 2.1) : 0;
        var an2 = base + fl, L2 = a * 0.26;
        stArrow(c, x2 - Math.cos(an2) * L2, y2 - Math.sin(an2) * L2, x2 + Math.cos(an2) * L2, y2 + Math.sin(an2) * L2, C.ink, 5);
      }
      if (!narrow) {
        label(c, C, 'Cu', P2.x + P2.w - 70, P2.y + 24, { size: 11, color: C.muted });
        dot(c, P2.x + P2.w - 78, P2.y + 20, 4, C.warm);
        label(c, C, 'O', P2.x + P2.w - 32, P2.y + 24, { size: 11, color: C.muted });
        dot(c, P2.x + P2.w - 40, P2.y + 20, 2.5, C.muted);
      }
    }
    var a3 = stSpan(t, 4.0, 4.7);
    if (a3 > 0) {
      c.globalAlpha = a0 * a3;
      var txt = 'Comparing what the two models rely on can point to the pairing mechanism';
      if (!narrow) {
        stArrow(c, P1.x + P1.w / 2, P1.y + P1.h + 4, B.x + B.w / 2 - 30, bottomY - 14, C.axis, 6);
        stArrow(c, P2.x + P2.w / 2, P2.y + P2.h + 4, B.x + B.w / 2 + 30, bottomY - 14, C.axis, 6);
        dot(c, B.x + B.w / 2, bottomY - 4, 9, C.surface, C.warm);
        label(c, C, '?', B.x + B.w / 2, bottomY - 3, { align: 'center', base: 'middle', size: 11, weight: '700', color: C.warm });
        label(c, C, txt, B.x + B.w / 2, bottomY + 20, { align: 'center', size: 12.5, weight: '600', color: C.ink });
      } else stPara(c, C, txt, B.x + B.w / 2, bottomY, B.w, 16, { size: 12, weight: '600', color: C.ink, align: 'center' });
    }
  };


  /* 9 · the loop */
  const drawStoryLoop = function drawStoryLoop(c, C, B, t, narrow) {
    var a0 = stSpan(t, 0, 0.5), live = stLive();
    c.globalAlpha = a0;
    var cx = narrow ? B.x + B.w / 2 : B.x + B.w * 0.3, cy = narrow ? B.y + B.h * 0.36 : B.y + B.h * 0.5;
    var R = narrow ? Math.min(B.w * 0.24, B.h * 0.25) : Math.min(B.h * 0.34, B.w * 0.17);
    var nr = narrow ? 20 : 24;
    var steps = [['Predict', -Math.PI / 2], ['Screen', 0], ['Verify', Math.PI / 2], ['Learn', Math.PI]];
    c.lineWidth = 2; c.strokeStyle = C.grid;
    c.beginPath(); c.arc(cx, cy, R, 0, Math.PI * 2); c.stroke();
    steps.forEach(function (s) {
      var am = s[1] + Math.PI / 4, hx = cx + R * Math.cos(am), hy = cy + R * Math.sin(am), tg = am + Math.PI / 2;
      c.fillStyle = C.axis; c.beginPath();
      c.moveTo(hx + Math.cos(tg) * 6, hy + Math.sin(tg) * 6);
      c.lineTo(hx + Math.cos(tg + 2.5) * 6, hy + Math.sin(tg + 2.5) * 6);
      c.lineTo(hx + Math.cos(tg - 2.5) * 6, hy + Math.sin(tg - 2.5) * 6);
      c.closePath(); c.fill();
    });
    var per = 4, ang = -Math.PI / 2 + 2 * Math.PI * ((t % per) / per);
    steps.forEach(function (s, i) {
      var nx = cx + R * Math.cos(s[1]), ny = cy + R * Math.sin(s[1]);
      var dA = Math.abs(Math.atan2(Math.sin(ang - s[1]), Math.cos(ang - s[1])));
      var on = motionOK() ? stClamp(1 - dA / 0.6) : (i === 0 ? 1 : 0);
      dot(c, nx, ny, nr, mix(C.surface, C.accent, 0.16 * on), mix(C.axis, C.accent, on));
      label(c, C, String(i + 1), nx, ny + 1, { align: 'center', base: 'middle', size: 14, weight: '700', color: on > 0.5 ? C.accent : C.ink2 });
      var cosv = Math.cos(s[1]), sinv = Math.sin(s[1]);
      var lx = nx + cosv * (nr + 10), ly = ny + sinv * (nr + 10);
      label(c, C, s[0], lx, ly + (sinv < -0.5 ? -2 : 0), { align: cosv > 0.5 ? 'left' : cosv < -0.5 ? 'right' : 'center', base: sinv > 0.5 ? 'top' : sinv < -0.5 ? 'alphabetic' : 'middle', size: 13, weight: '600', color: C.ink });
    });
    if (motionOK()) dot(c, cx + R * Math.cos(ang), cy + R * Math.sin(ang), 6, C.accent, C.surface);
    label(c, C, 'Each round', cx, cy - 3, { align: 'center', size: 12, color: C.ink2 });
    label(c, C, 'improves the model', cx, cy + 13, { align: 'center', size: 12, color: C.ink2 });
    var lines = [];
    if (live.now) lines.push(['Now working on', live.now]);
    if (live.release) lines.push(['Next milestone', 'v0.1 on ' + fmtDay(live.release)]);
    lines.push(['Code and data', 'github.com/' + REPO]);
    c.globalAlpha = a0 * stSpan(t, 1.0, 1.6);
    if (!narrow) {
      var x = cx + R + nr + 110, y = B.y + B.h * 0.24;
      if (B.x + B.w - x > 220) {
        label(c, C, 'Follow along', x, y, { size: 16, weight: '600', color: C.ink });
        lines.forEach(function (ln, i) {
          label(c, C, ln[0], x, y + 34 + i * 44, { size: 11.5, color: C.muted });
          label(c, C, ln[1], x, y + 52 + i * 44, { size: 13.5, weight: '600', color: C.ink });
        });
        label(c, C, 'The Progress tab shows every training run.', x, y + 52 + lines.length * 44, { size: 12.5, color: C.ink2 });
      }
    } else {
      var yy = cy + R + nr + 40;
      lines.forEach(function (ln, i) {
        label(c, C, ln[0] + ': ' + ln[1], cx, yy + i * 19, { align: 'center', size: 12, color: i < lines.length - 1 ? C.ink : C.ink2, weight: i < lines.length - 1 ? '600' : '400' });
      });
    }
  };
