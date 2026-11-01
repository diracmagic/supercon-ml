import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

test('entering News starts polling, leaving stops it, and reentering restarts the ticker without rebuilding the page', () => {
  const calls = [], nodes = new Map();
  for (const id of ['demos', 'learn', 'papers', 'authors', 'main', 'candidates', ...['progress', 'candidates', 'demos', 'learn', 'papers', 'authors'].map(name => 'view-' + name)]) {
    nodes.set('#' + id, { hidden: false, setAttribute(name, value) { this[name] = value; } });
  }
  const context = vm.createContext({ view: 'progress', state: { data: {} }, paperState: { built: false }, learn: { built: true },
    store: { set() {} }, $: selector => nodes.get(selector),
    aiStart: () => calls.push('start'), aiStop: () => calls.push('stop'),
    buildPapers() { calls.push('build'); context.paperState.built = true; }, renderAIList: () => calls.push('render-ai'),
    loadPapers: () => calls.push('load-papers'), loadContent: () => calls.push('load-content'), miniKick: () => calls.push('mini') });
  vm.runInContext(fs.readFileSync(new URL('../app/dist/js/definitions/phone.js', import.meta.url), 'utf8'), context);
  vm.runInContext('setView("papers")', context);
  assert.deepEqual(calls, ['build', 'start', 'load-papers', 'load-content', 'mini']);
  calls.length = 0;
  vm.runInContext('setView("progress")', context);
  assert.deepEqual(calls, ['stop']);
  assert.equal(nodes.get('#papers').hidden, true);
  calls.length = 0;
  vm.runInContext('setView("papers")', context);
  assert.deepEqual(calls, ['render-ai', 'start', 'load-papers', 'load-content', 'mini']);
  assert.equal(nodes.get('#papers').hidden, false);
  calls.length = 0;
  vm.runInContext('setView("ai")', context);
  assert.equal(context.view, 'progress');
  assert.deepEqual(calls, ['stop']);
});

test('a late feed response cannot restart headline animation outside News & Papers', () => {
  const intervals = new Map(); let next = 1;
  const element = { hidden: false, children: [], appendChild(child) { this.children.push(child); } };
  const context = vm.createContext({ view: 'progress', document: { hidden: false }, aiState: { tickTimer: 4, tick: 0 },
    $: () => element, clear: node => { node.children = []; }, h: (tag, attrs) => ({ tag, attrs }),
    fmtDayISO: date => date, motionOK: () => true, clearInterval: id => intervals.delete(id),
    setInterval: fn => { const id = next++; intervals.set(id, fn); return id; } });
  vm.runInContext(fs.readFileSync(new URL('../app/dist/js/definitions/ai-view.js', import.meta.url), 'utf8'), context);
  context.items = [{ title: 'One', url: 'https://example.org/one' }, { title: 'Two', url: 'https://example.org/two' }];
  vm.runInContext('renderTicker(items)', context);
  assert.equal(intervals.size, 0);
  context.view = 'papers'; vm.runInContext('renderTicker(items)', context);
  assert.equal(intervals.size, 1);
  context.view = 'progress'; vm.runInContext('renderTicker(items)', context);
  assert.equal(intervals.size, 0);
});
