import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const module = { exports: {} };
vm.runInNewContext(fs.readFileSync(new URL('../app/dist/team-material.js', import.meta.url), 'utf8'), { module });
const { createMaterialAnimation, normalizeKind, classifyMaterial, kinds, geometry } = module.exports;
class Target {
  constructor() { this.events = new Map(); }
  addEventListener(name, fn) { if (!this.events.has(name)) this.events.set(name, new Set()); this.events.get(name).add(fn); }
  removeEventListener(name, fn) { this.events.get(name)?.delete(fn); }
  emit(name) { for (const fn of [...(this.events.get(name) || [])]) fn({ target: this }); }
  get listenerCount() { return [...this.events.values()].reduce((sum, set) => sum + set.size, 0); }
}
class Element extends Target {
  constructor(tag) { super(); this.tagName = tag.toUpperCase(); this.children = []; this.attrs = {}; this._text = ''; this.hidden = false; this.open = false; }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  appendChild(child) { this.children.push(child); return child; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  set innerHTML(_) { throw new Error('Only text nodes are allowed'); }
  all() { return [this, ...this.children.flatMap(child => child.all())]; }
}
function harness({ kind = 'hydride_cage', caption, reduced = false } = {}) {
  const doc = new Target(); doc.hidden = false;
  doc.createElement = tag => new Element(tag); doc.createElementNS = (_namespace, tag) => new Element(tag);
  const details = new Element('details'), media = new Target(); media.matches = reduced;
  const observers = [], frames = new Map(), callbacks = [];
  let serial = 0, clock = 0;
  const win = { matchMedia: () => media,
    requestAnimationFrame(fn) { const id = ++serial; frames.set(id, fn); callbacks.push(fn); return id; },
    cancelAnimationFrame(id) { frames.delete(id); },
    IntersectionObserver: class {
      constructor(fn) { this.fn = fn; observers.push(this); }
      observe(target) { this.target = target; }
      disconnect() { this.disconnected = true; }
      emit(ratio) { this.fn([{ target: this.target, isIntersecting: ratio > 0, intersectionRatio: ratio }]); }
    }
  };
  const animation = createMaterialAnimation({ document: doc, window: win, details, kind, caption });
  const elements = tag => animation.node.all().filter(node => node.tagName === tag.toUpperCase());
  return { animation, doc, details, media, observers, frames, callbacks, elements,
    open() { details.open = true; details.emit('toggle'); observers[0].emit(1); },
    play() { elements('button')[0].emit('click'); },
    advance(count = 20) { for (let i = 0; i < count; i++) { clock += 100; const pending = [...frames]; frames.clear(); for (const [, fn] of pending) fn(clock); } }
  };
}

test('only controlled material motifs are selected and unknown input has an explicit generic fallback', () => {
  assert.equal(kinds.length, 8);
  for (const kind of kinds) {
    assert.equal(normalizeKind(kind), kind);
    const h = harness({ kind });
    assert.ok(h.elements('circle').length >= 4); assert.ok(h.elements('line').length >= 4);
    assert.match(h.animation.node.textContent, /not a complete crystal or measured motion/);
    assert.equal(h.frames.size, 0); h.animation.destroy();
  }
  for (const kind of [undefined, '', 'experimentally_confirmed', { kind: 'hydride_cage' }]) {
    assert.equal(normalizeKind(kind), 'unknown');
    const h = harness({ kind: kind || '' });
    assert.match(h.animation.node.textContent, /No material-specific structural illustration/);
  }
});

test('material classification requires specific motifs and never chooses between mixed families', () => {
  for (const [kind, label] of [['hydride_cage', 'Sodalite hydrogen-rich candidates'], ['octahedral_hydride', 'Hydride with octahedral coordination'], ['cuprate_layers', 'Copper-oxide research'], ['nickelate_layers', 'Bilayer nickelate films'], ['boron_carbon_network', 'Boron honeycomb network'], ['intermetallic', 'BCC intermetallic candidates'], ['kagome_net', 'Kagome lattice superconductor']]) {
    assert.equal(classifyMaterial({heading: label}), kind);
    assert.equal(classifyMaterial({result: label}), kind);
  }
  assert.equal(classifyMaterial({heading: 'Hydride and nickelate search'}), 'methodology');
  assert.equal(classifyMaterial({title: 'Cuprate study', result: 'Comparisons with borides'}), 'methodology');
  for (const heading of ['Hydrogen-rich candidates', 'Nickelate films', 'Infinite-layer nickelate', 'Bilayer versus infinite-layer nickelates', 'Boron–carbon network', 'Intermetallic candidates', 'Hydride without octahedral coordination', 'Kagome and cuprate comparison', 'Sodalite and octahedral hydride motifs']) assert.equal(classifyMaterial({heading}), 'methodology', heading);
  for (const entry of [null, [], {}, {heading: 42}, {heading: 'General composition model'}, {heading: 'x'.repeat(3000) + ' hydride'}]) assert.equal(classifyMaterial(entry), 'methodology');
  assert.equal(classifyMaterial({material_visual: 'intermetallic', heading: 'Hydride comparison'}), 'intermetallic');
  assert.equal(classifyMaterial({material_visual: 'invented_structure', heading: 'General search'}), 'methodology');
});

test('octahedral coordination has six equal radial neighbours in three antipodal pairs', () => {
  const { atoms, bonds } = geometry('octahedral_hydride');
  assert.equal(atoms.length, 7); assert.equal(bonds.length, 6);
  for (const a of atoms.slice(1)) {
    assert.equal(Math.hypot(a.x, a.y, a.z), 1);
    assert.ok(atoms.slice(1).some(b => a.x === -b.x && a.y === -b.y && a.z === -b.z));
  }
  assert.ok(bonds.every(([a]) => a === 0));
});

test('sodalite cage is a connected 24-vertex trivalent net, not a cube or hexagonal prism', () => {
  const { atoms, bonds } = geometry('hydride_cage');
  assert.equal(atoms.length, 25); assert.equal(bonds.length, 36);
  const degree = new Array(25).fill(0);
  for (const [a, b] of bonds) { degree[a]++; degree[b]++; }
  assert.equal(degree[0], 0); assert.ok(degree.slice(1).every(value => value === 3));
  const seen = new Set([1]); for (let pass = 0; pass < 24; pass++) for (const [a, b] of bonds) if (seen.has(a) || seen.has(b)) { seen.add(a); seen.add(b); }
  assert.equal(seen.size, 24);
});

test('oxide fragments put oxygen on every metal-metal link and distinguish a plane from a bilayer', () => {
  for (const [kind, layers] of [['cuprate_layers', 1], ['nickelate_layers', 2]]) {
    const { atoms, bonds } = geometry(kind), metals = atoms.filter(a => a.type === 1);
    assert.equal(new Set(metals.map(a => a.y)).size, layers);
    assert.ok(bonds.every(([a, b]) => atoms[a].type !== atoms[b].type), 'No oxygen-oxygen or direct metal-metal link');
    for (let i = 0; i < atoms.length; i++) if (atoms[i].type === 0) {
      const neighbours = bonds.filter(([a, b]) => a === i || b === i).map(([a, b]) => atoms[a === i ? b : a]);
      assert.equal(neighbours.length, 2);
      for (const axis of ['x', 'y', 'z']) assert.ok(Math.abs(atoms[i][axis] - (neighbours[0][axis] + neighbours[1][axis]) / 2) < 1e-9);
    }
  }
});

test('kagome fragment contains corner-sharing triangles and a connected four-coordinated interior', () => {
  const { atoms, bonds } = geometry('kagome_net'), edges = new Set(bonds.map(([a, b]) => a + ':' + b));
  const adjacent = (a, b) => edges.has(Math.min(a, b) + ':' + Math.max(a, b));
  const degree = atoms.map((_, i) => atoms.filter((_, j) => adjacent(i, j)).length);
  assert.equal(Math.max(...degree), 4);
  let triangles = 0;
  for (let i = 0; i < atoms.length; i++) for (let j = i + 1; j < atoms.length; j++) for (let k = j + 1; k < atoms.length; k++) if (adjacent(i, j) && adjacent(i, k) && adjacent(j, k)) triangles++;
  assert.ok(triangles > 9, 'Neighbouring cells share triangles of both orientations');
  const seen = new Set([0]); for (let pass = 0; pass < atoms.length; pass++) for (const [a, b] of bonds) if (seen.has(a) || seen.has(b)) { seen.add(a); seen.add(b); }
  assert.equal(seen.size, atoms.length);
});

test('private captions remain bounded text and cannot create markup or imply new evidence', () => {
  const marker = '<img src=x onerror=alert(1)>SYNTHETIC_ONLY';
  const h = harness({ caption: marker });
  assert.match(h.animation.node.textContent, /SYNTHETIC_ONLY/);
  assert.equal(h.elements('img').length, 0); assert.equal(h.elements('script').length, 0);
  const tooLong = harness({ caption: 'x'.repeat(801) });
  assert.equal(tooLong.animation.node.textContent.includes('x'.repeat(801)), false);
});

test('material motion starts manually only when open and visible, then moves and pauses', () => {
  const h = harness(); h.play(); assert.equal(h.frames.size, 0);
  h.open(); assert.equal(h.frames.size, 0);
  const before = h.elements('circle').map(circle => ({ ...circle.attrs }));
  h.play(); assert.equal(h.frames.size, 1); h.advance();
  assert.notDeepEqual(h.elements('circle').map(circle => ({ ...circle.attrs })), before);
  h.play(); assert.equal(h.frames.size, 0); assert.match(h.animation.node.textContent, /Paused/);
});

test('reduced-motion view is complete and every offscreen, close or visibility change stops playback', () => {
  const reduced = harness({ reduced: true }); reduced.open(); reduced.play();
  assert.equal(reduced.frames.size, 0); assert.equal(reduced.elements('button')[0].hidden, true);
  assert.match(reduced.animation.node.textContent, /Static view/);
  for (const reason of ['offscreen', 'closed', 'hidden', 'reduced']) {
    const h = harness(); h.open(); h.play(); h.advance();
    if (reason === 'offscreen') h.observers[0].emit(0);
    if (reason === 'closed') { h.details.open = false; h.details.emit('toggle'); }
    if (reason === 'hidden') { h.doc.hidden = true; h.doc.emit('visibilitychange'); }
    if (reason === 'reduced') { h.media.matches = true; h.media.emit('change'); }
    assert.equal(h.frames.size, 0, reason);
    h.details.open = true; h.doc.hidden = false; h.media.matches = false; h.observers[0].emit(1);
    assert.equal(h.frames.size, 0, 'Returning to view never auto-resumes'); h.animation.destroy();
  }
});

test('logout destruction removes private text, listeners and frames and rejects late callbacks', () => {
  const h = harness({ caption: 'PRIVATE_SYNTHETIC_TEXT' }); h.open(); h.play(); h.advance();
  const old = h.animation.node.all(), frame = h.callbacks.at(-1);
  h.animation.destroy(); h.animation.destroy();
  assert.equal(h.animation.node.textContent, ''); assert.equal(h.frames.size, 0);
  assert.equal(h.doc.listenerCount, 0); assert.equal(h.media.listenerCount, 0); assert.equal(h.details.listenerCount, 0);
  assert.ok(old.every(element => element.listenerCount === 0)); assert.equal(h.observers[0].disconnected, true);
  frame(5000); h.observers[0].emit(1); old.find(node => node.tagName === 'BUTTON').emit('click');
  assert.equal(h.frames.size, 0); assert.equal(h.animation.node.textContent, '');
});
