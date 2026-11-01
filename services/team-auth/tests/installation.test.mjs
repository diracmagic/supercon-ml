import test from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import { APP_ID, INSTALLATION_ID, appJwt, createInstallationReader, importAppKey } from '../src/installation.mjs';
import { OWNER_ID, REPOSITORY_ID, encoder } from '../src/security.mjs';

// Ephemeral test-only keys; no credentials are stored in source or printed.
const pair = generateKeyPairSync('rsa', { modulusLength: 2048 });
const pem = pair.privateKey.export({ type: 'pkcs1', format: 'pem' });
const NOW = 1800000000000;
const repo = () => ({ id: REPOSITORY_ID, private: true, owner: { id: OWNER_ID }, full_name: 'diracmagic/supercon-research-notes' });
const installed = () => ({ id: INSTALLATION_ID, app_id: APP_ID, account: { id: OWNER_ID }, suspended_at: null, repository_selection: 'selected', permissions: { contents: 'read', metadata: 'read' } });
const tokenResponse = () => ({ token: 'fake_installation_token_for_tests', expires_at: new Date(NOW + 3600000).toISOString(), permissions: { contents: 'read', metadata: 'read' }, repositories: [repo()] });

test('GitHub PKCS1 and PKCS8 keys sign a short RS256 JWT with bounded clock skew', async () => {
  for (const type of ['pkcs1', 'pkcs8']) {
    const jwt = await appJwt(pair.privateKey.export({ type, format: 'pem' }), NOW);
    const [head, body, signature] = jwt.split('.');
    assert.deepEqual(JSON.parse(Buffer.from(head, 'base64url')), { alg: 'RS256', typ: 'JWT' });
    assert.deepEqual(JSON.parse(Buffer.from(body, 'base64url')), { iss: String(APP_ID), iat: NOW / 1000 - 60, exp: NOW / 1000 + 300 });
    const key = await crypto.subtle.importKey('spki', pair.publicKey.export({ type: 'spki', format: 'der' }), { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
    assert.equal(await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, Buffer.from(signature, 'base64url'), encoder.encode(head + '.' + body)), true);
  }
});

test('bad keys fail closed without reflecting their content', async () => {
  for (const value of [undefined, 'DO_NOT_REFLECT_PRIVATE_VALUE', pem.replace('END RSA', 'END EC'), 'x'.repeat(20000)]) {
    await assert.rejects(importAppKey(value), error => error.code === 'team_not_configured' && !error.message.includes('DO_NOT'));
  }
});

test('every token request revalidates the installation and pins exactly one read-only repository', async () => {
  const calls = [];
  const read = createInstallationReader({ now: () => NOW, fetchImpl: async (url, options) => {
    calls.push({ url, options });
    assert.equal(options.redirect, 'manual');
    if (options.method === 'GET') return Response.json(installed());
    assert.deepEqual(JSON.parse(options.body), { repository_ids: [REPOSITORY_ID], permissions: { contents: 'read', metadata: 'read' } });
    return Response.json(tokenResponse());
  } });
  assert.equal(await read({ GITHUB_APP_PRIVATE_KEY: pem }), 'fake_installation_token_for_tests');
  await read({ GITHUB_APP_PRIVATE_KEY: pem });
  assert.equal(calls.length, 4);
  assert.ok(calls.every(call => call.url === 'https://api.github.com/app/installations/' + INSTALLATION_ID || call.url === 'https://api.github.com/app/installations/' + INSTALLATION_ID + '/access_tokens'));
});

test('suspended, wrong-owner, broad or write-capable installations never receive a token', async () => {
  for (const change of [value => value.suspended_at = '2026-01-01', value => value.app_id++, value => value.account.id++, value => value.repository_selection = 'all', value => value.permissions.contents = 'write']) {
    const value = installed(); change(value); let count = 0;
    const read = createInstallationReader({ now: () => NOW, fetchImpl: async () => { count++; return Response.json(value); } });
    await assert.rejects(read({ GITHUB_APP_PRIVATE_KEY: pem }), error => error.code === 'memo_service_unavailable');
    assert.equal(count, 1);
  }
});

test('returned grant must preserve identity, repository privacy, read permission and bounded expiry', async () => {
  const changes = [v => v.repositories.push(repo()), v => v.repositories[0].private = false, v => v.repositories[0].id++, v => v.repositories[0].owner.id++,
    v => v.permissions.contents = 'write', v => v.expires_at = new Date(NOW).toISOString(), v => v.expires_at = new Date(NOW + 7200000).toISOString(), v => v.token = 'bad\r\nheader'];
  for (const change of changes) {
    const grant = tokenResponse(); change(grant);
    const read = createInstallationReader({ now: () => NOW, fetchImpl: async (_, init) => Response.json(init.method === 'GET' ? installed() : grant) });
    await assert.rejects(read({ GITHUB_APP_PRIVATE_KEY: pem }), error => error.code === 'memo_service_unavailable');
  }
});

test('redirects are cancelled and never followed with the App JWT', async () => {
  let cancelled = false, count = 0;
  const read = createInstallationReader({ now: () => NOW, fetchImpl: async () => {
    count++; return new Response(new ReadableStream({ cancel() { cancelled = true; } }), { status: 307, headers: { Location: 'https://example.invalid' } });
  } });
  await assert.rejects(read({ GITHUB_APP_PRIVATE_KEY: pem }), error => error.code === 'memo_service_unavailable');
  assert.equal(cancelled, true); assert.equal(count, 1);
});
