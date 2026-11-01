import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createHandler, AuthState } from '../src/worker.mjs';
import { APP_ORIGIN, APP_RETURN, OWNER_ID, REPOSITORY_ID, base64url, encoder, hexHash, randomToken, sha256 } from '../src/security.mjs';

const BACKEND = 'https://auth.example.test';
const COMMIT = 'a'.repeat(40);
const PARTS = ['external-research-memo/part-01.json', 'external-research-memo/part-02.json', 'external-research-memo/part-03.json'];

class MemoryStorage {
  constructor() { this.values = new Map(); this.queue = Promise.resolve(); this.alarmAt = null; }
  async get(key) { return structuredClone(this.values.get(key)); }
  async put(key, value) { this.values.set(key, structuredClone(value)); }
  async delete(key) { return this.values.delete(key); }
  async deleteAll() { this.values.clear(); }
  async setAlarm(value) { this.alarmAt = value; }
  async deleteAlarm() { this.alarmAt = null; }
  transaction(callback) {
    const result = this.queue.then(async () => {
      const original = structuredClone(this.values);
      try { return await callback(this); } catch (error) { this.values = original; throw error; }
    });
    this.queue = result.catch(() => {}); return result;
  }
}
class MemoryNamespace {
  constructor() { this.objects = new Map(); }
  idFromName(value) { return value; }
  get(id) {
    if (!this.objects.has(id)) {
      const storage = new MemoryStorage();
      this.objects.set(id, { storage, object: new AuthState({ storage }) });
    }
    return this.objects.get(id).object;
  }
  snapshot() { return JSON.stringify([...this.objects].map(([id, value]) => ({ id, data: [...value.storage.values] }))); }
}

async function fixtureFiles(change = () => {}) {
  const files = new Map();
  const hashes = {};
  for (let i = 0; i < PARTS.length; i++) {
    // Entirely invented records: no actual research findings, citations or notes.
    const value = { schema_version: 1, entries: [{ id: 'fake-' + i, heading: 'Invented fixture heading', title: 'Invented test record', result: 'Synthetic test result', boundary: 'Not a scientific claim', doi: null,
      url: 'https://example.org/synthetic', primary_refs: [{ label: 'Invented fixture', url: 'https://example.org/synthetic', private_extra: 'DROP_THIS' }],
      progress_steps: [{ kind: 'test', label: 'Synthetic step', detail: 'Fixture only', status: 'not_reported', secret_extra: 'DROP_THIS' }],
      extra: [['Fixture reference', 'https://example.org/extra']], secret_extra: 'DROP_THIS' }] };
    const bytes = encoder.encode(JSON.stringify(value));
    files.set('data/' + PARTS[i], bytes); hashes[PARTS[i]] = await hexHash(bytes);
  }
  const manifest = { schema_version: 1, language: 'en', updated: '2026-01-01', reviewed_on: '2026-01-01', entry_count: 3,
    entry_parts: PARTS, translation: { part_sha256: hashes }, internal_extra: 'DROP_THIS' };
  change(manifest, files);
  files.set('data/external_research_memo.json', encoder.encode(JSON.stringify(manifest)));
  return files;
}

async function harness(options = {}) {
  let clock = 1800000000000, count = 0;
  const namespace = new MemoryNamespace();
  const env = { AUTH_STATE: namespace, GITHUB_CLIENT_ID: 'fake-client-id', GITHUB_CLIENT_SECRET: 'FAKE_SECRET_ONLY_FOR_SYNTHETIC_TESTS',
    SESSION_KEY: base64url(new Uint8Array(32).fill(7)), ...options.env };
  const files = await fixtureFiles(options.changeManifest);
  const grants = new Map(), tokens = new Map(), calls = [];
  const controls = { revoked: false, substituted: false, outage: false, lifetime: options.lifetime ?? 28800, ...options.controls };
  function redirectResponse(status) {
    return new Response(new ReadableStream({ cancel() { controls.redirectCancelled = (controls.redirectCancelled || 0) + 1; } }),
      { status, headers: { Location: 'https://attacker.example/DO_NOT_FORWARD' } });
  }
  const getObject = namespace.get.bind(namespace);
  namespace.get = id => {
    const object = getObject(id);
    return { fetch(request) {
      if (controls.storageFailKind && id.startsWith(controls.storageFailKind + ':') && new URL(request.url).pathname === '/' + controls.storageFailOperation) throw new Error('DO_NOT_REFLECT_STORAGE_DETAIL');
      return object.fetch(request);
    } };
  };
  async function upstream(url, init = {}) {
    calls.push(url);
    assert.ok(url.startsWith('https://api.github.com/') || url === 'https://github.com/login/oauth/access_token');
    // Model the Workers runtime, which rejects redirect:'error' before any I/O.
    if (init.redirect === 'error') throw new TypeError('Synthetic Workers unsupported redirect mode');
    assert.equal(init.redirect, 'manual');
    if (url === 'https://github.com/login/oauth/access_token') {
      assert.equal(new Headers(init.headers).get('User-Agent'), 'supercon-team-auth');
      const body = new URLSearchParams(init.body);
      const grant = grants.get(body.get('code'));
      assert.ok(grant, 'Fake provider only exchanges the issued code');
      assert.equal(body.get('client_id'), env.GITHUB_CLIENT_ID);
      assert.equal(body.get('client_secret'), env.GITHUB_CLIENT_SECRET);
      assert.equal(body.get('redirect_uri'), BACKEND + '/auth/github/callback');
      assert.equal(body.get('repository_id'), String(REPOSITORY_ID));
      assert.equal(await sha256(body.get('code_verifier')), grant.challenge, 'Provider PKCE must validate');
      grants.delete(body.get('code'));
      if (controls.tokenRedirect) return redirectResponse(controls.tokenRedirect);
      if (controls.tokenThrow) throw new Error('DO_NOT_REFLECT_TRANSPORT_DETAIL');
      if (controls.tokenMalformed) return new Response('DO_NOT_REFLECT_NON_JSON', { status: 502 });
      if (controls.tokenError) return Response.json({ error: controls.tokenError, error_description: 'DO_NOT_REFLECT_PROVIDER_DETAIL', error_uri: 'https://example.org/DO_NOT_REFLECT' }, { status: controls.tokenStatus || 200 });
      if (Object.hasOwn(controls, 'tokenGrant')) return Response.json(controls.tokenGrant, { status: controls.tokenStatus || 200 });
      return Response.json({ access_token: grant.token, token_type: 'bearer', expires_in: controls.lifetime, refresh_token: 'REFRESH_MUST_NEVER_PERSIST' });
    }
    const authorization = new Headers(init.headers).get('authorization');
    const role = tokens.get(authorization?.slice(7));
    assert.ok(role, 'Only a fake provider token may reach this fake GitHub API');
    if (controls.apiRedirect) return redirectResponse(controls.apiRedirect);
    if (controls.outage) return new Response('temporary', { status: 503 });
    if (url === 'https://api.github.com/user') {
      if (controls.revoked) return new Response('revoked', { status: 401 });
      const actualRole = controls.substituted ? (role === 'owner' ? 'other' : 'owner') : role;
      return Response.json({ id: actualRole === 'owner' ? OWNER_ID : 456, login: actualRole === 'owner' ? 'diracmagic' : 'example-user', private_fields: 'NEVER_RETURN' });
    }
    if (url === 'https://api.github.com/repositories/' + REPOSITORY_ID) {
      if (controls.repoDenied) return new Response('no access', { status: controls.repoDenied });
      return Response.json({ id: controls.wrongRepo ? 99 : REPOSITORY_ID,
        owner: { id: controls.wrongRepoOwner ? 999 : OWNER_ID }, private: !controls.publicRepo,
        permissions: controls.repoPullMissing ? {} : { pull: !controls.repoPullDenied }, full_name: 'diracmagic/supercon-research-notes' });
    }
    if (url === 'https://api.github.com/repos/diracmagic/supercon-research-notes/git/ref/heads/main') return Response.json({ ref: 'refs/heads/main', object: { type: controls.wrongRefType ? 'tag' : 'commit', sha: controls.wrongRefSha ? 'main' : COMMIT } });
    const prefix = 'https://api.github.com/repos/diracmagic/supercon-research-notes/contents/';
    assert.ok(url.startsWith(prefix));
    const parsed = new URL(url);
    const name = parsed.pathname.slice('/repos/diracmagic/supercon-research-notes/contents/'.length);
    const reference = parsed.searchParams.get('ref');
    assert.ok(reference === COMMIT || (reference === 'main' && name === 'data/external_research_memo.json'), 'Only the session readability probe may use main; memo data reads pin one commit');
    assert.ok(['data/external_research_memo.json', ...PARTS.map(value => 'data/' + value)].includes(name));
    if (name === 'data/external_research_memo.json' && controls.manifestDenied) return new Response('contents permission removed', { status: controls.manifestDenied });
    const bytes = files.get(name); assert.ok(bytes);
    const lead = encoder.encode('blob ' + bytes.length + '\0');
    const blob = new Uint8Array(lead.length + bytes.length); blob.set(lead); blob.set(bytes, lead.length);
    let encoded = btoa(String.fromCharCode(...bytes));
    if (controls.invalidBase64) encoded += '!';
    return Response.json({ type: controls.symlink ? 'symlink' : 'file', path: name, encoding: 'base64', content: encoded,
      size: controls.oversize ? 9999999 : bytes.length, sha: controls.wrongBlob ? '0'.repeat(40) : await hexHash(blob, 'SHA-1'),
      download_url: 'https://untrusted.example.test/DO_NOT_FETCH' });
  }
  const handler = createHandler({ fetchImpl: upstream, now: () => clock });
  const send = (route, { method = 'GET', body, token, origin = APP_ORIGIN, headers = {}, cookie: cookieHeader } = {}) => {
    const all = new Headers(headers);
    if (origin !== null) all.set('Origin', origin);
    if (token) all.set('Authorization', 'Bearer ' + token);
    if (body !== undefined) all.set('Content-Type', 'application/json');
    if (cookieHeader) all.set('Cookie', cookieHeader);
    return handler.fetch(new Request(BACKEND + route, { method, headers: all, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) }), env);
  };
  async function start(role = 'owner') {
    const verifier = randomToken(), state = randomToken();
    const response = await send('/auth/start?challenge=' + await sha256(verifier) + '&state=' + state, { origin: null });
    assert.equal(response.status, 303);
    const authorize = new URL(response.headers.get('location'));
    assert.equal(authorize.origin + authorize.pathname, 'https://github.com/login/oauth/authorize');
    assert.equal(authorize.searchParams.get('code_challenge_method'), 'S256');
    assert.equal(authorize.searchParams.has('scope'), false);
    const cookie = response.headers.get('set-cookie').split(';')[0];
    assert.match(response.headers.get('set-cookie'), /Path=\/; HttpOnly; Secure; SameSite=Lax; Max-Age=600/);
    const code = controls.providerCode ?? ('fake_code_' + ++count);
    const token = controls.providerToken ?? ('ghu_FAKE_' + role + '_' + count);
    grants.set(code, { challenge: authorize.searchParams.get('code_challenge'), token }); tokens.set(token, role);
    return { verifier, state, serverState: authorize.searchParams.get('state'), cookie, code, providerToken: token };
  }
  async function callback(flow, changes = {}) {
    const response = await send('/auth/github/callback?state=' + flow.serverState + '&code=' + encodeURIComponent(flow.code), { origin: null, cookie: flow.cookie, ...changes });
    const destination = new URL(response.headers.get('location'));
    assert.equal(destination.origin + destination.pathname, APP_RETURN);
    return { response, fields: new URLSearchParams(destination.hash.slice(1)), diagnostic: destination.searchParams.get('login_status') };
  }
  async function ticket(role) {
    const flow = await start(role); const result = await callback(flow);
    assert.equal(result.fields.get('team_state'), flow.state);
    assert.ok(result.fields.get('team_ticket'));
    assert.equal(new URL(result.response.headers.get('location')).search, '', 'Successful callbacks retain the canonical app URL without diagnostics');
    return { ...flow, ticket: result.fields.get('team_ticket') };
  }
  const exchange = flow => send('/auth/exchange', { method: 'POST', body: { ticket: flow.ticket, verifier: flow.verifier, state: flow.state } });
  async function login(role) {
    const flow = await ticket(role); const response = await exchange(flow); assert.equal(response.status, 200);
    return { ...flow, session: await response.json() };
  }
  return { env, namespace, controls, calls, files, send, start, callback, ticket, exchange, login, advance: milliseconds => { clock += milliseconds; }, now: () => clock };
}

test('owner receives a bounded real-provider identity session and validated memo fields only', async () => {
  const h = await harness(), flow = await h.login('owner');
  assert.equal(flow.session.user.id, OWNER_ID); assert.equal(flow.session.can_read_memo, true);
  assert.equal(flow.session.expires_at, h.now() + 3600000);
  assert.match(flow.session.session_token, /^[A-Za-z0-9_-]{43}$/);
  const session = await h.send('/api/session', { token: flow.session.session_token });
  assert.deepEqual(await session.json(), { expires_at: flow.session.expires_at, user: { id: OWNER_ID, login: 'diracmagic' }, can_read_memo: true, can_manage_team: true });
  const response = await h.send('/api/memo', { token: flow.session.session_token });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('Access-Control-Allow-Origin'), APP_ORIGIN);
  assert.match(response.headers.get('cache-control'), /private, no-store/);
  assert.equal(response.headers.has('Access-Control-Allow-Credentials'), false);
  const data = await response.json(); assert.equal(data.entry_count, 3);
  assert.equal(data.entries.every(entry => !Object.hasOwn(entry, 'doi')), true, 'A missing DOI must stay absent');
  assert.deepEqual(Object.keys(data).sort(), ['entries', 'entry_count', 'reviewed_on', 'updated']);
  assert.doesNotMatch(JSON.stringify(data), /DROP_THIS|NEVER_RETURN|ghu_|refresh_token|session_token/);
  assert.equal(h.calls.some(url => url.includes('DO_NOT_FETCH')), false);
});

test('ordinary GitHub identity can sign in but can never read owner notes or claim membership', async () => {
  const h = await harness(), { session } = await h.login('other');
  assert.equal(session.user.id, 456); assert.equal(session.can_read_memo, false);
  assert.equal(Object.hasOwn(session, 'role'), false);
  assert.equal((await h.send('/api/session', { token: session.session_token })).status, 200);
  const response = await h.send('/api/memo', { token: session.session_token });
  assert.equal(response.status, 403); assert.deepEqual(await response.json(), { error: 'owner_only' });
  assert.equal(h.calls.some(url => url.includes('/repositories/') || url.includes('/contents/')), false);
});

test('forged owner fields cannot override the verified provider identity', async () => {
  const h = await harness(), flow = await h.ticket('other');
  const forged = await h.send('/auth/exchange', { method: 'POST', body: { ticket: flow.ticket, verifier: flow.verifier, state: flow.state, user: { id: OWNER_ID } } });
  assert.equal(forged.status, 400);
  const response = await h.exchange(flow); assert.equal((await response.json()).can_read_memo, false);
  assert.equal((await h.send('/api/memo?user_id=' + OWNER_ID, { headers: { Authorization: 'Bearer ' + randomToken() } })).status, 400);
});

test('OAuth transaction requires its host cookie and state and cannot be replayed', async () => {
  const h = await harness(), flow = await h.start();
  const missing = await h.callback(flow, { cookie: null }); assert.equal(missing.fields.get('team_error'), 'oauth_state_invalid');
  assert.equal(missing.fields.has('team_state'), false);
  const wrong = await h.callback(flow, { cookie: '__Host-supercon_oauth=' + randomToken() }); assert.equal(wrong.fields.get('team_error'), 'oauth_state_invalid');
  const duplicate = await h.callback(flow, { cookie: flow.cookie + '; ' + flow.cookie }); assert.equal(duplicate.fields.get('team_error'), 'oauth_state_invalid');
  const good = await h.callback(flow); assert.ok(good.fields.get('team_ticket'));
  assert.match(good.response.headers.get('set-cookie'), /Max-Age=0/);
  const replay = await h.callback(flow); assert.equal(replay.fields.get('team_error'), 'oauth_state_invalid');
  assert.equal(h.calls.filter(url => url.endsWith('/access_token')).length, 1);
});

test('OAuth state substitution and expired transactions fail closed', async () => {
  const h = await harness(), flow = await h.start();
  const wrong = await h.callback({ ...flow, serverState: randomToken() }); assert.equal(wrong.fields.get('team_error'), 'oauth_state_invalid');
  h.advance(600001);
  const expired = await h.callback(flow); assert.equal(expired.fields.get('team_error'), 'oauth_state_invalid');
  assert.equal(h.calls.length, 0);
});

test('provider denial is a fixed error and consumes the verified transaction', async () => {
  const h = await harness(), flow = await h.start();
  const response = await h.send('/auth/github/callback?state=' + flow.serverState + '&error=access_denied&error_description=do-not-reflect', { origin: null, cookie: flow.cookie });
  const location = response.headers.get('location'); assert.match(location, /team_error=oauth_denied/); assert.doesNotMatch(location, /do-not-reflect/);
  assert.equal((await h.callback(flow)).fields.get('team_error'), 'oauth_state_invalid');
});

test('OAuth token errors expose only fixed diagnostic categories and consume the transaction', async () => {
  const cases = [
    [{ tokenError: 'incorrect_client_credentials' }, 'oauth_credentials_invalid'],
    [{ tokenError: 'incorrect_client_credentials', tokenStatus: 401 }, 'oauth_credentials_invalid'],
    [{ tokenError: 'redirect_uri_mismatch' }, 'oauth_redirect_invalid'],
    [{ tokenError: 'bad_verification_code' }, 'oauth_failed'],
    [{ tokenError: 'DO_NOT_REFLECT_UNKNOWN_ERROR' }, 'oauth_exchange_unavailable'],
    [{ tokenMalformed: true }, 'oauth_exchange_unavailable'],
    [{ tokenThrow: true }, 'oauth_exchange_unavailable'],
  ];
  for (const [controls, expected] of cases) {
    const h = await harness({ controls }), flow = await h.start(), result = await h.callback(flow);
    assert.equal(result.fields.get('team_error'), expected);
    assert.equal(result.fields.get('team_state'), flow.state);
    assert.equal(result.fields.has('team_ticket'), false);
    assert.doesNotMatch(result.response.headers.get('location'), /DO_NOT_REFLECT|ghu_|FAKE_SECRET/);
    assert.match(result.response.headers.get('cache-control'), /private, no-store/);
    assert.match(result.response.headers.get('set-cookie'), /Max-Age=0/);
    assert.equal(h.calls.some(url => url.endsWith('/user')), false);
    assert.equal((await h.callback(flow)).fields.get('team_error'), 'oauth_state_invalid');
  }
});

test('OAuth identity failures have a fixed category without issuing a ticket', async () => {
  for (const controls of [{ revoked: true }, { outage: true }]) {
    const h = await harness({ controls }), flow = await h.start(), result = await h.callback(flow);
    assert.equal(result.fields.get('team_error'), 'oauth_identity_unavailable');
    assert.equal(result.diagnostic, 'provider_identity');
    assert.equal(result.fields.has('team_ticket'), false);
    assert.equal(result.fields.get('team_state'), flow.state);
    assert.doesNotMatch(result.response.headers.get('location'), /ghu_|revoked|temporary/);
    assert.equal([...h.namespace.objects.keys()].some(name => name.startsWith('ticket:')), false);
  }
});

test('callback diagnostics distinguish fixed failure stages without echoing provider values', async () => {
  for (const [controls, expected] of [
    [{ tokenError: 'bad_verification_code' }, 'provider_bad_code'],
    [{ tokenError: 'incorrect_client_credentials' }, 'provider_credentials'],
    [{ tokenError: 'redirect_uri_mismatch' }, 'provider_redirect'],
    [{ tokenError: 'DO_NOT_REFLECT_UNKNOWN_ERROR' }, 'provider_grant_error_unknown'],
    [{ providerCode: '\r' }, 'code_invalid'],
    [{ storageFailKind: 'ticket', storageFailOperation: 'create' }, 'ticket_storage'],
  ]) {
    const h = await harness({ controls }), result = await h.callback(await h.start());
    assert.equal(result.diagnostic, expected);
    const target = new URL(result.response.headers.get('location'));
    assert.deepEqual([...target.searchParams.keys()], ['login_status']);
    assert.doesNotMatch(target.href, /DO_NOT_REFLECT|ghu_|FAKE_SECRET|fake_code/);
    assert.equal(result.fields.has('team_ticket'), false);
  }
  const h = await harness(), flow = await h.start();
  h.controls.storageFailKind = 'transaction'; h.controls.storageFailOperation = 'consume';
  const failure = await h.callback(flow);
  assert.equal(failure.diagnostic, 'transaction_storage');
  assert.equal(failure.fields.has('team_state'), false);
  const malformed = await h.send('/auth/github/callback?state=' + flow.serverState + '&code=' + flow.code + '&code=DO_NOT_REFLECT', { origin: null, cookie: flow.cookie });
  const target = new URL(malformed.headers.get('location'));
  assert.equal(target.searchParams.get('login_status'), 'callback_parameters');
  assert.doesNotMatch(target.href, /DO_NOT_REFLECT|fake_code/);
});

test('exchange diagnostics expose only fixed transport, JSON, HTTP, grant and token validation stages', async () => {
  const grant = { access_token: 'ghu_SYNTHETIC_ONLY', token_type: 'bearer', expires_in: 28800 };
  for (const [controls, expected] of [
    [{ tokenThrow: true }, 'provider_transport'],
    [{ tokenMalformed: true }, 'provider_response_json'],
    [{ tokenGrant: null }, 'provider_response_json'],
    [{ tokenGrant: grant, tokenStatus: 503 }, 'provider_http_503'],
    [{ tokenGrant: grant, tokenStatus: 418 }, 'provider_http_other'],
    [{ tokenError: 'unverified_user_email' }, 'provider_email_unverified'],
    [{ tokenError: 'DO_NOT_REFLECT_ARBITRARY_ERROR' }, 'provider_grant_error_unknown'],
    [{ tokenGrant: { ...grant, access_token: 'invalid token' } }, 'provider_token_format'],
    [{ tokenGrant: { ...grant, token_type: 'DO_NOT_REFLECT_TYPE' } }, 'provider_token_type'],
    [{ tokenGrant: { ...grant, expires_in: -1 } }, 'provider_expiry'],
  ]) {
    const h = await harness({ controls }), result = await h.callback(await h.start());
    assert.equal(result.diagnostic, expected);
    assert.equal(result.fields.get('team_error'), 'oauth_exchange_unavailable');
    assert.equal(result.fields.has('team_ticket'), false);
    assert.doesNotMatch(result.response.headers.get('location'), /DO_NOT_REFLECT|ghu_|SYNTHETIC_ONLY|invalid.token/);
    assert.equal(h.calls.some(url => url.endsWith('/user')), false);
  }
});

test('manual token redirects are cancelled without forwarding the code or client secret', { timeout: 5000 }, async () => {
  for (const tokenRedirect of [302, 307]) {
    const h = await harness({ controls: { tokenRedirect } }), result = await h.callback(await h.start());
    assert.equal(result.diagnostic, 'provider_http_' + tokenRedirect);
    assert.equal(result.fields.get('team_error'), 'oauth_exchange_unavailable');
    assert.equal(result.fields.has('team_ticket'), false);
    assert.equal(h.controls.redirectCancelled, 1);
    assert.deepEqual(h.calls, ['https://github.com/login/oauth/access_token']);
    assert.doesNotMatch(result.response.headers.get('location'), /attacker|DO_NOT_FORWARD|FAKE_SECRET|fake_code/);
  }
});

test('manual API redirects are cancelled without forwarding bearer identity or private reads', { timeout: 5000 }, async () => {
  for (const apiRedirect of [302, 307]) {
    const h = await harness(), { session } = await h.login();
    h.controls.apiRedirect = apiRedirect;
    const before = h.calls.length;
    const response = await h.send('/api/memo', { token: session.session_token });
    assert.equal(response.status, 503); assert.deepEqual(await response.json(), { error: 'upstream_unavailable' });
    assert.equal(h.controls.redirectCancelled, 1);
    assert.deepEqual(h.calls.slice(before), ['https://api.github.com/user']);
    assert.equal(h.calls.some(url => url.includes('attacker.example')), false);
  }
});

test('OAuth callback ignores unknown provider parameters without trusting caller redirects', async () => {
  const h = await harness(), flow = await h.start();
  const query = new URLSearchParams({ state: flow.serverState, code: flow.code,
    scope: 'DO_NOT_REFLECT_SCOPE', installation_id: '123', setup_action: 'install',
    redirect_uri: 'https://attacker.example/callback', return_to: 'https://attacker.example/return' });
  query.append('unknown', 'DO_NOT_REFLECT_ONE'); query.append('unknown', 'DO_NOT_REFLECT_TWO');
  const response = await h.send('/auth/github/callback?' + query, { origin: null, cookie: flow.cookie });
  const target = new URL(response.headers.get('location')), fields = new URLSearchParams(target.hash.slice(1));
  assert.equal(target.origin + target.pathname, APP_RETURN); assert.equal(target.search, '');
  assert.ok(fields.get('team_ticket')); assert.equal(fields.get('team_state'), flow.state);
  assert.doesNotMatch(target.href, /attacker|DO_NOT_REFLECT|installation_id|setup_action|redirect_uri|return_to/);
  const exchanged = await h.exchange({ ...flow, ticket: fields.get('team_ticket') });
  assert.equal(exchanged.status, 200);
});

test('OAuth callback still rejects duplicate known fields and missing state before exchange', async () => {
  for (const duplicate of ['state', 'code', 'error', 'error_description', 'error_uri', null]) {
    const h = await harness(), flow = await h.start();
    const query = new URLSearchParams({ state: flow.serverState, code: flow.code });
    if (duplicate === null) query.delete('state');
    else {
      if (!query.has(duplicate)) query.set(duplicate, 'DO_NOT_REFLECT_ONE');
      query.append(duplicate, 'DO_NOT_REFLECT_TWO');
    }
    const response = await h.send('/auth/github/callback?' + query, { origin: null, cookie: flow.cookie });
    const target = new URL(response.headers.get('location')), fields = new URLSearchParams(target.hash.slice(1));
    assert.equal(target.searchParams.get('login_status'), 'callback_parameters');
    assert.equal(fields.has('team_ticket'), false); assert.equal(fields.has('team_state'), false);
    assert.doesNotMatch(target.href, /DO_NOT_REFLECT/); assert.equal(h.calls.length, 0);
  }
});

test('opaque provider codes accept RFC 6749 punctuation and bounded lengths without altering PKCE', async () => {
  for (const providerCode of ['opaque.code+with/slash=and~tilde:%?&quoted\" space', 'x'.repeat(2048)]) {
    const h = await harness({ controls: { providerCode } }), flow = await h.login();
    assert.equal(flow.session.user.id, OWNER_ID);
    assert.match(flow.ticket, /^[A-Za-z0-9_-]{43}$/);
    assert.equal(h.calls.filter(url => url.endsWith('/access_token')).length, 1);
  }
});

test('opaque provider codes still reject controls, non-ASCII and oversized values before exchange', async () => {
  for (const providerCode of ['', 'code\r\nheader', 'code\0', 'code\x7f', 'code\u00e9', 'x'.repeat(2049)]) {
    const h = await harness({ controls: { providerCode } }), result = await h.callback(await h.start());
    assert.equal(result.fields.get('team_error'), 'oauth_failed');
    assert.equal(result.fields.has('team_ticket'), false);
    assert.equal(h.calls.length, 0);
  }
});

test('opaque provider bearer tokens accept RFC 6750 punctuation and trailing padding only server-side', async () => {
  const providerToken = 'ghu_SYNTHETIC.token-with~all+punctuation/==';
  const h = await harness({ controls: { providerToken } }), flow = await h.login();
  assert.equal(flow.session.user.id, OWNER_ID);
  assert.doesNotMatch(JSON.stringify(flow.session), /SYNTHETIC/);
  assert.doesNotMatch(h.namespace.snapshot(), /SYNTHETIC/);
  assert.equal((await h.send('/api/session', { token: flow.session.session_token })).status, 200);
});

test('opaque provider bearer tokens reject header injection, interior padding and oversized values', async () => {
  for (const providerToken of ['', 'token\r\nX-Injected: yes', 'token with space', 'token\x7f', 'token\u00e9', 'token=middle', 'x'.repeat(2049)]) {
    const h = await harness({ controls: { providerToken } }), result = await h.callback(await h.start());
    assert.equal(result.fields.get('team_error'), 'oauth_exchange_unavailable');
    assert.equal(result.fields.has('team_ticket'), false);
    assert.equal(h.calls.some(url => url.endsWith('/user')), false);
  }
});

test('ticket redemption binds both browser PKCE and client state', async () => {
  const h = await harness(), flow = await h.ticket();
  assert.equal((await h.exchange({ ...flow, verifier: randomToken() })).status, 400);
  assert.equal((await h.exchange({ ...flow, state: randomToken() })).status, 400);
  assert.equal((await h.exchange(flow)).status, 200);
  assert.equal((await h.exchange(flow)).status, 400);
});

test('parallel exchanges atomically consume one ticket only once', async () => {
  const h = await harness(), flow = await h.ticket();
  const results = await Promise.all(Array.from({ length: 8 }, () => h.exchange(flow)));
  assert.equal(results.filter(response => response.status === 200).length, 1);
  assert.equal(results.filter(response => response.status === 400).length, 7);
});

test('five-minute ticket expiry prevents later redemption', async () => {
  const h = await harness(), flow = await h.ticket(); h.advance(300001);
  assert.equal((await h.exchange(flow)).status, 400);
});

test('sessions expire no later than the shorter provider grant', async () => {
  const h = await harness({ lifetime: 30 }), flow = await h.login();
  assert.equal(flow.session.expires_at, h.now() + 30000);
  h.advance(30001);
  assert.equal((await h.send('/api/session', { token: flow.session.session_token })).status, 401);
});

test('sessions also enforce the one-hour application cap', async () => {
  const h = await harness(), flow = await h.login(); h.advance(3600001);
  assert.equal((await h.send('/api/memo', { token: flow.session.session_token })).status, 401);
});

test('GitHub token and refresh token never persist in plaintext or reach the browser', async () => {
  const h = await harness(), flow = await h.login();
  const snapshot = h.namespace.snapshot();
  assert.match(snapshot, /ciphertext/);
  assert.doesNotMatch(snapshot, /ghu_FAKE_|REFRESH_MUST_NEVER_PERSIST/);
  assert.doesNotMatch(JSON.stringify(flow.session), /ghu_FAKE_|REFRESH_MUST_NEVER_PERSIST/);
  assert.ok([...h.namespace.objects.values()].every(item => item.storage.alarmAt !== null));
});

test('revoked provider token invalidates and deletes the application session', async () => {
  const h = await harness(), { session } = await h.login(); h.controls.revoked = true;
  const response = await h.send('/api/session', { token: session.session_token });
  assert.equal(response.status, 401); assert.deepEqual(await response.json(), { error: 'session_revoked' });
  h.controls.revoked = false;
  assert.equal((await h.send('/api/session', { token: session.session_token })).status, 401);
});

test('provider identity substitution cannot reuse a session for another account', async () => {
  const h = await harness(), { session } = await h.login(); h.controls.substituted = true;
  assert.equal((await h.send('/api/memo', { token: session.session_token })).status, 401);
  h.controls.substituted = false;
  assert.equal((await h.send('/api/session', { token: session.session_token })).status, 401);
});

test('logout destroys only the bearer session and is replay-safe', async () => {
  const h = await harness(), first = (await h.login()).session, second = (await h.login()).session;
  assert.equal((await h.send('/auth/logout', { method: 'POST', token: first.session_token })).status, 200);
  assert.equal((await h.send('/api/session', { token: first.session_token })).status, 401);
  assert.equal((await h.send('/api/session', { token: second.session_token })).status, 200);
  assert.equal((await h.send('/auth/logout', { method: 'POST', token: first.session_token })).status, 200);
});

test('ciphertext tampering or session-key rotation fails closed', async () => {
  const h = await harness(), { session } = await h.login();
  const item = [...h.namespace.objects.entries()].find(([name]) => name.startsWith('session:'))[1];
  const record = await item.storage.get('record'); record.encrypted.ciphertext = randomToken(); await item.storage.put('record', record);
  assert.equal((await h.send('/api/session', { token: session.session_token })).status, 401);
  const h2 = await harness(), second = (await h2.login()).session;
  h2.env.SESSION_KEY = base64url(new Uint8Array(32).fill(9));
  assert.equal((await h2.send('/api/session', { token: second.session_token })).status, 401);
});

test('exact CORS rejects missing, suffix and unrelated origins without reflecting them', async () => {
  const h = await harness(), { session } = await h.login();
  for (const origin of [null, 'https://evil.example', APP_ORIGIN + '.evil.example', 'null']) {
    const response = await h.send('/api/session', { token: session.session_token, origin });
    assert.equal(response.status, 403); assert.equal(response.headers.has('Access-Control-Allow-Origin'), false);
  }
  const ok = await h.send('/api/session', { method: 'OPTIONS', headers: { 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'authorization' } });
  assert.equal(ok.status, 204); assert.equal(ok.headers.get('Access-Control-Allow-Origin'), APP_ORIGIN);
  assert.equal(ok.headers.has('Access-Control-Allow-Credentials'), false);
  const bad = await h.send('/api/session', { method: 'OPTIONS', headers: { 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'x-owner-id' } });
  assert.equal(bad.status, 403);
});

test('missing credentials or unsafe key fail closed without upstream traffic', async () => {
  for (const replacement of [{ GITHUB_CLIENT_ID: '' }, { GITHUB_CLIENT_SECRET: '' }, { SESSION_KEY: 'not-a-key' }, { AUTH_STATE: null }]) {
    const h = await harness({ env: replacement });
    const response = await h.send('/auth/start?challenge=' + randomToken() + '&state=' + randomToken());
    assert.equal(response.status, 503); assert.deepEqual(await response.json(), { error: 'not_configured' });
    assert.equal(h.calls.length, 0);
  }
});

test('caller-controlled redirects, paths, duplicate parameters and malformed exchanges are rejected', async () => {
  const h = await harness();
  for (const route of ['/auth/start?challenge=x&state=x', '/auth/start?challenge=' + randomToken() + '&state=' + randomToken() + '&return_to=https://evil.example',
    '/auth/start?challenge=' + randomToken() + '&challenge=' + randomToken() + '&state=' + randomToken()]) assert.equal((await h.send(route)).status, 400);
  assert.equal((await h.send('/internal/consume')).status, 404);
  assert.equal((await h.send('/api/session', { method: 'POST' })).status, 405);
  for (const body of [null, [], {}, { ticket: 'x', verifier: 'y', state: 'z' }]) assert.equal((await h.send('/auth/exchange', { method: 'POST', body })).status, 400);
  assert.equal(h.calls.length, 0);
});

for (const setting of ['wrongRepo', 'wrongRepoOwner', 'publicRepo']) test('memo verifies fixed private repository identity: ' + setting, async () => {
  const h = await harness({ controls: { [setting]: true } }), { session } = await h.login();
  assert.equal((await h.send('/api/memo', { token: session.session_token })).status, 403);
  assert.equal(h.calls.some(url => url.includes('/contents/')), false);
});

for (const setting of ['wrongBlob', 'invalidBase64', 'oversize', 'symlink']) test('memo rejects invalid content envelope: ' + setting, async () => {
  const h = await harness({ controls: { [setting]: true } }), { session } = await h.login();
  const response = await h.send('/api/memo', { token: session.session_token }); assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), { error: 'invalid_memo' });
});

for (const name of ['remote-path', 'traversal', 'hash', 'count']) test('manifest cannot expand paths or bypass integrity: ' + name, async () => {
  const h = await harness({ changeManifest(manifest) {
    if (name === 'remote-path') manifest.entry_parts = ['https://evil.example', ...PARTS.slice(1)];
    if (name === 'traversal') manifest.entry_parts = ['../README.md', ...PARTS.slice(1)];
    if (name === 'hash') manifest.translation.part_sha256[PARTS[0]] = '0'.repeat(64);
    if (name === 'count') manifest.entry_count = 4;
  } });
  const { session } = await h.login();
  assert.equal((await h.send('/api/memo', { token: session.session_token })).status, 502);
  assert.equal(h.calls.some(url => url.includes('evil.example') || url.includes('/README.md')), false);
});

test('upstream failure does not fall back to cached private records', async () => {
  const h = await harness(), { session } = await h.login();
  assert.equal((await h.send('/api/memo', { token: session.session_token })).status, 200);
  h.controls.outage = true;
  const response = await h.send('/api/memo', { token: session.session_token });
  assert.equal(response.status, 503); assert.deepEqual(await response.json(), { error: 'upstream_unavailable' });
});

test('expiry alarms remove ciphertext, transaction records and alarm metadata', async () => {
  const h = await harness(); await h.login(); h.advance(3600001);
  for (const item of h.namespace.objects.values()) await item.object.alarm();
  assert.ok([...h.namespace.objects.values()].every(item => item.storage.values.size === 0 && item.storage.alarmAt === null));
});

test('deployment declares SQLite state, excludes local secrets and disables application logging', () => {
  const config = JSON.parse(fs.readFileSync(new URL('../wrangler.jsonc', import.meta.url), 'utf8'));
  assert.deepEqual(config.migrations, [{ tag: 'v1', new_sqlite_classes: ['AuthState'] }, { tag: 'v2', new_sqlite_classes: ['TeamDirectory'] }]);
  assert.equal(config.observability.enabled, false);
  assert.deepEqual(Object.keys(config.vars || {}).sort(), ['FIREBASE_API_KEY', 'FIREBASE_PROJECT_ID']);
  const ignore = fs.readFileSync(new URL('../.gitignore', import.meta.url), 'utf8');
  assert.match(ignore, /\.dev\.vars/); assert.match(ignore, /\.env/);
  for (const file of ['worker.mjs', 'state.mjs', 'memo.mjs', 'security.mjs']) {
    const code = fs.readFileSync(new URL('../src/' + file, import.meta.url), 'utf8');
    assert.doesNotMatch(code, /console\.|caches\.|localStorage|sessionStorage/);
  }
});

test('health reports configuration readiness without any credential, identity or upstream access', async () => {
  const h = await harness();
  const response = await h.send('/health', { origin: null });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: 'ready', configured: true, github_login: true, email_login: false, team_notes: false });
  assert.equal(h.calls.length, 0);
  assert.equal((await h.send('/health?secret=echo', { origin: null })).status, 400);
  h.env.GITHUB_CLIENT_SECRET = '';
  const missing = await h.send('/health', { origin: null }); assert.equal(missing.status, 503);
  assert.deepEqual(await missing.json(), { status: 'not_configured', configured: false, github_login: false, email_login: false, team_notes: false });
});

test('ciphertext cannot be transplanted between two independent bearer sessions', async () => {
  const h = await harness(), first = (await h.login()).session, second = (await h.login()).session;
  const items = [...h.namespace.objects.entries()].filter(([name]) => name.startsWith('session:')).map(([, item]) => item);
  const a = await items[0].storage.get('record'), b = await items[1].storage.get('record');
  b.encrypted = a.encrypted; await items[1].storage.put('record', b);
  assert.equal((await h.send('/api/session', { token: second.session_token })).status, 401);
  assert.equal((await h.send('/api/session', { token: first.session_token })).status, 200);
});

test('array coercion cannot satisfy the browser proof string contract', async () => {
  const h = await harness(), flow = await h.ticket();
  const response = await h.send('/auth/exchange', { method: 'POST', body: { ticket: [flow.ticket], verifier: [flow.verifier], state: [flow.state] } });
  assert.equal(response.status, 400); assert.equal((await h.exchange(flow)).status, 200);
});

test('memo resolves a small commit ref and rejects malformed object type or SHA before reading files', async () => {
  for (const setting of ['wrongRefType', 'wrongRefSha']) {
    const h = await harness({ controls: { [setting]: true } }), { session } = await h.login();
    const response = await h.send('/api/memo', { token: session.session_token });
    assert.equal(response.status, 502); assert.deepEqual(await response.json(), { error: 'invalid_memo' });
    assert.equal(h.calls.some(url => url.includes('/contents/') || url.includes('/commits/')), false);
    assert.equal(h.calls.some(url => url.endsWith('/git/ref/heads/main')), true);
  }
});

test('owner session polling rechecks fixed repository access when GitHub identity remains valid', async () => {
  for (const denied of [403, 404]) {
    const h = await harness(), { session } = await h.login();
    assert.equal((await h.send('/api/session', { token: session.session_token })).status, 200);
    const contentsBefore = h.calls.filter(url => url.includes('/contents/')).length;
    h.controls.repoDenied = denied;
    for (const route of ['/api/session', '/api/memo']) {
      const response = await h.send(route, { token: session.session_token });
      assert.equal(response.status, 403);
      const result = await response.json(); assert.deepEqual(result, { error: 'memo_access_revoked' });
      assert.equal(Object.hasOwn(result, 'can_read_memo'), false);
    }
    assert.equal(h.calls.filter(url => url.includes('/contents/')).length, contentsBefore);
  }
});

test('owner session polling requires a positive pull permission, but non-owner login does not access notes repository', async () => {
  const h = await harness(), { session } = await h.login(); h.controls.repoPullDenied = true;
  assert.equal((await h.send('/api/session', { token: session.session_token })).status, 403);
  assert.equal((await h.send('/api/memo', { token: session.session_token })).status, 403);
  const other = await harness({ controls: { repoDenied: 404 } }), otherSession = (await other.login('other')).session;
  const response = await other.send('/api/session', { token: otherSession.session_token });
  assert.equal(response.status, 200); assert.equal((await response.json()).can_read_memo, false);
  assert.equal(other.calls.some(url => url.includes('/repositories/')), false);
});

test('ordinary user tokens cannot use the trusted installation exception for absent pull metadata', async () => {
  const h = await harness({ controls: { repoPullMissing: true } }), { session } = await h.login();
  for (const path of ['/api/session', '/api/memo']) assert.equal((await h.send(path, { token: session.session_token })).status, 403);
  assert.equal(h.calls.some(url => url.includes('/contents/')), false);
});

test('owner polling denies stale note access when metadata remains available but Contents permission is revoked', async () => {
  for (const status of [403, 404]) {
    const h = await harness(), { session } = await h.login();
    assert.equal((await h.send('/api/session', { token: session.session_token })).status, 200);
    h.controls.manifestDenied = status;
    for (const route of ['/api/session', '/api/memo']) {
      const response = await h.send(route, { token: session.session_token });
      assert.equal(response.status, 403); assert.deepEqual(await response.json(), { error: 'memo_access_revoked' });
    }
    assert.equal(h.calls.some(url => url.includes('/part-')), false, 'A session access check reads no memo parts');
  }
});
