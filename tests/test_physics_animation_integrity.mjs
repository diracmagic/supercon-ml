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

test('automatic topics cannot imply hydride cages, pressure, triplet pairing, CDW or Majorana observation', () => {
  const context = vm.createContext({ list: value => Array.isArray(value) ? value : [] });
  vm.runInContext(read('js/definitions/news-drawings.js'), context);
  const art = entry => vm.runInContext('newsArt(' + JSON.stringify(entry) + ')', context);
  for (const topics of [['Hydrides'], ['Nickelates'], ['Triplet and ruthenates'], ['Topological'], ['Iron-based'], ['Heavy fermions'], ['Hydrides', 'Cuprates']]) assert.equal(art({ topics, title: 'Superconductivity study' }), 'news-research');
  assert.equal(art({ topics: ['Nickelates'], title: 'Infinite-layer nickelate film' }), 'news-research');
  assert.equal(art({ topics: ['Nickelates'], title: 'Bilayer nickelate film' }), 'news-nickelate');
  assert.equal(art({ topics: ['Nickelates'], title: 'Bilayer and infinite-layer nickelates' }), 'news-research');
  assert.equal(art({ topics: ['Kagome'], title: 'Kagome superconductor' }), 'news-kagome');
  assert.equal(art({ topics: ['Cuprates'], title: 'Cuprate normal-state study' }), 'news-cuprate');
  assert.equal(art({ title: 'No superconductivity detected in a tested candidate' }), 'news-research');
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
