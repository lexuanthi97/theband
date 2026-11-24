// Service worker: cho app mở nhanh và xem được dữ liệu gần nhất khi mất mạng.
const VERSION = "v1";
const SHELL = `shell-${VERSION}`;
const DATA = "data";
const SHELL_FILES = ["./", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png", "icons/favicon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith("shell-") && k !== SHELL).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.includes("/api/")) return; // tra cứu trực tiếp: luôn đi mạng

  // Dữ liệu: ưu tiên mạng để luôn mới nhất, mất mạng thì dùng bản đã lưu
  if (url.origin === location.origin && url.pathname.includes("/data/")) {
    e.respondWith(
      fetch(req).then(res => {
        if (res.ok) { const copy = res.clone(); caches.open(DATA).then(c => c.put(req, copy)); }
        return res;
      }).catch(() => caches.match(req).then(r => r || Response.error()))
    );
    return;
  }

  // Giao diện, icon, font: trả bản đã lưu ngay, cập nhật ngầm
  if (url.origin === location.origin || url.host.endsWith("fonts.googleapis.com") || url.host.endsWith("fonts.gstatic.com")) {
    e.respondWith(
      caches.open(SHELL).then(cache => cache.match(req, { ignoreSearch: url.origin === location.origin }).then(hit => {
        const net = fetch(req).then(res => { if (res.ok || res.type === "opaque") cache.put(req, res.clone()); return res; }).catch(() => hit);
        return hit || net;
      }))
    );
  }
});
