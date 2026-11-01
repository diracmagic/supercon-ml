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

function harness({ apiBase = 'https://auth.example.org', hash = '', pending = null, initialStorage = {}, fetch: customFetch, session = metadata(), accountUI } = {}) {
  const doc = { events: {}, hidden: false, activeElement: null, readyState: 'complete',
    createElement(tag) { return new Element(tag, doc); },
    getElementById(id) { return flatten(doc.body).find((node) => node.attributes.id === id) || null; },
    addEventListener(kind, fn) { (doc.events[kind] ||= []).push(fn); },
    dispatch(kind) { (doc.events[kind] || []).forEach((fn) => fn()); } };
  doc.body = doc.createElement('body');
  const header = doc.body.appendChild(doc.createElement('div'));
  const login = header.appendChild(doc.createElement('button')); login.setAttribute('id', 'team-login');
  const values = new Map(Object.entries(initialStorage));
  if (pending) values.set(auth.PENDING_KEY, JSON.stringify(pending));
  const writes = [], requests = [], redirects = [], history = [], events = {}, timers = new Map();
  let tick = TIME, nextTimer = 1;
  const win = { location: { hash, pathname: '/supercon-ml/', search: '?test=1', assign: (url) => redirects.push(url) },
    history: { replaceState(_state, _title, path) { history.push(path); win.location.hash = ''; } },
    sessionStorage: { getItem: (key) => values.get(key) ?? null, setItem(key, value) { values.set(key, value); writes.push([key, value]); }, removeItem: (key) => values.delete(key) },
    addEventListener(kind, fn) { (events[kind] ||= []).push(fn); },
    btoa: (value) => Buffer.from(value, 'binary').toString('base64') };
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
  const controller = auth.createController({ window: win, document: doc, config: { apiBase }, crypto: webcrypto, fetch, accountUI,
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
  assert.equal(h.get('team-notes').hidden, false); assert.equal(h.get('team-manage').hidden, true);
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
  assert.equal(h.requests.at(-1).options.headers.Authorization, 'Bearer ' + TOKEN);
  await assert.rejects(adapter.teamRequest('/api/team/delete', 'POST', {}));
  await assert.rejects(adapter.teamRequest('/api/team', 'POST', {}));
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
