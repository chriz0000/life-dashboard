// Forces every page load (including the iOS "Add to Home Screen" standalone
// launch, which has no reload button and no pull-to-refresh) to bypass the
// HTTP cache and fetch the live index.html from the network. Without this,
// the installed icon can keep showing whatever copy it first loaded.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") return;
  event.respondWith(fetch(event.request, { cache: "no-store" }));
});
