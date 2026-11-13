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
  appendChild(child) { if (child.parentNode) child.parentNode.removeChild(child); this.children.push(child); child.parentNode = this; return child; }
  get isConnected() { return this.tagName === '#document' || !!this.parentNode?.isConnected; }
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

function harness({ feed = [], content = false, moving = false, allPapers = false, data = null } = {}) {
  const document = new Element('#document'); document.hidden = false;
  document.createElement = (tag) => new Element(tag);
  document.createTextNode = (text) => { const node = new Element('#text'); node.textContent = text; return node; };
  const root = document.appendChild(new Element('main')); root.setAttribute('id', allPapers ? 'papers' : 'papers-ai-feed');
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
    state: { data: {} }, paperState: { data: data || { ai: feed }, failed: false, busy: false, built: false, kind: 'all', src: 'all', topic: 'all', shown: 5, advShown: 5, aiAdvShown: 5, newsSrc: 'all', newsShown: 5 }, learn: { built: false },
    store: { get() { return ''; }, set() {} }, view: 'papers', motionOK: () => moving,
    NEWS_ART: [['Hydrides', 'hydride'], ['Cuprates', 'cuprate'], ['AI and data', 'ai']], RECENT: [], THEORIES: [], MATERIALS: [],
    PAPER_SOURCES: [['all', 'All'], ['arXiv', 'arXiv']], KIND_LABEL: {}, MONTHS: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    PAPERS_URL: 'https://example.org/public-papers.json', MINI: { items: [] },
    miniPrune() {}, miniKick() {}, miniCanvas(kind) { const canvas = new Element('canvas'); canvas.className = 'mini'; canvas.setAttribute('data-news-art', kind); return canvas; },
    recentLink: entry => make('a', { text: entry.h }), fmtMonth: date => date,
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
    setTimeout(fn) { const id = nextTimer++; return id; }, clearTimeout() {},
    fetch(url) { requests.push(['papers', url]); return Promise.resolve({ ok: true, json: () => Promise.resolve({ ai: feed, arxiv: [] }) }); },
    // A stale page or third-party content must not resurrect either list.
    SuperconExternalResearch: { entries: [{ id: '01', title: 'Removed memo entry' }] },
    AI_FOUND: [{ h: 'Legacy discovery claim' }], AI_WATCH: [{ h: 'Legacy prediction list' }],
  });
  for (const file of ['js/definitions/core.js', 'js/definitions/papers-view.js', 'js/definitions/news-drawings.js', 'js/definitions/ai-view.js', 'js/initialize/ai-view.js', ...(content ? ['js/definitions/content.js'] : [])]) {
    vm.runInContext(read(file), context, { filename: file });
  }
  const run = (code) => vm.runInContext(code, context);
  run('initializeSuperconAiView(); ' + (allPapers ? 'buildPapers();' : 'buildAI();'));
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

test('public AI feed lives inside News & Papers without memo, models or legacy discovery cards', () => {
  const h = harness();
  assert.equal(h.root.children.length, 1);
  assert.doesNotMatch(h.root.textContent, /Our AI-designed models|Storm|Hurricane 4.0/);
  assert.match(h.root.textContent, /AI papers and news/);
  assert.match(h.root.textContent, /Tags are assigned automatically/);
  assert.doesNotMatch(h.root.textContent, /Removed memo entry|Legacy discovery claim|Legacy prediction list|reviewed studies above|Superconductors found with AI by other groups|Private research notes|Sign in as diracmagic/);
  for (const id of ['ai-found', 'ai-watch', 'ai-curated', 'external-research-list', 'ai-private-notes']) assert.equal(h.get(id), null);
  assert.equal(Object.hasOwn(h.context.aiState, 'external'), false);
  assert.equal(h.document.events.visibilitychange, undefined);
});

test('main header provides a right-aligned app login button without anonymous private-note links', () => {
  const h = harness();
  const html = read('index.html');
  const header = /<header\b[^>]*>[\s\S]*?<\/header>/.exec(html)?.[0] || '';
  const controls = /<div class="header-actions">([\s\S]*?)<\/div>/.exec(header)?.[1] || '';
  const matches = [...controls.matchAll(/<button\b([^>]*)>([^<]*)<\/button>/g)];
  const links = matches.map(match => ({ text: match[2], attrs: Object.fromEntries([...match[1].matchAll(/([\w-]+)="([^"]*)"/g)].map(attr => [attr[1], attr[2]])) }));
  const matching = links.filter(link => link.attrs.id === 'team-login');
  assert.equal(matching.length, 1);
  const link = matching[0];
  assert.equal(link.text, 'Login for team');
  assert.equal(link.attrs.type, 'button');
  assert.equal(link.attrs.href, undefined);
  assert.equal(link.attrs.target, undefined);
  assert.match(link.attrs.class, /\bteam-login\b/);
  const css = read('styles.css');
  assert.match(css, /\.team-login\s*\{[^}]*background:\s*transparent;/);
  assert.match(css, /\.header-actions\s*\{[^}]*justify-self:\s*end;/);
  assert.equal(link.attrs.hidden, undefined);
  assert.equal(link.attrs.onclick, undefined);
  assert.doesNotMatch(html + read('js/definitions/ai-view.js'), /Private research notes|Sign in as diracmagic|Sign in to view notes|ai-private-notes/);
  assert.equal(h.get('ai-private-notes'), null);
  assert.deepEqual(h.requests, []);
  assert.doesNotMatch(read('js/definitions/ai-view.js'), /fetch\s*\(|XMLHttpRequest|localStorage|sessionStorage|caches\s*\./);
});

test('automatic feed still filters, sorts and expands current papers and news', () => {
  const feed = Array.from({ length: 13 }, (_, index) => ({ title: 'Paper ' + index, url: 'https://example.org/paper/' + index,
    date: '2026-10-' + String(index + 1).padStart(2, '0'), source: 'Test source', kind_of: 'paper', ai_kind: 'prediction' }));
  feed.push({ title: 'Latest experiment news', url: 'https://example.org/news', date: '2026-11-01', source: 'Test news', kind_of: 'news', ai_kind: 'experiment', topics: [] });
  feed.push({ title: 'Unsafe URL', url: 'javascript:alert(1)', date: '2026-11-02' });
  const h = harness({ feed });
  assert.equal(h.get('ai-list').children.length, 5, 'The list opens with five items');
  assert.match(h.get('ai-list').children[0].textContent, /Latest experiment news/);
  assert.doesNotMatch(h.root.textContent, /Unsafe URL/);
  assert.match(h.get('ai-more').textContent, /Show more \(9 left\)/);
  h.get('ai-more').children[0].dispatch('click');
  assert.equal(h.get('ai-list').children.length, 10, 'Show more adds five');
  h.get('ai-more').children[0].dispatch('click');
  assert.equal(h.get('ai-list').children.length, 14);
  assert.equal(h.get('ai-more').children.length, 0);
  const experiments = h.get('ai-filter').children.find((node) => node.textContent.startsWith('Experiments'));
  experiments.dispatch('click');
  assert.equal(h.get('ai-list').children.length, 1);
  assert.match(h.get('ai-list').textContent, /Latest experiment news/);
});

test('News & Papers separates explicit public AI identities from general superconductivity and preserves sources', () => {
  const ai = { id: '2610.12345', source: 'arXiv', title: 'Machine learning for superconductors', url: 'https://arxiv.org/abs/2610.12345v2', date: '2026-10-30', kind_of: 'paper', topics: [] };
  const general = { id: 'general', source: 'arXiv', title: 'Measurements of a nickelate', url: 'https://arxiv.org/abs/2610.11111', date: '2026-10-29', topics: ['AI and data'] };
  const news = { id: 'news', title: 'AI model suggests hydride candidates', url: 'https://example.org/news', date: '2026-10-28', source: 'Public news', kind_of: 'news', topics: ['Hydrides'], ai_kind: 'prediction' };
  const ordinaryNews = { title: 'A cuprate measurement', url: 'https://example.org/cuprate', date: '2026-10-27', source: 'Public news', topics: ['Cuprates'] };
  const h = harness({ allPapers: true, data: { ai: [ai, news], arxiv: [{ ...ai, url: 'https://arxiv.org/pdf/2610.12345v1.pdf' }, general], news: [news, ordinaryNews] } });
  assert.equal(h.get('papers-ai-heading').textContent, 'AI for Superconductors');
  assert.equal(h.get('papers-superconductors-heading').textContent, 'Superconductors');
  assert.match(h.get('ai-list').textContent, /Machine learning|AI model suggests/);
  assert.doesNotMatch(h.get('feed-list').textContent, /Machine learning for superconductors/);
  assert.match(h.get('feed-list').textContent, /Measurements of a nickelate/, 'A broad topic tag alone must not classify a paper as AI');
  assert.doesNotMatch(h.get('news-list').textContent, /AI model suggests/);
  assert.match(h.get('news-list').textContent, /A cuprate measurement/);
  assert.equal(h.get('ai-list').children[0].querySelector('a').getAttribute('href'), ai.url);
  const canvases = flatten(h.get('ai-list')).filter(node => node.tagName === 'canvas');
  assert.deepEqual(canvases.map(node => node.getAttribute('data-news-art')), ['news-features', 'news-hydride']);
  assert.equal(flatten(h.get('ai-list')).filter(node => String(node.className || '').split(' ').includes('news-art')).length, 2, 'Each public AI item receives one compact topic thumbnail');
  assert.equal(h.get('news-list').querySelector('canvas').getAttribute('data-news-art'), 'news-cuprate');
  assert.equal(h.requests.length, 0, 'Rendering public records cannot fetch private content');
});

test('every News & Papers list opens with five items and Show more adds five at a time', () => {
  const day = i => '2026-10-' + String(i + 10).padStart(2, '0');
  const papers = Array.from({ length: 12 }, (_, i) => ({ id: 'p' + i, source: 'arXiv', title: 'Superconductivity paper ' + i, url: 'https://arxiv.org/abs/2610.' + (10000 + i), date: day(i), topics: [] }));
  const news = Array.from({ length: 12 }, (_, i) => ({ title: 'Superconductor story ' + i, url: 'https://example.org/story/' + i, date: day(i), source: 'Public news', topics: [] }));
  const h = harness({ allPapers: true, data: { ai: [], arxiv: papers, news } });
  assert.equal(h.get('news-list').children.length, 5);
  assert.match(h.get('news-more').textContent, /Show more \(7 left\)/);
  h.get('news-more').children[0].dispatch('click');
  assert.equal(h.get('news-list').children.length, 10);
  assert.equal(h.get('feed-list').children.length, 5);
  assert.match(h.get('feed-more').textContent, /Show more \(7 left\)/);
  h.get('feed-more').children[0].dispatch('click');
  assert.equal(h.get('feed-list').children.length, 10);
  h.context.RECENT = Array.from({ length: 12 }, (_, i) => ({ d: '2026-0' + (1 + (i % 9)), k: 'experiment', cards: [i < 6 ? 'field' : 'ai'], h: 'Advance ' + i, x: 'A result.', ref: 'r' + i }));
  h.run('renderAdvances();');
  assert.equal(h.get('adv-list').children.length, 5);
  assert.equal(h.get('ai-adv-list').children.length, 5);
  assert.match(h.get('adv-more').textContent, /Show more \(1 left\)/);
  assert.match(h.get('ai-adv-more').textContent, /Show more \(1 left\)/);
  h.get('adv-more').children[0].dispatch('click');
  assert.equal(h.get('adv-list').children.length, 6);
  assert.equal(h.get('adv-more').children.length, 0);
  assert.equal(h.get('ai-adv-list').children.length, 5, 'Each list keeps its own count');
});

test('a preprint and its journal version are listed once in New papers', () => {
  const doi = '10.1038/s41467-026-77988-x';
  const h = harness({ allPapers: true, data: { ai: [], news: [],
    arxiv: [{ id: '2610.37753', source: 'arXiv', title: "Approaching Landauer's limit in a single superconducting vortex memory bit", doi, url: 'https://arxiv.org/abs/2610.37753', date: '2026-10-27', topics: [] },
      { id: '2610.40000', source: 'arXiv', title: 'Another vortex paper', url: 'https://arxiv.org/abs/2610.40000', date: '2026-10-20', topics: [] }],
    journals: [{ id: doi, source: 'Nat. Commun.', title: 'Approaching Landauer’s limit in a single superconducting vortex memory bit', doi, url: 'https://doi.org/' + doi, date: '2026-09-24', topics: [] }] } });
  assert.equal(h.get('feed-list').children.length, 2);
  assert.equal((h.get('feed-list').textContent.match(/Landauer/g) || []).length, 1);
});

test('AI feed deduplicates DOI, canonical URLs and arXiv versions without title-based merging', () => {
  const h = harness({ feed: [
    { title: 'Original', source: 'Journal', doi: '10.1234/example', url: 'https://publisher.test/paper', date: '2026-10-31' },
    { title: 'Duplicate', source: 'Journal', url: 'https://doi.org/10.1234/EXAMPLE', date: '2026-10-30' },
    { title: 'Same title', source: 'arXiv', url: 'https://arxiv.org/abs/2610.12345v2', date: '2026-10-29' },
    { title: 'Old version', source: 'arXiv', url: 'https://arxiv.org/pdf/2610.12345v1.pdf', date: '2026-10-28' },
    { title: 'Same title', source: 'News', url: 'https://example.org/distinct', date: '2026-10-27' },
    { title: 'Tracking duplicate', source: 'News', url: 'https://example.org/distinct?utm_source=test#section', date: '2026-10-26' },
  ] });
  assert.equal(h.get('ai-list').children.length, 3);
  assert.equal(h.run('aiItems().length'), 3);
  assert.equal(h.run('feedIsAI({url:"https://evilarxiv.org/abs/2610.12345"})'), false);
  assert.doesNotMatch(h.get('ai-list').textContent, /Tracking duplicate|Old version|Duplicate/);
});

test('empty, missing, loading and failed public feeds have distinct honest states', async () => {
  const h = harness({ allPapers: true, data: { ai: [], arxiv: [], journals: [], news: [] } });
  assert.match(h.get('ai-list').textContent, /Nothing here yet/);
  assert.match(h.get('feed-list').textContent, /No papers match/);
  h.context.paperState.data = { arxiv: [], news: [] };
  h.run('renderAIList();');
  assert.match(h.get('ai-list').textContent, /AI list starts with the next feed update/);
  h.context.paperState.data = null; h.context.paperState.busy = true;
  h.run('renderAIList(); renderFeed();');
  assert.match(h.get('ai-status').textContent, /Checking for new items/);
  assert.match(h.get('feed-list').textContent, /Loading the latest papers/);
  h.context.paperState.busy = false;
  h.context.fetch = () => Promise.reject(new Error('offline'));
  await h.run('loadPapers(true)');
  assert.equal(h.context.paperState.failed, true);
  assert.equal(h.context.paperState.busy, false);
  assert.match(h.get('ai-status').textContent, /Couldn’t reach the feed/);
  assert.match(h.get('feed-list').textContent, /Couldn’t reach the paper feed/);
  h.context.paperState.data = { ai: [], arxiv: [], updated: '2026-11-01T00:00:00Z' };
  await h.run('loadPapers(true)');
  assert.match(h.get('ai-status').textContent, /Couldn’t refresh\. Showing the feed updated/);
  assert.equal(h.context.paperState.data.updated, '2026-11-01T00:00:00Z', 'A failed refresh retains the actual prior data and its date');
});

test('article lists keep compact thumbnails without detailed-diagram expansion', () => {
  const h = harness({ feed: [{ title: 'A generated candidate', url: 'https://example.org/predict', date: '2026-11-01', ai_kind: 'prediction', kind_of: 'news' }] });
  const list = h.get('ai-list');
  assert.equal(list.querySelector('.ai-workflow'), null);
  assert.equal(list.querySelector('.article-figure-evidence'), null);
  assert.equal(flatten(list).filter(node => node.tagName === 'canvas').length, 1);
  assert.equal(h.intervals.size, 0);
  assert.doesNotMatch(list.textContent, /What this drawing uses|Explore the AI workflow|Related concept/);
});

test('existing mini-animation engine stays static with reduced motion and animates only its active views', () => {
  const frames = [], drawn = [], ctx = { setTransform() {}, clearRect() {}, fillRect() {}, save() {}, restore() {} };
  const canvas = { clientWidth: 112, clientHeight: 84, isConnected: true };
  const item = { cv: canvas, kind: 'news-ai', t: 0, vis: true, W: 112, H: 84, dpr: 1, ctx };
  const context = vm.createContext({ MINI: { items: [item], raf: 0, last: 1000 }, MINI_DRAW: { 'news-ai': (...args) => drawn.push(args[4]) },
    MINI_STATIC: { 'news-ai': 1.2 }, view: 'papers', document: { hidden: false }, window: { devicePixelRatio: 1 },
    colors: () => ({}), motionOK: () => false, requestAnimationFrame: fn => { frames.push(fn); return frames.length; } });
  vm.runInContext(read('js/definitions/mini-player.js'), context);
  vm.runInContext('miniFrame(1050)', context);
  assert.deepEqual(drawn, [1.2]); assert.equal(item.t, 0); assert.equal(frames.length, 0);
  context.motionOK = () => true;
  vm.runInContext('miniFrame(1100)', context);
  assert.equal(item.t, .05); assert.equal(frames.length, 1);
  context.view = 'progress'; vm.runInContext('miniFrame(1150)', context);
  assert.equal(item.t, .05); assert.equal(frames.length, 1);
});

test('the checked-in public feed supplies animated AI entries without private memo data', () => {
  const data = JSON.parse(fs.readFileSync(new URL('../progress/papers.json', import.meta.url), 'utf8'));
  const h = harness({ allPapers: true, data });
  assert.ok(data.ai.length > 0);
  const list = h.get('ai-list');
  assert.equal(flatten(list).filter(node => node.tagName === 'canvas').length, list.children.length);
  assert.equal(flatten(list).filter(node => node.className === 'ai-workflow').length, 0);
  assert.equal(h.get('ai-private-notes'), null);
  assert.equal(h.requests.length, 0);
});

test('feed refresh and polling remain available with clean start-stop lifecycle', async () => {
  const h = harness();
  h.get('ai-refresh').dispatch('click');
  assert.deepEqual(h.requests, [['papers', 'https://example.org/public-papers.json'], ['content', true]]);
  await h.run('Promise.resolve().then(function () { return Promise.resolve(); })');
  h.context.paperState.busy = false;
  h.run('aiStart(); aiStart();');
  assert.equal(h.intervals.size, 1);
  [...h.intervals.values()][0]();
  assert.deepEqual(h.requests.at(-1), ['papers', 'https://example.org/public-papers.json']);
  h.run('aiStop();'); assert.equal(h.intervals.size, 0);
});

test('content updates cannot call removed renderers or restore the memo', () => {
  const h = harness({ content: true });
  assert.doesNotThrow(() => h.run('contentChanged(); renderAI();'));
  assert.equal(h.root.children.length, 1);
  assert.equal(h.get('ai-found'), null);
  assert.doesNotMatch(h.root.textContent, /Removed memo entry|Legacy discovery claim/);
});

test('service-worker upgrade discards the old memo cache while preserving other apps', async () => {
  const handlers = {}, deleted = []; let activation;
  const source = read('sw.js');
  const current = /const CACHE = '([^']+)'/.exec(source)[1];
  const old = 'supercon-0.3.9-research31-tc-ranking';
  const previous = 'supercon-0.3.11-team-password';
  assert.equal(current, 'supercon-0.3.32-hull-correction');
  assert.notEqual(current, old);
  const context = { self: { addEventListener: (kind, fn) => { handlers[kind] = fn; }, clients: { claim: async () => {} } },
    caches: { keys: async () => [old, previous, current, 'unrelated-app'], delete: async (key) => { deleted.push(key); } } };
  vm.runInNewContext(source, context);
  handlers.activate({ waitUntil: (promise) => { activation = promise; } });
  await activation;
  assert.deepEqual(deleted, [old, previous]);
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
