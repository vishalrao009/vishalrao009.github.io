/*!
 * search.js — site-wide search, entirely client-side. No server, no API.
 *
 * Load it on any page:  <script src="/wiki/assets/search.js"></script>
 * Configure it by setting window.SEARCH_CONFIG = {...} BEFORE that tag.
 *
 * How it works: on first open it fetches /wiki/assets/search-index.json (built
 * by build_search_index.py — run that script after regenerating the wiki HTML
 * and commit the file), which lists every page's url/title/text excerpt. The
 * query is ranked against every page with BM25 — the same scoring pagebot.js
 * uses per-page, applied here across the whole site — and the best-matching
 * pages are shown as a results list you click through to.
 *
 * Sibling of pagebot.js (which answers questions from a single page's text);
 * this instead finds *which* page to go to in the first place.
 */
(function (global) {
  "use strict";

  var DEFAULTS = {
    indexUrl: "/wiki/assets/search-index.json",
    maxResults: 8,
    title: "Search this site",
    placeholder: "Search pages…",
    emptyHint: "Start typing to search every page on the site.",
    accent: "#6b4f2a",
    panelBg: "#fbf6e9",
    textColor: "#2b2620",
    launcherSelector: null,   // dock the launcher inside an existing element
    launcherLabel: "🔍",   // magnifying glass
    launcherTitle: "Search this site",
    autoInit: true
  };

  var CFG = Object.assign({}, DEFAULTS, global.SEARCH_CONFIG || {});

  /* ---------------------------------------------------------------- text */

  var STOP = new Set(("a an the and or but if then else of in on at to for from by " +
    "with as is are was were be been being it its this that these those there here " +
    "what which who whom whose how why when where can could should would may might " +
    "will shall do does did done not no nor so than too very just also into over " +
    "under again further once about we you i they he she them his her our your my " +
    "have has had").split(" "));

  // Deliberately imperfect stemmer, kept identical in spirit to pagebot.js so
  // query words and indexed words are normalised the same way.
  function stem(w) {
    if (w.length > 4 && /ies$/.test(w)) w = w.slice(0, -3) + "y";
    else if (w.length > 4 && /(sses|shes|ches|xes)$/.test(w)) w = w.slice(0, -2);
    else if (w.length > 3 && /s$/.test(w) && !/ss$/.test(w)) w = w.slice(0, -1);
    if (w.length >= 7 && /ing$/.test(w)) w = w.slice(0, -3);
    else if (w.length >= 6 && /ed$/.test(w)) w = w.slice(0, -2);
    if (w.length > 3 && /([bdfgmnprt])\1$/.test(w)) w = w.slice(0, -1);
    if (w.length > 4 && /e$/.test(w)) w = w.slice(0, -1);
    return w;
  }

  function normalise(w) {
    return w.toLowerCase().replace(/[^a-z0-9'-]/g, "").replace(/^[-']+|[-']+$/g, "");
  }

  function tokenize(text) {
    var out = [], raw = String(text || "").split(/\s+/);
    for (var i = 0; i < raw.length; i++) {
      var w = normalise(raw[i]);
      if (w.length < 2 || STOP.has(w)) continue;
      out.push(stem(w));
    }
    return out;
  }

  /* ------------------------------------------------------------- ranking */

  function counts(tokens) {
    var m = new Map();
    for (var i = 0; i < tokens.length; i++) m.set(tokens[i], (m.get(tokens[i]) || 0) + 1);
    return m;
  }

  function buildIndex(docs) {
    var toks = docs.map(function (d) { return tokenize(d.title + " " + d.text); });
    var titleToks = docs.map(function (d) { return new Set(tokenize(d.title)); });
    var df = new Map();
    toks.forEach(function (t) {
      new Set(t).forEach(function (w) { df.set(w, (df.get(w) || 0) + 1); });
    });
    var lens = toks.map(function (t) { return t.length; });
    var total = lens.reduce(function (s, n) { return s + n; }, 0);
    return {
      docs: docs, tf: toks.map(counts), titleToks: titleToks, df: df,
      N: toks.length || 1, avgdl: total / (toks.length || 1) || 1, lens: lens
    };
  }

  function search(index, query, topK) {
    topK = topK || CFG.maxResults;
    var q = Array.from(new Set(tokenize(query)));
    if (!q.length) return [];
    var k1 = 1.5, b = 0.75, out = [];

    for (var i = 0; i < index.docs.length; i++) {
      var score = 0;
      for (var j = 0; j < q.length; j++) {
        var t = q[j], n = index.df.get(t) || 0;
        if (!n) continue;
        var idf = Math.log(1 + (index.N - n + 0.5) / (n + 0.5));
        var f = index.tf[i].get(t) || 0;
        if (f > 0) {
          score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * index.lens[i] / index.avgdl));
        }
        // A title hit matters a lot more here than a body hit: at whole-page
        // granularity the title is by far the strongest relevance signal.
        if (index.titleToks[i].has(t)) score += 1.4 * idf;
      }
      if (score > 0) out.push({ doc: index.docs[i], score: score, stems: q });
    }
    out.sort(function (a, c) { return c.score - a.score; });
    return out.slice(0, topK);
  }

  // Densest window of text around the query terms, like pagebot's snippet().
  function snippet(text, stems, size) {
    size = size || 32;
    var words = text.split(/\s+/);
    if (words.length <= size) return { words: words, head: false, tail: false };
    var want = new Set(stems), best = 0, bestScore = -1, i, j;
    for (i = 0; i + size <= words.length; i += 5) {
      var s = 0;
      for (j = i; j < i + size; j++) if (want.has(stem(normalise(words[j])))) s++;
      if (s > bestScore) { bestScore = s; best = i; }
    }
    return { words: words.slice(best, best + size), head: best > 0, tail: best + size < words.length };
  }

  // launcherLabel may be either plain text ("Search") or inline SVG markup for
  // an icon. Only ever called with our own constant from SEARCH_CONFIG, never
  // with anything a visitor supplied.
  function setLabel(el, label) {
    if (/^\s*</.test(label)) el.innerHTML = label;
    else el.textContent = label;
  }

  function pathLabel(url) {
    if (url === "/index.html") return "Home";
    if (url === "/author.html") return "PII";
    if (url === "/resources.html") return "Resources";
    var m = /^\/wiki\/vimwiki_html\/(.*)\.html?$/i.exec(url);
    if (!m) return url.replace(/^\//, "");
    return m[1].split("/").join(" › ");
  }

  /* ------------------------------------------------------------------ UI */

  var CSS = "" +
    ":host{all:initial}" +
    "*{box-sizing:border-box}" +
    ".fab{position:fixed;right:24px;bottom:24px;z-index:2147483000;width:48px;height:48px;border:0;" +
    "border-radius:50%;background:var(--se-accent);color:#fff;font:20px/48px system-ui,sans-serif;" +
    "cursor:pointer;padding:0;box-shadow:0 2px 8px rgba(0,0,0,.3);opacity:.85}" +
    ".fab:hover{opacity:1}" +
    ".fab.docked{display:none}" +
    ".panel{position:fixed;right:24px;bottom:24px;z-index:2147483001;width:min(420px,calc(100vw - 28px));" +
    "height:min(560px,calc(100vh - 48px));display:none;flex-direction:column;background:var(--se-bg);" +
    "color:var(--se-fg);border:1px solid rgba(107,79,42,.35);border-radius:12px;overflow:hidden;" +
    "box-shadow:0 10px 40px rgba(0,0,0,.32);font:15px/1.55 system-ui,-apple-system,sans-serif}" +
    ".panel.open{display:flex}" +
    ".hd{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;" +
    "background:var(--se-accent);color:#fff;font-weight:600;flex:0 0 auto}" +
    ".hd button{background:transparent;border:0;color:#fff;font-size:22px;line-height:1;cursor:pointer;padding:0 2px}" +
    ".row{flex:0 0 auto;display:flex;gap:8px;padding:10px;border-bottom:1px solid rgba(107,79,42,.25)}" +
    ".row input{flex:1;min-width:0;padding:9px 11px;border:1px solid rgba(107,79,42,.35);border-radius:8px;" +
    "font:15px system-ui,sans-serif;background:#fff;color:var(--se-fg)}" +
    ".row button{padding:9px 14px;border:0;border-radius:8px;background:var(--se-accent);color:#fff;" +
    "font:600 14px system-ui,sans-serif;cursor:pointer}" +
    ".results{flex:1 1 auto;overflow-y:auto;padding:8px}" +
    ".hint,.empty{padding:14px;font-size:13.5px;opacity:.7;text-align:center}" +
    ".res{display:block;padding:9px 11px;border-radius:8px;cursor:pointer;text-decoration:none;color:inherit}" +
    ".res:hover,.res.active{background:rgba(107,79,42,.12)}" +
    ".res .rt{font-weight:600;color:var(--se-accent);margin-bottom:2px}" +
    ".res .rp{font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;opacity:.6;margin-bottom:3px}" +
    ".res .rs{font-size:13px;opacity:.85;line-height:1.4}" +
    ".res mark{background:rgba(255,214,80,.75);color:inherit;padding:0 1px;border-radius:2px}" +
    "@media (max-width:600px){.fab{right:14px;bottom:14px;width:44px;height:44px;font-size:18px;line-height:44px}" +
    ".panel{right:14px;bottom:14px;width:calc(100vw - 28px);height:min(75vh,calc(100vh - 28px))}}";

  function init() {
    if (global.__sitesearch) return global.__sitesearch;

    var index = null, indexPromise = null;
    function ensureIndex() {
      if (index) return Promise.resolve(index);
      if (indexPromise) return indexPromise;
      indexPromise = fetch(CFG.indexUrl, { credentials: "same-origin" })
        .then(function (res) {
          if (!res.ok) throw new Error("search index fetch failed: " + res.status);
          return res.json();
        })
        .then(function (docs) {
          index = buildIndex(docs);
          return index;
        });
      return indexPromise;
    }

    var host = document.createElement("div");
    host.setAttribute("data-search-ignore", "");
    document.body.appendChild(host);
    var sh = host.attachShadow({ mode: "open" });

    var style = document.createElement("style");
    style.textContent = ":host{--se-accent:" + CFG.accent + ";--se-bg:" + CFG.panelBg +
      ";--se-fg:" + CFG.textColor + "}" + CSS;
    sh.appendChild(style);

    var fab = document.createElement("button");
    fab.className = "fab";
    fab.type = "button";
    setLabel(fab, CFG.launcherLabel);
    fab.title = CFG.launcherTitle;
    fab.setAttribute("aria-label", CFG.launcherTitle);
    sh.appendChild(fab);

    var panel = document.createElement("div");
    panel.className = "panel";
    panel.innerHTML =
      '<div class="hd"><span class="t"></span><button class="x" type="button" aria-label="Close">&times;</button></div>' +
      '<div class="row"><input type="text" /><button class="go" type="button">Go</button></div>' +
      '<div class="results"></div>';
    sh.appendChild(panel);
    panel.querySelector(".t").textContent = CFG.title;

    var results = panel.querySelector(".results"),
        input = panel.querySelector("input"),
        go = panel.querySelector(".go");
    input.placeholder = CFG.placeholder;

    // Dock the launcher into an existing button stack, if one was named.
    var docked = null;
    if (CFG.launcherSelector) {
      var holder = document.querySelector(CFG.launcherSelector);
      if (holder) {
        docked = document.createElement("button");
        docked.type = "button";
        docked.id = "sitesearch-launcher";
        setLabel(docked, CFG.launcherLabel);
        docked.title = CFG.launcherTitle;
        docked.setAttribute("aria-label", CFG.launcherTitle);
        holder.insertBefore(docked, holder.firstChild);
        fab.classList.add("docked");
      }
    }

    function renderHint(text) {
      results.innerHTML = "";
      var d = document.createElement("div");
      d.className = "hint";
      d.textContent = text;
      results.appendChild(d);
    }

    function renderResults(hits) {
      results.innerHTML = "";
      if (!hits.length) { renderHint("No pages match that."); return; }
      hits.forEach(function (hit, i) {
        var a = document.createElement("a");
        a.className = "res" + (i === 0 ? " active" : "");
        a.href = hit.doc.url;

        var rt = document.createElement("div");
        rt.className = "rt";
        rt.textContent = hit.doc.title;
        a.appendChild(rt);

        var rp = document.createElement("div");
        rp.className = "rp";
        rp.textContent = pathLabel(hit.doc.url);
        a.appendChild(rp);

        var rs = document.createElement("div");
        rs.className = "rs";
        var s = snippet(hit.doc.text, hit.stems);
        var want = new Set(hit.stems);
        if (s.head) rs.appendChild(document.createTextNode("… "));
        s.words.forEach(function (w, wi) {
          if (wi) rs.appendChild(document.createTextNode(" "));
          if (want.has(stem(normalise(w)))) {
            var m = document.createElement("mark");
            m.textContent = w;
            rs.appendChild(m);
          } else {
            rs.appendChild(document.createTextNode(w));
          }
        });
        if (s.tail) rs.appendChild(document.createTextNode(" …"));
        a.appendChild(rs);

        results.appendChild(a);
      });
    }

    var debounceTimer = null;
    function runSearch() {
      var q = input.value.trim();
      if (!q) { renderHint(CFG.emptyHint); return; }
      renderHint("Searching…");
      ensureIndex().then(function (idx) {
        if (input.value.trim() !== q) return; // a newer query has since been typed
        renderResults(search(idx, q));
      }).catch(function () {
        renderHint("Couldn't load the search index right now.");
      });
    }

    function activeIndex() {
      var items = results.querySelectorAll(".res");
      for (var i = 0; i < items.length; i++) if (items[i].classList.contains("active")) return i;
      return -1;
    }
    function setActive(i) {
      var items = results.querySelectorAll(".res");
      if (!items.length) return;
      i = Math.max(0, Math.min(items.length - 1, i));
      items.forEach(function (el) { el.classList.remove("active"); });
      items[i].classList.add("active");
      items[i].scrollIntoView({ block: "nearest" });
    }

    input.addEventListener("input", function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(runSearch, 150);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { close(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); setActive(activeIndex() + 1); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); setActive(activeIndex() - 1); return; }
      if (e.key === "Enter") {
        e.preventDefault();
        var active = results.querySelector(".res.active") || results.querySelector(".res");
        if (active) global.location.href = active.getAttribute("href");
      }
    });
    go.addEventListener("click", function () { clearTimeout(debounceTimer); runSearch(); input.focus(); });

    function open() {
      panel.classList.add("open");
      fab.style.display = "none";
      if (docked) docked.style.display = "none";
      if (!input.value.trim()) renderHint(CFG.emptyHint);
      input.focus();
      ensureIndex().catch(function () { /* surfaced on first real search */ });
    }
    function close() {
      panel.classList.remove("open");
      fab.style.display = "";
      if (docked) docked.style.display = "";
    }

    fab.addEventListener("click", open);
    if (docked) docked.addEventListener("click", open);
    panel.querySelector(".x").addEventListener("click", close);

    global.__sitesearch = { open: open, close: close, search: function (q, k) {
      return ensureIndex().then(function (idx) { return search(idx, q, k); });
    } };
    return global.__sitesearch;
  }

  var API = { tokenize: tokenize, stem: stem, buildIndex: buildIndex, search: search, init: init, config: CFG };
  global.SiteSearch = API;
  if (typeof module !== "undefined" && module.exports) module.exports = API;

  if (typeof document !== "undefined" && CFG.autoInit) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { init(); });
    else init();
  }
})(typeof window !== "undefined" ? window : globalThis);
