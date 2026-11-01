import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// Regression checks for the requested removal. Private research records must
// not return to the published app through an asset, cached global or feed refresh.
const asset = (file) => new URL('../app/dist/' + file, import.meta.url);
const read = (file) => fs.readFileSync(asset(file), 'utf8');
class Element {
  constructor(tag = '') { this.tagName = tag; this.children = []; this.attributes = {}; this.events = {}; this.parentNode = null; this._text = ''; this.hidden = false; this.value = ''; }
  get firstChild() { return this.children[0] || null; }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
  set textContent(value) { this._text = String(value); this.children.forEach((c) => { c.parentNode = null; }); this.children = []; }
  appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
  removeChild(child) { this.children.splice(this.children.indexOf(child), 1); child.parentNode = null; return child; }
  setAttribute(key, value) { this.attributes[key] = String(value); if (key === 'value') this.value = String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  addEventListener(event, fn) { (this.events[event] ||= []).push(fn); }
  dispatch(event) { for (const fn of this.events[event] || []) fn({ target: this }); }
  querySelector(selector) {
    return flatten(this).find((node) => selector.startsWith('#') ? node.attributes.id === selector.slice(1) :
      selector.startsWith('.') ? String(node.className || '').split(' ').includes(selector.slice(1)) : node.tagName === selector) || null;
  }
}
const flatten = (element) => [element, ...element.children.flatMap(flatten)];

function harness({ feed = [], content = false } = {}) {
  const document = new Element('#document'); document.hidden = false;
  document.createElement = (tag) => new Element(tag);
  document.createTextNode = (text) => { const node = new Element('#text'); node.textContent = text; return node; };
  const root = document.appendChild(new Element('main')); root.setAttribute('id', 'ai');
  const intervals = new Map(); let nextTimer = 1;
  const requests = [];
  const make = (tag, attrs = {}, ...children) => {
    const node = new Element(tag);
    if (attrs.class) node.className = attrs.class;
    if (attrs.text) node.textContent = attrs.text;
    children.forEach((child) => node.appendChild(child));
    return node;
  };
  const context = vm.createContext({ document, Node: Element, URL, console, window: { Intl },
    AI_POLL_MS: null, AI_KIND_LABEL: null, aiState: null, MODEL_GLYPH: {},
    state: { data: {} }, paperState: { data: { ai: feed }, failed: false, busy: false, built: false }, learn: { built: false },
    store: { get() { return ''; }, set() {} }, view: 'ai', motionOK: () => false,
    modelFamily: () => [{ id: 'storm', name: 'Storm', role: 'DFT superconductivity', status: 'Research' },
      { id: 'hurricane', name: 'Hurricane', role: 'Experimental records', status: 'Hurricane 4.0' }],
    familyOverride: () => ({}), radInfo: () => null,
    richText: (node, text) => { node.textContent = text; return node; },
    cardHead: (title, subtitle) => make('div', { class: 'card-head' }, make('h2', { text: title }), make('p', { text: subtitle })),
    paperItem: (entry) => make('li', {}, make('p', { class: 'paper-meta' }), make('h3', { text: entry.title })),
    fmtDayISO: (date) => date,
    loadPapers: (force) => requests.push(['papers', force]), loadContent: (force) => requests.push(['content', force]),
    setInterval(fn) { const id = nextTimer++; intervals.set(id, fn); return id; },
    clearInterval(id) { intervals.delete(id); },
    // A stale page or third-party content must not resurrect either list.
    SuperconExternalResearch: { entries: [{ id: '01', title: 'Removed memo entry' }] },
    AI_FOUND: [{ h: 'Legacy discovery claim' }], AI_WATCH: [{ h: 'Legacy prediction list' }],
  });
  for (const file of ['js/definitions/core.js', 'js/definitions/ai-view.js', 'js/initialize/ai-view.js', ...(content ? ['js/definitions/content.js'] : [])]) {
    vm.runInContext(read(file), context, { filename: file });
  }
  const run = (code) => vm.runInContext(code, context);
  run('initializeSuperconAiView(); buildAI();');
  return { document, root, context, run, intervals, requests, get: (id) => document.querySelector('#' + id) };
}

test('published assets exclude the removed memo bundle and stylesheet', () => {
  const manifest = JSON.parse(read('assets.json'));
  const files = [...manifest.styles, ...manifest.scripts];
  assert.ok(files.includes('js/definitions/ai-view.js'));
  for (const file of ['external-research-data.js', 'external-research.css']) {
    assert.equal(files.includes(file), false);
    assert.equal(read('index.html').includes(file), false);
    assert.equal(fs.existsSync(asset(file)), false, file + ' must not be shipped even as an unreferenced asset');
  }
  assert.doesNotMatch(read('js/definitions/ai-view.js'), /SuperconExternalResearch|external-research|renderAIFound|renderAICurated/);
  assert.doesNotMatch(read('js/initialize/ai-view.js'), /stopExternalResearch|external\s*:/);
});

test('AI view renders the models and automatic feed without memo or legacy discovery cards', () => {
  const h = harness();
  assert.equal(h.root.children.length, 3);
  assert.match(h.root.textContent, /Our AI-designed models/);
  assert.match(h.root.textContent, /Storm/);
  assert.match(h.root.textContent, /Hurricane 4.0/);
  assert.match(h.root.textContent, /Automatic research feed/);
  assert.match(h.root.textContent, /Tags are assigned automatically/);
  assert.doesNotMatch(h.root.textContent, /Removed memo entry|Legacy discovery claim|Legacy prediction list|reviewed studies above|Superconductors found with AI by other groups/);
  for (const id of ['ai-found', 'ai-watch', 'ai-curated', 'external-research-list']) assert.equal(h.get(id), null);
  assert.equal(Object.hasOwn(h.context.aiState, 'external'), false);
  assert.equal(h.document.events.visibilitychange, undefined);
});

test('private notes entry only opens GitHub sign-in without loading or caching private records', () => {
  const h = harness();
  const card = h.get('ai-private-notes');
  assert.ok(card);
  assert.equal(card.querySelector('h2').textContent, 'Private research notes');
  assert.equal(card.querySelector('p').textContent, 'Your research memo is stored in a private GitHub repository. Sign in as diracmagic to view it.');
  const link = card.querySelector('a');
  assert.equal(link.textContent, 'Sign in to view notes');
  assert.equal(link.getAttribute('href'), 'https://github.com/login?return_to=%2Fdiracmagic%2Fsupercon-research-notes');
  assert.equal(link.getAttribute('target'), '_blank');
  assert.equal(link.getAttribute('rel'), 'noopener noreferrer');
  assert.deepEqual(h.requests, []);
  assert.doesNotMatch(read('js/definitions/ai-view.js'), /fetch\s*\(|XMLHttpRequest|localStorage|sessionStorage|caches\s*\./);
});

test('automatic feed still filters, sorts and expands current papers and news', () => {
  const feed = Array.from({ length: 13 }, (_, index) => ({ title: 'Paper ' + index, url: 'https://example.org/paper/' + index,
    date: '2026-10-' + String(index + 1).padStart(2, '0'), source: 'Test source', kind_of: 'paper', ai_kind: 'prediction' }));
  feed.push({ title: 'Latest experiment news', url: 'https://example.org/news', date: '2026-11-01', source: 'Test news', kind_of: 'news', ai_kind: 'experiment', topics: [] });
  feed.push({ title: 'Unsafe URL', url: 'javascript:alert(1)', date: '2026-11-02' });
  const h = harness({ feed });
  assert.equal(h.get('ai-list').children.length, 12);
  assert.match(h.get('ai-list').children[0].textContent, /Latest experiment news/);
  assert.doesNotMatch(h.root.textContent, /Unsafe URL/);
  h.get('ai-more').children[0].dispatch('click');
  assert.equal(h.get('ai-list').children.length, 14);
  const experiments = h.get('ai-filter').children.find((node) => node.textContent.startsWith('Experiments'));
  experiments.dispatch('click');
  assert.equal(h.get('ai-list').children.length, 1);
  assert.match(h.get('ai-list').textContent, /Latest experiment news/);
});

test('feed refresh and polling remain available with clean start-stop lifecycle', () => {
  const h = harness();
  h.get('ai-refresh').dispatch('click');
  assert.deepEqual(h.requests, [['papers', true], ['content', true]]);
  h.run('aiStart(); aiStart();');
  assert.equal(h.intervals.size, 1);
  [...h.intervals.values()][0]();
  assert.deepEqual(h.requests.at(-1), ['papers', true]);
  h.run('aiStop();'); assert.equal(h.intervals.size, 0);
});

test('content updates cannot call removed renderers or restore the memo', () => {
  const h = harness({ content: true });
  assert.doesNotThrow(() => h.run('contentChanged(); renderAI();'));
  assert.equal(h.root.children.length, 3);
  assert.equal(h.get('ai-found'), null);
  assert.doesNotMatch(h.root.textContent, /Removed memo entry|Legacy discovery claim/);
});

test('service-worker upgrade discards the old memo cache while preserving other apps', async () => {
  const handlers = {}, deleted = []; let activation;
  const source = read('sw.js');
  const current = /const CACHE = '([^']+)'/.exec(source)[1];
  const old = 'supercon-0.3.9-research31-tc-ranking';
  assert.notEqual(current, old);
  const context = { self: { addEventListener: (kind, fn) => { handlers[kind] = fn; }, clients: { claim: async () => {} } },
    caches: { keys: async () => [old, current, 'unrelated-app'], delete: async (key) => { deleted.push(key); } } };
  vm.runInNewContext(source, context);
  handlers.activate({ waitUntil: (promise) => { activation = promise; } });
  await activation;
  assert.deepEqual(deleted, [old]);
});

test('private research sources and export tooling stay outside the public repository', () => {
  for (const path of [
    '../data/external_research_memo.json',
    '../tools/build_external_research.py',
    '../tests/test_external_research.py',
  ]) {
    assert.equal(fs.existsSync(new URL(path, import.meta.url)), false, path);
  }
  const sourceDir = new URL('../data/external-research-memo/', import.meta.url);
  // Git does not track an empty directory left behind by a local file removal.
  assert.deepEqual(fs.existsSync(sourceDir) ? fs.readdirSync(sourceDir) : [], []);
  const checks = fs.readFileSync(new URL('../.github/workflows/checks.yml', import.meta.url), 'utf8');
  assert.doesNotMatch(checks, /tools\/build_external_research\.py/);
});
