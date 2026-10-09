/* Service worker vnswap — cache app shell, jangan pernah cache /api/*.
 * Konversi butuh server lokal, jadi offline hanya membuka kerangka +
 * pesan ramah; semua data live selalu lewat jaringan.
 */

const CACHE = "vnswap-shell-v1";
const SHELL = [
  "/",
  "/app.js",
  "/styles.css",
  "/manifest.webmanifest",
  "/icon-192.png",
  "/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;
  if (url.pathname.startsWith("/api/")) return; // data live: selalu jaringan
  event.respondWith(
    caches.match(event.request).then(
      (hit) => hit || fetch(event.request).then((res) => {
        // simpan salinan statis saja untuk buka offline berikutnya
        if (res.ok && (url.pathname === "/" || url.pathname.startsWith("/static/")
            || ["/app.js", "/styles.css", "/manifest.webmanifest",
                "/icon-192.png", "/icon-512.png",
                "/apple-touch-icon.png"].includes(url.pathname))) {
          const copy = res.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return res;
      }).catch(() => caches.match("/"))
    )
  );
});
