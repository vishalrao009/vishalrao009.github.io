/* ---------------------------------------------------------------
   EatNmove - service worker
   Lives at /wiki/vimwiki_html/Tools/sw.js

   IMPORTANT: a service worker's scope is the folder it is served
   from, so this one is registered over the whole Tools/ directory -
   every other page in that part of the wiki included. It must
   therefore touch nothing but its own files. Every request is
   checked against the owned list below, and anything else is
   returned unhandled so the browser fetches it normally.

   Getting this wrong is not theoretical. A worker that treated any
   navigation as "the app" would cache a sibling wiki page under the
   app's key and the ledger would start opening the wrong page.

   BUMP CACHE_VERSION when anything in ledger/ changes. Editing
   calorie_counter.html alone needs no bump; it is fetched
   network-first and the cached copy is only a fallback.
   --------------------------------------------------------------- */

const CACHE_VERSION = "v25";
const CACHE = `eatnmove-${CACHE_VERSION}`;

const PAGE = "calorie_counter.html";

const ASSETS = [
  "manifest.webmanifest",
  "ledger/fonts/fraunces-var-latin.woff2",
  "ledger/fonts/plex-sans-400.woff2",
  "ledger/fonts/plex-sans-500.woff2",
  "ledger/fonts/plex-sans-600.woff2",
  "ledger/icons/icon-192.png",
  "ledger/icons/icon-512.png",
  "ledger/icons/icon-maskable-512.png",
  "ledger/icons/apple-touch-icon.png"
];

// Absolute URLs, resolved against wherever this worker is actually served
// from, so moving the whole folder needs no edits here.
const PAGE_URL = new URL(PAGE, self.registration.scope).href;
const OWNED = new Set(ASSETS.map(p => new URL(p, self.registration.scope).href));

/* Strip query and hash. The manifest shortcuts append ?action=food, and
   that must still resolve to the one cached page. */
const bare = url => { const u = new URL(url); u.search = ""; u.hash = ""; return u.href; };

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE)
      /* All-or-nothing: one 404 fails the whole install, which is the
         loud failure you want while setting this up. */
      .then(cache => cache.addAll([PAGE, ...ASSETS]))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        /* Both prefixes: anyone who installed this before the rename still
           has an energy-ledger-* cache sitting on their device, and nothing
           else will ever clean it up. */
        keys.filter(k => (k.startsWith("eatnmove-") || k.startsWith("calo-") || k.startsWith("energy-ledger-"))
                         && k !== CACHE)
            .map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = bare(req.url);

  /* --- the app page: network first, cached copy as the fallback ---
     Network first because the page is edited often and installed
     phones must not be stranded on an old build. */
  if (url === PAGE_URL) {
    event.respondWith(
      fetch(req)
        .then(res => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put(PAGE_URL, copy));
          }
          return res;
        })
        .catch(() => caches.match(PAGE_URL))
    );
    return;
  }

  /* --- our own fonts, icons and manifest: cache first --- */
  if (OWNED.has(url)) {
    event.respondWith(
      caches.match(url).then(hit => hit || fetch(req).then(res => {
        if (res && res.ok && res.type === "basic") {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(url, copy));
        }
        return res;
      }))
    );
    return;
  }

  /* --- anything else in Tools/ belongs to the rest of the wiki ---
     Returning without calling respondWith leaves it completely alone. */
});

self.addEventListener("notificationclick", event => {
  event.notification.close();
  const action = (event.notification.data && event.notification.data.action) || "meals";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if (c.url && bare(c.url) === PAGE_URL) {
          try { c.postMessage({ type: "remind", action }); } catch (e) {}
          return c.focus();
        }
      }
      return self.clients.openWindow(PAGE_URL + "?action=" + action);
    })
  );
});

self.addEventListener("message", event => {
  if (event.data === "skip-waiting") self.skipWaiting();
});
