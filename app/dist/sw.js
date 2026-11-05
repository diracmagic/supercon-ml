// Offline support for the phone web app. Pages from this site load network-first and
// fall back to the last copy; live data from GitHub always goes straight to the network.
const APP_VERSION = '0.3.25';
const CACHE = 'supercon-0.3.25-twinkling-names';
const SHELL = ['./', './index.html', './assets.json', './manifest.webmanifest', './progress.json', './icons/icon-192.png', './icons/icon-512.png'];

function shellFiles(manifest) {
  if (!Array.isArray(manifest.styles) || !Array.isArray(manifest.scripts)) throw new Error('Invalid asset manifest');
  const files = [...manifest.styles, ...manifest.scripts];
  if (files.some((file) => typeof file !== 'string' || file.startsWith('/') || file.includes('..') || !/^[A-Za-z0-9_./-]+$/.test(file))) {
    throw new Error('Asset manifest must contain local relative paths');
  }
  return [...new Set([...SHELL, ...files].map((file) => new URL(file, self.location.href).href))];
}

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const response = await fetch(new URL('./assets.json', self.location.href).href, { cache: 'no-store' });
    if (!response.ok) throw new Error('Asset manifest is unavailable');
    const files = shellFiles(await response.json());
    const cache = await caches.open(CACHE);
    // A new offline cache must not be populated from a fresh-but-old HTTP cache.
    await cache.addAll(files.map((url) => new Request(url, { cache: 'reload' })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('supercon-') && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Legacy email-action navigation must never refresh or enter the shell cache.
  // Production email links arrive through the no-store Worker bridge as fragments.
  if (url.origin === self.location.origin && ['mode', 'oobCode', 'team_email_code'].some(key => url.searchParams.has(key))) {
    event.respondWith(fetch(event.request, {cache: 'no-store', referrerPolicy: 'no-referrer'}));
    return;
  }
  // Authenticated requests and private API routes must never enter the offline cache.
  if (event.request.method !== 'GET' || url.origin !== self.location.origin ||
      event.request.headers.has('Authorization') || /\/(?:auth|api)\//.test(url.pathname)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const hit = await cache.match(event.request);
    // Only resources installed from the public shell manifest can be refreshed.
    // Arbitrary same-origin responses must not become an offline data store.
    if (!hit) return fetch(event.request);
    try {
      // "Network first" must bypass the separate browser HTTP cache as well.
      const response = await fetch(event.request, { cache: 'no-store' });
      if (response.ok && !/\b(?:private|no-store)\b/i.test(response.headers.get('Cache-Control') || '')) {
        event.waitUntil(cache.put(event.request, response.clone()));
      }
      return response;
    } catch {
      return hit;
    }
  })());
});
