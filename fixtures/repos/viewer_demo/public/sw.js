// The app shell only (SPEC_PWA_VIEWER A3): never /api.
const SHELL = ['/', '/manifest.webmanifest']
self.addEventListener('install', (e) => e.waitUntil(caches.open('shell-v1').then((c) => c.addAll(SHELL))))
self.addEventListener('fetch', (e) => {
  if (new URL(e.request.url).pathname.startsWith('/api/')) return
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)))
})
