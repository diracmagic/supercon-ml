import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const read = path => fs.readFileSync(new URL('../app/dist/' + path, import.meta.url), 'utf8');
const report = JSON.parse(fs.readFileSync(new URL('../results/validation/unsupervised-first-comparison.json', import.meta.url), 'utf8'));
const methods = JSON.parse(fs.readFileSync(new URL('../data/model_method_sources.json', import.meta.url), 'utf8'));
const source = read('js/definitions/unsupervised-results.js');
const plain = value => JSON.parse(JSON.stringify(value));
const descendants = node => typeof node === 'string' ? [] : [node, ...node.children.flatMap(descendants)];
const text = node => typeof node === 'string' ? node : node.textContent + node.children.map(text).join(' ');
const han = /[\u3400-\u4dbf\u4e00-\u9fff]/u;

// Conservative Arial-like glyph estimates are a geometry regression check, not
// a substitute for real-browser font/rendering QA. The production label() runs.
function estimatedWidth(value, font) {
  const size = Number(/([\d.]+)px/.exec(font)?.[1] || 12);
  return [...String(value)].reduce((sum, char) => sum +
    (/\s/.test(char) ? .29 : /[ilI1.,:;'|!]/.test(char) ? .28 :
      /[MW@%]/.test(char) ? .88 : /[A-Z]/.test(char) ? .67 :
        /[0-9]/.test(char) ? .57 : /[-+()/]/.test(char) ? .39 : .55), 0) * size;
}

function harness(width = 390, reduced = false) {
  const ids = new Map(), paint = [], scheduled = [];
  let path = null;
  const palette = { surface: '#ffffff', surface2: '#e9eff7', ink: '#102030', ink2: '#203040', muted: '#607080',
    grid: '#d0d8e0', axis: '#8899aa', accent: '#2471bc', warm: '#bb6611', font: 'Arial, sans-serif' };
  const ctx = {
    font: '12px Arial', textAlign: 'left', textBaseline: 'alphabetic', fillStyle: palette.surface, globalAlpha: 1,
    measureText(value) { return { width: estimatedWidth(value, this.font) }; },
    fillText(value, x, y) {
      const w = this.measureText(value).width;
      const size = Number(/([\d.]+)px/.exec(this.font)[1]);
      const left = x - (this.textAlign === 'right' ? w : this.textAlign === 'center' ? w / 2 : 0);
      paint.push({ kind: 'text', value: String(value), x, y, left, right: left + w,
        top: y - size, bottom: y + size * .23, font: this.font, color: this.fillStyle });
    },
    fillRect(x, y, w, h) { paint.push({ kind: 'rect', x, y, w, h, color: this.fillStyle }); },
    beginPath() { path = { kind: 'path', points: [] }; },
    rect(x, y, w, h) { path = { kind: 'rect', x, y, w, h }; },
    roundRect(x, y, w, h, radius) { assert.ok(Number.isFinite(radius) && radius >= 0); path = { kind: 'rect', x, y, w, h }; },
    moveTo(x, y) { assert.equal(path?.kind, 'path'); path.points.push([x, y]); },
    lineTo(x, y) { assert.equal(path?.kind, 'path'); path.points.push([x, y]); },
    arc(x, y, radius, start, end) {
      assert.ok([x, y, radius, start, end].every(Number.isFinite) && radius >= 0);
      path = { kind: 'circle', x, y, radius };
    },
    setLineDash(values) { assert.ok(values.every(Number.isFinite)); this.dash = [...values]; },
    fill() { assert.ok(path); paint.push({ ...path, color: this.fillStyle, alpha: this.globalAlpha }); },
    stroke() { assert.ok(path); paint.push({ ...path, stroke: true, color: this.strokeStyle, alpha: this.globalAlpha, lineWidth: this.lineWidth, dash: [...(this.dash || [])] }); },
    clearRect() {}, setTransform(...args) { assert.ok(args.every(Number.isFinite)); }
  };
  function h(tag, attrs = {}, ...children) {
    attrs ||= {};
    const node = { tag, attrs: { ...attrs }, children: [], style: {}, hidden: false, textContent: String(attrs.text || ''),
      appendChild(child) { this.children.push(child); if (typeof child === 'object') child.parentNode = this; return child; },
      setAttribute(key, value) { this.attrs[key] = String(value); }, getAttribute(key) { return this.attrs[key]; },
      addEventListener() {}, getBoundingClientRect() { return { width, left: 0, top: 0 }; },
      getContext() { assert.equal(tag, 'canvas'); return ctx; }
    };
    if (attrs.id) ids.set('#' + attrs.id, node);
    for (const child of children.flat(Infinity)) if (child !== null && child !== undefined) node.appendChild(child);
    return node;
  }
  const root = h('section', { id: 'demos' });
  const clear = node => { node.children = []; node.textContent = ''; };
  const sandbox = {
    DEMOS: [], demo: null, RAMP_LIGHT: [], TC_MAX: 0, view: 'progress',
    store: { get: key => key === 'demo' ? 'unsupervised' : null, set() {} },
    h, clear, append: (node, children) => children.forEach(child => node.appendChild(child)),
    $: selector => { assert.ok(ids.has(selector), 'Missing actual demo element: ' + selector); return ids.get(selector); },
    richText: (node, value) => { clear(node); node.textContent = value; return node; },
    renderRefs: node => clear(node), reducedMotion: () => reduced,
    document: { hidden: false, documentElement: { getAttribute: () => 'light' }, querySelectorAll: () => [], createTextNode: value => String(value) },
    window: { devicePixelRatio: 1, addEventListener() {}, matchMedia: () => ({ matches: false }) },
    getComputedStyle: () => ({ getPropertyValue: name => palette[name.slice(2).replace('-2', '2')] || '' }),
    requestAnimationFrame: callback => { scheduled.push(callback); return scheduled.length; },
    PRED_MODES: [], MODEL_VARIANTS: [], G: { prev: '<', next: '>', pause: 'pause', play: 'play' },
    STORY: [{ title: 'Tour', refs: [] }], HUR_STAGES: [{ node: 'Hurricane' }], RAD_STAGES: [{ node: 'Radar' }],
    MODEL_STAGES: { baseline: [{}] }, MODEL_LABEL: {}, MODEL_REFS: {},
    predExamples: () => [], stormStages: () => [{ node: 'Storm' }],
    drawStory() { throw new Error('Wrong story draw route'); },
    drawModel() { throw new Error('Wrong model draw route'); },
    drawStorm() { throw new Error('Wrong Storm draw route'); },
    drawHurricane() { throw new Error('Wrong Hurricane draw route'); },
    drawRadar() { throw new Error('Wrong Radar draw route'); },
    drawPredict() { throw new Error('Wrong prediction draw route'); }
  };
  const context = vm.createContext(sandbox);
  vm.runInContext(read('js/definitions/citation-contact.js'), context);
  vm.runInContext(read('js/definitions/demo-player.js'), context);
  vm.runInContext(read('js/definitions/tour.js'), context);
  vm.runInContext(source, context);
  vm.runInContext(read('js/initialize/demo-player.js'), context);
  vm.runInContext('initializeSuperconDemoPlayer(); buildDemos();', context);
  return { context, root, ids, paint, scheduled, palette,
    run: code => vm.runInContext(code, context),
    draw(stage = 3, time = 0, playing = true) {
      paint.length = 0;
      context.demo.unsupStage = stage; context.demo.unsupT = time; context.demo.unsupPlay = playing;
      vm.runInContext('drawUnsupervisedResults(demo.ctx, colors())', context);
      return plain(paint);
    }
  };
}

test('three result bars exactly match the audited within-run U0/U1 numbers', () => {
  const h = harness();
  const rows = plain(h.run('unsupervisedResults()'));
  assert.equal(rows.length, 3);
  assert.deepEqual(rows.map(row => row.id), ['storm-mae', 'hurricane-auc', 'hurricane-recall']);
  assert.deepEqual(rows.map(row => [row.before, row.after]), [
    [report.storm7.metrics.U0.point.mae_k, report.storm7.metrics.U1.point.mae_k],
    [report.hurricane8.macro.U0.observed_pu_auc, report.hurricane8.macro.U1.observed_pu_auc],
    [report.hurricane8.macro.U0.recall_at_budget * 100, report.hurricane8.macro.U1.recall_at_budget * 100]
  ]);
  assert.equal(rows[0].direction, 'Lower is better');
  assert.ok(rows.slice(1).every(row => row.direction === 'Higher is better'));
  const signed = (value, digits) => (value >= 0 ? '+' : '') + value.toFixed(digits);
  const storm = report.storm7.paired_U1_minus_U0.overall;
  const quantities = report.hurricane8.paired_U1_minus_U0.quantities;
  assert.equal(rows[0].delta, signed(storm.delta_mae_k_new_minus_reference, 4) + ' K');
  assert.equal(rows[1].delta, signed(quantities.observed_pu_auc.delta_new_minus_reference, 4));
  assert.equal(rows[2].delta, signed(quantities.recall_at_budget.delta_new_minus_reference * 100, 2) + ' percentage points');
  for (const [row, interval, factor, digits] of [
    [rows[0], storm.percentile_95_interval_k, 1, 4],
    [rows[1], [quantities.observed_pu_auc.lower95, quantities.observed_pu_auc.upper95], 1, 4],
    [rows[2], [quantities.recall_at_budget.lower95, quantities.recall_at_budget.upper95], 100, 2]
  ]) {
    assert.ok(interval[0] < 0 && interval[1] > 0);
    for (const bound of interval) assert.ok(row.interval.includes(signed(bound * factor, digits)));
    assert.equal(row.lower, interval[0] * factor);
    assert.equal(row.upper, interval[1] * factor);
    assert.ok(row.changeRange > Math.max(Math.abs(row.lower), Math.abs(row.upper)));
  }
  assert.equal(rows[0].change, storm.delta_mae_k_new_minus_reference);
  assert.equal(rows[1].change, quantities.observed_pu_auc.delta_new_minus_reference);
  assert.equal(rows[2].change, quantities.recall_at_budget.delta_new_minus_reference * 100);
  assert.equal(report.adopted, false);
  const caption = h.run('unsupervisedCaption()');
  assert.match(caption, /no new model adopted/i);
  assert.match(caption, /computed Tc/);
  assert.match(caption, /not superconductivity probabilities/);
  assert.match(caption, /not a new blind test/);
});

test('all four animated scenes stay finite and English within 280, 390 and 1000 pixel layouts', () => {
  for (const width of [280, 390, 1000]) {
    const h = harness(width);
    assert.equal(h.context.demo.W, width);
    assert.equal(h.context.demo.H, width < 560 ? 600 : 510);
    for (const stage of [0, 1, 2, 3]) for (const time of [0, .75, 2.3, 4, 7.9]) {
      const paint = h.draw(stage, time);
      assert.ok(paint.length > 20 && paint.length < 250, 'Bounded result drawing');
      for (const item of paint) {
        if (item.kind === 'text') {
          for (const key of ['x', 'y', 'left', 'right', 'top', 'bottom']) assert.ok(Number.isFinite(item[key]));
          assert.ok(item.left >= 0 && item.right <= width, `${width}px scene ${stage} horizontal overflow: ${item.value} (${item.left}, ${item.right})`);
          assert.ok(item.top >= 0 && item.bottom <= h.context.demo.H, `${width}px scene ${stage} vertical overflow: ${item.value}`);
          assert.doesNotMatch(item.value, han);
          assert.doesNotMatch(item.value, /doi\.org|10\.\d{4,9}\/|https?:|KMeans|\bRBF\b|\bPCA\b|\bSVD\b|2020|2022|Roter|prior work|references?/i,
            'Citations and methodological context belong beneath the canvas');
        } else {
          const points = item.kind === 'path' ? item.points : item.kind === 'circle' ?
            [[item.x - item.radius, item.y - item.radius], [item.x + item.radius, item.y + item.radius]] :
            [[item.x, item.y], [item.x + item.w, item.y + item.h]];
          if (item.kind === 'rect') assert.ok(item.w >= 0 && item.h >= 0);
          for (const [x, y] of points) assert.ok(Number.isFinite(x) && Number.isFinite(y) && x >= 0 && x <= width && y >= 0 && y <= h.context.demo.H,
            `${width}px scene ${stage} invalid ${item.kind} point ${x}, ${y}`);
        }
      }
      assert.doesNotMatch(h.context.demo.canvas.attrs['aria-label'], han);
    }
    const visible = h.draw(3).filter(item => item.kind === 'text').map(item => item.value).join(' ');
    for (const expected of ['0.967 K', '0.975 K', '0.604', '0.601', '24.8%', '25.4%', 'No new model adopted.']) assert.ok(visible.includes(expected), expected);
  }
});

test('each metric genuinely animates baseline then challenger then the audited interval, never counting numerical labels', () => {
  const h = harness();
  const before = plain(h.run('unsupervisedResults()'));
  const barWidth = (paint, color) => paint.find(item => item.kind === 'rect' && !item.stroke && item.h === 17 && item.color === color)?.w || 0;
  const interval = paint => paint.filter(item => item.kind === 'path' && item.stroke && item.color === h.palette.accent && item.lineWidth === 3);
  for (const [stage, row] of before.entries()) {
    const start = h.draw(stage, 0), blueHalf = h.draw(stage, .75), blueEnd = h.draw(stage, 1.5);
    const orangeHalf = h.draw(stage, 2.35), orangeEnd = h.draw(stage, 3.1), fading = h.draw(stage, 4), complete = h.draw(stage, 4.8);
    assert.equal(barWidth(start, h.palette.accent), 0);
    assert.ok(barWidth(blueHalf, h.palette.accent) > 0 && barWidth(blueHalf, h.palette.accent) < barWidth(blueEnd, h.palette.accent));
    assert.equal(barWidth(blueEnd, h.palette.warm), 0, 'The challenger waits for the baseline');
    assert.ok(barWidth(orangeHalf, h.palette.warm) > 0 && barWidth(orangeHalf, h.palette.warm) < barWidth(orangeEnd, h.palette.warm));
    assert.equal(barWidth(orangeEnd, h.palette.accent), barWidth(blueEnd, h.palette.accent));
    assert.ok(Math.abs(barWidth(complete, h.palette.warm) / barWidth(complete, h.palette.accent) - row.after / row.before) < 1e-12);
    assert.equal(interval(orangeEnd).length, 3);
    assert.ok(interval(orangeEnd).every(item => item.alpha === 0));
    assert.ok(interval(fading).every(item => item.alpha > 0 && item.alpha < 1));
    assert.ok(interval(complete).every(item => item.alpha === 1));
    const span = interval(complete)[0].points;
    const zero = complete.find(item => item.kind === 'path' && item.dash?.length)?.points[0][0];
    const marker = complete.find(item => item.kind === 'circle' && !item.stroke && item.radius === 6);
    assert.ok(span[0][0] < zero && zero < span[1][0], 'The real interval crosses zero');
    assert.ok(row.change > 0 ? marker.x > zero : marker.x < zero, 'The point estimate has the correct sign');
    assert.ok(Math.abs((marker.x - span[0][0]) / (span[1][0] - span[0][0]) - (row.change - row.lower) / (row.upper - row.lower)) < 1e-12);
    for (const paint of [start, blueHalf, blueEnd, orangeHalf, orangeEnd, fading, complete]) {
      const labels = paint.filter(item => item.kind === 'text').map(item => item.value);
      for (const value of [row.before, row.after]) assert.ok(labels.includes(value.toFixed(row.digits) + row.unit), 'Every numerical label stays at its audited value');
      assert.ok(labels.includes('Change: ' + row.delta));
      assert.match(h.context.demo.canvas.attrs['aria-label'], /No new model adopted/);
    }
  }
  assert.deepEqual(plain(h.run('unsupervisedResults()')), before);
});

test('reduced motion always shows the complete static summary and hides all motion controls', () => {
  const reduced = harness(390, true);
  assert.equal(reduced.context.demo.unsupPlay, false);
  for (const name of ['play', 'prev', 'next']) assert.equal(reduced.ids.get('#unsup-' + name).hidden, true);
  assert.match(reduced.ids.get('#unsup-readout').textContent, /Complete audited results/);
  const still = reduced.draw(0, 0, true);
  for (const stage of [0, 1, 2, 3]) assert.deepEqual(reduced.draw(stage, 120, true), still, 'Preference overrides stale animation state');
  assert.equal(reduced.context.demo.canvas.attrs['aria-label'], reduced.run('unsupervisedCaption()'));
});

test('native references are beneath the canvas, cite clustering/PCA precedents and PR17, and stay English', () => {
  const h = harness(), refs = h.ids.get('#demo-refs');
  const stage = h.root.children.findIndex(child => child.attrs?.class === 'demo-stage');
  const refIndex = h.root.children.indexOf(refs);
  assert.ok(stage >= 0 && refIndex > stage);
  assert.equal(descendants(h.root.children[stage]).filter(node => node.tag === 'a').length, 0);
  const content = text(refs);
  assert.match(content, /clustering/i); assert.match(content, /SVD\/PCA/); assert.match(content, /KMeans/);
  assert.match(content, /training features only/); assert.match(content, /do not establish a superconductivity mechanism/);
  assert.doesNotMatch(content + h.ids.get('#demo-caption').textContent, han);
  assert.doesNotMatch(content, /\uFFFD|\u00e2\u20ac|\u00c2\u00b7/, 'Reference text must not contain UTF-8 decoding artifacts');
  const links = descendants(refs).filter(node => node.tag === 'a');
  assert.equal(links.length, 3);
  for (const id of ['roter2020-pca', 'roter2022-clustering']) {
    const expected = methods.selected_references.find(row => row.id === id);
    assert.ok(expected, id);
    const node = links.find(link => link.attrs.href === 'https://doi.org/' + expected.doi);
    assert.ok(node, id + ' has its direct paper DOI');
    assert.equal(node.textContent, expected.title);
    assert.ok(content.includes(String(expected.year)));
  }
  assert.ok(links.some(link => link.attrs.href === report.pull_request));
});

test('demo-player routes, controls, sizing and animation scheduling use the results demo', () => {
  for (const [reduced, playing, expectedFrames] of [[false, true, 1], [false, false, 0], [true, true, 0]]) {
    const h = harness(390, reduced);
    const route = h.run('demoDef()');
    assert.equal(route.id, 'unsupervised'); assert.equal(route.unsupervised, true);
    assert.equal(h.ids.get('#demo-unsup-row').hidden, false);
    assert.equal(h.ids.get('#demo-zoo').hidden, true);
    for (const name of ['temp', 'ad', 'story', 'model', 'storm', 'hur', 'rad']) assert.equal(h.ids.get('#demo-' + name + '-row').hidden, true);
    h.context.view = 'demos'; h.context.demo.unsupPlay = playing;
    h.paint.length = 0;
    h.run('frame(1000)');
    assert.equal(h.scheduled.length, expectedFrames);
    assert.ok(h.paint.some(item => item.value === (reduced ? 'Unsupervised learning: results' : 'Storm 7: DFT Tc error')), 'Frame selected the real results renderer');
    if (reduced) assert.equal(h.context.demo.canvas.attrs['aria-label'], h.run('unsupervisedCaption()'));
    else assert.match(h.context.demo.canvas.attrs['aria-label'], /Storm 7, result 1 of 4/);
  }
});

test('real previous/play/next controls wrap scenes, reset only their clock and freeze animation when paused or hidden', () => {
  const h = harness();
  h.context.view = 'demos';
  h.context.demo.unsupT = 5;
  h.ids.get('#unsup-prev').attrs.onclick();
  assert.equal(h.context.demo.unsupStage, 3);
  assert.equal(h.context.demo.unsupT, 0);
  assert.match(h.ids.get('#unsup-readout').textContent, /Result 4 of 4 \/ Conclusion/);
  h.ids.get('#unsup-next').attrs.onclick();
  assert.equal(h.context.demo.unsupStage, 0);
  assert.match(h.ids.get('#unsup-readout').textContent, /Result 1 of 4 \/ Storm/);
  for (const stage of [1, 2, 3, 0]) {
    h.context.demo.unsupT = 7.99; h.context.demo.last = 1000;
    h.run('frame(1050)');
    assert.equal(h.context.demo.unsupStage, stage);
    assert.equal(h.context.demo.unsupT, 0);
  }
  h.context.demo.unsupT = 2.2;
  h.ids.get('#unsup-play').attrs.onclick();
  assert.equal(h.context.demo.unsupPlay, false);
  const framesBeforePause = h.scheduled.length;
  h.paint.length = 0; h.context.demo.last = 1000; h.run('frame(1050)');
  const pausedPaint = plain(h.paint);
  h.paint.length = 0; h.run('frame(1100)');
  assert.equal(h.context.demo.unsupT, 2.2);
  assert.equal(h.scheduled.length, framesBeforePause);
  assert.deepEqual(plain(h.paint), pausedPaint, 'Paused geometry stays at its exact partial-reveal state');
  h.ids.get('#unsup-next').attrs.onclick();
  assert.equal(h.context.demo.unsupStage, 1);
  assert.equal(h.context.demo.unsupT, 0);
  assert.equal(h.context.demo.unsupPlay, false, 'Manual stepping does not silently resume playback');
  h.ids.get('#unsup-play').attrs.onclick();
  assert.equal(h.context.demo.unsupPlay, true);
  h.context.demo.last = 1000; h.run('frame(1050)');
  assert.ok(h.context.demo.unsupT > 0);
  for (const hidden of [false, true]) {
    h.context.view = hidden ? 'demos' : 'papers';
    h.context.document.hidden = hidden;
    const time = h.context.demo.unsupT, frames = h.scheduled.length;
    h.paint.length = 0; h.run('frame(1200)');
    assert.equal(h.context.demo.unsupT, time);
    assert.equal(h.scheduled.length, frames);
    assert.equal(h.paint.length, 0, 'Hidden demos do not draw or schedule work');
  }
});
