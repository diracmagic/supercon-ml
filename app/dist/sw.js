// Offline support for the phone web app. Pages from this site load network-first and
// fall back to the last copy; live data from GitHub always goes straight to the network.
const CACHE = 'supercon-0.3.10-ai-feed';
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
    await cache.addAll(files);
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
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        if (response.ok) event.waitUntil(caches.open(CACHE).then((cache) => cache.put(event.request, copy)));
        return response;
      })
      .catch(() => caches.match(event.request).then((hit) => hit || caches.match('./index.html')))
  );
});
