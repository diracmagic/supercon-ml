import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// A small DOM model exercises the view's actual functions without a network or
// framework dependency. The parent integration checks use a real browser too.
class Element {
  constructor(tag = '') { this.tagName = tag; this.children = []; this.attributes = {}; this.events = {}; this.parentNode = null; this._text = ''; this.hidden = false; this.value = ''; this.open = false; }
  get firstChild() { return this.children[0] || null; }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
  set textContent(value) { this._text = String(value); this.children.forEach((c) => { c.parentNode = null; }); this.children = []; }
  get isConnected() { return this.tagName === '#document' || !!this.parentNode?.isConnected; }
  appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
  removeChild(child) { this.children.splice(this.children.indexOf(child), 1); child.parentNode = null; return child; }
  setAttribute(key, value) { this.attributes[key] = String(value); if (key === 'value') this.value = String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  addEventListener(event, fn) { (this.events[event] ||= []).push(fn); }
  dispatch(event) { for (const fn of this.events[event] || []) fn({ target: this }); }
  focus() { this.focused = true; }
  scrollIntoView() {}
}
const flatten = (element) => [element, ...element.children.flatMap(flatten)];
const byClass = (element, name) => flatten(element).filter((node) => String(node.className || '').split(' ').includes(name));

function harness({ reduced = false } = {}) {
  const document = new Element('#document');
  document.hidden = false;
  document.createElement = (tag) => new Element(tag);
  document.createTextNode = (text) => { const node = new Element('#text'); node.textContent = text; return node; };
  document.querySelector = (selector) => selector.startsWith('#') ? flatten(document).find((node) => node.attributes.id === selector.slice(1)) || null : null;
  const root = document.appendChild(new Element('section')); root.setAttribute('id', 'ai-found');
  const timeouts = new Map(); let nextTimer = 1;
  const observers = [];
  class Observer {
    constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); }
    observe(target) { this.target = target; }
    disconnect() { this.disconnected = true; }
    hide() { this.callback([{ isIntersecting: false, target: this.target }]); }
  }
  const context = vm.createContext({ document, Node: Element, URL, console,
    AI_POLL_MS: null, AI_KIND_LABEL: null, aiState: null,
    store: { get() { return ''; }, set() {} }, view: 'ai',
    motionOK: () => !reduced, IntersectionObserver: Observer,
    setTimeout(fn) { const id = nextTimer++; timeouts.set(id, fn); return id; },
    clearTimeout(id) { timeouts.delete(id); }, clearInterval() {},
  });
  for (const file of ['js/definitions/core.js', 'js/definitions/ai-view.js', 'js/initialize/ai-view.js', 'external-research-data.js']) {
    vm.runInContext(fs.readFileSync(new URL('../app/dist/' + file, import.meta.url), 'utf8'), context, { filename: file });
  }
  const run = (code) => vm.runInContext(code, context);
  run('initializeSuperconAiView(); renderAIFound();');
  const tick = () => { const queued = [...timeouts.values()]; timeouts.clear(); queued.forEach((fn) => fn()); };
  return { document, root, context, run, timeouts, observers, tick, get: (id) => document.querySelector('#' + id) };
}

test('all 31 reviewed entries remain reachable through six-item pages', () => {
  const h = harness();
  assert.equal(h.context.SuperconExternalResearch.entries.length, 31);
  const ids = [];
  for (let page = 0; page < 6; page++) {
    h.run(`aiState.external.page = ${page}; renderExternalResearchList();`);
    const cards = byClass(h.get('external-research-list'), 'external-research-card');
    ids.push(...cards.map((node) => node.getAttribute('data-study-id')));
    assert.ok(cards.length > 0 && cards.length <= 6);
  }
  assert.equal(new Set(ids).size, 31);
  assert.deepEqual(ids, Array.from(h.context.SuperconExternalResearch.entries, (entry) => entry.id));
  assert.match(h.get('external-research-count').textContent, /31–31 of 31/);
});

test('search and evidence filters update results without replacing search input or resetting on feed refresh', () => {
  const h = harness();
  const search = h.get('external-research-search');
  search.value = '10.1038/s41524-026-02117-7'; search.dispatch('input');
  assert.equal(byClass(h.get('external-research-list'), 'external-research-card').length, 1);
  assert.equal(byClass(h.root, 'external-research-card')[0].getAttribute('data-study-id'), '30');
  h.run('renderAIFound();');
  assert.equal(h.get('external-research-search'), search);
  assert.equal(search.value, '10.1038/s41524-026-02117-7');
  search.value = ''; search.dispatch('input');
  const category = h.get('external-research-category'); category.value = '研究计划'; category.dispatch('change');
  assert.equal(byClass(h.root, 'external-research-card').length, 2);
  assert.match(h.get('external-research-count').textContent, /of 2/);
  search.value = 'no-such-material-1234'; search.dispatch('input');
  assert.match(h.get('external-research-count').textContent, /No studies match/);
});

test('reference links allow HTTPS sources only and render claims as text', () => {
  const h = harness();
  assert.equal(h.run("externalResearchUrl('javascript:alert(1)')"), '');
  assert.equal(h.run("externalResearchUrl('http://example.org/paper')"), '');
  assert.equal(h.run("externalResearchUrl('https://user:pass@example.org/paper')"), '');
  h.context.hostile = { id: 'test', heading: '<img src=x onerror=alert(1)>', headline: 'prediction', url: 'javascript:alert(1)',
    primary_refs: [{ label: 'Author source', url: 'https://example.org/paper' }], progress_steps: [] };
  const node = h.run('buildExternalResearchCard(hostile)');
  assert.match(node.textContent, /<img src=x onerror=alert\(1\)>/);
  assert.equal(flatten(node).some((n) => n.tagName === 'img'), false);
  const links = flatten(node).filter((n) => n.tagName === 'a');
  assert.ok(links.length >= 1);
  assert.ok(links.every((n) => n.getAttribute('href') === 'https://example.org/paper'));
});

test('animation is finite and never upgrades a not-reported experiment', () => {
  const h = harness();
  const route = byClass(h.root, 'external-research-route')[0];
  const steps = byClass(route, 'external-research-step');
  const labels = byClass(route, 'external-research-step-evidence').map((node) => node.textContent);
  assert.deepEqual(labels, ['Reported', 'Reported', 'Not reported']);
  const play = byClass(route, 'external-research-route-controls')[0].children[0];
  play.dispatch('click'); assert.equal(h.timeouts.size, 1);
  h.tick(); assert.equal(steps[1].getAttribute('aria-pressed'), 'true');
  h.tick(); assert.equal(steps[2].getAttribute('aria-pressed'), 'true');
  assert.equal(h.timeouts.size, 0);
  assert.equal(play.textContent, 'Play again');
  assert.deepEqual(byClass(route, 'external-research-step-evidence').map((node) => node.textContent), labels);
});

test('leaving the view, hiding the document, or scrolling away pauses route playback', () => {
  const h = harness();
  const route = byClass(h.root, 'external-research-route')[0];
  const play = byClass(route, 'external-research-route-controls')[0].children[0];
  play.dispatch('click'); h.run('aiStop();'); assert.equal(h.timeouts.size, 0);
  play.dispatch('click'); h.document.hidden = true; h.document.dispatch('visibilitychange'); assert.equal(h.timeouts.size, 0);
  h.document.hidden = false; play.dispatch('click'); h.observers[0].hide(); assert.equal(h.timeouts.size, 0);
  play.dispatch('click'); h.run('aiState.external.page = 1; renderExternalResearchList();');
  assert.equal(h.timeouts.size, 0);
  assert.ok(h.observers.slice(0, 6).every((observer) => observer.disconnected));
});

test('reduced motion shows a static selectable route without scheduling animation', () => {
  const h = harness({ reduced: true });
  const route = byClass(h.root, 'external-research-route')[0];
  const controls = byClass(route, 'external-research-route-controls')[0];
  assert.equal(controls.children[0].hidden, true);
  controls.children[0].dispatch('click'); assert.equal(h.timeouts.size, 0);
  byClass(route, 'external-research-step')[1].dispatch('click');
  assert.match(byClass(route, 'external-research-route-readout')[0].textContent, /^2\./);
  assert.match(controls.textContent, /Reduced motion/);
});

test('review date and scheduled checks are distinct; missing data does not revive legacy discovery claims', () => {
  const h = harness();
  const text = h.run('externalResearchSchedule(SuperconExternalResearch)');
  assert.match(text, /Source review: 2026-11-01/);
  assert.match(text, /Review schedule: daily at 09:00 \(America\/Chicago\)/);
  assert.match(text, /does not mean a new review has completed/);
  assert.match(h.run("externalResearchSchedule({schedule:{frequency:'daily',status:'planned'}})"), /Planned review/);
  h.run('globalThis.SuperconExternalResearch = undefined; renderAIFound();');
  assert.match(h.root.textContent, /registry is unavailable/);
  assert.match(h.root.textContent, /Superconductors found with AI by other groups/);
  assert.doesNotMatch(h.root.textContent, /experiments then confirmed/);
  assert.equal(byClass(h.root, 'external-research-card').length, 0);
});
