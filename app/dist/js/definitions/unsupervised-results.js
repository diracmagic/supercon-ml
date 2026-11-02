'use strict';
// Audited, fixed results. Motion changes emphasis only, never numerical values.

  const unsupervisedResults = function unsupervisedResults() {
    return [
      { id: 'storm-mae', model: 'Storm 7', metric: 'DFT Tc error', direction: 'Lower is better', unit: ' K', digits: 3,
        before: 0.9674607593639637, after: 0.9747182910305756, max: 1.2,
        delta: '+0.0073 K', interval: '95% interval for change: -0.0036 to +0.0166 K',
        scope: '7,582 materials / 4,288 chemical systems' },
      { id: 'hurricane-auc', model: 'Hurricane 8', metric: 'Held-family ranking AUC', direction: 'Higher is better', unit: '', digits: 3,
        before: 0.6040009458817508, after: 0.6008997675251545, max: 1,
        delta: '-0.0031', interval: '95% interval for change: -0.0273 to +0.0224',
        scope: '615 parents / 4 held-out families' },
      { id: 'hurricane-recall', model: 'Hurricane 8', metric: 'Recall in the top 20%', direction: 'Higher is better', unit: '%', digits: 1,
        before: 24.774029982363316, after: 25.380939412802156, max: 100,
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

  const drawUnsupervisedResults = function drawUnsupervisedResults(c, C) {
    var W = demo.W, H = demo.H, narrow = W < 560, rows = unsupervisedResults();
    var x = 16, right = W - 16, width = right - x, cardH = narrow ? 164 : 126, top = 70;
    label(c, C, 'Unsupervised learning: results', x, 25, { size: narrow ? 15 : 19, weight: '600', color: C.ink });
    label(c, C, 'No substantive improvement demonstrated', x, 46, { size: narrow ? 11 : 13, color: C.ink2 });
    rows.forEach(function (r, i) {
      var y = top + i * cardH, active = motionOK() && demo.unsupPlay && Math.floor(demo.clock / 3) % rows.length === i;
      stRound(c, x - 4, y - 14, width + 8, cardH - 4, 10);
      c.fillStyle = C.surface2; c.fill();
      c.lineWidth = 1; c.strokeStyle = C.grid; c.stroke();
      if (active) {
        c.globalAlpha = .25 + .55 * Math.pow(Math.sin(Math.PI * (demo.clock % 3) / 3), 2);
        stRound(c, x - 4, y - 14, width + 8, cardH - 4, 10);
        c.strokeStyle = C.accent; c.lineWidth = 1.5; c.stroke(); c.globalAlpha = 1;
      }
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
