// The argus-viewer service worker (SPEC_PWA_VIEWER A3). Argus pins its sha256 (SW_SHA256 in router/stage_viewer.py):
// staging refuses a release whose sw.js differs, so a change here is a strict-lane change in Argus.
// It keeps only the fixed app shell below, network first (the cache is the fallback when offline), and never /api/.
// Built assets have hashed names and are not kept: offline, the cached shell loads no script (a blank page).
const CACHE = 'argus-viewer-shell-v1'
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icon.svg', '/icon-192.png', '/icon-512.png']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
    .then(() => self.clients.claim()))
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return
  const kept = SHELL.includes(url.pathname)
  if (!kept && request.mode !== 'navigate') return       // built assets and the rest: the network only
  event.respondWith(fetch(request).then((response) => {
    if (kept && response.ok) {
      const copy = response.clone()
      event.waitUntil(caches.open(CACHE).then((cache) => cache.put(url.pathname, copy)))
    }
    return response
  }).catch(() => caches.match(kept ? url.pathname : '/').then((hit) => hit || Response.error())))
})
