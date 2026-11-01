'use strict';
// demo-player: shared lexical function definitions; no startup side effects.


  const demoDef = function demoDef() { return DEMOS.filter(function (d) { return d.id === demo.id; })[0]; };

  const gapRatio = function gapRatio(t) { return t >= 1 ? 0 : Math.tanh(1.74 * Math.sqrt(1 / Math.max(t, 1e-3) - 1)); };

  const allenDynes = function allenDynes(lam, wlog, mu) {
    var d = lam - mu * (1 + 0.62 * lam);
    return d > 0 ? (wlog / 1.2) * Math.exp(-1.04 * (1 + lam) / d) : 0;
  };

  const cssVar = function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); };

  const colors = function colors() {
    return {
      aqua: cssVar('--series-3'), gold: cssVar('--gold'), surface: cssVar('--surface'), surface2: cssVar('--surface-2'), ink: cssVar('--ink'), ink2: cssVar('--ink-2'),
      muted: cssVar('--muted'), grid: cssVar('--grid'), axis: cssVar('--axis'), accent: cssVar('--accent'),
      track: cssVar('--accent-track'), warm: cssVar('--warm'), font: cssVar('--font') || 'system-ui, sans-serif',
      dark: document.documentElement.getAttribute('data-theme') === 'dark' ||
        (document.documentElement.getAttribute('data-theme') !== 'light' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches)
    };
  };

  const hexRgb = function hexRgb(hex) {
    var m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || '');
    return m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : [128, 128, 128];
  };

  const mix = function mix(a, b, k) {
    var x = hexRgb(a), y = hexRgb(b);
    return 'rgb(' + [0, 1, 2].map(function (i) { return Math.round(x[i] + (y[i] - x[i]) * k); }).join(',') + ')';
  };

  const rampColor = function rampColor(v, dark) {
    var stops = dark ? RAMP_LIGHT.slice().reverse() : RAMP_LIGHT;
    var p = Math.max(0, Math.min(1, v)) * (stops.length - 1);
    var i = Math.min(stops.length - 2, Math.floor(p));
    var a = hexRgb(stops[i]), b = hexRgb(stops[i + 1]), k = p - i;
    return [0, 1, 2].map(function (j) { return Math.round(a[j] + (b[j] - a[j]) * k); });
  };

  const motionOK = function motionOK() { return !reducedMotion(); };


  const buildDemos = function buildDemos() {
    var el = $('#demos');
    clear(el);
    var tabs = h('div', { class: 'demo-tabs', role: 'tablist', 'aria-label': 'Demos' });
    DEMOS.forEach(function (d) {
      tabs.appendChild(h('button', {
        class: 'demo-tab', type: 'button', role: 'tab', 'data-id': d.id,
        'aria-selected': d.id === demo.id ? 'true' : 'false', text: d.label,
        onclick: function () { selectDemo(d.id); }
      }));
    });
    var canvas = h('canvas', { role: 'img' });
    var stage = h('div', { class: 'demo-stage' }, canvas);
    var play = h('button', { class: 'btn', type: 'button', id: 'demo-play', onclick: function () { demo.auto = !demo.auto; syncControls(); kick(); } });
    var tempIn = h('input', { type: 'range', min: '0.2', max: '1.6', step: '0.01', id: 'demo-temp', 'aria-label': 'Temperature as a fraction of Tc' });
    tempIn.addEventListener('input', function () { demo.t = parseFloat(tempIn.value); demo.auto = false; syncControls(); kick(); });
    var tempOut = h('output', { id: 'demo-temp-out' });
    var tempRow = h('div', { class: 'demo-controls', id: 'demo-temp-row' },
      play,
      h('label', { class: 'slider' }, h('span', { text: 'Temperature' }), tempIn, tempOut),
      h('span', { class: 'demo-readout', id: 'demo-readout' }));
    function slider(id, labelText, min, max, step, key, fmtv) {
      var input = h('input', { type: 'range', min: String(min), max: String(max), step: String(step), id: id, 'aria-label': labelText });
      var out = h('output', { id: id + '-out' });
      input.addEventListener('input', function () { demo[key] = parseFloat(input.value); syncControls(); kick(); });
      out.fmt = fmtv;
      return h('label', { class: 'slider' }, h('span', { text: labelText }), input, out);
    }
    var predSeg = h('div', { class: 'seg', role: 'group', 'aria-label': 'What to show', id: 'pred-seg' });
    PRED_MODES.forEach(function (m) { predSeg.appendChild(h('button', { type: 'button', 'data-pred': m[0], onclick: function () { setPredMode(m[0]); } }, m[1])); });
    var adRow = h('div', { class: 'demo-controls', id: 'demo-ad-row' },
      predSeg,
      h('button', { class: 'btn', type: 'button', id: 'pred-play', onclick: function () { demo.predPlay = !demo.predPlay; syncControls(); kick(); } }),
      h('button', { class: 'btn', type: 'button', id: 'pred-next', onclick: function () { predNext(); } }, 'Next'),
      h('span', { class: 'pred-sliders', id: 'pred-sliders' },
        slider('demo-lam', 'λ', 0.1, 2.5, 0.01, 'lam', function (v) { return v.toFixed(2); }),
        slider('demo-wlog', 'ω_log', 20, 1000, 5, 'wlog', function (v) { return Math.round(v) + ' K'; }),
        slider('demo-mu', 'μ*', 0.05, 0.2, 0.005, 'mu', function (v) { return v.toFixed(3); })),
      h('span', { class: 'demo-readout', id: 'demo-ad-readout' }));
    var storyRow = h('div', { class: 'demo-controls', id: 'demo-story-row' },
      h('button', { class: 'btn icon-only', type: 'button', id: 'story-prev', 'aria-label': 'Previous step', title: 'Previous step', onclick: function () { goScene(demo.scene - 1); } }),
      h('button', { class: 'btn', type: 'button', id: 'story-play', onclick: function () { demo.storyPlay = !demo.storyPlay; syncControls(); kick(); } }),
      h('button', { class: 'btn icon-only', type: 'button', id: 'story-next', 'aria-label': 'Next step', title: 'Next step', onclick: function () { goScene(demo.scene + 1); } }),
      h('span', { class: 'demo-readout', id: 'story-readout' }));
    var seg = h('div', { class: 'seg', role: 'group', 'aria-label': 'Baseline for' });
    MODEL_VARIANTS.forEach(function (m) { seg.appendChild(h('button', { type: 'button', 'data-variant': m[0], onclick: function () { setModelVariant(m[0]); } }, m[1])); });
    var modelRow = h('div', { class: 'demo-controls', id: 'demo-model-row' },
      seg,
      h('button', { class: 'btn', type: 'button', id: 'model-play', onclick: function () { demo.modelPlay = !demo.modelPlay; syncControls(); kick(); } }),
      h('span', { class: 'demo-readout', id: 'model-readout' }));
    var stormRow = h('div', { class: 'demo-controls', id: 'demo-storm-row' },
      h('div', { class: 'seg', role: 'group', 'aria-label': 'Storm version', id: 'storm-seg' }),
      h('button', { class: 'btn', type: 'button', id: 'storm-play', onclick: function () { demo.stormPlay = !demo.stormPlay; syncControls(); kick(); } }),
      h('span', { class: 'demo-readout', id: 'storm-readout' }));
    var hurRow = h('div', { class: 'demo-controls', id: 'demo-hur-row' },
      h('button', { class: 'btn', type: 'button', id: 'hur-play', onclick: function () { demo.hurPlay = !demo.hurPlay; syncControls(); kick(); } }),
      h('span', { class: 'demo-readout', id: 'hur-readout' }));
    var radRow = h('div', { class: 'demo-controls', id: 'demo-rad-row' },
      h('button', { class: 'btn', type: 'button', id: 'rad-play', onclick: function () { demo.radPlay = !demo.radPlay; syncControls(); kick(); } }),
      h('span', { class: 'demo-readout', id: 'rad-readout' }));
    var caption = h('p', { class: 'demo-caption', id: 'demo-caption' });
    var zoo = h('div', { class: 'zoo', id: 'demo-zoo' });
    var refs = h('div', { class: 'demo-refs', id: 'demo-refs' });
    append(el, [
      h('div', { class: 'card-head' }, h('div', null,
        h('h2', null, 'Hello ', h('span', { class: 'hs-accent', text: 'Super' })),
        h('p', { text: 'Our project in 90 seconds, how our AI models work, and the physics behind it.' }))),
      tabs, stage, tempRow, adRow, storyRow, modelRow, stormRow, hurRow, radRow, caption, zoo, refs
    ]);
    $('#story-prev').innerHTML = G.prev;
    $('#story-next').innerHTML = G.next;
    demo.canvas = canvas;
    demo.ctx = canvas.getContext('2d');
    canvas.addEventListener('pointermove', function (e) {
      var r = canvas.getBoundingClientRect(), k = demo.scale || 1;
      demo.hover = { x: (e.clientX - r.left) / k, y: (e.clientY - r.top) / k };
      var d = demoDef();
      canvas.style.cursor = (d.story && demo.hover.y < 30) || (d.model && hitModelNode(demo.hover) >= 0) || (d.storm && hitStormNode(demo.hover) >= 0) || (d.hurricane && hitHurNode(demo.hover) >= 0) || (d.radar && hitRadNode(demo.hover) >= 0) ? 'pointer' : '';
      kick();
    });
    canvas.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse') return;
      var r = canvas.getBoundingClientRect(), k = demo.scale || 1;
      demo.hover = { x: (e.clientX - r.left) / k, y: (e.clientY - r.top) / k };
      kick();
    });
    canvas.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse') { demo.hover = null; kick(); } });
    canvas.addEventListener('click', function (e) {
      var d = demoDef(), r = canvas.getBoundingClientRect(), k = demo.scale || 1, p = { x: (e.clientX - r.left) / k, y: (e.clientY - r.top) / k };
      if (d.story && p.y < 30) {
        var n = STORY.length, segW = (demo.W - 32) / n, i = Math.floor((p.x - 16) / segW);
        if (i >= 0 && i < n) goScene(i);
      } else if (d.model) {
        var k = hitModelNode(p);
        if (k >= 0) { demo.modelStage = k; demo.modelT = 0; if (motionOK()) demo.modelPlay = true; syncControls(); kick(); }
      } else if (d.storm) {
        var q = hitStormNode(p);
        if (q >= 0) { demo.stormStage = q; demo.stormT = 0; if (motionOK()) demo.stormPlay = true; syncControls(); kick(); }
      } else if (d.hurricane) {
        var q2 = hitHurNode(p);
        if (q2 >= 0) { demo.hurStage = q2; demo.hurT = 0; if (motionOK()) demo.hurPlay = true; syncControls(); kick(); }
      } else if (d.radar) {
        var q3 = hitRadNode(p);
        if (q3 >= 0) { demo.radStage = q3; demo.radT = 0; if (motionOK()) demo.radPlay = true; syncControls(); kick(); }
      }
    });
    if (window.ResizeObserver) new ResizeObserver(function () { sizeCanvas(); kick(); }).observe(stage);
    else window.addEventListener('resize', function () { sizeCanvas(); kick(); });
    demo.built = true;
    if (!motionOK()) { demo.auto = false; demo.storyPlay = false; demo.modelPlay = false; demo.stormPlay = false; demo.hurPlay = false; demo.radPlay = false; demo.predPlay = false; }
    syncControls();
    sizeCanvas();
  };


  const hitModelNode = function hitModelNode(p) {
    var nodes = demo.modelNodes || [];
    for (var i = 0; i < nodes.length; i++) {
      var b = nodes[i];
      if (p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h) return i;
    }
    return -1;
  };

  const setModelVariant = function setModelVariant(v) {
    demo.modelVariant = v;
    demo.modelStage = 0; demo.modelT = 0;
    store.set('model', v);
    if (motionOK()) demo.modelPlay = true;
    syncControls();
    kick();
  };


  const renderZoo = function renderZoo() {
    var el = $('#demo-zoo');
    clear(el);
    var live = stLive();
    var fs = live.foundation === 'done' || live.foundationMae !== null ? ['done', 'Done'] : live.foundation === 'active' ? ['running', 'Training now'] : ['pending', 'Next'];
    var ms = live.measured === 'done' ? ['done', 'Done'] : live.measured === 'active' ? ['running', 'In progress'] : ['pending', 'Planned'];
    var rows = [
      stormZooRow(),
      ['Gradient boosting', '43 hand-made composition and structure features', ['done', 'Done'], 'Tc error ' + MAE_BASELINE.toFixed(2) + ' K'],
      ['MACE-MP-0 + boosted ensemble', 'frozen foundation-model fingerprint, three models for error bars', fs, live.foundationMae !== null ? 'Tc error ' + live.foundationMae.toFixed(2) + ' K' : ''],
      gnnZooRow(),
      hurZooRow(ms),
      radarZooRow()
    ];
    var ul = h('ul', { class: 'zoo-list' });
    rows.forEach(function (r) {
      ul.appendChild(h('li', null,
        h('span', { class: 'zoo-name' }, h('b', { text: r[0] }), h('span', { text: r[1] })),
        h('span', { class: 'chip' }, h('i', { class: 'd-' + r[2][0] }), r[2][1]),
        h('span', { class: 'zoo-score' }, r[3] ? richText(h('span'), r[3]) : '')));
    });
    append(el, [
      h('h3', { text: 'Models we are trying' }),
      ul,
      richText(h('p', { class: 'zoo-ai' }), 'Storm and Hurricane, our AI-designed models: we let an AI agent design models itself. It proposes a new architecture or feature set, trains and scores it with the same grouped cross-validation, and keeps the design only if it beats the current best. Storm’s errors are against DFT-computed Tc and Hurricane’s against measured Tc. A locked test set is used only once, at the very end, so no design can be tuned to it. ' + (radInfo() ? 'Radar, which picks the model for each material, was designed the same way.' : 'Radar will be designed the same way.'))
    ]);
  };


  // The graph neural network baseline: progress.json "gnn" block and results tagged "gnn", so its scores appear without an app update.
  const gnnInfo = function gnnInfo() {
    var d = state.data, g = (d && d.gnn) || {}, best = null;
    list(d && d.results).forEach(function (r) { if (r && r.tag === 'gnn' && r.target === 'Tc' && typeof r.mae === 'number' && (!best || r.mae < best.mae)) best = r; });
    var st = typeof g.status === 'string' && g.status ? g.status : best ? 'done' : 'planned';
    return { status: st, mae: best ? best.mae : typeof g.tc_mae === 'number' ? g.tc_mae : null,
      // the version appears once there is more than one (round 2 and later)
      name: (typeof g.name === 'string' && g.name ? g.name : 'Graph neural network') + (list(g.versions).length > 1 && typeof g.current === 'string' ? ' ' + g.current : ''),
      desc: typeof g.summary === 'string' && g.summary ? g.summary : 'message passing on the crystal graph, trained end to end' };
  };

  const gnnZooRow = function gnnZooRow() {
    var gi = gnnInfo(), chip = gi.status === 'done' ? ['done', 'Done'] : gi.status === 'training' || gi.status === 'active' ? ['running', 'Training now'] : gi.status === 'experimental' ? ['active', 'Experimental'] : ['pending', 'Planned'];
    return [gi.name, gi.desc, chip, gi.mae !== null ? 'Tc error ' + gi.mae.toFixed(2) + ' K' : ''];
  };

  const hurZooRow = function hurZooRow(ms) {
    var info = hurInfo();
    if (!info) return ['Hurricane · our AI model', 'for unconventional superconductors (cuprates, nickelates, iron-based, heavy-fermion), learns from graded measured Tc', ms, ''];
    var v = info.v, ok = v.status === 'adopted';
    return [hurTitle(info) + ' · our AI model', 'designed by an AI agent, for unconventional superconductors: ' + lcFirst(v.summary),
      ok ? ['done', 'Released'] : ['active', 'Experimental'], 'measured-Tc error ' + hurK(v.scores.tc_mae) + ' K'];
  };

  const radarZooRow = function radarZooRow() {
    var info = radInfo();
    if (!info) return ['Radar · router', 'decides whether a material goes to Storm or Hurricane', ['pending', 'Planned'], ''];
    var v = info.v, ok = v.status === 'adopted';
    return [radTitle(info) + ' · our AI model', 'designed by an AI agent, routes each material to Storm or Hurricane: ' + lcFirst(v.summary),
      ok ? ['done', 'Released'] : ['active', 'Experimental'], 'right model ' + radPct(v.scores.balanced_accuracy)];
  };

  const stormZooRow = function stormZooRow() {
    var info = stormInfo();
    if (!info) return ['Storm (AI-designed)', 'an AI agent proposes, trains and tests new designs', ['active', 'Exploring'], ''];
    var v = info.v, ok = v.status === 'adopted', cal = stormIsCurrent(info) ? stormCal() : null, ens = stormIsCurrent(info) ? stormEns() : null;
    var unc = ens ? stormUnc() : null;
    if (ens) return ['Storm ' + (unc ? unc.version : ens.version) + ' · our AI model', 'designed by an AI agent, for conventional superconductors: ' + lcFirst(ens.summary) + (unc ? ', with a 90% range for every prediction' : ''),
      ['done', 'Released'], 'Tc error ' + ens.scores.tc_mae.toFixed(2) + ' K (DFT), ' + ens.calibration.mae.toFixed(2) + ' K (measured)'];
    if (cal) return ['Storm ' + cal.version + ' · our AI model', 'designed by an AI agent, for conventional superconductors: ' + lcFirst(v.summary) + ', calibrated to measured Tc',
      ['done', 'Released'], 'Tc error ' + v.scores.tc_mae.toFixed(2) + ' K (DFT), ' + cal.scores.mae.toFixed(2) + ' K (measured)'];
    return [stormTitle(info) + ' · our AI model', 'designed by an AI agent, for conventional superconductors: ' + lcFirst(v.summary),
      ok ? ['done', 'Released'] : ['active', 'Experimental'], 'Tc error ' + v.scores.tc_mae.toFixed(2) + ' K'];
  };


  const selectDemo = function selectDemo(id) {
    demo.id = id;
    store.set('demo', id);
    [].forEach.call(document.querySelectorAll('.demo-tab[data-id]'), function (b) { b.setAttribute('aria-selected', b.getAttribute('data-id') === id ? 'true' : 'false'); });
    demo.electrons = null; demo.ions = null; demo.sizeKey = '';
    syncControls();
    sizeCanvas();
    kick();
  };


  const syncControls = function syncControls() {
    var d = demoDef();
    $('#demo-temp-row').hidden = !d.temp;
    $('#demo-ad-row').hidden = d.id !== 'allen-dynes';
    $('#demo-story-row').hidden = !d.story;
    $('#demo-model-row').hidden = !d.model;
    $('#demo-storm-row').hidden = !d.storm;
    $('#demo-hur-row').hidden = !d.hurricane;
    $('#demo-rad-row').hidden = !d.radar;
    $('#demo-zoo').hidden = !d.model && !d.storm && !d.hurricane && !d.radar;
    if (d.model || d.storm || d.hurricane || d.radar) renderZoo();
    if (d.storm) renderStormSeg();
    var cap = d.story ? storyCaption(demo.scene) : d.model ? modelCaption(demo.modelVariant, demo.modelStage) : d.storm ? stormCaption(demo.stormStage) : d.hurricane ? hurCaption(demo.hurStage) : d.radar ? radCaption(demo.radStage) : d.id === 'allen-dynes' ? predCaption() : d.caption;
    richText($('#demo-caption'), cap);
    renderRefs($('#demo-refs'), d.story ? STORY[demo.scene].refs : d.model ? MODEL_REFS[demo.modelVariant] || d.refs : d.id === 'allen-dynes' && demo.predMode !== 'formula' ? (demo.predMode === 'storm' ? d.stormRefs : d.hurRefs) || d.refs : d.refs);
    var walk = d.id === 'allen-dynes' && demo.predMode !== 'formula';
    [].forEach.call(document.querySelectorAll('#pred-seg button'), function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-pred') === demo.predMode ? 'true' : 'false'); });
    $('#pred-sliders').hidden = walk;
    var pp = $('#pred-play');
    pp.innerHTML = demo.predPlay ? G.pause : G.play;
    pp.appendChild(document.createTextNode(demo.predPlay ? 'Pause' : 'Play'));
    pp.hidden = !walk || !motionOK();
    // with motion, Next steps through the walk-through and then to the next material; without motion every step shows at once, so it moves to the next material
    var pn = $('#pred-next');
    pn.hidden = !walk || predExamples(demo.predMode).length < (motionOK() ? 1 : 2);
    pn.textContent = motionOK() ? 'Next' : 'Next material';
    var play = $('#demo-play');
    play.innerHTML = demo.auto ? G.pause : G.play;
    play.appendChild(document.createTextNode(demo.auto ? 'Pause' : 'Play'));
    play.setAttribute('aria-label', demo.auto ? 'Pause the temperature sweep' : 'Play a temperature sweep');
    play.hidden = !motionOK();
    var sp = $('#story-play');
    sp.innerHTML = demo.storyPlay ? G.pause : G.play;
    sp.appendChild(document.createTextNode(demo.storyPlay ? 'Pause' : 'Play'));
    sp.hidden = !motionOK();
    $('#story-readout').textContent = 'Step ' + (demo.scene + 1) + ' of ' + STORY.length + ' · ' + STORY[demo.scene].title;
    var mp = $('#model-play');
    mp.innerHTML = demo.modelPlay ? G.pause : G.play;
    mp.appendChild(document.createTextNode(demo.modelPlay ? 'Pause' : 'Play'));
    mp.hidden = !motionOK();
    [].forEach.call(document.querySelectorAll('#demo-model-row .seg button'), function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-variant') === demo.modelVariant ? 'true' : 'false'); });
    var sp2 = $('#storm-play');
    sp2.innerHTML = demo.stormPlay ? G.pause : G.play;
    sp2.appendChild(document.createTextNode(demo.stormPlay ? 'Pause' : 'Play'));
    sp2.hidden = !motionOK();
    var stSt = stormStages();
    $('#storm-readout').textContent = (motionOK() ? 'Step ' + (demo.stormStage + 1) + ' of ' + stSt.length + ' · ' : '') + stSt[demo.stormStage].node + (motionOK() ? '' : ' · click a step to explore');
    if (d.storm) demo.canvas.setAttribute('aria-label', 'Storm, the AI-designed model, step ' + (demo.stormStage + 1) + ': ' + stSt[demo.stormStage].node + '. ' + stormCaption(demo.stormStage));
    var hp = $('#hur-play');
    hp.innerHTML = demo.hurPlay ? G.pause : G.play;
    hp.appendChild(document.createTextNode(demo.hurPlay ? 'Pause' : 'Play'));
    hp.hidden = !motionOK();
    $('#hur-readout').textContent = (motionOK() ? 'Step ' + (demo.hurStage + 1) + ' of ' + HUR_STAGES.length + ' · ' : '') + HUR_STAGES[demo.hurStage].node + (motionOK() ? '' : ' · click a step to explore');
    if (d.hurricane) demo.canvas.setAttribute('aria-label', 'Hurricane, the AI-designed model for unconventional superconductors, step ' + (demo.hurStage + 1) + ': ' + HUR_STAGES[demo.hurStage].node + '. ' + hurCaption(demo.hurStage));
    var rp = $('#rad-play');
    rp.innerHTML = demo.radPlay ? G.pause : G.play;
    rp.appendChild(document.createTextNode(demo.radPlay ? 'Pause' : 'Play'));
    rp.hidden = !motionOK();
    $('#rad-readout').textContent = (motionOK() ? 'Step ' + (demo.radStage + 1) + ' of ' + RAD_STAGES.length + ' · ' : '') + RAD_STAGES[demo.radStage].node + (motionOK() ? '' : ' · click a step to explore');
    if (d.radar) demo.canvas.setAttribute('aria-label', 'Radar, the AI-designed router between Storm and Hurricane, step ' + (demo.radStage + 1) + ': ' + RAD_STAGES[demo.radStage].node + '. ' + radCaption(demo.radStage));
    var ms = MODEL_STAGES[demo.modelVariant];
    $('#model-readout').textContent = motionOK() ? 'Step ' + (demo.modelStage + 1) + ' of ' + ms.length : 'Click a step in the pipeline to explore it';
    if (d.story) demo.canvas.setAttribute('aria-label', 'Hello Super tour, step ' + (demo.scene + 1) + ' of ' + STORY.length + ': ' + STORY[demo.scene].title + '. ' + storyCaption(demo.scene));
    if (d.model) demo.canvas.setAttribute('aria-label', (MODEL_LABEL[demo.modelVariant] || 'Baseline') + ', step ' + (demo.modelStage + 1) + ': ' + modelTitle(demo.modelVariant, demo.modelStage) + '. ' + modelCaption(demo.modelVariant, demo.modelStage));
    $('#demo-temp').value = String(demo.t.toFixed(2));
    $('#demo-temp-out').textContent = demo.t.toFixed(2) + ' Tc';
    ['lam', 'wlog', 'mu'].forEach(function (k) {
      var input = $('#demo-' + k), out = $('#demo-' + k + '-out');
      input.value = String(demo[k]);
      out.textContent = out.fmt(demo[k]);
    });
  };


  const sizeCanvas = function sizeCanvas() {
    if (!demo.canvas) return;
    var stage = demo.canvas.parentNode;
    // Below 280 px the drawing keeps its 280 px layout and is scaled down evenly, so it never squeezes sideways.
    var stageW = Math.floor(stage.getBoundingClientRect().width), W = Math.max(280, stageW);
    var d = demoDef();
    var H = W < 560 ? (d.narrowHeight || Math.round(d.height * 0.85)) : d.height;
    var dpr = Math.min(2, window.devicePixelRatio || 1), scale = stageW > 0 && stageW < W ? stageW / W : 1;
    if (W === demo.W && H === demo.H && dpr === demo.dpr && scale === demo.scale) return;
    demo.W = W; demo.H = H; demo.dpr = dpr; demo.scale = scale;
    demo.canvas.width = Math.round(W * dpr);
    demo.canvas.height = Math.round(H * dpr);
    demo.canvas.style.height = Math.round(H * scale) + 'px';
    demo.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    demo.electrons = null; demo.ions = null; demo.fieldKey = ''; demo.heatKey = '';
  };


  const demosVisible = function demosVisible() { return view === 'demos' && demo.built && !document.hidden; };

  const kick = function kick() {
    if (!demosVisible() || demo.raf) return;
    demo.last = 0;
    demo.raf = requestAnimationFrame(frame);
  };

  const frame = function frame(ts) {
    demo.raf = 0;
    if (!demosVisible()) return;
    var moving = motionOK();
    var dt = moving && demo.last ? Math.min(0.05, (ts - demo.last) / 1000) : 0;
    demo.last = ts;
    demo.clock += dt;
    var d = demoDef();
    if (d.story && demo.storyPlay && moving) {
      demo.sceneT += dt;
      if (demo.sceneT >= STORY[demo.scene].dur) { demo.scene = (demo.scene + 1) % STORY.length; demo.sceneT = 0; syncControls(); }
    }
    if (d.model && demo.modelPlay && moving) {
      demo.modelT += dt;
      if (demo.modelT >= MODEL_STAGE_DUR) { demo.modelStage = (demo.modelStage + 1) % MODEL_STAGES[demo.modelVariant].length; demo.modelT = 0; syncControls(); }
    }
    if (d.storm && demo.stormPlay && moving) {
      demo.stormT += dt;
      if (demo.stormT >= STORM_DUR) { demo.stormStage = (demo.stormStage + 1) % stormStages().length; demo.stormT = 0; syncControls(); }
    }
    if (d.hurricane && demo.hurPlay && moving) {
      demo.hurT += dt;
      if (demo.hurT >= HUR_DUR) { demo.hurStage = (demo.hurStage + 1) % HUR_STAGES.length; demo.hurT = 0; syncControls(); }
    }
    if (d.id === 'allen-dynes' && demo.predMode !== 'formula' && demo.predPlay && moving) {
      var pst = predSteps(demo.predMode, predExample()), pat0 = predAt(pst, demo.predT).i;
      demo.predT += dt;
      if (pst.length && demo.predT >= predTotal(pst) + 1.5) { demo.predEx += 1; demo.predT = 0; syncControls(); }
      else if (pst.length && predAt(pst, demo.predT).i !== pat0) syncControls();
    }
    if (d.radar && demo.radPlay && moving) {
      demo.radT += dt;
      if (demo.radT >= RAD_DUR) { demo.radStage = (demo.radStage + 1) % RAD_STAGES.length; demo.radT = 0; syncControls(); }
    }
    if (d.temp && demo.auto && moving) {
      demo.t = 0.9 + 0.65 * Math.cos(2 * Math.PI * demo.clock / 14);
      $('#demo-temp').value = demo.t.toFixed(2);
      $('#demo-temp-out').textContent = demo.t.toFixed(2) + ' Tc';
    }
    var C = colors();
    var c = demo.ctx;
    c.clearRect(0, 0, demo.W, demo.H);
    c.fillStyle = C.surface;
    c.fillRect(0, 0, demo.W, demo.H);
    if (d.story) drawStory(c, C);
    else if (d.model) drawModel(c, C);
    else if (d.storm) drawStorm(c, C);
    else if (d.hurricane) drawHurricane(c, C);
    else if (d.radar) drawRadar(c, C);
    else if (d.id === 'resistance') drawResistance(c, C, dt);
    else if (d.id === 'meissner') drawMeissner(c, C, dt);
    else if (d.id === 'pairs') drawPairs(c, C, dt);
    else drawPredict(c, C);
    var paused = (d.story && !demo.storyPlay) || (d.model && !demo.modelPlay) || (d.storm && !demo.stormPlay) || (d.hurricane && !demo.hurPlay) || (d.radar && !demo.radPlay) ||
      (d.id === 'allen-dynes' && demo.predMode !== 'formula' && !demo.predPlay);
    if (moving && !paused) demo.raf = requestAnimationFrame(frame);
  };


  const dot = function dot(c, x, y, r, fill, ring) {
    c.beginPath();
    c.arc(x, y, r, 0, Math.PI * 2);
    if (ring) { c.lineWidth = 2; c.strokeStyle = ring; c.stroke(); }
    c.fillStyle = fill;
    c.fill();
  };

  const label = function label(c, C, text, x, y, opts) {
    opts = opts || {};
    c.font = (opts.weight || '400') + ' ' + (opts.size || 12) + 'px ' + C.font;
    c.fillStyle = opts.color || C.ink2;
    c.textAlign = opts.align || 'left';
    c.textBaseline = opts.base || 'alphabetic';
    c.fillText(text, x, y);
  };

  const stateText = function stateText(s) { return s > 0 ? 'Superconducting' : 'Normal state'; };


  // Small line plot shared by the resistance and gap demos.
  const miniPlot = function miniPlot(c, C, box, fn, yMax, t, yLabel, valueText) {
    var x0 = box.x + 44, x1 = box.x + box.w - 16, y0 = box.y + 18, y1 = box.y + box.h - 40;
    function X(v) { return x0 + (v / 1.6) * (x1 - x0); }
    function Y(v) { return y1 - (v / yMax) * (y1 - y0); }
    c.lineWidth = 1;
    [0.25, 0.5, 0.75, 1].forEach(function (g) {
      var yy = Math.round(Y(g * yMax)) + 0.5;
      c.strokeStyle = C.grid; c.beginPath(); c.moveTo(x0, yy); c.lineTo(x1, yy); c.stroke();
    });
    c.strokeStyle = C.axis; c.beginPath(); c.moveTo(x0, Math.round(y1) + 0.5); c.lineTo(x1, Math.round(y1) + 0.5); c.stroke();
    var tcx = Math.round(X(1)) + 0.5;
    c.strokeStyle = C.axis; c.beginPath(); c.moveTo(tcx, y0); c.lineTo(tcx, y1); c.stroke();
    [0, 0.5, 1, 1.5].forEach(function (v) {
      label(c, C, v === 1 ? 'Tc' : String(v), X(v), y1 + 16, { align: 'center', size: 11, color: C.muted });
    });
    label(c, C, 'Temperature (T / Tc)', (x0 + x1) / 2, y1 + 32, { align: 'center', size: 11, color: C.muted });
    label(c, C, yLabel, x0, y0 - 6, { size: 11, color: C.muted });
    c.beginPath();
    for (var v = 0; v <= 1.6001; v += 0.005) {
      var px = X(v), py = Y(fn(v));
      if (v === 0) c.moveTo(px, py); else c.lineTo(px, py);
    }
    c.lineWidth = 2; c.lineJoin = 'round'; c.strokeStyle = C.accent; c.stroke();
    var mx = X(Math.max(0, Math.min(1.6, t))), my = Y(fn(t));
    dot(c, mx, my, 5, C.accent, C.surface);
    var right = mx > x1 - 150;
    label(c, C, valueText, right ? mx - 12 : mx + 12, my - 10, { align: right ? 'right' : 'left', weight: '600', color: C.ink });
  };


  const resistanceOf = function resistanceOf(t) {
    var normal = 0.55 + 0.45 * (t / 1.6);
    return normal / (1 + Math.exp(-(t - 1) / 0.015));
  };


  const drawResistance = function drawResistance(c, C, dt) {
    var W = demo.W, H = demo.H, t = demo.t, s = gapRatio(t);
    var left = 16, right = W - 16, top = 16, wireH = Math.min(132, Math.round(H * 0.4));
    c.fillStyle = C.surface2;
    c.beginPath();
    if (c.roundRect) c.roundRect(left, top, right - left, wireH, 12); else c.rect(left, top, right - left, wireH);
    c.fill();
    var cols = Math.max(8, Math.floor((right - left) / 36)), rows = 3;
    var amp = (0.6 + 3.4 * Math.min(t, 1.6) / 1.6) * (1 - 0.55 * s);
    for (var r = 0; r < rows; r++) {
      for (var k = 0; k < cols; k++) {
        var x = left + (k + 0.5) * (right - left) / cols + amp * Math.sin(demo.clock * 9 + k * 1.7 + r * 2.3);
        var y = top + (r + 0.5) * wireH / rows + amp * Math.cos(demo.clock * 11 + k * 2.1 + r);
        dot(c, x, y, 5, mix(C.muted, C.surface2, 0.35));
      }
    }
    var N = 24;
    if (!demo.electrons) {
      demo.electrons = [];
      for (var i = 0; i < N; i++) {
        var a0 = Math.random() * Math.PI * 2;
        demo.electrons.push({ x: left + Math.random() * (right - left), y: top + 8 + Math.random() * (wireH - 16), vx: 60 * Math.cos(a0), vy: 60 * Math.sin(a0) });
      }
    }
    var es = demo.electrons;
    var scatter = (1 - s) * (2 + 5 * Math.min(t, 1.6) / 1.6);
    es.forEach(function (p) {
      if (dt && Math.random() < scatter * dt) {
        var ang = Math.random() * Math.PI * 2, sp = 60 + 50 * Math.random();
        p.vx = sp * Math.cos(ang) + 25; p.vy = sp * Math.sin(ang);
      }
      var k = Math.min(1, dt * (0.4 + 5 * s));
      p.vx += (90 * s + 25 * (1 - s) - p.vx) * k * (s > 0 ? 1 : 0.15);
      p.vy += (0 - p.vy) * Math.min(1, dt * 5 * s);
    });
    for (var j = 0; j + 1 < N; j += 2) {
      var p = es[j], q = es[j + 1];
      if (s > 0) {
        var mx = (p.x + q.x) / 2, my = (p.y + q.y) / 2, pull = Math.min(1, dt * 3 * s);
        if (Math.abs(p.x - q.x) > (right - left) / 2) { q.x = p.x; }
        p.x += (mx - 6 - p.x) * pull; q.x += (mx + 6 - q.x) * pull;
        p.y += (my - p.y) * pull; q.y += (my - q.y) * pull;
        q.vx = p.vx = (p.vx + q.vx) / 2 * (1 - pull) + 90 * pull;
      }
    }
    es.forEach(function (p) {
      p.x += p.vx * dt; p.y += p.vy * dt;
      if (p.y < top + 7) { p.y = top + 7; p.vy = Math.abs(p.vy); }
      if (p.y > top + wireH - 7) { p.y = top + wireH - 7; p.vy = -Math.abs(p.vy); }
      if (p.x > right - 4) p.x -= right - left - 8;
      if (p.x < left + 4) p.x += right - left - 8;
    });
    if (s > 0.05) {
      c.lineWidth = 2; c.strokeStyle = C.accent; c.globalAlpha = Math.min(0.8, s);
      for (var m = 0; m + 1 < N; m += 2) {
        if (Math.abs(es[m].x - es[m + 1].x) < 40) { c.beginPath(); c.moveTo(es[m].x, es[m].y); c.lineTo(es[m + 1].x, es[m + 1].y); c.stroke(); }
      }
      c.globalAlpha = 1;
    }
    es.forEach(function (p) { dot(c, p.x, p.y, 3.5, C.accent); });
    var narrow = W < 560;
    label(c, C, s > 0 ? (narrow ? 'Pairs flow freely' : 'Cooper pairs flow without scattering') : (narrow ? 'Electrons scatter' : 'Electrons scatter off vibrating ions'), left + 10, top + wireH + 20, { size: 12, color: C.ink2 });
    label(c, C, stateText(s), right - 10, top + wireH + 20, { align: 'right', size: 12, weight: '600', color: C.ink });
    var R = resistanceOf(t);
    miniPlot(c, C, { x: 0, y: top + wireH + 30, w: W, h: H - (top + wireH + 30) }, resistanceOf, 1.1, t,
      'Resistance (R / Rₙ)', R < 0.005 ? 'R = 0' : 'R = ' + R.toFixed(2) + ' Rₙ');
    $('#demo-readout').textContent = R < 0.005 ? 'Zero resistance' : 'Resistance ' + R.toFixed(2) + ' Rₙ';
    demo.canvas.setAttribute('aria-label', 'Zero-resistance demo at ' + t.toFixed(2) + ' Tc: ' + stateText(s));
  };


  const solveFieldLine = function solveFieldLine(x, cval, re) {
    if (re < 0.5) return cval;
    var lo = Math.sqrt(Math.max(re * re - x * x, 0)), hi = cval + re;
    for (var i = 0; i < 30; i++) {
      var mid = (lo + hi) / 2;
      var g = mid * (1 - re * re / (x * x + mid * mid));
      if (g < cval) lo = mid; else hi = mid;
    }
    return (lo + hi) / 2;
  };


  const drawMeissner = function drawMeissner(c, C, dt) {
    var W = demo.W, H = demo.H, t = demo.t, s = Math.min(1, gapRatio(t) * 1.6);
    var band = H - 30, cx = W / 2, cy = band / 2 + 4, a = Math.min(W, band) * 0.26;
    var re = a * Math.sqrt(s);
    var key = [W, H, Math.round(re * 4)].join(':');
    if (demo.fieldKey !== key) {
      demo.fieldKey = key;
      demo.field = [];
      var spacing = Math.max(18, Math.round(H / 16));
      for (var k = 1; k * spacing < H / 2 + spacing; k++) {
        var cval = k * spacing - spacing / 2;
        var top = [], bottom = [];
        for (var x = -W / 2 - 8; x <= W / 2 + 8; x += 4) {
          var y = solveFieldLine(x, cval, re);
          top.push([cx + x, cy - y]);
          bottom.push([cx + x, cy + y]);
        }
        demo.field.push(top, bottom);
      }
    }
    c.save();
    c.beginPath();
    c.rect(0, 0, W, band);
    c.clip();
    c.beginPath();
    c.arc(cx, cy, a, 0, Math.PI * 2);
    c.fillStyle = mix(C.surface2, C.track, s);
    c.fill();
    c.lineWidth = 1; c.strokeStyle = C.axis; c.stroke();
    c.lineWidth = 1.6; c.strokeStyle = C.ink2;
    c.setLineDash([7, 9]);
    c.lineDashOffset = -demo.clock * 36;
    demo.field.forEach(function (pts) {
      c.beginPath();
      pts.forEach(function (p, i) { if (i) c.lineTo(p[0], p[1]); else c.moveTo(p[0], p[1]); });
      c.stroke();
    });
    c.setLineDash([]);
    if (s > 0.03) {
      c.globalAlpha = Math.min(1, s * 1.4);
      var rr = 5 + 4 * s;
      [[cx, cy - a, 'in'], [cx, cy + a, 'out'], [cx - a * 0.71, cy - a * 0.71, 'in'], [cx + a * 0.71, cy - a * 0.71, 'in'], [cx - a * 0.71, cy + a * 0.71, 'out'], [cx + a * 0.71, cy + a * 0.71, 'out']].forEach(function (m) {
        dot(c, m[0], m[1], rr, C.surface, C.accent);
        c.strokeStyle = C.accent; c.fillStyle = C.accent; c.lineWidth = 2;
        if (m[2] === 'out') { c.beginPath(); c.arc(m[0], m[1], 1.8, 0, Math.PI * 2); c.fill(); }
        else { var q = rr * 0.55; c.beginPath(); c.moveTo(m[0] - q, m[1] - q); c.lineTo(m[0] + q, m[1] + q); c.moveTo(m[0] + q, m[1] - q); c.lineTo(m[0] - q, m[1] + q); c.stroke(); }
      });
      c.globalAlpha = 1;
    }
    label(c, C, s > 0 ? 'Superconductor' : 'Normal metal', cx, cy + 4, { align: 'center', size: 13, weight: '600', color: C.ink });
    c.restore();
    c.strokeStyle = C.grid; c.lineWidth = 1;
    c.beginPath(); c.moveTo(0, band + 0.5); c.lineTo(W, band + 0.5); c.stroke();
    var what = s <= 0 ? 'Field passes straight through' : s >= 0.98 ? 'Field expelled from the interior' : 'Field being expelled';
    label(c, C, 'Magnetic field →', 16, H - 11, { size: 12, color: C.muted });
    label(c, C, stateText(s) + ' · ' + what, W - 16, H - 11, { align: 'right', size: 12, weight: '600', color: C.ink });
    $('#demo-readout').textContent = what;
    demo.canvas.setAttribute('aria-label', 'Meissner-effect demo at ' + t.toFixed(2) + ' Tc: ' + what);
  };


  const drawPairs = function drawPairs(c, C, dt) {
    var W = demo.W, H = demo.H, t = demo.t, s = gapRatio(t);
    var d = 34, top = 14, regionH = Math.round(H * 0.6);
    var rows = Math.max(3, Math.floor(regionH / d)), cols = Math.ceil(W / d) + 1;
    var key = [W, H].join(':');
    if (!demo.ions || demo.sizeKey !== key) {
      demo.sizeKey = key;
      demo.ions = [];
      for (var r = 0; r < rows; r++) for (var k = 0; k < cols; k++) demo.ions.push({ x0: (k + 0.5) * d, y0: top + (r + 0.5) * d, ux: 0, uy: 0 });
      var lane = top + Math.floor(rows / 2) * d;
      demo.e1 = { x: W * 0.55, y: lane };
      demo.e2 = { x: W * 0.55 - 2.6 * d, y: lane, vx: 30, vy: 0 };
    }
    var e1 = demo.e1, e2 = demo.e2, laneY = e1.y;
    e1.x += 70 * dt;
    if (e1.x > W + 40) { e1.x -= W + 80; e2.x -= W + 80; }
    var pullR2 = (2.3 * d) * (2.3 * d), sig2 = 2 * (0.9 * d) * (0.9 * d);
    demo.ions.forEach(function (ion) {
      var dx = e1.x - ion.x0, dy = e1.y - ion.y0, r2 = dx * dx + dy * dy;
      if (r2 < pullR2 && r2 > 1) {
        var f = 160 * Math.exp(-r2 / sig2) / Math.sqrt(r2);
        ion.ux += f * dx * dt; ion.uy += f * dy * dt;
      }
      ion.ux -= ion.ux * dt * 0.8; ion.uy -= ion.uy * dt * 0.8;
      var u = Math.hypot(ion.ux, ion.uy);
      if (u > 9) { ion.ux *= 9 / u; ion.uy *= 9 / u; }
    });
    var target = { x: e1.x - 2.6 * d, y: laneY + 4 * Math.sin(demo.clock * 3) };
    if (dt && Math.random() < (1 - s) * 3 * dt) {
      var ang = Math.random() * Math.PI * 2;
      e2.vx = 70 * Math.cos(ang) + 20; e2.vy = 70 * Math.sin(ang);
    }
    var free = { x: e2.vx * dt, y: e2.vy * dt };
    var paired = { x: (target.x - e2.x) * Math.min(1, dt * 2.5), y: (target.y - e2.y) * Math.min(1, dt * 2.5) };
    e2.x += (1 - s) * free.x + s * paired.x;
    e2.y += (1 - s) * free.y + s * paired.y;
    if (e2.y < top + 8) { e2.y = top + 8; e2.vy = Math.abs(e2.vy); }
    if (e2.y > top + rows * d - 8) { e2.y = top + rows * d - 8; e2.vy = -Math.abs(e2.vy); }
    if (e2.x > W + 40) e2.x -= W + 80;
    if (e2.x < -40) e2.x += W + 80;
    var jitter = (0.4 + 3.2 * Math.min(t, 1.6) / 1.6) * (1 - 0.4 * s);
    demo.ions.forEach(function (ion, i) {
      var w = Math.min(1, Math.hypot(ion.ux, ion.uy) / 7);
      var x = ion.x0 + ion.ux + jitter * Math.sin(demo.clock * 8 + i * 1.3);
      var y = ion.y0 + ion.uy + jitter * Math.cos(demo.clock * 10 + i * 0.7);
      dot(c, x, y, 6 + 1.5 * w, mix(mix(C.muted, C.surface, 0.35), C.warm, w));
      c.strokeStyle = C.surface; c.lineWidth = 1.4;
      c.beginPath(); c.moveTo(x - 2.5, y); c.lineTo(x + 2.5, y); c.moveTo(x, y - 2.5); c.lineTo(x, y + 2.5); c.stroke();
    });
    if (s > 0.15 && Math.abs(e1.x - e2.x) < 4 * d) {
      c.globalAlpha = Math.min(0.9, s);
      c.setLineDash([4, 5]); c.lineWidth = 1.5; c.strokeStyle = C.accent;
      var midx = (e1.x + e2.x) / 2, midy = Math.min(e1.y, e2.y) - 26;
      c.beginPath(); c.moveTo(e2.x, e2.y - 8); c.quadraticCurveTo(midx, midy, e1.x, e1.y - 8); c.stroke();
      c.setLineDash([]);
      c.font = '600 12px ' + C.font;
      var tw = c.measureText('Cooper pair').width;
      c.fillStyle = C.surface;
      c.beginPath();
      if (c.roundRect) c.roundRect(midx - tw / 2 - 6, midy - 19, tw + 12, 20, 6); else c.rect(midx - tw / 2 - 6, midy - 19, tw + 12, 20);
      c.fill();
      label(c, C, 'Cooper pair', midx, midy - 4, { align: 'center', size: 12, weight: '600', color: C.ink });
      c.globalAlpha = 1;
    }
    [e2, e1].forEach(function (e) {
      dot(c, e.x, e.y, 6.5, C.accent, C.surface);
      c.strokeStyle = C.surface; c.lineWidth = 1.6; c.beginPath(); c.moveTo(e.x - 3, e.y); c.lineTo(e.x + 3, e.y); c.stroke();
    });
    var gapTop = top + rows * d + 6;
    miniPlot(c, C, { x: 0, y: gapTop, w: W, h: H - gapTop }, gapRatio, 1.1, t, 'Energy gap (Δ / Δ₀)',
      s > 0 ? 'Δ = ' + s.toFixed(2) + ' Δ₀' : 'No gap');
    $('#demo-readout').textContent = s > 0 ? 'Energy gap ' + s.toFixed(2) + ' Δ₀' : 'No energy gap above Tc';
    demo.canvas.setAttribute('aria-label', 'Cooper-pair demo at ' + t.toFixed(2) + ' Tc: ' + stateText(s));
  };


  const drawAllenDynes = function drawAllenDynes(c, C) {
    var W = demo.W, H = demo.H;
    var x0 = 56, x1 = W - 20, y0 = 16, y1 = H - 70;
    var LMAX = 2.5, WMAX = 1000;
    function X(l) { return x0 + (l / LMAX) * (x1 - x0); }
    function Y(w) { return y1 - (w / WMAX) * (y1 - y0); }
    var key = [Math.round(x1 - x0), Math.round(y1 - y0), demo.mu, C.dark ? 'd' : 'l'].join(':');
    if (demo.heatKey !== key) {
      demo.heatKey = key;
      var nx = 150, ny = 100;
      var off = document.createElement('canvas');
      off.width = nx; off.height = ny;
      var g = off.getContext('2d'), img = g.createImageData(nx, ny);
      for (var j = 0; j < ny; j++) {
        for (var i = 0; i < nx; i++) {
          var tc = allenDynes(LMAX * (i + 0.5) / nx, WMAX * (ny - j - 0.5) / ny, demo.mu);
          var rgb = rampColor(Math.sqrt(Math.min(tc, TC_MAX) / TC_MAX), C.dark);
          var o = (j * nx + i) * 4;
          img.data[o] = rgb[0]; img.data[o + 1] = rgb[1]; img.data[o + 2] = rgb[2]; img.data[o + 3] = 255;
        }
      }
      g.putImageData(img, 0, 0);
      demo.heat = off;
    }
    c.imageSmoothingEnabled = true;
    c.drawImage(demo.heat, x0, y0, x1 - x0, y1 - y0);
    c.lineWidth = 1; c.strokeStyle = C.axis;
    c.strokeRect(Math.round(x0) + 0.5, Math.round(y0) + 0.5, Math.round(x1 - x0), Math.round(y1 - y0));
    [0, 0.5, 1, 1.5, 2, 2.5].forEach(function (l) { label(c, C, String(l), X(l), y1 + 15, { align: 'center', size: 11, color: C.muted }); });
    label(c, C, 'Electron–phonon coupling λ', x1, y1 + 30, { align: 'right', size: 11, color: C.muted });
    [0, 250, 500, 750, 1000].forEach(function (w) { label(c, C, String(w), x0 - 8, Y(w) + 4, { align: 'right', size: 11, color: C.muted }); });
    c.save(); c.translate(14, (y0 + y1) / 2); c.rotate(-Math.PI / 2);
    label(c, C, 'ω_log (K)', 0, 0, { align: 'center', size: 11, color: C.muted, base: 'middle' });
    c.restore();
    var lx0 = x0, lx1 = Math.min(x1, x0 + 260), ly = H - 22;
    for (var p = 0; p <= 100; p++) {
      var rgb2 = rampColor(p / 100, C.dark);
      c.fillStyle = 'rgb(' + rgb2.join(',') + ')';
      c.fillRect(lx0 + (lx1 - lx0) * p / 101, ly - 10, (lx1 - lx0) / 101 + 1, 10);
    }
    [0, 5, 20, 45, 80].forEach(function (v) {
      label(c, C, v + (v === 80 ? '+ K' : ''), lx0 + (lx1 - lx0) * Math.sqrt(v / TC_MAX), ly + 13, { align: 'center', size: 10, color: C.muted });
    });
    label(c, C, 'Tc', lx1 + 10, ly - 1, { size: 11, color: C.muted });
    var mx = X(demo.lam), my = Y(demo.wlog);
    if (motionOK()) {
      var k = (demo.clock % 1.6) / 1.6;
      c.globalAlpha = 1 - k; c.lineWidth = 2; c.strokeStyle = C.ink;
      c.beginPath(); c.arc(mx, my, 7 + 10 * k, 0, Math.PI * 2); c.stroke();
      c.globalAlpha = 1;
    }
    dot(c, mx, my, 6, C.surface, C.ink);
    var tc = allenDynes(demo.lam, demo.wlog, demo.mu);
    var right = mx > x1 - 120;
    label(c, C, 'Tc = ' + tc.toFixed(1) + ' K', right ? mx - 12 : mx + 12, my - 10, { align: right ? 'right' : 'left', weight: '600', size: 13, color: C.ink });
    var text = 'Tc = ' + tc.toFixed(1) + ' K';
    var hv = demo.hover;
    if (hv && hv.x >= x0 && hv.x <= x1 && hv.y >= y0 && hv.y <= y1) {
      var hl = (hv.x - x0) / (x1 - x0) * LMAX, hw = (y1 - hv.y) / (y1 - y0) * WMAX;
      c.strokeStyle = C.ink; c.globalAlpha = 0.5; c.lineWidth = 1;
      c.beginPath(); c.moveTo(hv.x + 0.5, y0); c.lineTo(hv.x + 0.5, y1); c.moveTo(x0, hv.y + 0.5); c.lineTo(x1, hv.y + 0.5); c.stroke();
      c.globalAlpha = 1;
      text += ' · at the pointer: λ ' + hl.toFixed(2) + ', ω_log ' + Math.round(hw) + ' K → Tc ' + allenDynes(hl, hw, demo.mu).toFixed(1) + ' K';
    }
    $('#demo-ad-readout').textContent = text;
    demo.canvas.setAttribute('aria-label', 'Allen-Dynes map; at lambda ' + demo.lam.toFixed(2) + ' and omega_log ' + Math.round(demo.wlog) + ' K the estimated Tc is ' + tc.toFixed(1) + ' K');
  };
