import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createHandler, AuthState, TeamDirectory, TeamBoardDO } from '../src/worker.mjs';
import { boardAccess, normalizeBoardBody } from '../src/board.mjs';
import { teamAccess } from '../src/team.mjs';
import { stateAccess } from '../src/state.mjs';
import { APP_ORIGIN, OWNER_ID, REPOSITORY_ID, base64url, encoder, encryptionKey, encryptToken, hexHash, randomToken, sha256 } from '../src/security.mjs';
import { APP_ID, INSTALLATION_ID } from '../src/installation.mjs';

// Synthetic in-memory providers and ephemeral signing keys only. These tests
// never access a deployed board or send a message to an actual team member.
const PROJECT = 'synthetic-board', KEY = 'SYNTHETIC_PUBLIC_FIREBASE_KEY';
const pair = await crypto.subtle.generateKey({ name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, true, ['sign', 'verify']);
const pem = '-----BEGIN PRIVATE KEY-----\n' + Buffer.from(await crypto.subtle.exportKey('pkcs8', pair.privateKey)).toString('base64') + '\n-----END PRIVATE KEY-----';
class Storage {
  constructor() { this.data = new Map(); this.queue = Promise.resolve(); }
  async get(key) { return structuredClone(this.data.get(key)); }
  async put(key, value) { this.data.set(key, structuredClone(value)); }
  async delete(key) { return this.data.delete(key); }
  async deleteAll() { this.data.clear(); }
  async setAlarm() {} async deleteAlarm() {}
  transaction(fn) { const answer = this.queue.then(async () => { const previous = structuredClone(this.data); try { return await fn(this); } catch (error) { this.data = previous; throw error; } }); this.queue = answer.catch(() => {}); return answer; }
}
class Namespace {
  constructor(Type) { this.Type = Type; this.objects = new Map(); this.stores = new Map(); this.calls = 0; this.paths = []; this.before = null; this.after = null; }
  idFromName(name) { return name; }
  get(name) {
    if (!this.stores.has(name)) this.stores.set(name, new Storage());
    if (!this.objects.has(name)) this.objects.set(name, new this.Type({ storage: this.stores.get(name) }, this.env));
    return { fetch: async request => { this.calls++; this.paths.push(new URL(request.url).pathname); if (this.before) await this.before(request); const response = await this.objects.get(name).fetch(request); if (this.after) await this.after(request); return response; } };
  }
}
async function harness() {
  let clock = 1800000000000;
  const env = { AUTH_STATE: new Namespace(AuthState), TEAM_DIRECTORY: new Namespace(TeamDirectory), TEAM_BOARD: new Namespace(TeamBoardDO),
    SESSION_KEY: base64url(new Uint8Array(32).fill(8)), GITHUB_CLIENT_ID: 'synthetic-client', GITHUB_CLIENT_SECRET: 'SYNTHETIC_CLIENT_SECRET_ONLY',
    GITHUB_APP_PRIVATE_KEY: pem, FIREBASE_PROJECT_ID: PROJECT, FIREBASE_API_KEY: KEY };
  for (const namespace of [env.AUTH_STATE, env.TEAM_DIRECTORY, env.TEAM_BOARD]) namespace.env = env;
  const controls = {}, identities = new Map(), calls = [];
  const repository = { id: REPOSITORY_ID, private: true, owner: { id: OWNER_ID }, full_name: 'diracmagic/supercon-research-notes', permissions: { pull: true } };
  const bytes = encoder.encode('{"synthetic":"access probe only"}'), prefix = encoder.encode('blob ' + bytes.length + '\0'), blob = new Uint8Array(prefix.length + bytes.length); blob.set(prefix); blob.set(bytes, prefix.length);
  const blobSha = await hexHash(blob, 'SHA-1');
  const fetchImpl = async (url, init) => {
    calls.push(url); assert.equal(init.redirect, 'manual');
    if (url.startsWith('https://identitytoolkit.googleapis.com/v1/accounts:lookup')) {
      const identity = identities.get(JSON.parse(init.body).idToken);
      if (!identity || controls.providerRevoked) return Response.json({ error: { message: 'INVALID_ID_TOKEN' } }, { status: 401 });
      return Response.json({ users: [{ localId: identity.sub, email: identity.email, emailVerified: true, validSince: String(Math.floor(clock / 1000) - 100), passwordUpdatedAt: identity.passwordUpdatedAt + (controls.passwordChanged ? 1000 : 0), disabled: false }] });
    }
    assert.ok(url.startsWith('https://api.github.com/'));
    const token = new Headers(init.headers).get('Authorization');
    if (url.endsWith('/user')) {
      if (controls.providerRevoked) return new Response(null, { status: 401 });
      return Response.json({ id: token === 'Bearer synthetic_owner' ? OWNER_ID : 77, login: token === 'Bearer synthetic_owner' ? 'diracmagic' : 'outsider' });
    }
    if (url === 'https://api.github.com/app/installations/' + INSTALLATION_ID) return Response.json({ id: INSTALLATION_ID, app_id: APP_ID, account: { id: OWNER_ID }, suspended_at: null, repository_selection: 'selected', permissions: { contents: 'read', metadata: 'read' } });
    if (url.endsWith('/access_tokens')) return Response.json({ token: 'synthetic_installation', expires_at: new Date(clock + 3600000).toISOString(), permissions: { contents: 'read', metadata: 'read' }, repositories: [repository] });
    assert.ok(['Bearer synthetic_owner', 'Bearer synthetic_installation'].includes(token));
    if (url.endsWith('/repositories/' + REPOSITORY_ID)) return Response.json({ ...repository, permissions: { pull: !controls.repoRevoked } });
    assert.equal(new URL(url).pathname, '/repos/diracmagic/supercon-research-notes/contents/data/external_research_memo.json');
    if (controls.repoRevoked) return new Response(null, { status: 403 });
    if (controls.revokeDuringProbe) { const id = controls.revokeDuringProbe; delete controls.revokeDuringProbe; await teamAccess(env, 'revoke', clock, { memberId: id }); }
    return Response.json({ type: 'file', path: 'data/external_research_memo.json', encoding: 'base64', content: Buffer.from(bytes).toString('base64'), size: bytes.length, sha: blobSha });
  };
  const handler = createHandler({ fetchImpl, now: () => clock });
  const send = (path = '/api/board', { token, method = 'GET', body, raw, origin = APP_ORIGIN, headers = {} } = {}) => handler.fetch(new Request('https://auth.example.test' + path, {
    method, headers: { ...(origin ? { Origin: origin } : {}), ...(token ? { Authorization: 'Bearer ' + token } : {}), ...(body !== undefined || raw !== undefined ? { 'Content-Type': 'application/json' } : {}), ...headers },
    ...(raw !== undefined ? { body: raw } : body !== undefined ? { body: JSON.stringify(body) } : {}),
  }), env);
  async function createSession(record, providerToken) {
    const token = randomToken(), key = await encryptionKey(env);
    await stateAccess(env, 'session', token, 'create', clock, { record: { kind: 'session', expiresAt: clock + 3600000, ...record, encrypted: await encryptToken(providerToken, key, 'session:' + await sha256(token)) } });
    return token;
  }
  const owner = (admin = true) => createSession({ user: { id: admin ? OWNER_ID : 77, login: admin ? 'diracmagic' : 'outsider' } }, admin ? 'synthetic_owner' : 'synthetic_other');
  async function member({ uid = 'synthetic_member', name = 'Ada', invited = true, existing } = {}) {
    if (existing) uid = existing.uid;
    const email = uid + '@example.test'; let membership = existing ? { id: existing.memberId, version: existing.memberVersion } : { id: randomToken(), version: 1 };
    if (invited && !existing) {
      const pending = await teamAccess(env, 'invite', clock, { uid, email, name, expectedMemberId: null, expectedVersion: null });
      await teamAccess(env, 'delivery', clock, { memberId: pending.member_id, version: pending.version, status: 'accepted' });
      membership = await teamAccess(env, 'claim', clock, { uid, email, authTime: clock });
    }
    const claims = { aud: PROJECT, iss: 'https://securetoken.google.com/' + PROJECT, sub: uid, email, email_verified: true, iat: Math.floor(clock / 1000), auth_time: Math.floor(clock / 1000), exp: Math.floor(clock / 1000) + 3600, firebase: { sign_in_provider: 'password' } };
    const idToken = base64url(encoder.encode('{"alg":"RS256"}')) + '.' + base64url(encoder.encode(JSON.stringify(claims))) + '.' + randomToken();
    const passwordUpdatedAt = clock - 100000; identities.set(idToken, { ...claims, passwordUpdatedAt });
    const token = await createSession({ provider: 'firebase', user: { id: 'firebase:' + uid, login: email, email }, firebaseUid: uid, memberId: membership.id, memberVersion: membership.version, passwordUpdatedAt }, idToken);
    return { token, memberId: membership.id, memberVersion: membership.version, uid, email };
  }
  return { env, controls, calls, send, owner, member, now: () => clock, advance: ms => { clock += ms; } };
}
const fakeActor = n => ({ id: 'github:' + (n + 1000), name: 'Synthetic ' + n });

test('anonymous, foreign-origin and non-team requests cannot read or post and return private headers', async () => {
  const h = await harness(), outsider = await h.owner(false), uninvited = await h.member({ invited: false });
  for (const method of ['GET', 'POST']) for (const [token, origin, status] of [[undefined, APP_ORIGIN, 401], [outsider, APP_ORIGIN, 403], [uninvited.token, APP_ORIGIN, method === 'GET' ? 403 : 401], [outsider, null, 403], [outsider, 'https://attacker.example', 403]]) {
    const response = await h.send('/api/board', { method, token, origin, ...(method === 'POST' ? { body: { body: 'Synthetic only' } } : {}) });
    assert.equal(response.status, status); assert.match(response.headers.get('cache-control'), /private, no-store/);
    assert.equal(response.headers.get('Access-Control-Allow-Origin'), origin === APP_ORIGIN ? APP_ORIGIN : null);
    assert.deepEqual(Object.keys(await response.json()), ['error']);
  }
  assert.equal(h.env.TEAM_BOARD.calls, 0);
});

test('owner and invited email members share the board with server names and request-relative is_self', async () => {
  const h = await harness(), owner = await h.owner(), member = await h.member();
  let response = await h.send('/api/board', { method: 'POST', token: owner, body: { body: '  Synthetic owner message\n\tsecond line  ' } });
  assert.equal(response.status, 200); const first = await response.json();
  assert.deepEqual(first, { message: { id: 1, body: 'Synthetic owner message\n\tsecond line', created_at: h.now(), author: { name: 'diracmagic', is_self: true } }, latest_id: 1,
    presence: { members: [{ name: 'diracmagic', is_self: true, online: true }], window_seconds: 150, observed_at: h.now() } });
  response = await h.send('/api/board', { method: 'POST', token: member.token, body: { body: '<b>Synthetic literal text</b>' } }); assert.equal(response.status, 200);
  assert.deepEqual((await response.json()).message.author, { name: 'Ada', is_self: true });
  response = await h.send('/api/board?after=0', { token: member.token }); assert.equal(response.status, 200);
  const page = await response.json(); assert.deepEqual(page.messages.map(message => message.author.is_self), [false, true]);
  assert.equal(page.messages[1].body, '<b>Synthetic literal text</b>'); assert.equal(page.latest_id, 2); assert.equal(page.has_more, false);
  assert.doesNotMatch(JSON.stringify(page), /example\.test|synthetic_member|actorId|memberId|firebase:/);
  assert.equal(response.headers.get('Access-Control-Allow-Origin'), APP_ORIGIN); assert.match(response.headers.get('cache-control'), /private, no-store/);
});

test('blank member names use a neutral fallback and current admin-edited names apply to new messages', async () => {
  const h = await harness(), member = await h.member({ name: '' });
  const post = () => h.send('/api/board', { method: 'POST', token: member.token, body: { body: 'Synthetic body' } });
  assert.equal((await (await post()).json()).message.author.name, 'Team member');
  await teamAccess(h.env, 'name', h.now(), { memberId: member.memberId, name: 'Ada Updated' }); h.advance(3000);
  assert.equal((await (await post()).json()).message.author.name, 'Ada Updated');
});

test('client author, identity, timestamp and permission fields are rejected without writing', async () => {
  const h = await harness(), token = await h.owner();
  for (const extra of [{ author: { name: 'Forged', is_self: false } }, { actor: fakeActor(1) }, { created_at: 1 }, { is_self: true }, { id: 99 }, { can_read_memo: true }]) {
    const response = await h.send('/api/board', { method: 'POST', token, body: { body: 'Synthetic', ...extra } }); assert.equal(response.status, 400);
  }
  assert.equal(h.env.TEAM_BOARD.calls, 0);
});

test('revoked, expired, password-changed and repository-denied identities cannot read or post', async () => {
  for (const reason of ['membership', 'expiry', 'password', 'provider', 'repository']) for (const method of ['GET', 'POST']) {
    const h = await harness(), member = await h.member();
    if (reason === 'membership') await teamAccess(h.env, 'revoke', h.now(), { memberId: member.memberId });
    if (reason === 'expiry') h.advance(3600000);
    if (reason === 'password') h.controls.passwordChanged = true;
    if (reason === 'provider') h.controls.providerRevoked = true;
    if (reason === 'repository') h.controls.repoRevoked = true;
    const response = await h.send('/api/board', { token: member.token, method, ...(method === 'POST' ? { body: { body: 'Synthetic' } } : {}) });
    assert.ok([401, 403].includes(response.status), reason); assert.equal(h.env.TEAM_BOARD.paths.filter(path => path !== '/revoke').length, 0, reason);
  }
  const h = await harness(), token = await h.owner(); h.controls.repoRevoked = true;
  assert.equal((await h.send('/api/board', { token })).status, 403); assert.equal(h.env.TEAM_BOARD.calls, 0);
});

test('revocation during repository verification prevents both board access and a pending write', async () => {
  for (const method of ['GET', 'POST']) {
    const h = await harness(), member = await h.member(); h.controls.revokeDuringProbe = member.memberId;
    const response = await h.send('/api/board', { token: member.token, method, ...(method === 'POST' ? { body: { body: 'Synthetic' } } : {}) });
    assert.equal(response.status, 403); assert.equal(h.env.TEAM_BOARD.paths.filter(path => path !== '/revoke').length, 0);
  }
});

test('completed revoke between the Worker precheck and board append leaves no stored message', async () => {
  const h = await harness(), member = await h.member();
  h.env.TEAM_BOARD.before = async request => {
    if (new URL(request.url).pathname === '/post') {
      h.env.TEAM_BOARD.before = null;
      await teamAccess(h.env, 'revoke', h.now(), { memberId: member.memberId });
    }
  };
  const response = await h.send('/api/board', { method: 'POST', token: member.token, body: { body: 'Synthetic delayed post' } });
  assert.equal(response.status, 403); assert.deepEqual(await response.json(), { error: 'membership_revoked' });
  const store = [...h.env.TEAM_BOARD.stores.values()][0];
  assert.equal([...store.data.keys()].filter(key => key.startsWith('message:')).length, 0);
  assert.equal(store.data.has('latest'), false);
});

test('an in-flight append committed before its revocation returns an honest success receipt', async () => {
  const h = await harness(), member = await h.member();
  h.env.TEAM_BOARD.after = async request => {
    if (new URL(request.url).pathname === '/post') {
      h.env.TEAM_BOARD.after = null;
      await teamAccess(h.env, 'revoke', h.now(), { memberId: member.memberId });
    }
  };
  const response = await h.send('/api/board', { method: 'POST', token: member.token, body: { body: 'Synthetic already committed post' } });
  assert.equal(response.status, 200); assert.equal((await response.json()).message.id, 1);
  assert.equal((await h.send('/api/board', { method: 'POST', token: member.token, body: { body: 'Synthetic rejected later post' } })).status, 403);
  assert.equal([...h.env.TEAM_BOARD.stores.values()][0].data.get('latest'), 1);
});

test('persistent fences reject old in-flight versions after revoke and reinvite and survive restart', async () => {
  const h = await harness(), member = await h.member();
  const oldActor = { id: 'firebase:' + member.uid, name: 'Ada', memberId: member.memberId, memberVersion: member.memberVersion };
  const revoked = await teamAccess(h.env, 'revoke', h.now(), { memberId: member.memberId });
  const pending = await teamAccess(h.env, 'invite', h.now(), { uid: member.uid, email: member.email, expectedMemberId: member.memberId, expectedVersion: revoked.version });
  await teamAccess(h.env, 'delivery', h.now(), { memberId: member.memberId, version: pending.version, status: 'accepted' });
  const current = await teamAccess(h.env, 'claim', h.now(), { uid: member.uid, email: member.email, authTime: h.now() });
  h.env.TEAM_BOARD.objects.clear();
  await assert.rejects(boardAccess(h.env, 'post', h.now(), { actor: oldActor, body: 'Synthetic obsolete version' }), error => error.code === 'membership_revoked');
  const accepted = await boardAccess(h.env, 'post', h.now(), { actor: { ...oldActor, memberVersion: current.version }, body: 'Synthetic new active version' });
  assert.equal(accepted.message.id, 1);
  const again = await teamAccess(h.env, 'revoke', h.now(), { memberId: member.memberId });
  await boardAccess(h.env, 'revoke', h.now(), { memberId: member.memberId, version: revoked.version });
  const store = [...h.env.TEAM_BOARD.stores.values()][0];
  assert.equal(store.data.get('revoked:' + await sha256(member.memberId)), again.version, 'Delayed older revoke cannot lower the persistent fence');
  await assert.rejects(boardAccess(h.env, 'post', h.now(), { actor: { ...oldActor, memberVersion: current.version }, body: 'Synthetic newly obsolete version' }), error => error.code === 'membership_revoked');
  assert.equal(store.data.get('latest'), 1);
});

test('revocation is never acknowledged before its board fence persists and failed fencing can be retried', async () => {
  const h = await harness(), member = await h.member();
  let release, entered, acknowledged = false;
  const paused = new Promise(resolve => { entered = resolve; });
  h.env.TEAM_BOARD.before = async request => {
    if (new URL(request.url).pathname === '/revoke') { entered(); await new Promise(resolve => { release = resolve; }); }
  };
  const revocation = teamAccess(h.env, 'revoke', h.now(), { memberId: member.memberId }).then(value => { acknowledged = true; return value; });
  await paused; assert.equal(acknowledged, false); release(); await revocation; assert.equal(acknowledged, true);
  const store = [...h.env.TEAM_BOARD.stores.values()][0]; assert.ok(store.data.get('revoked:' + await sha256(member.memberId)) >= 2);
  h.env.TEAM_BOARD.before = async () => { throw new Error('Synthetic internal failure'); };
  await assert.rejects(teamAccess(h.env, 'revoke', h.now(), { memberId: member.memberId }), error => error.code === 'team_unavailable');
  h.env.TEAM_BOARD.before = null;
  const retry = await teamAccess(h.env, 'revoke', h.now(), { memberId: member.memberId });
  assert.equal(store.data.get('revoked:' + await sha256(member.memberId)), retry.version);
});

test('message body is bounded plain text and invalid requests cannot consume a message ID', async () => {
  const h = await harness(), token = await h.owner();
  for (const body of ['', ' \t\n ', 'x'.repeat(2001), 'x\u0000y', 'x\ry', 'x\u007fy', 'x\u009fy', 12, null]) {
    const response = await h.send('/api/board', { method: 'POST', token, body: { body } }); assert.equal(response.status, 400); assert.deepEqual(await response.json(), { error: 'invalid_message' });
  }
  for (const raw of ['{"body":"' + 'x'.repeat(9000) + '"}', '{broken', '[]']) assert.equal((await h.send('/api/board', { method: 'POST', token, raw })).status, 400);
  const response = await h.send('/api/board', { method: 'POST', token, body: { body: '中'.repeat(2000) } }); assert.equal(response.status, 200); assert.equal((await response.json()).message.id, 1);
  assert.equal(normalizeBoardBody('\n a\t b \n'), 'a\t b');
});

test('post limits enforce three-second spacing and a rolling twenty-per-hour window atomically', async () => {
  const h = await harness(), token = await h.owner();
  const post = () => h.send('/api/board', { method: 'POST', token, body: { body: 'Synthetic rate fixture' } });
  assert.equal((await post()).status, 200); assert.equal((await post()).status, 429); h.advance(2999); assert.equal((await post()).status, 429); h.advance(1);
  for (let i = 1; i < 20; i++) { assert.equal((await post()).status, 200); h.advance(3000); }
  assert.equal((await post()).status, 429);
  h.advance(3600000); const fresh = await h.owner();
  assert.equal((await h.send('/api/board', { method: 'POST', token: fresh, body: { body: 'Synthetic after rate window' } })).status, 200);
  const records = [...h.env.TEAM_BOARD.stores.values()][0].data; assert.equal(records.get('latest'), 21);
});

test('history retains all separate messages and paginates newest, older and newer pages in ascending order', async () => {
  const h = await harness();
  for (let i = 1; i <= 130; i++) { await boardAccess(h.env, 'post', h.now(), { actor: fakeActor(Math.floor((i - 1) / 20)), body: 'Synthetic ' + i }); h.advance(3000); }
  const token = await h.owner(), get = async suffix => { const response = await h.send('/api/board' + suffix, { token }); assert.equal(response.status, 200); return response.json(); };
  const latest = await get('?after=0'); assert.deepEqual(latest.messages.map(m => m.id), Array.from({ length: 50 }, (_, i) => 81 + i)); assert.equal(latest.latest_id, 130); assert.equal(latest.has_more, true);
  const older = await get('?before=81'); assert.equal(older.messages[0].id, 31); assert.equal(older.messages.at(-1).id, 80); assert.equal(older.has_more, true);
  const oldest = await get('?before=31'); assert.equal(oldest.messages[0].id, 1); assert.equal(oldest.messages.length, 30); assert.equal(oldest.has_more, false);
  const newer = await get('?after=10&limit=20'); assert.equal(newer.messages[0].id, 11); assert.equal(newer.messages.at(-1).id, 30); assert.equal(newer.has_more, true);
  const tail = await get('?after=120'); assert.equal(tail.messages.length, 10); assert.equal(tail.has_more, false);
  for (const suffix of ['?after=9007199254740991', '?before=1']) { const page = await get(suffix); assert.deepEqual(page.messages, []); assert.equal(page.has_more, false); }
  const store = [...h.env.TEAM_BOARD.stores.values()][0]; assert.equal([...store.data.keys()].filter(key => key.startsWith('message:')).length, 130);
  h.env.TEAM_BOARD.objects.clear(); const reloaded = await get('?after=129'); assert.equal(reloaded.messages[0].body, 'Synthetic 130');
});

test('concurrent posts get unique durable monotonic IDs and the same actor cannot bypass rate limits', async () => {
  const h = await harness();
  const results = await Promise.all(Array.from({ length: 12 }, (_, i) => boardAccess(h.env, 'post', h.now(), { actor: fakeActor(i), body: 'Synthetic concurrent ' + i })));
  assert.deepEqual(results.map(result => result.message.id).sort((a, b) => a - b), Array.from({ length: 12 }, (_, i) => i + 1));
  const attempts = await Promise.allSettled(Array.from({ length: 8 }, () => boardAccess(h.env, 'post', h.now(), { actor: fakeActor(99), body: 'Synthetic duplicate rate' })));
  assert.equal(attempts.filter(result => result.status === 'fulfilled').length, 1);
  assert.ok(attempts.filter(result => result.status === 'rejected').every(result => result.reason.code === 'rate_limited'));
  assert.equal([...h.env.TEAM_BOARD.stores.values()][0].data.get('latest'), 13);
});

test('bad cursors, duplicate parameters and unsupported methods cannot request arbitrary keys', async () => {
  const h = await harness(), token = await h.owner();
  for (const suffix of ['?limit=0', '?limit=51', '?after=-1', '?after=1.5', '?after=01', '?after=9007199254740992', '?before=0', '?after=0&before=5', '?after=0&after=1', '?actor=github:1', '?path=../members']) assert.equal((await h.send('/api/board' + suffix, { token })).status, 400, suffix);
  assert.equal((await h.send('/api/board?after=0', { token, method: 'POST', body: { body: 'Synthetic' } })).status, 400);
  for (const method of ['PUT', 'DELETE', 'PATCH']) assert.equal((await h.send('/api/board', { token, method })).status, 405);
  assert.equal(h.env.TEAM_BOARD.calls, 0);
});

test('board CORS preflight exposes only exact allowed origin and methods without authentication or data', async () => {
  const h = await harness();
  for (const method of ['GET', 'POST']) {
    const response = await h.send('/api/board', { method: 'OPTIONS', headers: { 'Access-Control-Request-Method': method, 'Access-Control-Request-Headers': 'Authorization, Content-Type' } });
    assert.equal(response.status, 204); assert.equal(response.headers.get('Access-Control-Allow-Methods'), 'GET, POST'); assert.equal(await response.text(), '');
  }
  assert.equal((await h.send('/api/board', { method: 'OPTIONS', origin: 'https://attacker.example', headers: { 'Access-Control-Request-Method': 'GET' } })).status, 403);
  assert.equal(h.calls.length, 0); assert.equal(h.env.TEAM_BOARD.calls, 0);
});

test('presence is private and rejects anonymous, non-team, revoked and forged requests', async () => {
  const h = await harness(), outsider = await h.owner(false), member = await h.member();
  for (const [token, origin, status] of [[undefined, APP_ORIGIN, 401], [outsider, APP_ORIGIN, 403], [member.token, 'https://attacker.example', 403], [member.token, null, 403]]) {
    const response = await h.send('/api/presence', { token, origin });
    assert.equal(response.status, status); assert.deepEqual(Object.keys(await response.json()), ['error']);
    assert.match(response.headers.get('cache-control'), /private, no-store/);
  }
  assert.equal((await h.send('/api/presence?name=Forged&online=true', { token: member.token })).status, 400);
  assert.equal((await h.send('/api/presence', { token: member.token, method: 'POST', body: { actor: { name: 'Forged' } } })).status, 405);
  await teamAccess(h.env, 'revoke', h.now(), { memberId: member.memberId });
  assert.equal((await h.send('/api/presence', { token: member.token })).status, 403);
});

test('validated board and session requests piggyback names-only presence without another provider poll', async () => {
  const h = await harness(), owner = await h.owner(), member = await h.member();
  let response = await h.send('/api/board', { token: owner }); assert.equal(response.status, 200);
  assert.deepEqual((await response.json()).presence, { members: [{ name: 'diracmagic', is_self: true, online: true }], window_seconds: 150, observed_at: h.now() });
  const calls = h.calls.length;
  response = await h.send('/api/session', { token: member.token }); assert.equal(response.status, 200);
  const presence = (await response.json()).presence;
  assert.deepEqual(presence.members, [{ name: 'Ada', is_self: true, online: true }, { name: 'diracmagic', is_self: false, online: true }]);
  assert.equal(h.calls.slice(calls).filter(url => url.startsWith('https://identitytoolkit.googleapis.com/')).length, 1);
  assert.doesNotMatch(JSON.stringify(presence), /email|example\.test|synthetic_member|memberId|sessionKey|firebase:/);
  assert.equal(h.env.TEAM_BOARD.paths.at(-1), '/presence');
  assert.match(response.headers.get('cache-control'), /private, no-store/);
  assert.equal(response.headers.get('Access-Control-Allow-Origin'), APP_ORIGIN);
});

test('presence expires at150 seconds without implying live connectivity and bounds session expiry', async () => {
  const h = await harness(), owner = await h.owner(), member = await h.member();
  await h.send('/api/presence', { token: member.token });
  h.advance(149999);
  let result = await (await h.send('/api/presence', { token: owner })).json();
  assert.ok(result.presence.members.some(person => person.name === 'Ada'));
  h.advance(1);
  result = await (await h.send('/api/presence', { token: owner })).json();
  assert.equal(result.presence.members.some(person => person.name === 'Ada'), false);
  h.advance(3600000);
  assert.equal((await h.send('/api/presence', { token: owner })).status, 401);
  const renewedOwner = await h.owner();
  result = await (await h.send('/api/presence', { token: renewedOwner })).json();
  assert.deepEqual(result.presence.members, [{ name: 'diracmagic', is_self: true, online: true }]);
});

test('logout removes only its session and another active device preserves one person in the list', async () => {
  const h = await harness(), owner = await h.owner(), member = await h.member(), second = await h.member({ existing: member });
  await h.send('/api/presence', { token: member.token }); await h.send('/api/presence', { token: second.token });
  let result = await (await h.send('/api/presence', { token: owner })).json();
  assert.equal(result.presence.members.filter(person => person.name === 'Ada').length, 1);
  assert.equal((await h.send('/auth/logout', { method: 'POST', token: member.token })).status, 200);
  result = await (await h.send('/api/presence', { token: owner })).json();
  assert.equal(result.presence.members.filter(person => person.name === 'Ada').length, 1);
  assert.equal((await h.send('/auth/logout', { method: 'POST', token: second.token })).status, 200);
  assert.equal((await h.send('/auth/logout', { method: 'POST', token: second.token })).status, 200);
  result = await (await h.send('/api/presence', { token: owner })).json();
  assert.equal(result.presence.members.some(person => person.name === 'Ada'), false);
});

test('completed signout fences a delayed presence refresh across object recreation', async () => {
  const h = await harness(), owner = await h.owner(), member = await h.member();
  await h.send('/api/presence', { token: member.token });
  h.env.TEAM_BOARD.before = async request => {
    if (new URL(request.url).pathname === '/presence') {
      h.env.TEAM_BOARD.before = null;
      assert.equal((await h.send('/auth/logout', { method: 'POST', token: member.token })).status, 200);
      for (const [name, storage] of h.env.TEAM_BOARD.stores) h.env.TEAM_BOARD.objects.set(name, new TeamBoardDO({ storage }));
    }
  };
  assert.equal((await h.send('/api/presence', { token: member.token })).status, 401);
  const result = await (await h.send('/api/presence', { token: owner })).json();
  assert.equal(result.presence.members.some(person => person.name === 'Ada'), false);
});

test('revocation immediately removes all devices and fences delayed presence after reinstantiation', async () => {
  const h = await harness(), owner = await h.owner(), member = await h.member(), second = await h.member({ existing: member });
  await h.send('/api/presence', { token: member.token }); await h.send('/api/presence', { token: second.token });
  h.env.TEAM_BOARD.before = async request => {
    if (new URL(request.url).pathname === '/presence') {
      h.env.TEAM_BOARD.before = null;
      await teamAccess(h.env, 'revoke', h.now(), { memberId: member.memberId });
      for (const [name, storage] of h.env.TEAM_BOARD.stores) h.env.TEAM_BOARD.objects.set(name, new TeamBoardDO({ storage }));
    }
  };
  assert.equal((await h.send('/api/presence', { token: member.token })).status, 403);
  const result = await (await h.send('/api/presence', { token: owner })).json();
  assert.equal(result.presence.members.some(person => person.name === 'Ada'), false);
  assert.equal((await h.send('/api/presence', { token: second.token })).status, 403);
});

test('presence names use current verified directory data, neutral fallback and per-person aggregation', async () => {
  const h = await harness(), owner = await h.owner(), member = await h.member({ name: '' }), second = await h.member({ existing: member });
  await h.send('/api/presence', { token: member.token });
  let result = await (await h.send('/api/presence', { token: owner })).json();
  assert.ok(result.presence.members.some(person => person.name === 'Team member'));
  await teamAccess(h.env, 'name', h.now(), { memberId: member.memberId, name: 'Ada Updated' });
  await h.send('/api/presence', { token: second.token });
  result = await (await h.send('/api/presence', { token: owner })).json();
  assert.equal(result.presence.members.filter(person => person.name === 'Ada Updated').length, 1);
  assert.equal(result.presence.members.some(person => person.name === 'Team member'), false);
});

test('failed repository checks cannot refresh presence and listing shares existing private API limits', async () => {
  const h = await harness(), owner = await h.owner(), member = await h.member();
  h.controls.repoRevoked = true;
  assert.equal((await h.send('/api/presence', { token: member.token })).status, 403);
  h.controls.repoRevoked = false;
  const result = await (await h.send('/api/presence', { token: owner })).json();
  assert.equal(result.presence.members.some(person => person.name === 'Ada'), false);
  const fresh = await h.member({ existing: member });
  for (let i = 0; i < 11; i++) assert.equal((await h.send('/api/presence', { token: fresh.token })).status, 200);
  const before = h.calls.length;
  assert.equal((await h.send('/api/presence', { token: fresh.token })).status, 429);
  assert.equal(h.calls.length, before);
});

test('board binding and migration preserve prior classes and neither data path logs nor auto-deletes messages', () => {
  const config = JSON.parse(fs.readFileSync(new URL('../wrangler.jsonc', import.meta.url), 'utf8'));
  assert.ok(config.durable_objects.bindings.some(binding => binding.name === 'TEAM_BOARD' && binding.class_name === 'TeamBoardDO'));
  assert.deepEqual(config.migrations.at(-1), { tag: 'v3', new_sqlite_classes: ['TeamBoardDO'] });
  assert.equal(config.observability.enabled, false);
  const source = fs.readFileSync(new URL('../src/board.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /console\.|\.delete\(|deleteAll|setAlarm|caches\./);
});
