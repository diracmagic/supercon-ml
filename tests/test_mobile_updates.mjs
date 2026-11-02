import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const definitions = fs.readFileSync(new URL('../app/dist/js/definitions/updates.js', import.meta.url), 'utf8');
const initialize = fs.readFileSync(new URL('../app/dist/js/initialize/updates.js', import.meta.url), 'utf8');
const flush = async () => { for (let i = 0; i < 10; i++) await new Promise(setImmediate); };
const flat = node => [node, ...(node.children || []).flatMap(child => typeof child === 'object' ? flat(child) : [])];
const text = node => String(node.text || '') + (node.children || []).map(child => typeof child === 'object' ? text(child) : child).join('');
function harness({ controlled = true, standalone = true, desktop = false, version = '0.3.9' } = {}) {
  let clock = 1800000000000, reloads = 0, updateCalls = 0, fetchCalls = 0, releaseChecks = 0, browserOpens = 0;
  const controls = { published: "const APP_VERSION = '0.3.10';\nconst CACHE = 'supercon-8.9.99-internal';", updateFailed: false, fetchFailed: false, status: 200,
    releaseVersion: '0.3.10', releaseFailed: false, assetReady: true, nativeError: '', artifactOverrides: {} };
  const nativeCalls = [];
  const swEvents = {}, documentEvents = {}, windowEvents = {}, intervals = [], timeouts = [], badges = [], values = new Map();
  const element = (tag, attrs = {}, ...children) => ({ tag, attrs, text: attrs.text || '', children: children.flat(Infinity).filter(value => value !== null && value !== undefined), hidden: false,
    appendChild(child) { this.children.push(child); return child; } });
  const update = element('section'), foot = element('footer');
  const document = { visibilityState: 'visible', hidden: false, createTextNode: value => value,
    addEventListener(name, fn) { (documentEvents[name] ||= []).push(fn); } };
  const serviceWorker = { controller: controlled ? {} : null,
    register: async () => ({ update: async () => { updateCalls++; if (controls.updateFailed) throw new Error('offline'); } }),
    addEventListener(name, fn) { (swEvents[name] ||= []).push(fn); } };
  const navigator = { serviceWorker, onLine: true, standalone: standalone && !desktop, userAgent: 'Synthetic test browser', platform: desktop ? 'Win32' : '',
    setAppBadge(value) { badges.push(['set', value]); return Promise.resolve(); }, clearAppBadge() { badges.push(['clear']); return Promise.resolve(); } };
  const window = { location: { reload() { reloads++; } }, matchMedia: () => ({ matches: standalone && !desktop }),
    addEventListener(name, fn) { (windowEvents[name] ||= []).push(fn); }, ...(desktop ? { __TAURI__: { core: { invoke: async (command, args) => {
      nativeCalls.push({ command, args: JSON.parse(JSON.stringify(args)) });
      if (controls.nativeError) throw controls.nativeError;
      if (command === 'download_app_update') return { version: controls.releaseVersion, platform: 'windows', size: 123456,
        downloadId: '11111111-2222-4333-8444-555555555555', ...controls.artifactOverrides };
      if (command === 'install_app_update') return { launched: true, version: controls.releaseVersion, platform: 'windows' };
      throw new Error('Unexpected native command');
    } } } } : {}) };
  const context = { window, document, navigator, location: { protocol: 'https:' }, Date: { now: () => clock }, Promise,
    UPD: null, UPD_EVERY: 0, UPD_LATER: 0, APP_VERSION: version, API: 'https://api.github.com/repos/example/test', REPO_URL: 'https://github.com/example/test',
    setInterval(fn, ms) { intervals.push({ fn, ms }); }, setTimeout(fn, ms) { timeouts.push({ fn, ms }); return timeouts.length; }, clearTimeout() {},
    $: selector => selector === '#update' ? update : selector === '#upd-foot' ? foot : null,
    h: element, glyph: name => element('svg', { name }), append(node, children) { children.filter(Boolean).forEach(child => node.appendChild(child)); }, clear(node) { node.children = []; node.text = ''; },
    store: { get: key => values.get(key), set: (key, value) => values.set(key, value) },
    fetch: async (_url, options) => { fetchCalls++; assert.equal(options.cache, 'no-store'); assert.equal(options.redirect, 'error'); if (controls.fetchFailed) throw new Error('offline');
      return { ok: controls.status >= 200 && controls.status < 300, text: async () => controls.published }; },
    getJSON: async () => { releaseChecks++; if (controls.releaseFailed) throw new Error('offline'); return {
      tag_name: 'app-v' + controls.releaseVersion, html_url: 'https://github.com/example/test/releases/tag/app-v' + controls.releaseVersion,
      assets: controls.assetReady ? [{ name: 'SuperconProgress-windows-x64-setup.exe', browser_download_url: 'https://github.com/example/test/releases/download/app-v' + controls.releaseVersion + '/SuperconProgress-windows-x64-setup.exe' }] : [], body: '' }; },
    openExternal() { browserOpens++; throw new Error('Updates must not open a browser'); } };
  vm.runInNewContext(definitions + '\n' + initialize + '\nthis.api = { initializeSuperconUpdates, renderUpdate, webReleaseVersion, checkUpdate, installUpdate };', context);
  return { context, controls, update, navigator, serviceWorker, badges, intervals, timeouts, nativeCalls,
    get reloads() { return reloads; }, get updateCalls() { return updateCalls; }, get fetchCalls() { return fetchCalls; },
    get releaseChecks() { return releaseChecks; }, get browserOpens() { return browserOpens; },
    advance(ms) { clock += ms; },
    async start() { context.api.initializeSuperconUpdates(); await flush(); },
    async fireTimeout(ms) { for (const timer of timeouts.filter(timer => timer.ms === ms)) timer.fn(); await flush(); },
    async emit(target, event) { const events = target === 'sw' ? swEvents : target === 'window' ? windowEvents : documentEvents; for (const fn of events[event] || []) fn(); await flush(); },
    button(label) { return flat(update).find(node => node.tag === 'button' && text(node) === label); } };
}

test('an installed app checks on startup and announces only the explicit app release version', async () => {
  const h = harness(); await h.start();
  assert.equal(h.updateCalls, 1); assert.equal(h.fetchCalls, 1);
  assert.equal(h.context.UPD.web, '0.3.10'); assert.match(text(h.update), /Supercon Progress 0\.3\.10 is available/);
  assert.doesNotMatch(text(h.update), /8\.9\.99/); assert.equal(h.reloads, 0);
  assert.deepEqual(h.badges, [['set', 1]]);
  h.button('Reload now').attrs.onclick(); assert.equal(h.reloads, 1, 'Only an explicit user action reloads');
});

test('foreground and online checks are prompt but throttled and do not reopen a dismissed same-version notice', async () => {
  const h = harness(); await h.start(); h.button('Later').attrs.onclick();
  assert.equal(h.update.hidden, true); assert.deepEqual(h.badges.at(-1), ['clear']);
  await h.emit('document', 'visibilitychange'); await h.emit('window', 'online'); assert.equal(h.updateCalls, 1);
  h.advance(60000); await h.emit('document', 'visibilitychange');
  assert.equal(h.updateCalls, 2); assert.equal(h.context.UPD.dismissed, true); assert.equal(h.update.hidden, true);
  h.advance(60000); h.controls.published = "const APP_VERSION = '0.3.11';"; await h.emit('window', 'online');
  assert.equal(h.updateCalls, 3); assert.equal(h.context.UPD.web, '0.3.11'); assert.equal(h.context.UPD.dismissed, false); assert.equal(h.reloads, 0);
});

test('first service-worker installation, same versions and internal-only cache bumps do not announce updates', async () => {
  const first = harness({ controlled: false }); await first.start();
  first.serviceWorker.controller = {}; await first.emit('sw', 'controllerchange');
  assert.equal(first.updateCalls, 0); assert.equal(first.fetchCalls, 0); assert.equal(first.context.UPD.web, '');
  for (const source of ["const APP_VERSION = '0.3.9';\nconst CACHE = 'supercon-9.9.9';", "const CACHE = 'supercon-9.9.9';", "const APP_VERSION = '0.3.8';"]) {
    const h = harness(); h.controls.published = source; await h.start(); await h.emit('sw', 'controllerchange');
    assert.equal(h.context.UPD.web, ''); assert.equal(h.reloads, 0);
  }
});

test('offline, failed and hidden checks remain quiet and a later online return retries', async () => {
  for (const failed of ['updateFailed', 'fetchFailed', 'status']) {
    const h = harness(); h.controls[failed] = failed === 'status' ? 503 : true; await h.start();
    if (failed !== 'updateFailed') await h.emit('sw', 'controllerchange');
    assert.equal(h.context.UPD.web, ''); assert.equal(h.reloads, 0);
  }
  const h = harness(); h.navigator.onLine = false; await h.start(); assert.equal(h.updateCalls, 0);
  h.navigator.onLine = true; await h.emit('window', 'online'); assert.equal(h.updateCalls, 1); assert.equal(h.context.UPD.web, '0.3.10');
  h.advance(60000); h.context.document.visibilityState = 'hidden'; await h.emit('document', 'visibilitychange'); assert.equal(h.updateCalls, 1);
  h.context.document.visibilityState = 'visible'; await h.emit('document', 'visibilitychange'); assert.equal(h.updateCalls, 2);
});

test('badges are optional and restricted to installed display modes', async () => {
  const browser = harness({ standalone: false }); await browser.start(); assert.deepEqual(browser.badges, []); assert.equal(browser.context.UPD.web, '0.3.10');
  const unavailable = harness(); unavailable.navigator.setAppBadge = () => Promise.reject(new Error('unsupported')); await unavailable.start();
  assert.equal(unavailable.context.UPD.web, '0.3.10'); assert.equal(unavailable.reloads, 0);
});

test('desktop startup downloads inside the app once and installation needs two explicit clicks', async () => {
  const h = harness({ desktop: true }); await h.start(); await h.fireTimeout(3000);
  assert.equal(h.releaseChecks, 1); assert.equal(h.updateCalls, 0); assert.equal(h.fetchCalls, 0);
  assert.deepEqual(h.nativeCalls, [{ command: 'download_app_update', args: { expectedVersion: '0.3.10' } }]);
  assert.match(text(h.update), /downloaded and verified/); assert.equal(h.browserOpens, 0); assert.equal(h.reloads, 0);
  h.context.api.installUpdate(); await flush(); assert.equal(h.nativeCalls.length, 1, 'Calling install without confirmation is ignored');
  h.button('Install update').attrs.onclick(); assert.equal(h.nativeCalls.length, 1);
  h.button('Confirm installation').attrs.onclick(); await flush();
  assert.deepEqual(h.nativeCalls[1], { command: 'install_app_update', args: { downloadId: '11111111-2222-4333-8444-555555555555' } });
  assert.match(text(h.update), /installer is open/); assert.equal(h.browserOpens, 0); assert.equal(h.reloads, 0);
});

test('desktop return and reconnect check within fifteen minutes without repeating a verified download', async () => {
  const h = harness({ desktop: true }); await h.start(); await h.fireTimeout(3000);
  await h.emit('document', 'visibilitychange'); await h.emit('window', 'online'); assert.equal(h.releaseChecks, 1);
  h.advance(15 * 60000); await h.emit('document', 'visibilitychange');
  assert.equal(h.releaseChecks, 2); assert.equal(h.nativeCalls.length, 1);
  h.advance(15 * 60000); h.controls.releaseVersion = '0.3.11'; await h.emit('window', 'online');
  assert.equal(h.releaseChecks, 3); assert.equal(h.nativeCalls.length, 2);
  assert.deepEqual(h.nativeCalls[1], { command: 'download_app_update', args: { expectedVersion: '0.3.11' } });
});

test('desktop failed or invalid downloads never install, leak provider errors or retry automatically', async () => {
  for (const invalid of [{ nativeError: 'PRIVATE_PROVIDER_ERROR' }, { artifactOverrides: { downloadId: 'C:/evil.exe' } }, { artifactOverrides: { version: '9.9.9' } }]) {
    const h = harness({ desktop: true }); Object.assign(h.controls, invalid); await h.start(); await h.fireTimeout(3000);
    assert.equal(h.context.UPD.download, null); assert.equal(h.button('Install update'), undefined);
    assert.doesNotMatch(text(h.update), /PRIVATE_PROVIDER_ERROR|evil\.exe|9\.9\.9/);
    h.advance(15 * 60000); await h.emit('window', 'online'); assert.equal(h.nativeCalls.length, 1);
    h.controls.nativeError = ''; h.controls.artifactOverrides = {};
    h.button('Retry download').attrs.onclick(); await flush(); assert.equal(h.nativeCalls.length, 2); assert.ok(h.button('Install update'));
    assert.equal(h.browserOpens, 0); assert.equal(h.reloads, 0);
  }
});

test('desktop does not download current versions, absent platform installers or during an offline start', async () => {
  for (const changes of [{ releaseVersion: '0.3.9' }, { assetReady: false }, { releaseFailed: true }]) {
    const h = harness({ desktop: true }); Object.assign(h.controls, changes); await h.start(); await h.fireTimeout(3000);
    assert.equal(h.nativeCalls.length, 0); assert.equal(h.browserOpens, 0); assert.equal(h.reloads, 0);
  }
  const h = harness({ desktop: true }); h.navigator.onLine = false; await h.start(); await h.fireTimeout(3000);
  assert.equal(h.releaseChecks, 0); h.navigator.onLine = true; await h.emit('window', 'online');
  assert.equal(h.releaseChecks, 1); assert.equal(h.nativeCalls.length, 1);
});

test('an installer integrity or missing-artifact failure requires an explicit new download', async () => {
  for (const code of ['update_integrity_failed', 'update_not_downloaded']) {
    const h = harness({ desktop: true }); await h.start(); await h.fireTimeout(3000);
    h.controls.nativeError = code;
    h.button('Install update').attrs.onclick(); h.button('Confirm installation').attrs.onclick(); await flush();
    assert.equal(h.nativeCalls.length, 2); assert.equal(h.context.UPD.download, null);
    assert.equal(h.context.UPD.installConfirm, false); assert.equal(h.button('Install update'), undefined);
    assert.ok(h.button('Retry download')); assert.equal(h.context.UPD.installError, ''); assert.ok(h.context.UPD.downloadError);
    h.advance(15 * 60000); await h.emit('window', 'online'); assert.equal(h.nativeCalls.length, 2, 'Foreground polling must not loop over a failed installer');
    h.controls.nativeError = ''; h.button('Retry download').attrs.onclick(); await flush();
    assert.equal(h.nativeCalls.length, 3); assert.equal(h.nativeCalls[2].command, 'download_app_update');
    assert.ok(h.button('Install update')); assert.equal(h.browserOpens, 0); assert.equal(h.reloads, 0);
  }
});
