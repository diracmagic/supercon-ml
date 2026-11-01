import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const read = (file) => fs.readFileSync(new URL('../app/dist/' + file, import.meta.url), 'utf8');

test('the public document no longer exposes an AI tab or section', () => {
  assert.doesNotMatch(read('index.html'), /\bid=["'](?:view-ai|ai)["']/);
});

function navigation(savedView = 'progress') {
  const nodes = new Map();
  const routes = ['progress', 'candidates', 'demos', 'learn', 'papers', 'authors'];
  for (const id of ['main', 'candidates', 'demos', 'learn', 'papers', 'authors', 'btn-refresh', 'btn-theme', ...routes.map((route) => 'view-' + route)]) {
    nodes.set('#' + id, { hidden: true, attributes: {}, events: {},
      setAttribute(key, value) { this.attributes[key] = value; },
      addEventListener(kind, fn) { this.events[kind] = fn; } });
  }
  const stored = new Map([['view', savedView]]), calls = [], events = {}, intervals = [];
  const context = vm.createContext({
    $: (selector) => {
      assert.notEqual(selector, '#ai', 'Retired AI section must not be queried');
      assert.notEqual(selector, '#view-ai', 'Retired AI tab must not be queried');
      return nodes.get(selector) || null;
    },
    view: savedView, DEMOS: null, RAMP_LIGHT: null, TC_MAX: null, demo: null,
    state: { data: {}, busy: false, checkedAt: null }, theme: 'system', REFRESH_MS: 180000,
    learn: { built: false }, paperState: { built: false },
    store: { get: (key) => stored.get(key), set: (key, value) => stored.set(key, value) },
    document: { hidden: false, addEventListener: (kind, fn) => { (events[kind] ||= []).push(fn); } },
    setInterval: (fn, ms) => { intervals.push([fn, ms]); return intervals.length; },
    xtDirty: () => calls.push('xtDirty'), xtSync: () => calls.push('xtSync'), xtKick: () => calls.push('xtKick'),
    buildDemos: () => calls.push('buildDemos'), syncControls: () => calls.push('syncControls'),
    sizeCanvas: () => calls.push('sizeCanvas'), kick: () => calls.push('kick'),
    buildLearn: () => calls.push('buildLearn'), miniKick: () => calls.push('miniKick'),
    buildPapers: () => calls.push('buildPapers'), loadPapers: () => calls.push('loadPapers'),
    loadContent: () => calls.push('loadContent'), renderAuthors: () => calls.push('renderAuthors'),
    applyTheme: () => calls.push('applyTheme'), render: () => calls.push('render'), renderChrome: () => calls.push('renderChrome'),
    refreshAll: () => { calls.push('refreshAll'); return Promise.resolve(); }, loadBundled: () => Promise.resolve(),
    // The retired standalone renderer stays unreachable; the public AI feed now
    // lives in News & Papers and shares its start/stop lifecycle.
    buildAI: () => { throw new Error('Retired AI renderer called'); },
    renderAI: () => { throw new Error('Retired AI renderer called'); },
    renderAIList: () => { assert.equal(context.view, 'papers'); calls.push('renderAIList'); },
    aiStart: () => { assert.equal(context.view, 'papers'); calls.push('aiStart'); },
    aiStop: () => calls.push('aiStop'),
  });
  for (const file of ['js/definitions/phone.js', 'js/initialize/demo-player.js', 'js/initialize/startup.js']) {
    vm.runInContext(read(file), context, { filename: file });
  }
  const run = (code) => vm.runInContext(code, context);
  return { nodes, routes, stored, calls, context, events, intervals, run };
}

test('a persisted AI view starts on Progress without a missing-section crash', async () => {
  const h = navigation('ai');
  h.run('initializeSuperconDemoPlayer();');
  assert.equal(h.context.view, 'progress');
  assert.doesNotThrow(() => h.run('initializeSuperconStartup();'));
  await Promise.resolve();
  assert.equal(h.stored.get('view'), 'progress');
  assert.equal(h.nodes.get('#main').hidden, false);
  assert.equal(h.nodes.get('#view-progress').attributes['aria-selected'], 'true');
  assert.ok(h.calls.includes('render'));
  assert.ok(h.calls.includes('refreshAll'));
});

test('a stale direct AI navigation request migrates to Progress', () => {
  const h = navigation('ai');
  assert.doesNotThrow(() => h.run("setView('ai');"));
  assert.equal(h.context.view, 'progress');
  assert.equal(h.stored.get('view'), 'progress');
  assert.equal(h.nodes.get('#main').hidden, false);
  assert.deepEqual(h.calls, ['aiStop'], 'The removed AI route only stops the news lifecycle; it cannot fetch or animate');
});

test('remaining public tabs keep their click handlers and selection state', () => {
  const h = navigation();
  h.run('initializeSuperconDemoPlayer(); initializeSuperconStartup();');
  for (const route of h.routes) {
    h.nodes.get('#view-' + route).events.click();
    assert.equal(h.context.view, route);
    assert.equal(h.stored.get('view'), route);
    assert.equal(h.nodes.get('#view-' + route).attributes['aria-selected'], 'true');
    for (const other of h.routes.filter((name) => name !== route)) {
      assert.equal(h.nodes.get('#view-' + other).attributes['aria-selected'], 'false');
    }
    assert.equal(h.nodes.get(route === 'progress' ? '#main' : '#' + route).hidden, false);
  }
  assert.ok(h.calls.includes('xtSync'));
  assert.ok(h.calls.includes('buildDemos'));
  assert.ok(h.calls.includes('buildLearn'));
  assert.ok(h.calls.includes('buildPapers'));
  assert.ok(h.calls.includes('aiStart'), 'The remaining News & Papers route starts its public feed lifecycle');
  assert.ok(h.calls.includes('renderAuthors'));
});

test('the AI fallback preserves the existing no-data visibility guard', () => {
  const h = navigation('ai');
  h.context.state.data = null;
  h.run("setView('ai');");
  assert.equal(h.context.view, 'progress');
  assert.equal(h.nodes.get('#main').hidden, true);
  assert.equal(h.nodes.get('#candidates').hidden, true);
});
