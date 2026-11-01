import test from 'node:test';
import assert from 'node:assert/strict';
import { createHandler, AuthState, TeamDirectory } from '../src/worker.mjs';
import { createFirebaseClient } from '../src/firebase.mjs';
import { teamAccess } from '../src/team.mjs';
import { stateAccess } from '../src/state.mjs';
import { APP_ORIGIN, APP_RETURN, OWNER_ID, REPOSITORY_ID, base64url, encoder, encryptionKey, encryptToken, hexHash, randomToken, sha256 } from '../src/security.mjs';
import { APP_ID, INSTALLATION_ID } from '../src/installation.mjs';

const BACKEND = 'https://auth.example.test', PROJECT = 'synthetic-team', API_KEY = 'SYNTHETIC_PUBLIC_API_KEY_ONLY';
const UID = 'synthetic_member', EMAIL = 'member@example.test', COMMIT = 'b'.repeat(40);
const pair = await crypto.subtle.generateKey({ name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, true, ['sign', 'verify']);
const pem = '-----BEGIN PRIVATE KEY-----\n' + btoa(String.fromCharCode(...new Uint8Array(await crypto.subtle.exportKey('pkcs8', pair.privateKey)))) + '\n-----END PRIVATE KEY-----';
class Storage {
  constructor() { this.data = new Map(); this.queue = Promise.resolve(); }
  async get(key) { return structuredClone(this.data.get(key)); }
  async put(key, value) { this.data.set(key, structuredClone(value)); }
  async delete(key) { return this.data.delete(key); }
  async deleteAll() { this.data.clear(); }
  async setAlarm() {}
  async deleteAlarm() {}
  transaction(callback) {
    const answer = this.queue.then(async () => { const old = structuredClone(this.data); try { return await callback(this); } catch (error) { this.data = old; throw error; } });
    this.queue = answer.catch(() => {}); return answer;
  }
}
class Namespace {
  constructor(Type) { this.Type = Type; this.objects = new Map(); }
  idFromName(name) { return name; }
  get(name) { if (!this.objects.has(name)) this.objects.set(name, new this.Type({ storage: new Storage() })); return this.objects.get(name); }
}
async function syntheticFiles() {
  const files = new Map(), hashes = {}, parts = [1, 2, 3].map(n => 'external-research-memo/part-0' + n + '.json');
  for (const [i, part] of parts.entries()) {
    const bytes = encoder.encode(JSON.stringify({ entries: [{ id: 'fixture-' + i, heading: 'Synthetic fixture', title: 'Synthetic fixture', result: 'Synthetic test result', boundary: 'No research claim', primary_refs: [{ label: 'Fixture', url: 'https://example.org/' }], progress_steps: [] }], schema_version: 1 }));
    files.set('data/' + part, bytes); hashes[part] = await hexHash(bytes);
  }
  files.set('data/external_research_memo.json', encoder.encode(JSON.stringify({ schema_version: 1, language: 'en', entry_count: 3, entry_parts: parts, translation: { part_sha256: hashes }, updated: '2026-01-01', reviewed_on: '2026-01-01' })));
  return files;
}
async function fixture(options = {}) {
  let clock = 1800000000000;
  const env = { AUTH_STATE: new Namespace(AuthState), TEAM_DIRECTORY: new Namespace(TeamDirectory), SESSION_KEY: base64url(new Uint8Array(32).fill(6)),
    GITHUB_CLIENT_ID: 'synthetic-client', GITHUB_CLIENT_SECRET: 'SYNTHETIC_CLIENT_SECRET_NOT_REAL', GITHUB_APP_PRIVATE_KEY: pem,
    FIREBASE_PROJECT_ID: PROJECT, FIREBASE_API_KEY: API_KEY, ...options.env };
  const controls = { emailVerified: true, validSince: String(Math.floor(clock / 1000) - 100), passwordUpdatedAt: clock - 100000, ...options.controls };
  const calls = [], validTokens = new Map(), files = await syntheticFiles();
  function idToken(change = {}) {
    const claims = { aud: PROJECT, iss: 'https://securetoken.google.com/' + PROJECT, sub: UID, email: EMAIL, email_verified: true,
      iat: Math.floor(clock / 1000), auth_time: Math.floor(clock / 1000), exp: Math.floor(clock / 1000) + 3600, firebase: { sign_in_provider: 'password' }, ...change };
    const token = base64url(encoder.encode(JSON.stringify({ alg: 'RS256' }))) + '.' + base64url(encoder.encode(JSON.stringify(claims))) + '.' + randomToken();
    validTokens.set(token, claims); return token;
  }
  const repository = { id: REPOSITORY_ID, private: true, owner: { id: OWNER_ID }, full_name: 'diracmagic/supercon-research-notes', permissions: { pull: true } };
  if (controls.missingPull) delete repository.permissions;
  if (controls.deniedPull) repository.permissions = { pull: false };
  async function fetchImpl(url, init) {
    assert.equal(init.redirect, 'manual'); calls.push({ url, body: init.body });
    if (url.startsWith('https://identitytoolkit.googleapis.com/v1/accounts:')) {
      assert.equal(new URL(url).searchParams.get('key'), API_KEY);
      assert.equal(new Headers(init.headers).has('Authorization'), false);
      const method = new URL(url).pathname.split(':')[1], body = JSON.parse(init.body);
      if (controls.providerRedirect) return new Response('Do not follow', { status: 307, headers: { Location: 'https://attacker.example' } });
      if (method === 'signUp') {
        if (controls.pauseSignup) await controls.pauseSignup();
        assert.match(body.password, /^.{80,}$/); assert.equal(body.returnSecureToken, false);
        if (controls.existing) return Response.json({ error: { message: 'EMAIL_EXISTS' } }, { status: 400 });
        return Response.json({ localId: UID, email: body.email, idToken: 'DISCARD_ID_TOKEN', refreshToken: 'DISCARD_REFRESH_TOKEN' });
      }
      if (method === 'sendOobCode') {
        assert.equal(body.requestType, 'PASSWORD_RESET'); assert.equal(body.continueUrl, APP_RETURN);
        assert.equal(Object.hasOwn(body, 'returnOobLink'), false);
        if (controls.emailFailure) return Response.json({ error: { message: 'DO_NOT_REFLECT_EMAIL_DETAIL' } }, { status: 429 });
        return Response.json({ email: body.email });
      }
      assert.equal(method, 'lookup');
      const claims = validTokens.get(body.idToken);
      if (!claims || controls.invalidSignature) return Response.json({ error: { message: 'INVALID_ID_TOKEN' } }, { status: 400 });
      const current = { localId: controls.substitutedUid || claims.sub, email: controls.changedEmail || claims.email, emailVerified: controls.emailVerified,
        disabled: controls.disabled || false, validSince: controls.validSince, passwordUpdatedAt: controls.passwordUpdatedAt };
      if (controls.omitRevocation) delete current.validSince;
      return Response.json({ users: [current] });
    }
    assert.ok(url.startsWith('https://api.github.com/'), 'Only fixed provider hosts may be requested');
    const token = new Headers(init.headers).get('Authorization');
    if (url.endsWith('/user')) return Response.json({ id: token === 'Bearer synthetic_owner' ? OWNER_ID : 456, login: token === 'Bearer synthetic_owner' ? 'diracmagic' : 'other' });
    if (url === 'https://api.github.com/app/installations/' + INSTALLATION_ID) return Response.json({ id: INSTALLATION_ID, app_id: APP_ID, account: { id: OWNER_ID }, suspended_at: null, repository_selection: 'selected', permissions: { contents: 'read', metadata: 'read' } });
    if (url.endsWith('/access_tokens')) {
      assert.deepEqual(JSON.parse(init.body), { repository_ids: [REPOSITORY_ID], permissions: { contents: 'read', metadata: 'read' } });
      return Response.json({ token: 'ghs_SYNTHETIC_INSTALLATION', expires_at: new Date(clock + 3600000).toISOString(), permissions: { contents: 'read', metadata: 'read' }, repositories: [repository] });
    }
    assert.equal(token, 'Bearer ghs_SYNTHETIC_INSTALLATION');
    if (url.endsWith('/repositories/' + REPOSITORY_ID)) return Response.json(repository);
    if (url.endsWith('/git/ref/heads/main')) return Response.json({ object: { type: 'commit', sha: COMMIT } });
    const parsed = new URL(url), prefix = '/repos/diracmagic/supercon-research-notes/contents/';
    assert.ok(parsed.pathname.startsWith(prefix));
    const name = parsed.pathname.slice(prefix.length), bytes = files.get(name); assert.ok(bytes);
    const lead = encoder.encode('blob ' + bytes.length + '\0'), blob = new Uint8Array(lead.length + bytes.length); blob.set(lead); blob.set(bytes, lead.length);
    if (controls.revokeDuringRead) { const record = controls.revokeDuringRead; controls.revokeDuringRead = null; await teamAccess(env, 'revoke', clock, { memberId: record }); }
    return Response.json({ type: 'file', path: name, encoding: 'base64', content: btoa(String.fromCharCode(...bytes)), size: bytes.length, sha: await hexHash(blob, 'SHA-1') });
  }
  const handler = createHandler({ fetchImpl, now: () => clock });
  const send = (path, { method = 'GET', token, body, origin = APP_ORIGIN, ip = '192.0.2.1' } = {}) => handler.fetch(new Request(BACKEND + path, {
    method, headers: { ...(origin ? { Origin: origin } : {}), 'CF-Connecting-IP': ip, ...(token ? { Authorization: 'Bearer ' + token } : {}), ...(body ? { 'Content-Type': 'application/json' } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}),
  }), env);
  async function githubSession(owner = true) {
    const token = randomToken(), key = await encryptionKey(env), record = { kind: 'session', expiresAt: clock + 3600000, user: { id: owner ? OWNER_ID : 456, login: owner ? 'diracmagic' : 'other' },
      encrypted: await encryptToken(owner ? 'synthetic_owner' : 'synthetic_other', key, 'session:' + await sha256(token)) };
    await stateAccess(env, 'session', token, 'create', clock, { record }); return token;
  }
  async function invite() {
    const owner = await githubSession(), response = await send('/api/team/invite', { method: 'POST', token: owner, body: { email: EMAIL } });
    assert.equal(response.status, 200); return { owner, member: (await response.json()).member };
  }
  const login = token => send('/auth/firebase', { method: 'POST', body: { id_token: token || idToken() } });
  return { env, controls, calls, idToken, send, githubSession, invite, login, now: () => clock, advance: ms => { clock += ms; }, firebase: createFirebaseClient({ fetchImpl, now: () => clock }) };
}

test('invited verified email member reads notes via installation without GitHub membership or admin rights', async () => {
  const h = await fixture(), { member } = await h.invite();
  assert.equal(member.status, 'invited'); assert.equal(member.delivery_status, 'accepted');
  const response = await h.login(); assert.equal(response.status, 200); const session = await response.json();
  assert.equal(session.user.id, 'firebase:' + UID); assert.equal(session.can_read_memo, true); assert.equal(session.can_manage_team, false);
  const notes = await h.send('/api/memo', { token: session.session_token }); assert.equal(notes.status, 200); assert.equal((await notes.json()).entry_count, 3);
  assert.equal((await h.send('/api/session', { token: session.session_token })).status, 200);
  assert.equal((await h.send('/api/team', { token: session.session_token })).status, 403);
  const persisted = JSON.stringify([...h.env.AUTH_STATE.objects.values()].map(item => [...item.storage.data]));
  assert.doesNotMatch(persisted, /DISCARD_|ghs_SYNTHETIC|synthetic_owner/);
  assert.ok(!h.calls.some(call => call.url.includes('/user') && call.body?.includes('idToken')));
});

test('uninvited, unverified, forged, wrong-project and substituted identities cannot obtain a member session', async () => {
  const h = await fixture(); assert.equal((await h.login()).status, 403); await h.invite();
  for (const change of [{ email_verified: false }, { aud: 'different-project' }, { iss: 'https://evil.example' }, { exp: 1 }, { firebase: { sign_in_provider: 'anonymous' } }]) assert.equal((await h.login(h.idToken(change))).status, 401);
  h.controls.invalidSignature = true; assert.equal((await h.login()).status, 401); h.controls.invalidSignature = false;
  h.controls.emailVerified = false; assert.equal((await h.login()).status, 401); h.controls.emailVerified = true;
  h.controls.substitutedUid = 'other_uid'; assert.equal((await h.login()).status, 401);
});

test('ordinary GitHub identities cannot invite, revoke or enumerate the team', async () => {
  const h = await fixture(), other = await h.githubSession(false);
  for (const [path, body] of [['/api/team', undefined], ['/api/team/invite', { email: EMAIL }], ['/api/team/revoke', { member_id: randomToken() }]]) {
    assert.equal((await h.send(path, { method: body ? 'POST' : 'GET', token: other, body })).status, 403);
  }
  assert.equal(h.calls.some(call => call.url.includes('googleapis.com')), false);
});

test('failed email requests remain visibly failed and do not activate a membership', async () => {
  const h = await fixture({ controls: { emailFailure: true } }), owner = await h.githubSession();
  const response = await h.send('/api/team/invite', { method: 'POST', token: owner, body: { email: EMAIL } });
  assert.equal(response.status, 503); assert.deepEqual(await response.json(), { error: 'invitation_delivery_failed' });
  const members = (await (await h.send('/api/team', { token: owner })).json()).members;
  assert.equal(members[0].delivery_status, 'failed'); assert.equal(members[0].status, 'invited');
  assert.equal((await h.login()).status, 403);
});

test('existing Firebase accounts require a fresh verified login and are atomically bound once', async () => {
  const h = await fixture({ controls: { existing: true } }); const stale = h.idToken(); h.advance(2000); await h.invite();
  assert.equal((await h.login(stale)).status, 403);
  const responses = await Promise.all([h.login(), h.login(h.idToken({ sub: 'other_uid' }))]);
  assert.deepEqual(responses.map(response => response.status).sort(), [200, 403]);
});

test('member revocation and reinvitation invalidate old sessions by version', async () => {
  const h = await fixture(), { owner, member } = await h.invite(), session = await (await h.login()).json();
  const revoked = await h.send('/api/team/revoke', { method: 'POST', token: owner, body: { member_id: member.member_id } }); assert.equal(revoked.status, 200);
  assert.equal((await h.send('/api/memo', { token: session.session_token })).status, 403);
  assert.equal((await h.send('/api/session', { token: session.session_token })).status, 401);
  h.advance(61000); await h.invite();
  assert.equal((await h.send('/api/memo', { token: session.session_token })).status, 401);
});

test('an invite paused at Firebase cannot overwrite a later administrator revocation', async () => {
  const h = await fixture(), { owner, member } = await h.invite(); h.advance(61000);
  let release, reached;
  const paused = new Promise(resolve => { reached = resolve; });
  h.controls.pauseSignup = () => { reached(); return new Promise(resolve => { release = resolve; }); };
  const staleInvite = h.send('/api/team/invite', { method: 'POST', token: owner, body: { email: EMAIL } });
  await paused;
  assert.equal((await h.send('/api/team/revoke', { method: 'POST', token: owner, body: { member_id: member.member_id } })).status, 200);
  release();
  const response = await staleInvite; assert.equal(response.status, 409);
  assert.deepEqual(await response.json(), { error: 'membership_changed' });
  const record = (await (await h.send('/api/team', { token: owner })).json()).members[0];
  assert.equal(record.status, 'revoked'); assert.equal(record.version, member.version + 1);
  assert.equal(h.calls.filter(call => call.url.includes(':sendOobCode')).length, 1, 'No email is sent by the stale request');
});

test('password changes, provider revocation, disabled accounts and absent revocation data fail closed', async () => {
  for (const alteration of ['password', 'validSince', 'disabled', 'missing']) {
    const h = await fixture(); await h.invite(); const session = await (await h.login()).json();
    if (alteration === 'password') h.controls.passwordUpdatedAt += 1;
    if (alteration === 'validSince') h.controls.validSince = String(Math.floor(h.now() / 1000) + 1);
    if (alteration === 'disabled') h.controls.disabled = true;
    if (alteration === 'missing') h.controls.omitRevocation = true;
    assert.equal((await h.send('/api/session', { token: session.session_token })).status, 401);
    assert.equal((await h.send('/api/memo', { token: session.session_token })).status, 401);
  }
});

test('revocation during a private read prevents returning the loaded notes', async () => {
  const h = await fixture(), { member } = await h.invite(), session = await (await h.login()).json();
  h.controls.revokeDuringRead = member.member_id;
  const response = await h.send('/api/memo', { token: session.session_token });
  assert.equal(response.status, 403); assert.deepEqual(await response.json(), { error: 'membership_revoked' });
});

test('persistent limits reject repeated login and invitation attempts without extra provider calls', async () => {
  const h = await fixture(), { owner } = await h.invite();
  const repeated = await h.send('/api/team/invite', { method: 'POST', token: owner, body: { email: EMAIL } }); assert.equal(repeated.status, 429);
  for (let i = 0; i < 30; i++) await h.send('/auth/firebase', { method: 'POST', body: { id_token: 'bad' } });
  const before = h.calls.length;
  assert.equal((await h.login()).status, 429); assert.equal(h.calls.length, before);
});

test('private member and global read limits apply before any provider or installation request', async () => {
  const h = await fixture(); await h.invite(); const session = await (await h.login()).json();
  for (let i = 0; i < 12; i++) assert.equal((await h.send('/api/session', { token: session.session_token })).status, 200);
  const before = h.calls.length;
  const limited = await h.send('/api/memo', { token: session.session_token }); assert.equal(limited.status, 429);
  assert.deepEqual(await limited.json(), { error: 'rate_limited' }); assert.equal(h.calls.length, before);
  for (const [key, maximum, window] of [['private-global-minute', 120, 60000], ['private-global-hour', 600, 3600000]]) {
    const other = await fixture(); await other.invite(); const active = await (await other.login()).json();
    for (let i = 0; i < maximum; i++) await teamAccess(other.env, 'limit', other.now(), { key, maximum, window });
    const count = other.calls.length;
    assert.equal((await other.send('/api/session', { token: active.session_token })).status, 429);
    assert.equal(other.calls.length, count);
  }
});

test('trusted installation reads accept omitted user pull metadata but never an explicit denial', async () => {
  for (const deniedPull of [false, true]) {
    const h = await fixture({ controls: { missingPull: !deniedPull, deniedPull } }); await h.invite();
    const session = await (await h.login()).json();
    assert.equal((await h.send('/api/session', { token: session.session_token })).status, deniedPull ? 403 : 200);
    assert.equal((await h.send('/api/memo', { token: session.session_token })).status, deniedPull ? 403 : 200);
  }
});

test('directory enforces a 100-member cap, invite expiry and bounded metadata', async () => {
  const h = await fixture();
  for (let i = 0; i < 100; i++) await teamAccess(h.env, 'invite', h.now(), { email: 'member' + i + '@example.test', uid: null, expectedMemberId: null, expectedVersion: null });
  await assert.rejects(teamAccess(h.env, 'invite', h.now(), { email: 'overflow@example.test', uid: null, expectedMemberId: null, expectedVersion: null }), error => error.code === 'team_capacity');
  const h2 = await fixture(); await h2.invite(); h2.advance(8 * 86400000);
  assert.equal((await h2.login()).status, 403);
});

test('email action bridge uses a fixed fragment and never consumes codes on GET', async () => {
  const h = await fixture();
  for (const mode of ['resetPassword', 'verifyEmail', 'recoverEmail']) {
    const response = await h.send('/auth/email/action?' + new URLSearchParams({ mode, oobCode: 'SYNTHETIC.action-code', apiKey: API_KEY, continueUrl: 'https://attacker.example' }), { origin: null });
    assert.equal(response.status, 303); assert.match(response.headers.get('cache-control'), /private, no-store/);
    const target = new URL(response.headers.get('location')); assert.equal(target.origin + target.pathname, APP_RETURN); assert.equal(target.search, '');
    assert.equal(new URLSearchParams(target.hash.slice(1)).get('team_email_mode'), mode);
    assert.doesNotMatch(target.href, /attacker|apiKey|continueUrl/);
  }
  for (const suffix of ['mode=resetPassword&mode=verifyEmail&oobCode=x', 'mode=resetPassword&oobCode=x&apiKey=wrong', 'mode=evil&oobCode=x', 'mode=resetPassword&oobCode=%0A']) assert.equal((await h.send('/auth/email/action?' + suffix, { origin: null })).status, 400);
  assert.equal(h.calls.length, 0);
});

test('Firebase provider redirects, missing configuration and forged role inputs fail closed', async () => {
  const h = await fixture(); await h.invite(); h.controls.providerRedirect = true;
  assert.equal((await h.login()).status, 503);
  assert.equal(h.calls.some(call => call.url.includes('attacker.example')), false);
  h.controls.providerRedirect = false;
  assert.equal((await h.send('/auth/firebase', { method: 'POST', body: { id_token: h.idToken(), role: 'admin' } })).status, 400);
  const missing = await fixture({ env: { FIREBASE_API_KEY: '' } }); assert.equal((await missing.login()).status, 503);
});

test('email sessions work without GitHub OAuth credentials while installation key remains mandatory for notes', async () => {
  const h = await fixture(); await h.invite(); h.env.GITHUB_CLIENT_SECRET = '';
  const session = await (await h.login()).json();
  assert.equal((await h.send('/api/session', { token: session.session_token })).status, 200);
  h.env.GITHUB_APP_PRIVATE_KEY = '';
  assert.equal((await h.send('/api/memo', { token: session.session_token })).status, 503);
});
