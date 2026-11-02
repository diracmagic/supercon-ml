import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../app/dist/team-board.js', import.meta.url), 'utf8');
const module = {exports: {}};
vm.runInNewContext(source, {module, AbortController});
const {createTeamBoard} = module.exports;
const ACCOUNT = 'A'.repeat(43), KEY = 'supercon-board-seen:' + ACCOUNT;
const message = (id, body = 'Synthetic message ' + id, own = false) => ({id, body, created_at: 1793552400000 + id,
  author: {name: own ? 'Example sender' : 'Example colleague', is_self: own}});
const page = (messages = [], latest = messages.at(-1)?.id || 0, has_more = false) => ({messages, latest_id: latest, has_more});
const flush = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); };
const flatten = node => [node, ...node.children.flatMap(flatten)];
class Events {
  constructor() { this.events = {}; }
  addEventListener(kind, fn) { (this.events[kind] ||= new Set()).add(fn); }
  removeEventListener(kind, fn) { this.events[kind]?.delete(fn); }
  dispatch(kind, extra = {}) { for (const fn of [...this.events[kind] || []]) fn({target: this, preventDefault() {}, ...extra}); }
}
class Element extends Events {
  constructor(tag, doc) { super(); Object.assign(this, {tagName: tag.toUpperCase(), doc, children: [], attributes: {}, _text: '', value: '', open: false, disabled: false, hidden: false}); }
  get firstChild() { return this.children[0] || null; }
  get isConnected() { return this === this.doc.body || !!this.parentNode?.isConnected; }
  get textContent() { return this._text + this.children.map(node => node.textContent).join(''); }
  set textContent(value) { this._text = String(value); this.children.forEach(node => {node.parentNode = null;}); this.children = []; }
  set innerHTML(_) { throw new Error('Board text must never use HTML'); }
  appendChild(node) { this.children.push(node); node.parentNode = this; return node; }
  removeChild(node) { this.children.splice(this.children.indexOf(node), 1); node.parentNode = null; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  focus() { this.doc.activeElement = this; }
  showModal() { this.open = true; }
  close() { this.open = false; this.dispatch('close'); }
}
function harness(options = {}) {
  const doc = new Events(); doc.hidden = false; doc.visibilityState = 'visible';
  doc.createElement = tag => new Element(tag, doc); doc.body = doc.createElement('body');
  const opener = doc.body.appendChild(doc.createElement('button')); opener.focus();
  const win = new Events(); win.navigator = {onLine: true};
  const stored = new Map(Object.entries(options.storage || {})), writes = [], requests = [], notifications = [], timers = new Map();
  win.localStorage = {getItem: key => stored.get(key) ?? null, setItem: (key, value) => {stored.set(key, value); writes.push({key, value});}};
  let clock = 100000, nextTimer = 1, unauthorized = 0;
  const ui = createTeamBoard({document: doc, window: win, storageKey: options.storageKey ?? ACCOUNT,
    onUnread: count => notifications.push(count), onUnauthorized: () => {unauthorized++;}, now: () => clock,
    setTimeout(fn, ms) { const id = nextTimer++; timers.set(id, {fn, due: clock + ms}); return id; },
    clearTimeout(id) { timers.delete(id); },
    request: async (path, method, body, settings) => {requests.push({path, method, body, settings}); return options.request ? options.request(path, method, body, settings, requests.length) : page();}});
  const nodes = () => flatten(doc.body), get = id => nodes().find(node => node.attributes.id === id);
  const button = text => {const found = nodes().find(node => node.tagName === 'BUTTON' && node.textContent === text); assert.ok(found, text); return found;};
  const click = text => button(text).dispatch('click');
  const compose = value => {const input = get('team-board-message'); input.value = value; input.dispatch('input'); input.parentNode.dispatch('submit');};
  return {ui, doc, win, stored, writes, requests, notifications, timers, get, button, click, compose, opener,
    get unauthorized() {return unauthorized;}, get unread() {return notifications.at(-1) || 0;},
    async advance(ms) {clock += ms; for (const [id, timer] of [...timers]) if (timer.due <= clock) {timers.delete(id); timer.fn();} await flush();},
    setVisible(value) {doc.hidden = !value; doc.visibilityState = value ? 'visible' : 'hidden'; doc.dispatch('visibilitychange');}};
}

test('the board is inert until team activation and stops fully on logout', async () => {
  const h = harness({request: () => page([message(1)])});
  h.ui.open(); await flush(); assert.equal(h.requests.length, 0); assert.equal(h.get('team-board-dialog'), undefined);
  h.ui.activate(); await flush(); assert.equal(h.requests.length, 1); assert.equal(h.unread, 1);
  h.ui.open(); await h.advance(5000); assert.match(h.doc.body.textContent, /Synthetic message 1/);
  h.ui.deactivate(); assert.equal(h.unread, 0); assert.equal(h.get('team-board-dialog').open, false);
  assert.doesNotMatch(h.doc.body.textContent, /Synthetic message|Example colleague/); assert.equal(h.timers.size, 0);
  const count = h.requests.length; h.win.dispatch('online'); h.setVisible(true); await h.advance(120000);
  assert.equal(h.requests.length, count);
  h.ui.destroy(); assert.equal(h.get('team-board-dialog'), undefined); assert.equal(h.win.events.online.size, 0);
});

test('unread excludes own posts, persists only an opaque account cursor, and marks read only while visible', async () => {
  const h = harness({storage: {[KEY]: '1'}, request: () => page([message(2), message(3, 'Own post', true)])});
  h.ui.activate(); await flush(); assert.equal(h.requests[0].path, '/api/board?after=1&limit=50');
  assert.equal(h.unread, 1); assert.equal(h.writes.length, 0);
  h.setVisible(false); h.ui.open(); await flush(); assert.equal(h.unread, 1); assert.equal(h.writes.length, 0);
  h.setVisible(true); assert.equal(h.unread, 0); assert.equal(h.stored.get(KEY), '3');
  assert.deepEqual(h.writes, [{key: KEY, value: '3'}]);
  assert.ok(h.writes.every(write => /^\d+$/.test(write.value)));
  assert.doesNotMatch(JSON.stringify(h.writes), /Synthetic|Example|Own post/);
});

test('message bodies and author names remain literal text, with no HTML nodes or links', async () => {
  const malicious = '<img src=x onerror=alert(1)> [link](javascript:alert(2))';
  const row = message(1, malicious); row.author.name = '<svg onload=alert(3)>';
  const h = harness({request: () => page([row])}); h.ui.activate(); await flush(); h.ui.open(); await h.advance(5000);
  assert.ok(h.doc.body.textContent.includes(malicious)); assert.ok(h.doc.body.textContent.includes(row.author.name));
  assert.equal(flatten(h.doc.body).some(node => ['IMG', 'SVG', 'A', 'SCRIPT'].includes(node.tagName)), false);
  assert.equal(h.get('team-board-message').getAttribute('maxlength'), '2000');
  assert.equal(h.get('team-board-dialog').getAttribute('aria-labelledby'), 'team-board-title');
  h.click('Close'); assert.equal(h.doc.activeElement, h.opener);
});

test('posting trims text, validates length and controls, and sends no client identity fields', async () => {
  const h = harness({request: (_path, method, body) => method === 'POST' ? {message: message(1, body.body, true), latest_id: 1} : page()});
  h.ui.activate(); await flush(); h.ui.open(); await h.advance(5000);
  for (const body of ['  ', 'x'.repeat(2001), 'bad\u0000text']) h.compose(body);
  assert.equal(h.requests.filter(item => item.method === 'POST').length, 0);
  h.compose('  A short\nteam update  '); await flush();
  const posts = h.requests.filter(item => item.method === 'POST'); assert.equal(posts.length, 1);
  assert.equal(JSON.stringify(posts[0].body), JSON.stringify({body: 'A short\nteam update'}));
  assert.equal(posts[0].path, '/api/board'); assert.equal(h.get('team-board-message').value, '');
  assert.equal(h.unread, 0); assert.match(h.doc.body.textContent, /A short\nteam update/);
});

test('failed posts retain draft and display only fixed errors, never raw service text', async () => {
  const h = harness({request: (_path, method) => {if (method === 'POST') throw {status: 500, code: '<script>private</script>', message: 'server secret'}; return page();}});
  h.ui.activate(); await flush(); h.ui.open(); await h.advance(5000); h.compose('Keep this draft'); await flush();
  assert.equal(h.get('team-board-message').value, 'Keep this draft');
  assert.match(h.get('team-board-status').textContent, /could not be confirmed/);
  assert.doesNotMatch(h.get('team-board-status').textContent, /private|script|server secret/);
  assert.equal(h.button('Post message').disabled, false);
});

test('stale requests are aborted and cannot repopulate private content after logout or reactivation', async () => {
  let resolve;
  const h = harness({request: (_p, _m, _b, _s, n) => n === 1 ? new Promise(done => {resolve = done;}) : page()});
  h.ui.activate(); h.ui.open(); h.ui.deactivate(); assert.equal(h.requests[0].settings.signal.aborted, true);
  h.ui.activate(); await flush(); resolve(page([message(1, 'STALE PRIVATE CONTENT')])); await flush();
  assert.doesNotMatch(h.doc.body.textContent, /STALE PRIVATE CONTENT/); assert.equal(h.unread, 0); assert.equal(h.writes.length, 0);
});

test('401 and 403 clear private messages and unread state before notifying the auth owner', async () => {
  for (const status of [401, 403]) {
    let reject = false;
    const h = harness({request: () => {if (reject) throw {status}; return page([message(1, 'PRIVATE AUTHORIZED MESSAGE')]);}});
    h.ui.activate(); await flush(); h.ui.open(); await h.advance(5000); assert.match(h.doc.body.textContent, /PRIVATE AUTHORIZED MESSAGE/);
    reject = true; await h.advance(60000);
    assert.equal(h.unauthorized, 1); assert.equal(h.unread, 0); assert.equal(h.get('team-board-dialog').open, false);
    assert.doesNotMatch(h.doc.body.textContent, /PRIVATE AUTHORIZED MESSAGE/); assert.equal(h.timers.size, 0);
  }
});

test('visible polling is one minute, hidden/offline polling stops, and rapid resume events are throttled', async () => {
  const h = harness(); h.ui.activate(); await flush(); assert.equal(h.requests.length, 1);
  await h.advance(59999); assert.equal(h.requests.length, 1); await h.advance(1); assert.equal(h.requests.length, 2);
  h.setVisible(false); await h.advance(120000); assert.equal(h.requests.length, 2);
  h.setVisible(true); await flush(); assert.equal(h.requests.length, 3);
  h.win.dispatch('online'); h.win.dispatch('online'); await flush(); assert.equal(h.requests.length, 3);
  await h.advance(5000); assert.equal(h.requests.length, 4);
  h.win.navigator.onLine = false; h.win.dispatch('offline'); await h.advance(120000); assert.equal(h.requests.length, 4);
  h.win.navigator.onLine = true; h.win.dispatch('online'); await flush(); assert.equal(h.requests.length, 5);
});

test('incremental pages advance by returned IDs rather than skipping to latest_id', async () => {
  const h = harness({storage: {[KEY]: '10'}, request: path => {
    const after = Number(new URL(path, 'https://example.test').searchParams.get('after'));
    if (after === 10) return page([message(11), message(12)], 15, true);
    if (after === 12) return page([message(13), message(14)], 15, true);
    if (after === 14) return page([message(15)], 15, false);
    return page([], 15);
  }});
  h.ui.activate(); await flush();
  assert.deepEqual(h.requests.map(item => item.path), ['/api/board?after=10&limit=50', '/api/board?after=12&limit=50', '/api/board?after=14&limit=50']);
  assert.equal(h.unread, 5); assert.equal(h.writes.length, 0);
});

test('latest-page has_more loads older history with before without generating new unread messages', async () => {
  const h = harness({request: path => path.includes('before=51') ? page([message(49), message(50)], 52, false) : page([message(51), message(52)], 52, true)});
  h.ui.activate(); await flush(); assert.equal(h.requests.length, 1, 'Initial has_more means older history, not forward pagination');
  h.ui.open(); await h.advance(5000); assert.equal(h.button('Load older messages').hidden, false);
  h.click('Load older messages'); await flush();
  assert.equal(h.requests.at(-1).path, '/api/board?before=51&limit=50');
  const ids = flatten(h.doc.body).filter(node => node.attributes['data-message-id']).map(node => Number(node.attributes['data-message-id']));
  assert.deepEqual(ids, [49, 50, 51, 52]); assert.equal(h.unread, 0); assert.equal(h.button('Load older messages').hidden, true);
});

test('a concurrent own post cannot mark an unreceived teammate message as read', async () => {
  let getCount = 0, releaseGet;
  const h = harness({request: (_p, method) => {
    if (method === 'POST') return {message: message(3, 'Own message', true), latest_id: 3};
    getCount++; if (getCount <= 2) return page([message(1)]);
    return new Promise(resolve => {releaseGet = resolve;});
  }});
  h.ui.activate(); await flush(); h.ui.open(); await h.advance(5000); assert.equal(h.stored.get(KEY), '1');
  h.compose('Own message'); await flush(); assert.equal(h.stored.get(KEY), '1');
  h.click('Close'); releaseGet(page([message(2, 'Concurrent colleague'), message(3, 'Own message', true)])); await flush();
  assert.equal(h.unread, 1); assert.equal(h.stored.get(KEY), '1');
});

test('invalid responses fail closed and email-like storage keys never persist messages or cursors', async () => {
  for (const result of [page([message(2), message(1)], 2), page([{...message(1), author: {name: 'A', is_self: 'true'}}]),
    page([{...message(1), created_at: 'yesterday'}]), {messages: [], latest_id: -1, has_more: false}]) {
    const h = harness({request: () => result}); h.ui.activate(); await flush(); h.ui.open(); await h.advance(5000);
    assert.equal(h.unread, 0); assert.doesNotMatch(h.doc.body.textContent, /Synthetic message/); assert.equal(h.writes.length, 0);
  }
  const h = harness({storageKey: 'member@example.org', request: () => page([message(1)])});
  h.ui.activate(); await flush(); h.ui.open(); await h.advance(5000); assert.equal(h.writes.length, 0);
});

test('another tab can mark the same account read without leaking or resetting another account cursor', async () => {
  const h = harness({request: () => page([message(1), message(2)])}); h.ui.activate(); await flush(); assert.equal(h.unread, 2);
  h.stored.set('supercon-board-seen:' + 'B'.repeat(43), '2');
  h.win.dispatch('storage', {key: 'supercon-board-seen:' + 'B'.repeat(43)}); assert.equal(h.unread, 2);
  h.stored.set(KEY, '2'); h.win.dispatch('storage', {key: KEY}); assert.equal(h.unread, 0);
  h.stored.set(KEY, '8'); h.ui.open(); await h.advance(5000);
  assert.equal(h.stored.get(KEY), '8', 'A slower tab never decreases the stored last-seen cursor');
  h.ui.destroy(); assert.equal(h.win.events.storage.size, 0);
});
