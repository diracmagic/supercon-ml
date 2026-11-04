import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// GitHub allows 60 unauthenticated API requests per hour for each network address, shared by every open copy of the app.
const read = file => fs.readFileSync(new URL('../app/dist/' + file, import.meta.url), 'utf8');
const MIN = 60 * 1000;

function harness({ runs = [] } = {}) {
  const urls = [], document = { hidden: false };
  const fetch = async url => {
    urls.push(String(url));
    const body = String(url).includes('/actions/runs') ? { workflow_runs: runs } : [];
    return { ok: true, status: 200, headers: { get: () => null }, json: async () => body };
  };
  const context = vm.createContext({ console, document, window: {}, fetch, setTimeout, clearTimeout });
  for (const file of ['js/bindings.js', 'js/definitions/core.js']) vm.runInContext(read(file), context, { filename: file });
  vm.runInContext("API = 'https://api.github.com/repos/diracmagic/supercon-ml'; state = {};", context);
  return {
    urls, document,
    load: force => vm.runInContext(force ? 'loadGitHub(true)' : 'loadGitHub()', context),
    ago: ms => vm.runInContext('state.ghAt = Date.now() - ' + ms, context),
  };
}

test('GitHub runs and commits are requested at most every 15 minutes, never in the background, and always on demand', async () => {
  const h = harness();
  await h.load();
  assert.equal(h.urls.length, 2, 'the first refresh asks once for runs and once for commits');
  assert.ok(h.urls.every(url => url.startsWith('https://api.github.com/repos/diracmagic/supercon-ml/')));
  await h.load();
  h.ago(14 * MIN); await h.load();
  assert.equal(h.urls.length, 2, 'refreshes within 15 minutes reuse the previous answer');
  h.ago(15 * MIN + 1000); await h.load();
  assert.equal(h.urls.length, 4, 'after 15 minutes GitHub is asked again');
  await h.load(true);
  assert.equal(h.urls.length, 6, 'the refresh button always asks');
  h.document.hidden = true; h.ago(60 * MIN); await h.load();
  assert.equal(h.urls.length, 6, 'nothing is requested while the app is in the background');
  await h.load(true);
  assert.equal(h.urls.length, 8, 'an explicit refresh still works in the background');
});

test('an active GitHub Actions run is followed every 5 minutes', async () => {
  const h = harness({ runs: [{ status: 'in_progress' }] });
  await h.load();
  h.ago(4 * MIN); await h.load();
  assert.equal(h.urls.length, 2);
  h.ago(5 * MIN + 1000); await h.load();
  assert.equal(h.urls.length, 4);
});
