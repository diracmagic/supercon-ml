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
    beginPath() { path = null; },
    rect(x, y, w, h) { path = { x, y, w, h }; },
    roundRect(x, y, w, h, radius) { assert.ok(Number.isFinite(radius) && radius >= 0); path = { x, y, w, h }; },
    fill() { assert.ok(path); paint.push({ kind: 'rect', ...path, color: this.fillStyle }); },
    stroke() { assert.ok(path); paint.push({ kind: 'stroke', ...path, color: this.strokeStyle, alpha: this.globalAlpha, lineWidth: this.lineWidth }); },
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
    draw(clock = 0, playing = true) {
      paint.length = 0;
      context.demo.clock = clock; context.demo.unsupPlay = playing;
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
  }
  assert.equal(report.adopted, false);
  const caption = h.run('unsupervisedCaption()');
  assert.match(caption, /no new model adopted/i);
  assert.match(caption, /computed Tc/);
  assert.match(caption, /not superconductivity probabilities/);
  assert.match(caption, /not a new blind test/);
});

test('result canvas stays finite and English within 280, 390 and 1000 pixel layouts', () => {
  for (const width of [280, 390, 1000]) {
    const h = harness(width);
    assert.equal(h.context.demo.W, width);
    assert.equal(h.context.demo.H, width < 560 ? 600 : 510);
    const paint = h.draw(4);
    assert.ok(paint.length > 20 && paint.length < 250, 'Bounded result drawing');
    for (const item of paint) {
      const coordinates = item.kind === 'text' ? ['x', 'y', 'left', 'right', 'top', 'bottom'] : ['x', 'y', 'w', 'h'];
      for (const key of coordinates) assert.ok(Number.isFinite(item[key]), `${width}px ${item.kind} ${key}`);
      if (item.kind === 'text') {
        assert.ok(item.left >= 0 && item.right <= width, `${width}px horizontal overflow: ${item.value} (${item.left}, ${item.right})`);
        assert.ok(item.top >= 0 && item.bottom <= h.context.demo.H, `${width}px vertical overflow: ${item.value}`);
        assert.doesNotMatch(item.value, han);
        assert.doesNotMatch(item.value, /doi\.org|10\.\d{4,9}\/|https?:|KMeans|\bRBF\b|\bPCA\b|\bSVD\b|2020|2022|Roter|prior work|references?/i,
          'Citations and methodological context belong beneath the canvas');
      } else {
        assert.ok(item.w >= 0 && item.h >= 0 && item.x >= 0 && item.y >= 0);
        assert.ok(item.x + item.w <= width && item.y + item.h <= h.context.demo.H);
      }
    }
    const visible = paint.filter(item => item.kind === 'text').map(item => item.value).join(' ');
    for (const expected of ['0.967 K', '0.975 K', '0.604', '0.601', '24.8%', '25.4%', 'No new model adopted.']) assert.ok(visible.includes(expected), expected);
    assert.doesNotMatch(h.context.demo.canvas.attrs['aria-label'], han);
  }
});

test('motion highlights one row only, while pause and reduced motion keep fixed numbers without highlights', () => {
  const h = harness();
  const before = plain(h.run('unsupervisedResults()'));
  const first = h.draw(0, true), second = h.draw(4, true);
  const highlighted = paint => paint.filter(item => item.kind === 'stroke' && item.color === h.palette.accent);
  assert.equal(highlighted(first).length, 1);
  assert.equal(highlighted(second).length, 1);
  assert.notEqual(highlighted(first)[0].y, highlighted(second)[0].y);
  assert.deepEqual(first.filter(item => item.kind === 'text'), second.filter(item => item.kind === 'text'));
  for (const clock of [0, 4, 10000]) assert.equal(highlighted(h.draw(clock, false)).length, 0);
  assert.deepEqual(plain(h.run('unsupervisedResults()')), before);
  const reduced = harness(390, true);
  assert.equal(reduced.context.demo.unsupPlay, false);
  assert.equal(reduced.ids.get('#unsup-play').hidden, true);
  const still = reduced.draw(0, true);
  assert.equal(highlighted(still).length, 0, 'Preference overrides a stale play flag');
  assert.deepEqual(reduced.draw(120, true), still);
  assert.deepEqual(plain(reduced.run('unsupervisedResults()')), before);
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
    assert.ok(h.paint.some(item => item.value === 'Unsupervised learning: results'), 'Frame selected the real results renderer');
    assert.equal(h.context.demo.canvas.attrs['aria-label'], h.run('unsupervisedCaption()'));
  }
});
