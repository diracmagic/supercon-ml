import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../app/dist/sw.js', import.meta.url), 'utf8');
function worker({ hit, response, fail = false } = {}) {
  const handlers = {}, writes = [], waits = [];
  let handled = false, answer;
  vm.runInNewContext(source, {
    URL,
    self: { location: new URL('https://example.org/supercon-ml/sw.js'), addEventListener(kind, fn) { handlers[kind] = fn; } },
    caches: { open: async () => ({ match: async () => hit, put: async (...values) => { writes.push(values); } }) },
    fetch: async () => { if (fail) throw new Error('offline'); return response; }
  });
  return { writes, async send(request) {
    handlers.fetch({ request, respondWith(promise) { handled = true; answer = promise; }, waitUntil(promise) { waits.push(promise); } });
    const result = handled ? await answer : undefined;
    await Promise.all(waits);
    return { handled, result };
  } };
}

test('authenticated, API and cross-origin requests bypass the offline worker', async () => {
  for (const req of [
    new Request('https://example.org/supercon-ml/index.html', { headers: { Authorization: 'Bearer synthetic' } }),
    new Request('https://example.org/supercon-ml/api/memo'),
    new Request('https://example.org/auth/github/callback'),
    new Request('https://login.example.org/api/memo'),
  ]) {
    const w = worker();
    assert.equal((await w.send(req)).handled, false);
    assert.equal(w.writes.length, 0);
  }
});

test('unlisted responses cannot be added to the public shell cache', async () => {
  const w = worker({ response: new Response('unlisted') });
  assert.equal(await (await w.send(new Request('https://example.org/unlisted.json'))).result.text(), 'unlisted');
  assert.equal(w.writes.length, 0);
});

test('private or no-store responses never overwrite a cached public shell resource', async () => {
  for (const policy of ['private, no-store', 'no-store', 'private']) {
    const w = worker({ hit: new Response('public'), response: new Response('sensitive', { headers: { 'Cache-Control': policy } }) });
    assert.equal(await (await w.send(new Request('https://example.org/supercon-ml/index.html'))).result.text(), 'sensitive');
    assert.equal(w.writes.length, 0);
  }
});

test('offline public shell fallback remains available without returning HTML for unknown requests', async () => {
  const w = worker({ hit: new Response('cached public shell'), fail: true });
  assert.equal(await (await w.send(new Request('https://example.org/supercon-ml/index.html'))).result.text(), 'cached public shell');
  const unknown = worker({ fail: true });
  await assert.rejects(unknown.send(new Request('https://example.org/unlisted.json')), /offline/);
});

test('successful public shell responses are refreshed', async () => {
  const w = worker({ hit: new Response('old'), response: new Response('new', { headers: { 'Cache-Control': 'public' } }) });
  assert.equal(await (await w.send(new Request('https://example.org/supercon-ml/index.html'))).result.text(), 'new');
  assert.equal(w.writes.length, 1);
});
