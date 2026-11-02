'use strict';
// Audited, fixed results. Motion changes emphasis only, never numerical values.

  const unsupervisedResults = function unsupervisedResults() {
    return [
      { id: 'storm-mae', model: 'Storm 7', metric: 'DFT Tc error', direction: 'Lower is better', unit: ' K', digits: 3,
        before: 0.9674607593639637, after: 0.9747182910305756, max: 1.2,
        change: 0.007257531666612158, lower: -0.00355736023799987, upper: 0.016609831510670154, changeRange: 0.02,
        delta: '+0.0073 K', interval: '95% interval for change: -0.0036 to +0.0166 K',
        scope: '7,582 materials / 4,288 chemical systems' },
      { id: 'hurricane-auc', model: 'Hurricane 8', metric: 'Held-family ranking AUC', direction: 'Higher is better', unit: '', digits: 3,
        before: 0.6040009458817508, after: 0.6008997675251545, max: 1,
        change: -0.0031011783565962903, lower: -0.027277006205176795, upper: 0.02239836523889876, changeRange: 0.04,
        delta: '-0.0031', interval: '95% interval for change: -0.0273 to +0.0224',
        scope: '615 parents / 4 held-out families' },
      { id: 'hurricane-recall', model: 'Hurricane 8', metric: 'Recall in the top 20%', direction: 'Higher is better', unit: '%', digits: 1,
        before: 24.774029982363316, after: 25.380939412802156, max: 100,
        change: 0.6069094304388401, lower: -2.7122548816885535, upper: 2.697012769490175, changeRange: 4,
        delta: '+0.61 percentage points', interval: '95% interval for change: -2.71 to +2.70 pp',
        scope: 'Equal-family average / recorded positives' }
    ];
  };

  const unsupervisedCaption = function unsupervisedCaption() {
    return 'Completed 2 Nov 2026. Storm 7 DFT Tc MAE: 0.967 K to 0.975 K. Hurricane 8 held-family ranking AUC: 0.604 to 0.601; recall within the top 20%: 24.8% to 25.4%. All paired 95% intervals for change include zero. No substantive improvement demonstrated; no new model adopted. Each comparison uses its own matched U0 baseline. Released models are unchanged. Storm uses computed Tc. Hurricane ranks recorded positives against unlabeled parents; its scores are not superconductivity probabilities. The reused folds and families make this an exploratory comparison, not a new blind test.';
  };

  const renderUnsupervisedReferences = function renderUnsupervisedReferences(el) {
    clear(el);
    el.hidden = false;
    el.appendChild(h('p', { class: 'refs-title', text: 'Method context and references' }));
    el.appendChild(h('p', { class: 'note', text: 'Method context and prior work. Earlier studies used clustering to explore superconductor families and SVD/PCA before supervised Tc prediction. Our comparison adds 16 KMeans-RBF prototype similarities fitted on training features only, keeps the prediction head unchanged, and evaluates the added value with chemical-system/family holdouts and paired system resampling. This is a test of an existing research direction; the results above do not establish a superconductivity mechanism.' }));
    modelMethodSources().filter(function (r) { return r.id === 'roter2022-clustering' || r.id === 'roter2020-pca'; }).forEach(function (r) {
      el.appendChild(h('p', null, h('a', { href: r.url, text: r.title }), ' | ' + r.citation));
    });
    el.appendChild(h('p', null, h('a', { href: 'https://github.com/diracmagic/supercon-ml/pull/17', text: 'Frozen comparison, complete results and independent audit' })));
  };

  const goUnsupervisedStep = function goUnsupervisedStep(index) {
    demo.unsupStage = ((Math.floor(index) % 4) + 4) % 4;
    demo.unsupT = 0;
    syncControls(); kick();
  };

  const drawUnsupervisedSummary = function drawUnsupervisedSummary(c, C) {
    var W = demo.W, H = demo.H, narrow = W < 560, rows = unsupervisedResults();
    var x = 16, right = W - 16, width = right - x, cardH = narrow ? 164 : 126, top = 70;
    label(c, C, 'Unsupervised learning: results', x, 25, { size: narrow ? 15 : 19, weight: '600', color: C.ink });
    label(c, C, 'No substantive improvement demonstrated', x, 46, { size: narrow ? 11 : 13, color: C.ink2 });
    rows.forEach(function (r, i) {
      var y = top + i * cardH;
      stRound(c, x - 4, y - 14, width + 8, cardH - 4, 10);
      c.fillStyle = C.surface2; c.fill();
      c.lineWidth = 1; c.strokeStyle = C.grid; c.stroke();
      label(c, C, r.model + ' / ' + r.metric, x, y, { size: narrow ? 11.5 : 13, weight: '600', color: C.ink });
      label(c, C, r.direction, x, y + 18, { size: 10.5, color: C.muted });
      var valueWidth = 59, plotX = x + 89, plotWidth = Math.max(50, right - plotX - valueWidth);
      [[r.before, 'Baseline', C.accent], [r.after, '+ Unsupervised', C.warm]].forEach(function (v, j) {
        var by = y + 37 + j * 22;
        label(c, C, v[1], x, by + 4, { size: 10, color: C.ink2 });
        stRound(c, plotX, by - 5, plotWidth, 9, 4.5); c.fillStyle = C.grid; c.fill();
        stRound(c, plotX, by - 5, plotWidth * v[0] / r.max, 9, 4.5); c.fillStyle = v[2]; c.fill();
        label(c, C, v[0].toFixed(r.digits) + r.unit, right, by + 4, { align: 'right', size: 11.5, weight: '600', color: C.ink });
      });
      label(c, C, 'Change: ' + r.delta, x, y + 87, { size: 10.5, color: C.ink2 });
      stPara(c, C, r.interval, x, y + 103, width, 14, { size: 10.5, color: C.ink2 });
      if (narrow) label(c, C, r.scope, x, y + 136, { size: 10.5, color: C.muted });
      else label(c, C, r.scope, right, y + 18, { align: 'right', size: 10.5, color: C.muted });
    });
    label(c, C, 'All change intervals include zero.', x, H - 30, { size: narrow ? 11 : 12, weight: '600', color: C.ink });
    label(c, C, 'No new model adopted.', x, H - 11, { size: narrow ? 11 : 12, color: C.ink2 });
    demo.canvas.setAttribute('aria-label', unsupervisedCaption());
  };

  const drawUnsupervisedResults = function drawUnsupervisedResults(c, C) {
    if (!motionOK() || demo.unsupStage === 3) { drawUnsupervisedSummary(c, C); return; }
    var W = demo.W, H = demo.H, narrow = W < 560, r = unsupervisedResults()[demo.unsupStage || 0];
    var left = 24, right = W - 24, width = right - left, time = demo.unsupT || 0;
    function reveal(start, duration) { var x = Math.max(0, Math.min(1, (time - start) / duration)); return 1 - Math.pow(1 - x, 3); }
    var names = ['Storm', 'Ranking', 'Recall', 'Conclusion'], gap = 7, segment = (width - gap * 3) / 4;
    names.forEach(function (name, i) {
      var sx = left + i * (segment + gap);
      stRound(c, sx, 17, segment, 4, 2); c.fillStyle = i === demo.unsupStage ? C.accent : C.grid; c.fill();
      label(c, C, name, sx + segment / 2, 38, { align: 'center', size: narrow ? 10 : 11, color: i === demo.unsupStage ? C.ink : C.muted });
    });
    var titleLines = stPara(c, C, r.model + ': ' + r.metric, left, 77, width, 22, { size: narrow ? 15 : 21, weight: '600', color: C.ink });
    var scopeY = 100 + (titleLines - 1) * 22;
    var scopeLines = stPara(c, C, r.scope + '. ' + r.direction + '.', left, scopeY, width, 17, { size: narrow ? 11 : 12, color: C.ink2 });
    var firstBarY = Math.max(155, scopeY + (scopeLines - 1) * 17 + 41);
    [[r.before, 'Baseline (U0)', C.accent, 0, firstBarY], [r.after, '+ Unsupervised (U1)', C.warm, 1.6, firstBarY + 66]].forEach(function (v) {
      label(c, C, v[1], left, v[4] - 12, { size: 12, color: C.ink2 });
      label(c, C, v[0].toFixed(r.digits) + r.unit, right, v[4] - 12, { align: 'right', size: 15, weight: '600', color: C.ink });
      stRound(c, left, v[4], width, 17, 8.5); c.fillStyle = C.grid; c.fill();
      var w = width * v[0] / r.max * reveal(v[3], 1.5);
      if (w > 0) { stRound(c, left, v[4], w, 17, Math.min(8.5, w / 2)); c.fillStyle = v[2]; c.fill(); }
      if (w > 5) dot(c, left + w - 4, v[4] + 8.5, 2.2, C.surface);
    });
    var deltaY = firstBarY + 123;
    label(c, C, 'Change: ' + r.delta, left, deltaY, { size: narrow ? 14 : 18, weight: '600', color: C.ink });
    var panelY = deltaY + 25, panelH = narrow ? 158 : 126;
    stRound(c, left - 7, panelY, width + 14, panelH, 12); c.fillStyle = C.surface2; c.fill();
    label(c, C, 'Paired 95% interval for the change', left + 3, panelY + 24, { size: narrow ? 11 : 13, weight: '600', color: C.ink });
    var axisLeft = left + 15, axisRight = right - 15, axisY = panelY + 62;
    function X(v) { return axisLeft + (v + r.changeRange) / (2 * r.changeRange) * (axisRight - axisLeft); }
    c.strokeStyle = C.axis; c.lineWidth = 1; c.beginPath(); c.moveTo(axisLeft, axisY); c.lineTo(axisRight, axisY); c.stroke();
    c.setLineDash([3, 4]); c.beginPath(); c.moveTo(X(0), axisY - 19); c.lineTo(X(0), axisY + 15); c.stroke(); c.setLineDash([]);
    label(c, C, '0', X(0), axisY + 30, { align: 'center', size: 11, color: C.muted });
    c.globalAlpha = reveal(3.4, 1.4); c.strokeStyle = C.accent; c.lineWidth = 3;
    c.beginPath(); c.moveTo(X(r.lower), axisY); c.lineTo(X(r.upper), axisY); c.stroke();
    [r.lower, r.upper].forEach(function (v) { c.beginPath(); c.moveTo(X(v), axisY - 6); c.lineTo(X(v), axisY + 6); c.stroke(); });
    dot(c, X(r.change), axisY, 6, C.warm, C.surface); c.globalAlpha = 1;
    stPara(c, C, r.interval.replace('95% interval for change: ', ''), left + 3, panelY + 113, width - 6, 15, { size: narrow ? 11 : 12, color: C.ink2 });
    var captionY = narrow ? H - 88 : H - 50;
    stPara(c, C, time < 1.6 ? '1 / Baseline result' : time < 3.4 ? '2 / Result with unsupervised features' : '3 / The interval includes zero: no stable gain.', left, captionY, width, 18, { size: narrow ? 11.5 : 13, weight: '600', color: C.ink });
    label(c, C, 'Numbers stay fixed during animation.', left, H - 18, { size: narrow ? 10 : 11, color: C.muted });
    demo.canvas.setAttribute('aria-label', r.model + ', result ' + ((demo.unsupStage || 0) + 1) + ' of 4. ' + r.metric + ': ' + r.before.toFixed(r.digits) + r.unit + ' to ' + r.after.toFixed(r.digits) + r.unit + '. ' + r.interval + '. The interval includes zero. No new model adopted.');
  };
