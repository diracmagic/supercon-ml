import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const read = path => fs.readFileSync(new URL('../app/dist/' + path, import.meta.url), 'utf8');

test('ideal zero-resistance illustration has no finite-resistance tail below Tc', () => {
  const context = vm.createContext({});
  vm.runInContext(read('js/definitions/demo-player.js'), context);
  for (const t of [0, .1, .5, .95, .99, .999999]) assert.equal(vm.runInContext('resistanceOf(' + t + ')', context), 0);
  for (const t of [1, 1.01, 1.4, 1.6]) assert.ok(vm.runInContext('resistanceOf(' + t + ')', context) > 0);
  const captions = read('js/initialize/demo-player.js');
  assert.match(captions, /not measured data/);
  assert.match(captions, /zero magnetic field and below the critical current/);
  assert.match(captions, /weak-field Meissner state/);
  assert.match(captions, /not literal trajectories of a Cooper pair/);
});

test('topic illustrations retain material distinctions without inventing cages, pressure or observed modes', () => {
  const context = vm.createContext({ list: value => Array.isArray(value) ? value : [] });
  vm.runInContext(read('js/definitions/news-drawings.js'), context);
  const art = entry => vm.runInContext('newsArt(' + JSON.stringify(entry) + ')', context);
  const expected = { Hydrides: 'hydride', Nickelates: 'layered', Topological: 'topo', 'Iron-based': 'iron', 'Heavy fermions': 'heavy' };
  for (const [topic, motif] of Object.entries(expected)) assert.equal(art({ topics: [topic], title: 'Superconductivity study' }), 'news-' + motif);
  assert.equal(art({ topics: ['Triplet and ruthenates'], title: 'Superconductivity study' }), 'news-research');
  assert.equal(art({ topics: ['Hydrides', 'Cuprates'], title: 'Superconductivity study' }), 'news-features');
  assert.equal(art({ topics: ['Nickelates'], title: 'Infinite-layer nickelate film' }), 'news-layered');
  assert.equal(art({ topics: ['Nickelates'], title: 'Bilayer nickelate film' }), 'news-nickelate');
  assert.equal(art({ topics: ['Nickelates'], title: 'Bilayer and infinite-layer nickelates' }), 'news-layered');
  assert.equal(art({ topics: ['Kagome'], title: 'Kagome superconductor' }), 'news-kagome');
  assert.equal(art({ topics: ['Cuprates'], title: 'Cuprate normal-state study' }), 'news-cuprate');
  assert.equal(art({ title: 'No superconductivity detected in a tested candidate' }), 'news-research');
});

test('article subject selects distinct AI, model and superconductivity illustrations', () => {
  const context = vm.createContext({ list: value => Array.isArray(value) ? value : [] });
  vm.runInContext(read('js/definitions/news-drawings.js') + read('js/definitions/ai-view.js'), context);
  const art = entry => vm.runInContext('aiArticleArt(' + JSON.stringify(entry) + ')', context);
  const examples = [
    ['Structured Extraction and Retrieval-Augmented Question Answering over Superconductivity Literature', 'literature'],
    ['Competition between stripes and superconductivity in the Hubbard model', 'stripes'],
    ['Learning the Geometry of Materials Space with Trained Neural Tangent Kernels', 'features'],
    ['ALIGNN 2.0 unified line-graph neural network', 'graph'],
    ['Guided diffusion for the discovery of new superconductors', 'search'],
    ['Orbital-projected density of states', 'spectrum'],
    ['Storm 5.0: a 90% range for every prediction', 'interval'],
    ['Storm 1.0: an AI agent designs a better Tc model', 'tree'],
    ['Hurricane 2.0: predicting unconventional Tc in two parts', 'two-stage'],
    ['Radar 1.0: a router between Storm and Hurricane', 'routing'],
    ['Unusual quantum states in six-layer graphene', 'layered-six'],
    ['Terahertz light probes superconducting vortices', 'vortex'],
    ['UTe2 reveals two flavors under extreme pressure', 'pressure']
  ];
  for (const [title, kind] of examples) assert.equal(art({ title, topics: ['AI and data'] }), 'news-' + kind, title);
  assert.equal(art({ title: 'New superconductors in a structure type', ai_kind: 'experiment' }), 'news-measurement');
  assert.equal(art({ title: 'Layered material', topics: ['Moiré and 2D'], abstract: 'Twisted layers are examined.' }), 'news-moire');
  assert.doesNotMatch(read('js/definitions/papers-view.js'), /miniCanvas\('news-ai'\)/, 'Selected advances must also use their subject');
});

test('every registered news motif produces finite foreground drawing at thumbnail sizes and reduced motion time', () => {
  const context = vm.createContext({ MINI_DRAW: {}, MINI_STATIC: {}, MINI_ALT: {}, NEWS_ART: null, stAlpha: value => value, stRng: () => () => .5, mix: a => a, stRound: () => {} });
  vm.runInContext(read('js/initialize/news-drawings.js'), context);
  vm.runInContext('initializeSuperconNewsDrawings()', context);
  const methods = ['save', 'restore', 'setLineDash', 'translate', 'rotate', 'beginPath', 'closePath', 'stroke', 'fill', 'fillRect', 'strokeRect', 'rect', 'moveTo', 'lineTo', 'arc', 'ellipse', 'fillText'];
  for (const [kind, draw] of Object.entries(context.MINI_DRAW)) {
    assert.ok(context.MINI_ALT[kind], kind + ' has a description');
    for (const [width, height] of [[112, 84], [168, 126]]) for (const time of [0, 1.2, 5]) {
      let paint = 0;
      const canvas = Object.fromEntries(methods.map(method => [method, (...args) => { for (const arg of args) if (typeof arg === 'number') assert.ok(Number.isFinite(arg), kind + ' ' + method); if (['stroke', 'fill', 'fillRect', 'strokeRect', 'fillText'].includes(method)) paint++; }]));
      draw(canvas, { surface: '#fff', accent: '#368', ink: '#123', ink2: '#234', axis: '#678', grid: '#abc', muted: '#789', warm: '#c63' }, width, height, time);
      assert.ok(paint >= 2, kind + ' must visibly paint rather than show an empty canvas');
    }
  }
  assert.match(context.MINI_ALT['news-hydride'], /unbonded/);
  assert.match(context.MINI_ALT['news-topo'], /not evidence/);
  assert.match(context.MINI_ALT['news-spectrum'], /not measured/);
  let sheetCount = 0;
  const sheets = Object.fromEntries(methods.map(method => [method, () => { if (method === 'closePath') sheetCount++; }]));
  context.MINI_DRAW['news-layered-six'](sheets, { accent: '#368' }, 112, 84, 1.2);
  assert.equal(sheetCount, 6, 'An explicitly six-layer graphene article shows six sheets without assuming twist');
});

test('kagome news drawing has both corner-sharing orientations and no fabricated CDW distortion', () => {
  const context = vm.createContext({ MINI_DRAW: {}, MINI_STATIC: {}, MINI_ALT: {}, NEWS_ART: null, stAlpha: value => value, stRng: () => () => .5 });
  vm.runInContext(read('js/initialize/news-drawings.js'), context);
  vm.runInContext('initializeSuperconNewsDrawings()', context);
  const segments = [], circles = [];
  let start;
  const canvas = { save() {}, restore() {}, setLineDash() {}, translate() {}, rotate() {}, beginPath() {}, stroke() {}, fill() {},
    moveTo(x, y) { start = [x, y]; }, lineTo(x, y) { segments.push([start, [x, y]]); start = [x, y]; }, arc(x, y) { circles.push([x, y]); } };
  const render = time => { segments.length = 0; circles.length = 0; context.MINI_DRAW['news-kagome'](canvas, { accent: '#000' }, 112, 84, time); return JSON.stringify({ segments, circles }); };
  assert.equal(render(0), render(5), 'Only the view angle changes; all intersite distances stay fixed');
  const key = p => p.map(v => v.toFixed(5)).join(',');
  const neighbours = new Map(circles.map(p => [key(p), new Set()]));
  for (const [a, b] of segments) { assert.ok(Math.abs(Math.hypot(a[0] - b[0], a[1] - b[1]) - 14) < 1e-7); neighbours.get(key(a)).add(key(b)); neighbours.get(key(b)).add(key(a)); }
  assert.equal(Math.max(...[...neighbours.values()].map(set => set.size)), 4);
  assert.ok([...neighbours.values()].filter(set => set.size === 4).length > 50, 'Interior sites belong to two joined triangles, not isolated triangle islands');
  assert.match(context.MINI_ALT['news-kagome'], /no charge-density wave/);
});

test('nickelate educational drawing distinguishes an interlayer-pairing proposal from observations', () => {
  assert.match(read('js/initialize/theory-drawings.js'), /proposed interlayer pairing/);
  assert.match(read('js/initialize/theory-drawings-2.js'), /not measured electron trajectories or an established mechanism/);
  const content = read('js/initialize/theory-view.js');
  assert.match(content, /pairing mechanism is not established/);
  assert.match(content, /'zhou2026', 'lu2024'/);
});

test('LaH10 educational view renders a trivalent 32-hydrogen cage rather than an invented 18-site ring', () => {
  const dots = [], strokes = [];
  let start, current = [];
  const context = vm.createContext({ MINI_DRAW: {}, MINI_STATIC: {}, stRng: () => () => .5,
    stAlpha: value => value, stSpan: (value, lo, hi) => Math.max(0, Math.min(1, (value - lo) / (hi - lo))),
    dot(_canvas, x, y, radius) { dots.push([x, y, radius]); }, label() {}, stText() {} });
  vm.runInContext(read('js/initialize/theory-drawings.js'), context);
  vm.runInContext('initializeSuperconTheoryDrawings()', context);
  const canvas = { save() {}, restore() {}, setLineDash() {}, measureText: text => ({ width: text.length * 5 }),
    beginPath() { current = []; }, moveTo(x, y) { start = [x, y]; }, lineTo(x, y) { current.push([start, [x, y]]); start = [x, y]; },
    closePath() {}, fill() {}, stroke() { strokes.push(current); } };
  context.MINI_DRAW.hydride(canvas, { accent: '#000', font: 'sans-serif' }, 300, 120, 1.6);
  assert.equal(dots.filter(point => point[2] === 2.3).length, 32);
  assert.equal(dots.filter(point => point[2] === 8.5).length, 1);
  const cageEdges = strokes.find(path => path.length === 48);
  assert.ok(cageEdges, 'H32 cage has 48 edges');
  const key = p => p.map(v => v.toFixed(6)).join(',');
  const degree = new Map();
  for (const edge of cageEdges) for (const p of edge) degree.set(key(p), (degree.get(key(p)) || 0) + 1);
  assert.equal(degree.size, 32); assert.ok([...degree.values()].every(value => value === 3));
  assert.match(read('js/initialize/theory-drawings-2.js'), /approximate coordinates from a calculated cubic LaH/);
});
