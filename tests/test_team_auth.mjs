import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { webcrypto, createHash } from 'node:crypto';

const source = fs.readFileSync(new URL('../app/dist/team-auth.js', import.meta.url), 'utf8');
const module = { exports: {} };
vm.runInNewContext(source, { module, URL, URLSearchParams, TextEncoder, AbortController, Uint8Array, console });
const auth = module.exports;
const TICKET = 'T'.repeat(43), STATE = 'S'.repeat(43), VERIFIER = 'V'.repeat(43), TOKEN = 'K'.repeat(43);
const TIME = 1800000000000;
const proof = (changes = {}) => ({ verifier: VERIFIER, state: STATE, created_at: TIME - 1000, ...changes });
const metadata = (changes = {}) => ({ user: { id: 350433501, login: 'demo-owner' }, expires_at: TIME + 120000, can_read_memo: true, ...changes });
const response = (value, status = 200) => ({ ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(value) });
const flush = async () => { for (let i = 0; i < 12; i++) await new Promise(setImmediate); };
async function waitFor(predicate, description, timeout = 5000) {
  const deadline = Date.now() + timeout;
  while (!predicate()) {
    assert.ok(Date.now() < deadline, 'Timed out waiting for ' + description);
    await new Promise(resolve => setTimeout(resolve, 2));
  }
}
const flatten = (node) => [node, ...node.children.flatMap(flatten)];

class Element {
  constructor(tag, doc) { this.tagName = tag.toUpperCase(); this.doc = doc; this.children = []; this.parentNode = null; this.attributes = {}; this.events = {}; this._text = ''; this.hidden = false; this.disabled = false; this.open = false; this.value = ''; }
  get firstChild() { return this.children[0] || null; }
  get isConnected() { return this === this.doc.body || !!this.parentNode?.isConnected; }
  get textContent() { return this._text + this.children.map((node) => node.textContent).join(''); }
  set textContent(value) { this._text = String(value); this.children.forEach((node) => { node.parentNode = null; }); this.children = []; }
  set innerHTML(_) { throw new Error('Private content must never enter innerHTML'); }
  appendChild(node) { this.children.push(node); node.parentNode = this; return node; }
  removeChild(node) { this.children.splice(this.children.indexOf(node), 1); node.parentNode = null; return node; }
  setAttribute(key, value) { this.attributes[key] = String(value); if (key === 'value') this.value = String(value); }
  removeAttribute(key) { delete this.attributes[key]; }
  getAttribute(key) { return this.attributes[key] ?? null; }
  addEventListener(kind, fn) { (this.events[kind] ||= []).push(fn); }
  removeEventListener(kind, fn) { this.events[kind] = (this.events[kind] || []).filter(value => value !== fn); }
  dispatch(kind) { for (const fn of this.events[kind] || []) fn({ target: this, preventDefault() {} }); }
  focus() { this.doc.activeElement = this; }
  showModal() { this.open = true; }
  close() { this.open = false; this.dispatch('close'); }
}

function memo(count = 31) {
  return { entry_count: count, reviewed_on: '2026-11-01', updated: '2026-11-01', entries: Array.from({ length: count }, (_, i) => ({
    id: String(i + 1).padStart(2, '0'), heading: i ? 'Research fixture ' + (i + 1) : '<img src=x onerror=alert(1)>',
    headline: 'A prediction, not a measured result', result: 'Fixture result ' + (i + 1), boundary: 'No candidate experiment reported.',
    reference_point: 'Use independent evidence.', category: '计算预测', year: '2026', stage: 'Theoretical prediction', team: 'Example team',
    publication: 'Example source', title: 'Primary research fixture', url: 'https://example.org/paper/' + i,
    pressure: 'Not specified', evidence_type: 'Calculation', tc_criterion: 'Calculated Tc', verified_version: 'Test version', reviewed_on: '2026-11-01',
    primary_refs: [{ label: 'Unsafe source', url: 'javascript:alert(1)' }, { label: 'Supplement', url: 'https://example.org/supplement/' + i }],
    progress_steps: [{ label: 'Calculation', detail: 'Model calculation.', status: 'completed' }, { label: 'Experiment', detail: 'Not performed.', status: 'not_reported' }]
  })) };
}

function harness({ apiBase = 'https://auth.example.org', hash = '', search = '?test=1', pending = null, initialStorage = {}, fetch: customFetch, session = metadata(), accountUI, materialUI, boardUI, crypto = webcrypto } = {}) {
  const doc = { events: {}, hidden: false, activeElement: null, readyState: 'complete',
    createElement(tag) { return new Element(tag, doc); },
    getElementById(id) { return flatten(doc.body).find((node) => node.attributes.id === id) || null; },
    addEventListener(kind, fn) { (doc.events[kind] ||= []).push(fn); },
    removeEventListener(kind, fn) { doc.events[kind] = (doc.events[kind] || []).filter(value => value !== fn); },
    dispatch(kind) { (doc.events[kind] || []).forEach((fn) => fn()); } };
  doc.body = doc.createElement('body');
  const header = doc.body.appendChild(doc.createElement('div'));
  const login = header.appendChild(doc.createElement('button')); login.setAttribute('id', 'team-login');
  const values = new Map(Object.entries(initialStorage));
  if (pending) values.set(auth.PENDING_KEY, JSON.stringify(pending));
  const writes = [], requests = [], redirects = [], history = [], events = {}, timers = new Map();
  let tick = TIME, nextTimer = 1;
  const win = { location: { hash, pathname: '/supercon-ml/', search, assign: (url) => redirects.push(url) },
    history: { replaceState(_state, _title, path) { history.push(path); win.location.hash = ''; } },
    sessionStorage: { getItem: (key) => values.get(key) ?? null, setItem(key, value) { values.set(key, value); writes.push([key, value]); }, removeItem: (key) => values.delete(key) },
    addEventListener(kind, fn) { (events[kind] ||= []).push(fn); },
    removeEventListener(kind, fn) { events[kind] = (events[kind] || []).filter(value => value !== fn); },
    setTimeout(fn, ms) { const id = nextTimer++; timers.set(id, {fn, ms}); return id; },
    clearTimeout(id) { timers.delete(id); },
    btoa: (value) => Buffer.from(value, 'binary').toString('base64') };
  if (materialUI) win.SuperconMaterialVisual = materialUI;
  Object.defineProperty(win, 'localStorage', { get() { throw new Error('Auth may not use localStorage'); } });
  const fetch = async (url, options) => {
    requests.push({ url, options });
    if (customFetch) return customFetch(url, options, requests.length);
    if (url.endsWith('/auth/exchange')) return response({ ...session, session_token: TOKEN });
    if (url.endsWith('/api/session')) return response(session);
    if (url.endsWith('/api/memo')) return response(memo());
    if (url.endsWith('/auth/logout')) return response({}, 204);
    throw new Error('Unexpected test URL');
  };
  const controller = auth.createController({ window: win, document: doc, config: { apiBase }, crypto, fetch, accountUI, boardUI,
    btoa: win.btoa, now: () => tick,
    setTimeout(fn, ms) { const id = nextTimer++; timers.set(id, { fn, ms }); return id; }, clearTimeout(id) { timers.delete(id); } });
  return { controller, doc, win, login, values, writes, requests, redirects, history, timers, events,
    get: (id) => doc.getElementById(id), setTime: (value) => { tick = value; },
    fire(ms) { const matches = [...timers].filter(([, timer]) => timer.ms === ms); for (const [id, timer] of matches) { timers.delete(id); timer.fn(); } },
    start() { controller.init(); return flush(); } };
}

test('endpoint and source validators reject unsafe URLs and non-origin API configuration', () => {
  assert.equal(auth.apiOrigin('https://auth.example.org/'), 'https://auth.example.org');
  for (const value of ['', 'http://auth.example.org', 'https://auth.example.org/path', 'https://auth.example.org/?', 'https://auth.example.org/#',
    'https://user:secret@auth.example.org', 'https://auth.example.org/?next=https://evil.example', 'https://auth.example.org/\n']) assert.equal(auth.apiOrigin(value), '', value);
  for (const value of ['javascript:alert(1)', 'http://example.org', 'https://a:b@example.org', 'https://example.org/%0aX']) assert.equal(auth.safeSourceUrl(value), '');
  assert.equal(auth.safeSourceUrl('https://doi.org/10.1234/example'), 'https://doi.org/10.1234/example');
});

test('proof uses independent 32-byte random values and the exact SHA-256 challenge', async () => {
  const value = await auth.makeProof(webcrypto, (x) => Buffer.from(x, 'binary').toString('base64'), TIME);
  assert.match(value.verifier, /^[A-Za-z0-9_-]{43}$/); assert.match(value.state, /^[A-Za-z0-9_-]{43}$/);
  assert.notEqual(value.verifier, value.state);
  assert.equal(value.challenge, createHash('sha256').update(value.verifier).digest('base64url'));
  assert.equal(auth.validProof(value, value.state, TIME), true);
  assert.equal(auth.validProof(value, 'wrong', TIME), false);
  assert.equal(auth.validProof(value, value.state, TIME + 600000), false);
  assert.equal(auth.validProof(value, value.state, TIME - 1), false);
});

test('empty endpoint fails closed and callback fragments are removed immediately', async () => {
  const h = harness({ apiBase: '', hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof() });
  assert.equal(h.win.location.hash, '');
  assert.deepEqual(h.history, ['/supercon-ml/?test=1']);
  await h.start(); await h.controller.signIn();
  assert.equal(h.requests.length, 0); assert.equal(h.redirects.length, 0);
  assert.equal(h.login.disabled, true); assert.equal(h.get('team-notes').hidden, true);
  assert.match(h.doc.body.textContent, /not available yet/);
});

test('sign-in redirects within the same tab with challenge and state, storing only the expiring proof', async () => {
  const h = harness(); await h.start(); await h.controller.signIn();
  assert.equal(h.redirects.length, 1); assert.equal(h.requests.length, 0);
  const url = new URL(h.redirects[0]);
  assert.equal(url.origin, 'https://auth.example.org'); assert.equal(url.pathname, '/auth/start');
  assert.deepEqual([...url.searchParams.keys()].sort(), ['challenge', 'state']);
  assert.equal(h.writes.length, 1); assert.equal(h.writes[0][0], auth.PENDING_KEY);
  const saved = JSON.parse(h.writes[0][1]);
  assert.deepEqual(Object.keys(saved).sort(), ['created_at', 'state', 'verifier']);
  assert.equal(url.searchParams.get('state'), saved.state);
  assert.equal(url.searchParams.get('challenge'), createHash('sha256').update(saved.verifier).digest('base64url'));
  assert.equal(url.href.includes(saved.verifier), false);
});

test('verified owner exchanges the proof, revalidates with the server and displays 31 inline notes safely', async () => {
  const h = harness({ hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof() });
  await h.start();
  assert.equal(h.values.has(auth.PENDING_KEY), false);
  assert.equal(h.writes.length, 0, 'Session token must never be written to storage');
  const exchange = h.requests.find((r) => r.url.endsWith('/auth/exchange'));
  assert.deepEqual(JSON.parse(exchange.options.body), { ticket: TICKET, verifier: VERIFIER, state: STATE });
  assert.equal(exchange.options.headers.Authorization, undefined);
  for (const request of h.requests) {
    assert.equal(request.options.credentials, 'omit'); assert.equal(request.options.cache, 'no-store');
    assert.equal(request.options.redirect, 'error'); assert.equal(request.options.referrerPolicy, 'no-referrer');
    if (request.url.includes('/api/')) assert.equal(request.options.headers.Authorization, 'Bearer ' + TOKEN);
  }
  assert.ok(h.requests.findIndex((r) => r.url.endsWith('/api/session')) < h.requests.findIndex((r) => r.url.endsWith('/api/memo')));
  assert.equal(h.get('team-notes').hidden, false); assert.equal(h.get('team-notes-dialog').open, true);
  assert.equal(flatten(h.doc.body).filter((node) => node.className === 'team-notes-card').length, 31);
  assert.match(h.doc.body.textContent, /<img src=x onerror=alert\(1\)>/);
  assert.equal(flatten(h.doc.body).some((node) => node.tagName === 'IMG'), false);
  assert.ok(flatten(h.doc.body).filter((node) => node.tagName === 'A').every((node) => node.attributes.href.startsWith('https://')));
  assert.match(h.doc.body.textContent, /Not reported/);
  const input = h.get('team-notes-search'); input.value = 'Fixture result 31'; input.dispatch('input');
  assert.equal(flatten(h.doc.body).filter((node) => node.className === 'team-notes-card').length, 1);
  h.get('team-notes-dialog').close(); assert.equal(h.doc.activeElement, h.get('team-notes'));
});

test('authenticated notes show sourced team and status text with both visuals and clean up material components', async () => {
  const classified = [], materials = [];
  const materialUI = {
    classifyMaterial(entry) { classified.push(entry.id); return 'unknown'; },
    createMaterialAnimation(options) {
      assert.equal(options.kind, 'unknown'); assert.equal(options.details.tagName, 'DETAILS');
      const node = options.document.createElement('section'); node.className = 'synthetic-material'; node.textContent = 'Synthetic material illustration';
      const record = { node, details: options.details, pauses: 0, destroys: 0 }; materials.push(record);
      return { node, pause() { record.pauses++; }, destroy() { record.destroys++; node.textContent = ''; } };
    }
  };
  const anonymous = harness({ materialUI }); await anonymous.start(); await anonymous.controller.openNotes();
  assert.equal(materials.length, 0, 'No material is constructed before authentication');
  const h = harness({ materialUI, hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof() });
  await h.start();
  assert.equal(materials.length, 31); assert.equal(new Set(classified).size, 31);
  const cards = flatten(h.doc.body).filter(node => node.className === 'team-notes-card');
  assert.equal(cards.length, 31);
  for (const card of cards) {
    const overview = card.children.find(node => node.className === 'team-notes-overview');
    assert.ok(overview, 'The overview is outside collapsed details');
    assert.match(overview.textContent, /Research teamExample team/);
    assert.match(overview.textContent, /This study: A prediction, not a measured result/);
    assert.match(overview.textContent, /Current status: Theoretical prediction/);
    const link = overview.children.find(node => node.tagName === 'A');
    assert.match(link.attributes.href, /^https:\/\/example\.org\/paper\//);
    assert.equal(link.attributes.rel, 'noopener noreferrer'); assert.equal(link.attributes.referrerpolicy, 'no-referrer');
    const details = card.children.find(node => node.tagName === 'DETAILS');
    assert.equal(details.children[0].textContent, 'Material, progress and sources');
    assert.equal(flatten(details).filter(node => node.className === 'synthetic-material').length, 1);
    assert.equal(flatten(details).filter(node => node.attributes.class === 'team-note-animation').length, 1, 'The existing workflow is retained');
    assert.match(details.textContent, /Evidence limitsNo candidate experiment reported/);
    assert.match(details.textContent, /Not reported/);
  }
  const initial = materials.slice();
  const search = h.get('team-notes-search'); search.value = 'Fixture result 31'; search.dispatch('input');
  assert.ok(initial.every(record => record.destroys === 1 && record.node.textContent === '' && !record.node.isConnected));
  assert.equal(materials.length, 32); assert.equal(flatten(h.doc.body).filter(node => node.className === 'synthetic-material').length, 1);
  const remaining = materials.at(-1);
  h.get('team-notes-dialog').close(); assert.equal(remaining.pauses, 1, 'Closing Notes pauses the material using the shared animation registry');
  await h.controller.logout();
  assert.ok(materials.every(record => record.destroys === 1 && record.node.textContent === '' && !record.node.isConnected));
  assert.doesNotMatch(h.doc.body.textContent, /Synthetic material|Example team|This study:|Current status:|Fixture result/);
});

test('both numeric owner ID and server permission are required; other accounts never fetch notes', async () => {
  for (const session of [metadata({ user: { id: 42, login: 'example-user' }, can_read_memo: true }), metadata({ can_read_memo: false })]) {
    const h = harness({ hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof(), session });
    await h.start(); await h.controller.openNotes();
    assert.equal(h.get('team-notes').hidden, true); assert.equal(h.get('team-logout').hidden, false);
    assert.equal(h.get('team-notes-dialog'), null);
    assert.equal(h.requests.some((r) => r.url.endsWith('/api/memo')), false);
  }
});

test('Firebase members require a typed, bounded server identity and can never gain admin capability', () => {
  const member = metadata({user: {id: 'firebase:example_uid', login: 'member@example.org', email: 'member@example.org', provider: 'firebase'},
    can_read_memo: true, can_manage_team: false});
  const verified = auth.sessionMetadata(member, TIME);
  assert.equal(verified.can_read_memo, true); assert.equal(verified.can_manage_team, false);
  for (const changed of [
    {...member, can_manage_team: true}, {...member, can_manage_team: undefined},
    {...member, user: {...member.user, id: '350433501'}}, {...member, user: {...member.user, email: 'different@example.org'}},
    {...member, user: {...member.user, provider: 'unknown'}}, {...member, user: {...member.user, email: '<img>@example.org', login: '<img>@example.org'}}
  ]) assert.equal(auth.sessionMetadata(changed, TIME), null);
  assert.equal(auth.sessionMetadata(metadata({can_manage_team: true}), TIME).can_manage_team, true);
  assert.equal(auth.sessionMetadata(metadata({user: {id: 42, login: 'other'}, can_manage_team: true}), TIME).can_manage_team, false);
});

test('account adapter exchanges only a Firebase ID token and rechecks membership before showing notes', async () => {
  let adapter, opened = 0, reset = 0;
  const member = metadata({user: {id: 'firebase:example_uid', login: 'member@example.org', email: 'member@example.org', provider: 'firebase'},
    can_read_memo: true, can_manage_team: false});
  const h = harness({session: member, accountUI: {createAccountUI(env) {adapter = env; return {
    openLogin() {opened++;}, openAdmin() {throw new Error('Member cannot open admin');}, reset() {reset++;}, handleEmailAction() {return false;}
  };}}, fetch: (url) => {
    if (url.endsWith('/auth/firebase')) return response({...member, session_token: TOKEN});
    if (url.endsWith('/api/session')) return response(member);
    if (url.endsWith('/api/memo')) return response(memo());
    return response({}, 204);
  }});
  await h.start(); h.login.dispatch('click'); assert.equal(opened, 1);
  await adapter.exchangeFirebase('synthetic-id-token'); await adapter.onAuthenticated();
  const exchange = h.requests.find(request => request.url.endsWith('/auth/firebase'));
  assert.deepEqual(JSON.parse(exchange.options.body), {id_token: 'synthetic-id-token'});
  assert.equal(exchange.options.headers.Authorization, undefined);
  assert.equal(h.get('team-notes').hidden, false); assert.equal(h.get('team-manage').hidden, false);
  assert.equal(h.login.textContent, 'member@example.org'); assert.equal(h.values.size, 0);
  assert.equal(h.get('team-notes-dialog').open, true);
  await h.controller.logout(); assert.ok(reset > 0); assert.equal(h.get('team-notes-dialog').open, false);
});

test('dismissing a pending email exchange cannot silently adopt a late session', async () => {
  let adapter, finish;
  const member = metadata({user: {id: 'firebase:example_uid', login: 'member@example.org', email: 'member@example.org', provider: 'firebase'},
    can_read_memo: true, can_manage_team: false});
  const h = harness({accountUI: {createAccountUI(env) {adapter = env; return {
    openLogin() {}, openAdmin() {}, reset() {}, handleEmailAction() {return false;}
  };}}, fetch: url => url.endsWith('/auth/firebase') ? new Promise(resolve => {finish = resolve;}) : response(member)});
  await h.start(); const exchange = adapter.exchangeFirebase('synthetic-id-token');
  adapter.onDismiss(); finish(response({...member, session_token: TOKEN}));
  await assert.rejects(exchange, /cancelled/);
  assert.equal(h.get('team-notes').hidden, true); assert.equal(h.get('team-logout').hidden, true);
  assert.equal(h.requests.length, 1); assert.equal(h.requests[0].options.signal.aborted, true);
});

test('only the verified GitHub owner can use the admin adapter, and all routes are fixed', async () => {
  let adapter, opens = 0;
  const owner = metadata({can_manage_team: true});
  const h = harness({hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof(), session: owner,
    accountUI: {createAccountUI(env) {adapter = env; return {openLogin() {}, openAdmin() {opens++;}, reset() {}, handleEmailAction() {return false;}};}},
    fetch: url => url.endsWith('/auth/exchange') ? response({...owner, session_token: TOKEN}) : url.endsWith('/api/session') ? response(owner) :
      url.endsWith('/api/memo') ? response(memo()) : response({members: []})});
  await h.start(); assert.equal(h.get('team-manage').hidden, false); h.get('team-manage').dispatch('click'); assert.equal(opens, 1);
  await adapter.teamRequest('/api/team', 'GET');
  await adapter.teamRequest('/api/team/name', 'POST', {member_id: 'M'.repeat(43), name: 'Alice'});
  assert.equal(h.requests.at(-1).options.headers.Authorization, 'Bearer ' + TOKEN);
  await assert.rejects(adapter.teamRequest('/api/team/delete', 'POST', {}));
  await assert.rejects(adapter.teamRequest('/api/team', 'POST', {}));
});

test('account adapter forwards only fixed invitation and member-name error categories', async () => {
  let adapter, errorCode;
  const owner = metadata({ can_manage_team: true });
  const h = harness({ hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof(), session: owner,
    accountUI: { createAccountUI(env) { adapter = env; return { openLogin() {}, openAdmin() {}, reset() {}, handleEmailAction() { return false; } }; } },
    fetch: url => url.endsWith('/auth/exchange') ? response({ ...owner, session_token: TOKEN }) : url.endsWith('/api/session') ? response(owner) :
      url.endsWith('/api/memo') ? response(memo()) : response({ error: errorCode, description: 'DO_NOT_REFLECT_PROVIDER_DETAIL' }, 400) });
  await h.start();
  for (const code of ['invitation_not_ready', 'fresh_login_required', 'invalid_member_name', 'member_not_found']) {
    errorCode = code;
    await assert.rejects(adapter.teamRequest('/api/team/name', 'POST', { member_id: 'M'.repeat(43), name: 'Synthetic Name' }), error => error.code === code && error.message === 'Request failed');
  }
  errorCode = '<img src=x onerror=alert(1)>';
  await assert.rejects(adapter.teamRequest('/api/team/name', 'POST', { member_id: 'M'.repeat(43), name: 'Synthetic Name' }), error => error.code === undefined && error.message === 'Request failed');
  assert.doesNotMatch(h.doc.body.textContent, /DO_NOT_REFLECT_PROVIDER_DETAIL/);
});

test('stored identity or session strings cannot sign a user in', async () => {
  const h = harness({ initialStorage: { session_token: TOKEN, user: JSON.stringify(metadata().user), can_read_memo: 'true' } });
  await h.start(); await h.controller.openNotes();
  assert.equal(h.requests.length, 0); assert.equal(h.get('team-notes').hidden, true);
  assert.equal(h.get('team-logout').hidden, true); assert.equal(h.login.disabled, false);
});

test('expired, mismatched and duplicate callback proofs fail before exchange', async () => {
  for (const options of [
    { pending: proof({ created_at: TIME - 600000 }) }, { pending: proof({ created_at: TIME + 1 }) },
    { pending: proof({ state: 'X'.repeat(43) }) }, { pending: null },
    { pending: proof(), hash: '#team_ticket=' + TICKET + '&team_state=' + STATE + '&team_state=' + STATE },
    { pending: proof(), hash: '#team_error=oauth_denied&team_state=' + STATE }
  ]) {
    const h = harness({ hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, ...options }); await h.start();
    assert.equal(h.requests.length, 0); assert.equal(h.win.location.hash, '');
    assert.equal(h.values.has(auth.PENDING_KEY), false); assert.equal(h.get('team-notes').hidden, true);
  }
});

test('fixed server callback codes give distinct safe diagnostics without attempting exchange', async () => {
  const expected = {
    oauth_state_invalid: /service could not verify the callback/,
    oauth_denied: /authorization was cancelled or denied/,
    oauth_failed: /failed at the authorization service/,
    oauth_credentials_invalid: /GitHub rejected the app credentials/,
    oauth_redirect_invalid: /GitHub rejected the callback address/,
    oauth_exchange_unavailable: /could not complete the GitHub exchange/,
    oauth_identity_unavailable: /could not verify your GitHub account/
  };
  const messages = new Set();
  for (const [code, pattern] of Object.entries(expected)) {
    // The server can report an invalid transaction without returning client state.
    const hash = '#team_error=' + code + (code === 'oauth_state_invalid' ? '' : '&team_state=' + STATE);
    const h = harness({ hash, pending: proof() });
    assert.equal(h.win.location.hash, '', 'Strip callback before initialization');
    await h.start();
    assert.match(h.doc.body.textContent, pattern);
    assert.doesNotMatch(h.doc.body.textContent, /request expired after 10 minutes/);
    assert.equal(h.requests.length, 0); assert.equal(h.values.has(auth.PENDING_KEY), false);
    assert.equal(h.get('team-notes').hidden, true); assert.equal(h.get('team-logout').hidden, true);
    messages.add(h.doc.body.textContent);
  }
  assert.equal(messages.size, Object.keys(expected).length);
});

test('allowlisted exchange diagnostics give actionable advice without retrying or changing authentication', async () => {
  const cases = [
    ['provider_email_unverified', /Verify your primary email in GitHub settings/],
    ['provider_transport', /could not reach GitHub or the request timed out/],
    ['provider_http_429', /temporarily limited sign-in requests/],
    ...[500, 502, 503, 504].map(status => ['provider_http_' + status, /temporary service error/]),
    ['provider_response_json', /unreadable response.*administrator needs to check/],
    ...['provider_token_format', 'provider_token_type', 'provider_expiry'].map(stage => [stage, /could not be validated.*administrator needs to check/])
  ];
  for (const [diagnostic, expected] of cases) {
    const h = harness({hash: '#team_error=oauth_exchange_unavailable&team_state=' + STATE,
      search: '?login_status=' + diagnostic, pending: proof()});
    await h.start();
    assert.match(h.doc.body.textContent, expected);
    assert.match(h.doc.body.textContent, /Login for team/);
    assert.equal(h.requests.length, 0); assert.equal(h.redirects.length, 0);
    assert.equal(h.values.has(auth.PENDING_KEY), false); assert.equal(h.get('team-notes').hidden, true);
    assert.equal(h.get('team-messages').hidden, true); assert.equal(h.get('team-logout').hidden, true);
    assert.equal(h.login.disabled, false, 'A fresh login remains available without an automatic retry loop');
  }
});

test('unknown, malicious and duplicate exchange diagnostics stay generic and do not invent a cause', async () => {
  const cases = ['PRIVATE_DIAGNOSTIC_MARKER', '__proto__', 'toString', '<img src=x onerror=alert(1)>', 'provider_http_599'];
  for (const diagnostic of cases) {
    const h = harness({hash: '#team_error=oauth_exchange_unavailable&team_state=' + STATE,
      search: '?login_status=' + encodeURIComponent(diagnostic) + '&error_description=DO_NOT_REFLECT', pending: proof()});
    await h.start();
    assert.match(h.doc.body.textContent, /could not complete the GitHub exchange/);
    assert.doesNotMatch(h.doc.body.textContent, /temporary service error|primary email|administrator needs to check/);
    assert.equal(h.doc.body.textContent.includes(diagnostic), false); assert.doesNotMatch(h.doc.body.textContent, /DO_NOT_REFLECT/);
    assert.equal(h.requests.length, 0);
  }
  const duplicate = harness({hash: '#team_error=oauth_exchange_unavailable',
    search: '?login_status=provider_email_unverified&login_status=provider_transport'});
  await duplicate.start(); assert.match(duplicate.doc.body.textContent, /could not complete the GitHub exchange/);
  assert.doesNotMatch(duplicate.doc.body.textContent, /primary email|request timed out/);
});

test('diagnostic advice cannot override another error or turn a valid ticket into a failed login', async () => {
  const denied = harness({hash: '#team_error=oauth_denied&team_state=' + STATE,
    search: '?login_status=provider_email_unverified', pending: proof()});
  await denied.start(); assert.match(denied.doc.body.textContent, /authorization was cancelled or denied/);
  assert.doesNotMatch(denied.doc.body.textContent, /primary email/); assert.equal(denied.requests.length, 0);
  const success = harness({hash: '#team_ticket=' + TICKET + '&team_state=' + STATE,
    search: '?login_status=provider_email_unverified', pending: proof()});
  await success.start(); assert.equal(success.get('team-notes').hidden, false);
  assert.ok(success.requests.some(item => item.url.endsWith('/auth/exchange')));
  assert.doesNotMatch(success.doc.body.textContent, /Verify your primary email/);
  const forged = harness({search: '?login_status=provider_email_unverified', pending: proof()});
  await forged.start(); assert.equal(forged.requests.length, 0); assert.doesNotMatch(forged.doc.body.textContent, /Verify your primary email/);
});

test('trusted-category cooldown advice accepts only a bounded canonical delay and never retries automatically', async () => {
  for (const [seconds, text] of [[1, '1 second'], [59, '59 seconds'], [60, '1 minute'], [61, '2 minutes'], [3600, '1 hour'], [86400, '24 hours']]) {
    const h = harness({hash: '#team_error=oauth_exchange_unavailable&team_state=' + STATE,
      search: '?login_status=provider_http_429&login_retry_after=' + seconds, pending: proof()});
    await h.start();
    assert.ok(h.doc.body.textContent.includes('Wait at least ' + text + ','));
    assert.match(h.doc.body.textContent, /GitHub sign-in is paused for this app/);
    assert.equal(h.requests.length, 0); assert.equal(h.redirects.length, 0); assert.equal(h.timers.size, 0);
    assert.equal(h.get('team-notes').hidden, true); assert.equal(h.get('team-messages').hidden, true);
    assert.equal(h.get('team-logout').hidden, true); assert.equal(h.values.has(auth.PENDING_KEY), false);
  }
});

test('invalid cooldown query values and unrelated fields cannot claim a countdown or grant access', async () => {
  for (const value of ['0', '-1', '+60', '060', '1.5', '1e3', '86401', '999999999999999999999', ' 60', '60\n', '60\u0000', '<img src=x>', '__proto__']) {
    const h = harness({hash: '#team_error=oauth_exchange_unavailable', search: '?login_status=provider_http_429&login_retry_after=' + encodeURIComponent(value)});
    await h.start();
    assert.match(h.doc.body.textContent, /Wait at least one minute/);
    assert.doesNotMatch(h.doc.body.textContent, /paused for this app|<img|__proto__/);
    assert.equal(h.requests.length, 0); assert.equal(h.get('team-notes').hidden, true);
  }
  for (const search of ['?login_status=provider_http_429&login_retry_after=60&login_retry_after=120',
    '?login_status=provider_http_429&retry_after=120&unknown=<script>PRIVATE</script>',
    '?login_status=provider_transport&login_retry_after=120', '?login_retry_after=120']) {
    const h = harness({hash: '#team_error=oauth_exchange_unavailable', search}); await h.start();
    assert.doesNotMatch(h.doc.body.textContent, /paused for this app|120|PRIVATE|<script>/);
    assert.equal(h.requests.length, 0); assert.equal(h.redirects.length, 0);
  }
  const success = harness({hash: '#team_ticket=' + TICKET + '&team_state=' + STATE,
    search: '?login_status=provider_http_429&login_retry_after=120', pending: proof()});
  await success.start(); assert.equal(success.get('team-notes').hidden, false);
  assert.doesNotMatch(success.doc.body.textContent, /paused for this app|temporarily limited/);
});

test('client missing, expired, mismatched and malformed proofs have separate diagnostics', async () => {
  const normalHash = '#team_ticket=' + TICKET + '&team_state=' + STATE;
  const cases = [
    [{ hash: normalHash }, /could not find a valid pending sign-in request/],
    [{ hash: normalHash, pending: proof({ created_at: TIME - 600000 }) }, /request expired after 10 minutes/],
    [{ hash: normalHash, pending: proof({ created_at: TIME + 1 }) }, /saved sign-in time is invalid/],
    [{ hash: normalHash, pending: proof({ state: 'X'.repeat(43) }) }, /does not match the request started in this tab/],
    [{ hash: '#team_ticket=bad&team_state=' + STATE, pending: proof() }, /did not include a valid login ticket/],
    [{ hash: normalHash + '&team_state=' + STATE, pending: proof() }, /callback was malformed/],
    [{ hash: normalHash + '&team_error=oauth_denied', pending: proof() }, /callback was malformed/]
  ];
  for (const [options, pattern] of cases) {
    const h = harness(options); await h.start();
    assert.match(h.doc.body.textContent, pattern); assert.equal(h.requests.length, 0);
    assert.equal(h.win.location.hash, ''); assert.equal(h.values.has(auth.PENDING_KEY), false);
    assert.equal(h.get('team-notes').hidden, true);
  }
});

test('unknown callback errors and descriptions are never reflected as text or markup', async () => {
  for (const code of ['__proto__', 'toString', '<img src=x onerror=alert(1)>', 'PRIVATE_ERROR_MARKER']) {
    const h = harness({ hash: '#team_error=' + encodeURIComponent(code) + '&error_description=DO_NOT_REFLECT&team_state=' + STATE,
      pending: proof() });
    await h.start();
    assert.match(h.doc.body.textContent, /unrecognized error/);
    assert.equal(h.doc.body.textContent.includes(code), false); assert.doesNotMatch(h.doc.body.textContent, /DO_NOT_REFLECT/);
    assert.equal(flatten(h.doc.body).some(node => node.tagName === 'IMG'), false);
    assert.equal(h.win.location.hash, ''); assert.equal(h.requests.length, 0); assert.equal(h.values.has(auth.PENDING_KEY), false);
  }
});

test('session revocation on visibility check immediately closes and clears private content', async () => {
  let denied = false;
  const h = harness({ hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof(), fetch: async (url) => {
    if (url.endsWith('/auth/exchange')) return response({ ...metadata(), session_token: TOKEN });
    if (url.endsWith('/api/session')) return denied ? response({}, 401) : response(metadata());
    return response(memo());
  } });
  await h.start(); assert.match(h.doc.body.textContent, /Fixture result 31/);
  denied = true; h.doc.dispatch('visibilitychange'); await flush();
  assert.doesNotMatch(h.doc.body.textContent, /Fixture result|No candidate experiment/);
  assert.equal(h.get('team-notes-dialog').open, false); assert.equal(h.get('team-notes').hidden, true);
  assert.equal(h.doc.activeElement, h.login);
});

test('a forbidden memo response clears the authenticated UI rather than showing a fallback', async () => {
  const h = harness({ hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof(), fetch: async (url) => {
    if (url.endsWith('/auth/exchange')) return response({ ...metadata(), session_token: TOKEN });
    if (url.endsWith('/api/session')) return response(metadata());
    return response({}, 403);
  } });
  await h.start();
  assert.equal(h.get('team-notes').hidden, true); assert.equal(h.get('team-logout').hidden, true);
  assert.equal(h.get('team-notes-dialog').open, false);
  assert.doesNotMatch(h.doc.body.textContent, /Fixture result/);
});

test('logout clears notes before the network request and ignores late memo responses', async () => {
  let releaseMemo;
  const h = harness({ hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof(), fetch: async (url) => {
    if (url.endsWith('/auth/exchange')) return response({ ...metadata(), session_token: TOKEN });
    if (url.endsWith('/api/session')) return response(metadata());
    if (url.endsWith('/api/memo')) return new Promise((resolve) => { releaseMemo = resolve; });
    return response({}, 204);
  } });
  await h.start(); assert.ok(releaseMemo);
  const pendingLogout = h.controller.logout();
  assert.equal(h.get('team-notes-dialog').open, false); assert.equal(h.get('team-notes').hidden, true);
  releaseMemo(response(memo())); await pendingLogout; await flush();
  assert.doesNotMatch(h.doc.body.textContent, /Fixture result/);
  const logout = h.requests.find((r) => r.url.endsWith('/auth/logout'));
  assert.equal(logout.options.method, 'POST'); assert.equal(logout.options.headers.Authorization, 'Bearer ' + TOKEN);
  assert.equal(h.writes.some(([, value]) => value.includes(TOKEN)), false);
});

test('expiry clears the memo and returns focus to the login control', async () => {
  const h = harness({ hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof() }); await h.start();
  h.setTime(TIME + 120000); h.fire(120000);
  assert.equal(h.get('team-notes').hidden, true); assert.equal(h.get('team-notes-dialog').open, false);
  assert.doesNotMatch(h.doc.body.textContent, /Fixture result/); assert.match(h.doc.body.textContent, /session expired/);
  assert.equal(h.doc.activeElement, h.login);
});

test('request deadlines include a stalled response body and leave no authenticated state', async () => {
  const h = harness({ hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof(),
    fetch: async () => ({ ok: true, status: 200, text: () => new Promise(() => {}) }) });
  await h.start(); h.fire(12000); await flush();
  assert.equal(h.requests[0].options.signal.aborted, true);
  assert.equal(h.get('team-notes').hidden, true); assert.equal(h.get('team-logout').hidden, true);
  assert.equal(h.login.disabled, false); assert.match(h.doc.body.textContent, /could not be completed/);
});

test('session expiry is milliseconds only and static evaluation has no DOM side effects', () => {
  assert.equal(auth.sessionMetadata(metadata({ expires_at: Math.floor(TIME / 1000) }), TIME), null);
  assert.equal(auth.sessionMetadata(metadata({ expires_at: new Date(TIME + 120000).toISOString() }), TIME), null);
  assert.doesNotThrow(() => vm.runInNewContext(source, {}));
  assert.doesNotMatch(source, /localStorage|console\.(?:log|debug|info)|innerHTML\s*=/);
});

function boardStub() {
  const instances = [];
  return {instances, createTeamBoard(options) {
    const entry = {options, activates: 0, opens: 0, destroys: 0}; instances.push(entry);
    const privateNode = options.document.createElement('div'); privateNode.textContent = 'Synthetic private board';
    options.document.body.appendChild(privateNode);
    return {activate() {entry.activates++;}, open() {entry.opens++;}, deactivate() {}, destroy() {
      entry.destroys++; privateNode.textContent = ''; if (privateNode.parentNode) privateNode.parentNode.removeChild(privateNode);
    }};
  }};
}
function presenceAccountStub() {
  const account = {options: null, updates: [], opens: 0, resets: 0};
  return Object.assign(account, {createAccountUI(options) {
    account.options = options;
    return {openLogin() {}, openTeam() {account.opens++;}, reset() {account.resets++;}, handleEmailAction() {return false;},
      setPresence(value) {account.updates.push(value);} };
  }});
}
async function startBoardSession(h, board) {
  await h.start();
  // WebCrypto runs outside the JS event loop. Fixed setImmediate turns do not
  // establish readiness under concurrent CI load; await observable completion.
  await waitFor(() => board.instances[0]?.activates === 1 &&
    h.get('team-notes-dialog')?.open && h.doc.body.textContent.includes('Fixture result 31'),
  'verified board activation and the completed automatic Notes load');
}
const loginOptions = {hash: '#team_ticket=' + TICKET + '&team_state=' + STATE, pending: proof()};

test('message routes accept only fixed paths and bounded integer pagination', () => {
  for (const path of ['/api/board', '/api/board?after=0&limit=50', '/api/board?limit=1&before=99', '/api/board?after=9007199254740991']) {
    assert.equal(auth.boardRoute(path, 'GET'), true, path);
  }
  assert.equal(auth.boardRoute('/api/board', 'POST'), true);
  for (const path of ['https://evil.example/api/board', '//evil.example/api/board', '/api/board/', '/api/board?',
    '/api/board?before=1&after=0', '/api/board?before=0', '/api/board?limit=51', '/api/board?limit=0', '/api/board?after=00',
    '/api/board?after=-1', '/api/board?after=1e3', '/api/board?after=9007199254740992', '/api/board?after=1&after=2',
    '/api/board?after=%31', '/api/board?after=1#x', '/api/board?next=https://evil.example', '/api/board?after=1&']) {
    assert.equal(auth.boardRoute(path, 'GET'), false, path);
  }
  assert.equal(auth.boardRoute('/api/board?after=1', 'POST'), false);
  assert.equal(auth.boardRoute('/api/board', 'DELETE'), false);
});

test('messages activate only for a verified team actor, with opaque storage and fixed-origin requests', async () => {
  const anonymousBoard = boardStub(), anonymous = harness({boardUI: anonymousBoard});
  await anonymous.start(); await anonymous.controller.openMessages();
  assert.equal(anonymousBoard.instances.length, 0); assert.equal(anonymous.get('team-messages').hidden, true);
  const board = boardStub();
  const h = harness({...loginOptions, boardUI: board, fetch: (url) =>
    url.endsWith('/auth/exchange') ? response({...metadata(), session_token: TOKEN}) :
    url.endsWith('/api/session') ? response(metadata()) : url.endsWith('/api/memo') ? response(memo()) : response({messages: []})});
  await startBoardSession(h, board);
  assert.equal(board.instances.length, 1); const instance = board.instances[0];
  assert.equal(instance.activates, 1); assert.equal(h.get('team-messages').hidden, false);
  assert.equal(instance.options.storageKey, createHash('sha256').update('github:350433501').digest('hex'));
  instance.options.onUnread(3); assert.equal(h.get('team-messages-unread').textContent, 'New');
  assert.match(h.get('team-messages').getAttribute('aria-label'), /new team messages/);
  await h.controller.openMessages(); assert.equal(instance.opens, 1); assert.equal(board.instances.length, 1);
  await instance.options.request('/api/board?after=0&limit=50', 'GET');
  const req = h.requests.at(-1);
  assert.equal(req.url, 'https://auth.example.org/api/board?after=0&limit=50');
  assert.equal(req.options.headers.Authorization, 'Bearer ' + TOKEN);
  assert.equal(req.options.cache, 'no-store'); assert.equal(req.options.credentials, 'omit');
  assert.equal(req.options.redirect, 'error'); assert.equal(req.options.referrerPolicy, 'no-referrer');
  const count = h.requests.length;
  await assert.rejects(instance.options.request('https://evil.example/api/board', 'GET'));
  await assert.rejects(instance.options.request('/api/board?after=0', 'POST', {}));
  assert.equal(h.requests.length, count);
  assert.equal(h.writes.length, 0, 'Only the board module may persist a numeric last-seen cursor');
  await h.controller.logout();
  assert.equal(instance.destroys, 1); assert.equal(h.get('team-messages').hidden, true);
  assert.equal(h.get('team-messages-unread').hidden, true); assert.doesNotMatch(h.doc.body.textContent, /Synthetic private board/);
  instance.options.onUnread(5); assert.equal(h.get('team-messages-unread').hidden, true);
  await assert.rejects(instance.options.request('/api/board', 'GET'), /cancelled/);
});

test('email members activate the board with a different opaque actor key', async () => {
  let account;
  const member = metadata({user: {id: 'firebase:example_uid', login: 'member@example.org', email: 'member@example.org', provider: 'firebase'}, can_manage_team: false});
  const board = boardStub(), h = harness({boardUI: board, accountUI: {createAccountUI(options) {account = options;
    return {openLogin() {}, reset() {}, handleEmailAction() {return false;}};
  }}, fetch: url => url.endsWith('/auth/firebase') ? response({...member, session_token: TOKEN}) : response(member)});
  await h.start(); await account.exchangeFirebase('synthetic-id-token');
  assert.equal(board.instances.length, 1); assert.equal(h.get('team-messages').hidden, false);
  assert.equal(board.instances[0].options.storageKey, createHash('sha256').update('firebase:firebase:example_uid').digest('hex'));
  assert.doesNotMatch(board.instances[0].options.storageKey, /member|example_uid/);
});

test('Team presence is available to approved email members without granting team administration', async () => {
  const anonymousAccount = presenceAccountStub(), anonymous = harness({accountUI: anonymousAccount});
  await anonymous.start();
  assert.equal(anonymous.get('team-manage').hidden, true);
  await assert.rejects(anonymousAccount.options.presenceRequest(), /unavailable/);
  assert.equal(anonymous.requests.length, 0);
  const snapshot = {members: [{name: 'Synthetic member', is_self: true, online: true}], window_seconds: 150, observed_at: TIME};
  const member = metadata({user: {id: 'firebase:example_uid', login: 'member@example.org', email: 'member@example.org', provider: 'firebase'}, can_manage_team: false, presence: snapshot});
  const account = presenceAccountStub(), h = harness({accountUI: account, fetch: url =>
    url.endsWith('/auth/firebase') ? response({...member, session_token: TOKEN}) :
    url.endsWith('/api/presence') ? response({presence: snapshot}) : response(member)});
  await h.start(); await account.options.exchangeFirebase('synthetic-id-token');
  assert.equal(h.get('team-manage').hidden, false); assert.equal(account.options.canReadTeam(), true); assert.equal(account.options.canManageTeam(), false);
  h.get('team-manage').dispatch('click'); assert.equal(account.opens, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(account.updates.at(-1))), snapshot);
  const before = h.requests.length;
  await account.options.presenceRequest('https://evil.example/private');
  assert.equal(h.requests.length, before + 1, 'Presence does not add a redundant session check');
  const req = h.requests.at(-1);
  assert.equal(req.url, 'https://auth.example.org/api/presence'); assert.equal(req.options.method, 'GET');
  assert.equal(req.options.headers.Authorization, 'Bearer ' + TOKEN); assert.equal(req.options.cache, 'no-store');
  await assert.rejects(account.options.teamRequest('/api/team', 'GET'), /management unavailable/);
  assert.equal(h.writes.length, 0);
  await h.controller.logout();
  assert.equal(account.updates.at(-1), null); assert.equal(account.options.canReadTeam(), false); assert.equal(h.get('team-manage').hidden, true);
});

test('presence piggybacks verified board responses and late snapshots cannot survive logout', async () => {
  const first = {members: [{name: 'Initial fixture', is_self: true, online: true}], window_seconds: 150, observed_at: TIME};
  const second = {...first, members: [{name: 'Board fixture', is_self: true, online: true}]};
  const account = presenceAccountStub(), board = boardStub(); let delayed = false, finish;
  const h = harness({...loginOptions, accountUI: account, boardUI: board, fetch: url =>
    url.endsWith('/auth/exchange') ? response({...metadata(), session_token: TOKEN}) :
    url.endsWith('/api/session') ? response({...metadata(), presence: first}) :
    url.endsWith('/api/memo') ? response(memo()) : url.includes('/api/board') ?
      delayed ? new Promise(resolve => {finish = resolve;}) : response({messages: [], presence: second}) : response({}, 204)});
  await startBoardSession(h, board); assert.deepEqual(JSON.parse(JSON.stringify(account.updates.at(-1))), first);
  const adapter = board.instances[0].options;
  await adapter.request('/api/board?after=0', 'GET'); assert.deepEqual(JSON.parse(JSON.stringify(account.updates.at(-1))), second);
  delayed = true;
  const pending = adapter.request('/api/board', 'GET'); const rejected = assert.rejects(pending, /cancelled/);
  await h.controller.logout(); await rejected;
  const count = account.updates.length;
  finish(response({messages: [], presence: second})); await flush();
  assert.equal(account.updates.length, count); assert.equal(account.updates.at(-1), null);
  assert.equal(h.requests.filter(req => req.url.endsWith('/api/presence')).length, 0, 'Existing polls supply presence without a new loop');
});

test('presence failures and membership loss preserve the authentication boundary', async () => {
  for (const status of [401, 403, 429, 503]) {
    const account = presenceAccountStub(), h = harness({...loginOptions, accountUI: account, fetch: url =>
      url.endsWith('/auth/exchange') ? response({...metadata(), session_token: TOKEN}) :
      url.endsWith('/api/session') ? response(metadata()) : url.endsWith('/api/memo') ? response(memo()) :
      response({error: status === 403 ? 'membership_revoked' : 'rate_limited'}, status)});
    await h.start();
    await assert.rejects(account.options.presenceRequest());
    assert.equal(h.get('team-manage').hidden, status === 401 || status === 403);
    if (status === 401 || status === 403) assert.equal(account.updates.at(-1), null);
  }
  let canRead = true;
  const account = presenceAccountStub(), h = harness({...loginOptions, accountUI: account, fetch: url =>
    url.endsWith('/auth/exchange') ? response({...metadata(), session_token: TOKEN}) :
    url.endsWith('/api/session') ? response(metadata({can_read_memo: canRead, can_manage_team: false})) : response(memo())});
  await h.start(); const resets = account.resets; canRead = false;
  h.doc.dispatch('visibilitychange'); await flush();
  assert.equal(account.resets, resets + 1, 'Losing read permission clears the Team dialog even without a prior admin role');
  assert.equal(account.updates.at(-1), null); assert.equal(h.get('team-manage').hidden, true);
});

test('board cancellation aborts the network request and a late response cannot survive logout', async () => {
  let finish;
  const board = boardStub(), h = harness({...loginOptions, boardUI: board, fetch: (url) =>
    url.endsWith('/auth/exchange') ? response({...metadata(), session_token: TOKEN}) : url.endsWith('/api/session') ? response(metadata()) :
    url.endsWith('/api/memo') ? response(memo()) : url.endsWith('/api/board') ? new Promise(resolve => {finish = resolve;}) : response({}, 204)});
  await startBoardSession(h, board); const options = board.instances[0].options, controller = new AbortController();
  const pending = options.request('/api/board', 'GET', undefined, {signal: controller.signal});
  const rejected = assert.rejects(pending, /cancelled/); controller.abort(); await rejected;
  assert.equal(h.requests.at(-1).options.signal.aborted, true);
  finish(response({messages: [{body: 'LATE_PRIVATE'}]})); await flush();
  const second = options.request('/api/board', 'GET'); const rejectedSecond = assert.rejects(second, /cancelled/);
  await h.controller.logout(); await rejectedSecond;
  finish(response({messages: [{body: 'LATE_PRIVATE'}]})); await flush();
  assert.equal(h.get('team-messages').hidden, true); assert.doesNotMatch(h.doc.body.textContent, /LATE_PRIVATE|Synthetic private board/);
});

test('board denial clears private UI while rate limits leave the authenticated team intact', async () => {
  for (const code of [401, 403, 429]) {
    const board = boardStub(), h = harness({...loginOptions, boardUI: board, fetch: url =>
      url.endsWith('/auth/exchange') ? response({...metadata(), session_token: TOKEN}) : url.endsWith('/api/session') ? response(metadata()) :
      url.endsWith('/api/memo') ? response(memo()) : response({error: 'rate_limited'}, code)});
    await startBoardSession(h, board); const instance = board.instances[0]; instance.options.onUnread(1);
    await assert.rejects(instance.options.request('/api/board', 'GET'), error => error.status === code);
    assert.equal(h.get('team-messages').hidden, code !== 429);
    assert.equal(instance.destroys, code === 429 ? 0 : 1);
  }
});

test('membership loss and timed expiry destroy the board and ignore old notifications', async () => {
  for (const expiry of [false, true]) {
    let permitted = true;
    const board = boardStub(), h = harness({...loginOptions, boardUI: board, fetch: url =>
      url.endsWith('/auth/exchange') ? response({...metadata(), session_token: TOKEN}) : url.endsWith('/api/session') ? response(metadata({can_read_memo: permitted})) : response(memo())});
    await startBoardSession(h, board); const instance = board.instances[0]; instance.options.onUnread(1);
    if (expiry) { h.setTime(TIME + 120001); h.fire(120000); } else { permitted = false; h.doc.dispatch('visibilitychange'); }
    await flush();
    assert.equal(instance.destroys, 1); assert.equal(h.get('team-messages').hidden, true);
    instance.options.onUnread(4); assert.equal(h.get('team-messages-unread').hidden, true);
    assert.doesNotMatch(h.doc.body.textContent, /Synthetic private board/);
  }
});

test('Notes highlight only explicit experimental evidence and keep limitations and citations visible', async () => {
  const data = memo(7);
  const statuses = [undefined, 'signal_only', 'experimental_support', 'bulk_supported', 'negative_test', 'process_only', 'unrecognized'];
  data.entries.forEach((entry, index) => {
    entry.experimental_status = statuses[index]; entry.experimental_note = 'Bounded sample evidence ' + index + ' <img src=x>';
    entry.category = '实验研究'; entry.heading = 'Synthetic superconductivity experiment ' + index;
  });
  const h = harness({...loginOptions, fetch: url => url.endsWith('/auth/exchange') ? response({...metadata(), session_token: TOKEN}) :
    url.endsWith('/api/session') ? response(metadata()) : response(data)});
  await h.start();
  const cards = () => flatten(h.doc.body).filter(node => /(?:^| )team-notes-card(?: |$)/.test(node.className || ''));
  assert.deepEqual(cards().map(card => card.children[1].textContent), [0,1,2,3,4,5,6].map(i => 'Synthetic superconductivity experiment ' + i));
  assert.equal(cards().filter(card => card.className.includes('is-experimental')).length, 2);
  assert.equal(flatten(h.doc.body).filter(node => /team-notes-evidence-badge/.test(node.className || '')).length, 5);
  assert.match(cards()[3].textContent, /Bulk superconductivity supported/);
  for (const card of cards()) {
    const overview = card.children.find(node => node.className === 'team-notes-overview');
    assert.match(overview.textContent, /Bounded sample evidence/);
    assert.ok(overview.children.some(node => node.tagName === 'A' && node.attributes.href.startsWith('https://example.org/paper/')));
  }
  assert.equal(flatten(h.doc.body).some(node => node.tagName === 'IMG'), false);
  const category = h.get('team-notes-category'); category.value = 'experimental_evidence'; category.dispatch('change');
  assert.equal(cards().length, 2);
  const search = h.get('team-notes-search'); search.value = 'Bounded sample evidence 2'; search.dispatch('input');
  assert.equal(cards().length, 1); assert.match(cards()[0].textContent, /Superconductivity: experimental evidence/);
  category.value = '实验研究'; search.value = 'experiment 1'; search.dispatch('input');
  assert.equal(cards().length, 1); assert.match(cards()[0].textContent, /Experimental signal · phase\/verification limits/);
  assert.doesNotMatch(cards()[0].className, /is-experimental/);
  await h.controller.logout(); assert.doesNotMatch(h.doc.body.textContent, /Bounded sample evidence|Bulk superconductivity supported/);
});

test('Notes group only explicit update dates, newest first, with stable IDs and no review-date substitution', async () => {
  const data = memo(7);
  data.updated = data.reviewed_on = '2026-11-05';
  data.entries.forEach(entry => { entry.reviewed_on = '2026-11-05'; entry.year = '2026'; });
  data.entries[0].updated_on = '2026-10-30'; data.entries[0].experimental_status = 'bulk_supported';
  data.entries[1].updated_on = '2026-11-01'; data.entries[1].experimental_status = 'not_experimental';
  data.entries[1].change_summary = 'New source checked <img src=x onerror=alert(1)>';
  data.entries[2].updated_on = '2026-10-30';
  data.entries[3].updated_on = '2026-11-01';
  data.entries[4].updated_on = '2026-02-30';
  data.entries[5].updated_on = undefined;
  data.entries[6].updated_on = '2026-11-01T00:00:00Z';
  data.entries.reverse();
  const h = harness({...loginOptions, fetch: url => url.endsWith('/auth/exchange') ? response({...metadata(), session_token: TOKEN}) :
    url.endsWith('/api/session') ? response(metadata()) : response(data)});
  await h.start();
  const groups = () => flatten(h.doc.body).filter(node => node.className === 'team-notes-date-group');
  assert.deepEqual(groups().map(group => group.children[0].textContent), ['Updated 2026-11-01', 'Updated 2026-10-30', 'Update date not recorded']);
  const ids = group => flatten(group).filter(node => node.className === 'team-notes-meta').map(node => node.textContent.slice(0, 3));
  assert.deepEqual(groups().map(ids), [['#02','#04'], ['#01','#03'], ['#05','#06','#07']]);
  assert.match(groups()[0].textContent, /New source checked <img src=x onerror=alert\(1\)>/);
  assert.equal(flatten(h.doc.body).some(node => node.tagName === 'IMG'), false);
  assert.ok(!groups().some(group => group.children[0].textContent.includes('2026-11-05')), 'A fresh overall review must not refresh old entries');
  const category = h.get('team-notes-category'); category.value = 'experimental_evidence'; category.dispatch('change');
  assert.deepEqual(groups().map(group => group.children[0].textContent), ['Updated 2026-10-30']);
  category.value = 'all'; const search = h.get('team-notes-search'); search.value = 'New source checked'; search.dispatch('input');
  assert.deepEqual(groups().map(group => group.children[0].textContent), ['Updated 2026-11-01']);
  assert.deepEqual(groups().map(ids), [['#02']]);
});

test('the actual board module integrates with authenticated requests, badges, dialogs and logout cleanup', async () => {
  const boardModule = {exports: {}};
  vm.runInNewContext(fs.readFileSync(new URL('../app/dist/team-board.js', import.meta.url), 'utf8'), {module: boardModule, AbortController});
  const h = harness({...loginOptions, boardUI: boardModule.exports, fetch: url =>
    url.endsWith('/auth/exchange') ? response({...metadata(), session_token: TOKEN}) : url.endsWith('/api/session') ? response(metadata()) :
    url.endsWith('/api/memo') ? response(memo()) : url.includes('/api/board?') ? response({messages: [
      {id: 1, body: 'Synthetic integrated message', created_at: TIME - 1000, author: {name: 'Synthetic member', is_self: false}}
    ], latest_id: 1, has_more: false}) : response({}, 204)});
  await h.start();
  await waitFor(() => h.get('team-messages-unread').textContent === 'New' && h.doc.body.textContent.includes('Fixture result 31'),
    'the initial authenticated board snapshot and automatic Notes load');
  assert.equal(h.get('team-messages-unread').textContent, 'New');
  assert.doesNotMatch(h.doc.body.textContent, /Synthetic integrated message/, 'Closed board keeps message bodies out of the DOM');
  await h.controller.openMessages(); await flush();
  assert.equal(h.get('team-board-dialog').open, true);
  assert.match(h.doc.body.textContent, /Synthetic integrated message/);
  assert.equal(h.get('team-messages-unread').hidden, true);
  h.get('team-board-message').value = 'Synthetic unsent draft';
  await h.controller.logout(); await flush();
  assert.equal(h.get('team-board-dialog'), null);
  assert.doesNotMatch(h.doc.body.textContent, /Synthetic integrated message|Synthetic unsent draft/);
  assert.equal(h.get('team-messages').hidden, true);
  assert.equal((h.events.online || []).length, 0);
  assert.equal((h.events.storage || []).length, 0);
});

test('successful board authorization suppresses duplicate minute checks without extending expiry', async () => {
  const longSession = metadata({expires_at: TIME + 600000}), board = boardStub();
  const h = harness({...loginOptions, boardUI: board, fetch: url =>
    url.endsWith('/auth/exchange') ? response({...longSession, session_token: TOKEN}) : url.endsWith('/api/session') ? response(longSession) :
    url.endsWith('/api/memo') ? response(memo()) : response({messages: []})});
  await startBoardSession(h, board);
  const requestsBefore = h.requests.filter(row => row.url.endsWith('/api/session')).length;
  const adapter = board.instances[0].options;
  await adapter.request('/api/board?after=0&limit=50', 'GET');
  h.setTime(TIME + 60000); h.fire(60000); await flush();
  assert.equal(h.requests.filter(row => row.url.endsWith('/api/session')).length, requestsBefore);
  await adapter.request('/api/board?after=1&limit=50', 'GET');
  assert.ok([...h.timers.values()].some(timer => timer.ms === 540000), 'Expiry still uses the original absolute deadline');
  h.setTime(TIME + 600001); h.fire(540000); await flush();
  assert.equal(h.get('team-messages').hidden, true); assert.equal(board.instances[0].destroys, 1);
});

test('delayed native hashing is awaited and logout cannot activate a stale board afterward', async () => {
  for (const cancelLogin of [false, true]) {
    let releaseDigest, finishDigest, digestStarted = false;
    const gate = new Promise(resolve => {releaseDigest = resolve;});
    const finished = new Promise(resolve => {finishDigest = resolve;});
    const crypto = {subtle: {async digest(...args) {
      digestStarted = true; await gate;
      try { return await webcrypto.subtle.digest(...args); }
      finally { finishDigest(); }
    }}};
    const board = boardStub(), h = harness({...loginOptions, boardUI: board, crypto});
    await h.start(); await waitFor(() => digestStarted, 'board digest request');
    assert.equal(board.instances.length, 0, 'A pending digest must not create a board');
    if (cancelLogin) await h.controller.logout();
    releaseDigest(); await finished;
    if (cancelLogin) {
      await flush();
      assert.equal(board.instances.length, 0);
      assert.equal(h.get('team-messages').hidden, true);
      assert.doesNotMatch(h.doc.body.textContent, /Synthetic private board/);
    } else {
      await waitFor(() => board.instances[0]?.activates === 1 && h.doc.body.textContent.includes('Fixture result 31'),
        'board activation after the delayed native digest');
      assert.equal(h.get('team-messages').hidden, false);
      assert.equal(board.instances[0].options.storageKey, createHash('sha256').update('github:350433501').digest('hex'));
    }
  }
});
