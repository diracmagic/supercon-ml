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

test('headline subjects pick their own schematic and known mismatches stay fixed', () => {
  const context = vm.createContext({ list: value => Array.isArray(value) ? value : [] });
  vm.runInContext(read('js/definitions/news-drawings.js'), context);
  const art = entry => vm.runInContext('newsArt(' + JSON.stringify(entry) + ')', context);
  const cases = [
    [{ title: 'Approaching Landauer’s limit in a single superconducting vortex memory bit', topics: ['Topological'] }, 'vortex'],
    [{ title: 'Orbital angular momentum transfer from terahertz vortex beam to a superconductor' }, 'light'],
    [{ title: 'NTL amplification in a SuperCDMS-style detector', topics: ['Iron-based'] }, 'detector'],
    [{ title: 'Single-photon detection in few-layer NbSe2 superconducting nanowires' }, 'detector'],
    [{ title: 'Field-free superconducting diode and tunable vortex dynamics in NbN/FePt stripe-domain heterostructures' }, 'diode'],
    [{ title: 'Parity-Resolved Many-Body Kinetics of a Topological Qubit under Nonequilibrium Phonon Pulses', topics: ['Topological', 'Electron–phonon'] }, 'qubit'],
    [{ title: 'Growth Phase Map of Tantalum as a Function of Oxygen Partial Pressure' }, 'interface'],
    [{ title: 'Superconductivity from doping symmetric mass generation insulators: application to La3Ni2O7 under pressure' }, 'pressure'],
    [{ title: 'Magic-angle graphene provides evidence for unconventional superconductivity' }, 'moire'],
    [{ title: 'Superconductivity and ferroelectric orbital magnetism in semimetallic rhombohedral hexalayer graphene' }, 'layered-six'],
    [{ title: 'High-temperature superconductivity at 100K in La3−xNdxNi2O7', topics: ['Nickelates'] }, 'nickelate'],
    [{ h: 'The lutetium hydride room-temperature claim is retracted', cards: ['field', 'hydride'] }, 'research'],
    [{ h: 'Possible superconductivity near room temperature in LaSc₂H₂₄', cards: ['hydride'] }, 'hydride'],
    [{ h: 'Sr₂RuO₄ after thirty years', cards: ['triplet'] }, 'timeline'],
    [{ h: 'Two superconducting orders meet at a tetracritical point in UTe₂' }, 'competition'],
    [{ h: 'Spin fluctuations set Tc in electron-doped cuprates' }, 'spinfluct'],
    [{ h: 'Even and odd molecular spin chains couple differently to a superconductor' }, 'molecule'],
    [{ h: 'A dark optical cavity raises the Tc of NbSe₂' }, 'cavity'],
    [{ h: 'A type-I superconductor that breaks time-reversal symmetry: YbSb₂' }, 'trsb'],
    [{ h: 'Band quantum geometry selects Kekulé superconductivity in Haldane phases' }, 'kekule'],
    [{ h: 'Coherence length and penetration depth computed from first principles' }, 'penetration'],
    [{ title: 'Orbital-driven Fulde–Ferrell–Larkin–Ovchinnikov state in a layer-locked 3D Ising superconductor' }, 'fflo'],
    [{ title: 'A First-Order Phase Transition in Spin-Imbalanced BCS Theory of Superconductivity' }, 'zeeman'],
    [{ title: 'Universal Scaling of the Little-Parks Oscillation Amplitude' }, 'ring'],
    [{ h: 'An MgB₂ line carries 94 kA for the High-Luminosity LHC', cards: ['mgb2'] }, 'cable'],
    [{ h: 'A REBCO fusion magnet reaches 20 tesla', cards: ['rebco'] }, 'coil'],
    [{ title: 'From coherent to fermionized microwave photons in a superconducting transmission line' }, 'resonator'],
    [{ title: 'A pathway to improve Nb₃Sn for SRF accelerator cavities via Zr inclusion', topics: ['Electron–phonon'] }, 'rf'],
    [{ title: 'A Map to a Long-Sought Quantum Simulator', summary: 'Ultracold atoms in an optical lattice could emulate a model of quantum matter.' }, 'coldatoms'],
    [{ title: 'Superconducting proximity effect in a strongly correlated charge-transfer insulator' }, 'proximity'],
    [{ title: 'Enhanced superconductivity at quantum-critical KTaO3 interfaces' }, 'interface'],
    [{ title: 'Anisotropic thermoelectric transport in the Sr2RuO4-Ru eutectic system' }, 'thermal'],
    [{ title: 'Monolayer superconductors enter the circuit', topics: ['Moiré and 2D'] }, 'monolayer'],
    [{ title: 'Magnetic Exchange-Coupled Superconducting Devices with Broken Symmetry for Cryogenic Memory' }, 'magnetism'],
    [{ title: 'Tilt-Controlled Multi-Gap Superconductivity in Type-II Weyl Semimetals' }, 'multigap'],
    [{ h: 'Tunnelling measures the gap of H₃S', cards: ['eliashberg', 'hydride'] }, 'gapdos'],
    [{ title: 'Neural-network wavefunctions find stripes and d-wave pairing almost tied' }, 'nqs'],
    [{ title: 'Competition between charge-density-wave and superconducting orders on eight-leg square Hubbard cylinders' }, 'cylinder'],
    [{ title: 'High magnetic fields revive superconductivity in nickelates', topics: ['Nickelates'] }, 'reentrant'],
    [{ title: 'Mirror-selective quasiparticle interference in bilayer nickelate superconductor' }, 'qpi'],
    [{ title: 'Giant Domain Walls and Intrinsic Heterogeneity in 214 Cuprate Superconductors' }, 'domains'],
    [{ title: 'Protection of Unconventional Superconductivity from Disorder' }, 'disorder'],
    [{ title: 'Superconducting half-dome in bilayer nickelates' }, 'dome'],
    [{ title: 'Evidence for clean d-wave superconductivity in the samarium nickelates' }, 'dwave'],
    [{ title: 'Checkerboard-type Zhang-Rice states in overdoped cuprate superconductors' }, 'zr'],
    [{ title: 'Role of the Apical Oxygen in Cuprate High-Temperature Superconductors' }, 'apical'],
    [{ title: 'Conductance measurements cannot distinguish crossed Andreev reflection from elastic co-tunnelling' }, 'andreev'],
    [{ title: 'Cold atoms show the first fragments of charge stripes' }, 'coldatoms'],
    [{ title: 'Observation of superconductivity-induced leading-edge gap in a bilayer nickelate' }, 'gapdos'],
    [{ title: 'A nodeless gap in ambient-pressure nickelate films' }, 'multigap'],
    [{ title: 'Coexistence of high temperature superconductivity and antiferromagnetic order in a cuprate' }, 'competition'],
    [{ title: 'Higher-order electrical magnetochiral anisotropy effect in high-temperature cuprate superconductors' }, 'diode'],
    [{ title: 'Superconducting weak links at substrate steps in bilayer nickelate films' }, 'junction'],
    [{ title: 'Flux-Floquet Instability in Fluctuating Superconductors' }, 'light'],
    [{ title: 'Enhancing superconductivity using thermal bosons' }, 'eph'],
    [{ title: 'Coherent Electronic Lensing in Proximitized Graphene' }, 'proximity'],
    [{ title: 'Anomalous charge density wave in a two-dimensional superatomic superconductor' }, 'stripes'],
    [{ title: 'Chemists overturn 40-year assumption', summary: 'A patchwork of different crystal structures throughout its bulk.' }, 'domains']
  ];
  for (const [entry, motif] of cases) assert.equal(art(entry), 'news-' + motif, entry.title || entry.h);
  assert.notEqual(art({ title: 'Superconductivity in Sr₂RuO₄', cards: ['triplet'] }), 'news-triplet', 'A card alone never asserts a pairing state');
});

test('every motif the classifier can choose is registered with a description', () => {
  const context = vm.createContext({ MINI_DRAW: {}, MINI_STATIC: {}, MINI_ALT: {}, NEWS_ART: null, stAlpha: value => value, stRng: () => () => .5, mix: a => a, stRound: () => {} });
  vm.runInContext(read('js/initialize/news-drawings.js'), context);
  vm.runInContext(read('js/initialize/news-looks.js'), context);
  vm.runInContext('initializeSuperconNewsDrawings(); initializeSuperconNewsLooks()', context);
  const source = read('js/definitions/news-drawings.js'), start = source.indexOf('const newsArt = function newsArt(n) {');
  const classifier = source.slice(start, source.indexOf('\n  };\n', start));
  const chosen = [...new Set([...classifier.matchAll(/'(news-[a-z-]+)'/g)].map(m => m[1]))];
  assert.ok(chosen.length >= 50);
  for (const kind of chosen) {
    assert.equal(typeof context.MINI_DRAW[kind], 'function', kind);
    assert.ok(context.MINI_ALT[kind], kind + ' has a description');
  }
  for (const kind of ['news-diode', 'news-gapdos', 'news-ring', 'news-competition', 'news-penetration', 'news-cavity', 'news-zr', 'news-domains', 'news-dome', 'news-qpi',
    'news-andreev', 'news-reentrant', 'news-cylinder', 'news-nqs', 'news-disorder', 'news-apical', 'news-dwave']) assert.match(context.MINI_ALT[kind], /not|No /, kind + ' says what is not shown');
});

test('every registered news motif produces finite foreground drawing at thumbnail sizes and reduced motion time', () => {
  const context = vm.createContext({ MINI_DRAW: {}, MINI_STATIC: {}, MINI_ALT: {}, NEWS_ART: null, stAlpha: value => value, stRng: () => () => .5, mix: a => a, stRound: () => {} });
  vm.runInContext(read('js/initialize/news-drawings.js'), context);
  vm.runInContext(read('js/initialize/news-looks.js'), context);
  vm.runInContext('initializeSuperconNewsDrawings(); initializeSuperconNewsLooks()', context);
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
  const dashes = info => { let n = 0; const canvas = Object.fromEntries(methods.map(method => [method, (...args) => { if (method === 'setLineDash' && args[0].length) n++; }]));
    context.MINI_DRAW['news-dome'](canvas, { accent: '#368', warm: '#c63', ink2: '#234' }, 112, 84, 1.2, info); return n; };
  assert.ok(dashes({ title: 'Superconducting half-dome in bilayer nickelates' }) > dashes({ title: 'Superconducting dome in a kagome metal' }), 'Only a named half-dome leaves the far side dashed');
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
