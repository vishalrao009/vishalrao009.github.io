/*!
 * pagebot.js — retrieval-only. Answers questions using the text of the page it
 * sits on. No server, no API, no network calls at all.
 *
 * Load it last:  <script src="/wiki/assets/pagebot.js"></script>
 * Configure it by setting window.PAGEBOT_CONFIG = {...} BEFORE that tag.
 *
 * How it works: the page is split into passages under their heading trail,
 * ranked against the question with BM25, and the best passages are shown with
 * the matching words marked and a link that scrolls to the source paragraph.
 *
 * The index is built lazily, the first time the panel is opened, so MathJax,
 * TikZJax and Mermaid have all finished rewriting the DOM by then.
 */
(function (global) {
  "use strict";

  var DEFAULTS = {
    rootSelector: null,        // null => <main>, then <article>, then <body>
    extraSkip: "",             // extra CSS selectors to leave out of the index
    maxChunkChars: 700,
    topK: 6,                   // passages ranked
    results: 3,                // passages shown
    snippetWords: 45,
    title: "Ask this page",
    placeholder: "Ask about this page\u2026",
    greeting: "Ask a question and I'll find the part of this page that answers it. I only read this page.",
    accent: "#6b4f2a",
    panelBg: "#fbf6e9",
    textColor: "#2b2620",
    launcherSelector: null,    // dock the launcher inside an existing element
    launcherLabel: "?",
    launcherTitle: "Ask this page",
    autoInit: true
  };

  var CFG = Object.assign({}, DEFAULTS, global.PAGEBOT_CONFIG || {});

  /* ---------------------------------------------------------------- text */

  var STOP = new Set(("a an the and or but if then else of in on at to for from by " +
    "with as is are was were be been being it its this that these those there here " +
    "what which who whom whose how why when where can could should would may might " +
    "will shall do does did done not no nor so than too very just also into over " +
    "under again further once about we you i they he she them his her our your my " +
    "have has had").split(" "));

  // Light, deliberately imperfect stemmer. The only requirement is that it maps
  // query words and page words the SAME way, so the rules must compose in order.
  function stem(w) {
    if (w.length > 4 && /ies$/.test(w)) w = w.slice(0, -3) + "y";
    else if (w.length > 4 && /(sses|shes|ches|xes)$/.test(w)) w = w.slice(0, -2);
    else if (w.length > 3 && /s$/.test(w) && !/ss$/.test(w)) w = w.slice(0, -1);
    if (w.length >= 7 && /ing$/.test(w)) w = w.slice(0, -3);   // keep >=4 chars of stem
    else if (w.length >= 6 && /ed$/.test(w)) w = w.slice(0, -2);
    if (w.length > 3 && /([bdfgmnprt])\1$/.test(w)) w = w.slice(0, -1);  // fitt -> fit
    if (w.length > 4 && /e$/.test(w)) w = w.slice(0, -1);                // estimate -> estimat
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

  /* ------------------------------------------------------------ chunking */

  var BLOCK_SEL = "h1,h2,h3,h4,h5,h6,p,li,dt,dd,td,th,pre,blockquote,figcaption";
  var SKIP_SEL = "nav,footer,header,aside,script,style,noscript,form,button,[data-pagebot-ignore]";
  // Removed from a block before its text is read: rendered maths leaves behind
  // assistive MathML that would otherwise pollute the index with symbol noise.
  var STRIP_SEL = "mjx-assistive-mml,.MJX_Assistive_MathML,mjx-container,math,svg,script,style,[data-pagebot-ignore]";

  function skipSel() {
    return CFG.extraSkip ? SKIP_SEL + "," + CFG.extraSkip : SKIP_SEL;
  }

  function pickRoot() {
    if (CFG.rootSelector) {
      var r = document.querySelector(CFG.rootSelector);
      if (r) return r;
    }
    return document.querySelector("main") || document.querySelector("article") || document.body;
  }

  function matchesUp(el, root, sel) {
    var p = el;
    while (p && p !== root) {
      if (p.matches && p.matches(sel)) return true;
      p = p.parentElement;
    }
    return false;
  }

  function isNested(el, root) {
    var p = el.parentElement;
    while (p && p !== root) {
      if (p.matches && p.matches(BLOCK_SEL)) return true;
      p = p.parentElement;
    }
    return false;
  }

  function blockText(el) {
    var c = el.cloneNode(true);
    var junk = c.querySelectorAll(STRIP_SEL);
    for (var i = 0; i < junk.length; i++) junk[i].parentNode.removeChild(junk[i]);
    return (c.textContent || "").replace(/\s+/g, " ").trim();
  }

  // Walks the page in document order, grouping text under its heading trail.
  function extractChunks(root) {
    root = root || pickRoot();
    var sel = skipSel();
    var nodes = root.querySelectorAll(BLOCK_SEL);
    var chunks = [], trail = [], cur = null;

    function flush() {
      if (cur && cur.text.length > 25) chunks.push(cur);
      cur = null;
    }

    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (matchesUp(el, root, sel) || isNested(el, root)) continue;
      var txt = blockText(el);
      if (!txt) continue;

      var h = /^H([1-6])$/.exec(el.tagName);
      if (h) {
        flush();
        var lvl = parseInt(h[1], 10);
        trail = trail.slice(0, lvl - 1);
        trail[lvl - 1] = txt;
        trail = trail.filter(Boolean);
        continue;
      }
      if (!cur) cur = { heading: trail.join(" \u203a "), text: "", el: el };
      cur.text += (cur.text ? " " : "") + txt;
      if (cur.text.length >= CFG.maxChunkChars) flush();
    }
    flush();

    if (!chunks.length) {
      var all = blockText(root);
      for (var j = 0; j < all.length; j += CFG.maxChunkChars) {
        chunks.push({ heading: document.title || "", text: all.slice(j, j + CFG.maxChunkChars), el: root });
      }
    }
    return chunks;
  }

  /* ------------------------------------------------------------- ranking */

  function counts(tokens) {
    var m = new Map();
    for (var i = 0; i < tokens.length; i++) m.set(tokens[i], (m.get(tokens[i]) || 0) + 1);
    return m;
  }

  function buildIndex(chunks) {
    var docs = chunks.map(function (c) { return tokenize(c.heading + " " + c.text); });
    var heads = chunks.map(function (c) { return new Set(tokenize(c.heading)); });
    var df = new Map();
    docs.forEach(function (d) {
      new Set(d).forEach(function (t) { df.set(t, (df.get(t) || 0) + 1); });
    });
    var lens = docs.map(function (d) { return d.length; });
    var total = lens.reduce(function (s, n) { return s + n; }, 0);
    return {
      chunks: chunks, tf: docs.map(counts), heads: heads, df: df,
      N: docs.length || 1, avgdl: total / (docs.length || 1) || 1, lens: lens
    };
  }

  function search(index, query, topK) {
    topK = topK || CFG.topK;
    var q = Array.from(new Set(tokenize(query)));
    if (!q.length) return [];
    var k1 = 1.5, b = 0.75, out = [];

    for (var i = 0; i < index.chunks.length; i++) {
      var score = 0, matched = 0;
      for (var j = 0; j < q.length; j++) {
        var t = q[j], n = index.df.get(t) || 0;
        if (!n) continue;
        var idf = Math.log(1 + (index.N - n + 0.5) / (n + 0.5));
        var f = index.tf[i].get(t) || 0;
        if (f > 0) {
          matched++;
          score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * index.lens[i] / index.avgdl));
        }
        if (index.heads[i].has(t)) score += 0.5 * idf;   // a heading hit means a lot
      }
      if (score > 0) out.push({ chunk: index.chunks[i], score: score, matched: matched, stems: q });
    }
    out.sort(function (a, c) { return c.score - a.score; });
    return out.slice(0, topK);
  }

  // Picks the densest window of the passage rather than always the opening words.
  function snippet(text, stems, size) {
    size = size || CFG.snippetWords;
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

  /* ------------------------------------------------------------------ UI */

  function flash(el) {
    if (!el || !el.scrollIntoView) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    var prevBg = el.style.backgroundColor, prevTr = el.style.transition;
    el.style.transition = "background-color .35s ease";
    el.style.backgroundColor = "rgba(255, 214, 80, .6)";
    setTimeout(function () {
      el.style.backgroundColor = prevBg;
      setTimeout(function () { el.style.transition = prevTr; }, 400);
    }, 2200);
  }

  var CSS = "" +
    ":host{all:initial}" +
    "*{box-sizing:border-box}" +
    ".fab{position:fixed;right:24px;bottom:24px;z-index:2147483000;width:48px;height:48px;border:0;" +
    "border-radius:50%;background:var(--pb-accent);color:#fff;font:22px/48px system-ui,sans-serif;" +
    "cursor:pointer;padding:0;box-shadow:0 2px 8px rgba(0,0,0,.3);opacity:.85}" +
    ".fab:hover{opacity:1}" +
    ".fab.docked{display:none}" +
    ".panel{position:fixed;right:24px;bottom:24px;z-index:2147483001;width:min(400px,calc(100vw - 28px));" +
    "height:min(540px,calc(100vh - 48px));display:none;flex-direction:column;background:var(--pb-bg);" +
    "color:var(--pb-fg);border:1px solid rgba(107,79,42,.35);border-radius:12px;overflow:hidden;" +
    "box-shadow:0 10px 40px rgba(0,0,0,.32);font:15px/1.55 system-ui,-apple-system,sans-serif}" +
    ".panel.open{display:flex}" +
    ".hd{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;" +
    "background:var(--pb-accent);color:#fff;font-weight:600;flex:0 0 auto}" +
    ".hd button{background:transparent;border:0;color:#fff;font-size:22px;line-height:1;cursor:pointer;padding:0 2px}" +
    ".log{flex:1 1 auto;overflow-y:auto;padding:12px 14px;display:flex;flex-direction:column;gap:10px}" +
    ".msg{max-width:92%;padding:8px 11px;border-radius:10px;word-wrap:break-word}" +
    ".me{align-self:flex-end;background:var(--pb-accent);color:#fff}" +
    ".bot{align-self:flex-start;background:rgba(107,79,42,.12)}" +
    ".src{font-size:13.5px;background:rgba(255,255,255,.6);border-left:3px solid var(--pb-accent);" +
    "padding:8px 10px;border-radius:0 8px 8px 0}" +
    ".src .h{display:block;font:600 11px/1.4 system-ui,sans-serif;text-transform:uppercase;" +
    "letter-spacing:.05em;opacity:.65;margin-bottom:3px}" +
    ".src mark{background:rgba(255,214,80,.75);color:inherit;padding:0 1px;border-radius:2px}" +
    ".src .jump{display:inline-block;margin-top:5px;color:var(--pb-accent);cursor:pointer;" +
    "text-decoration:underline;font-size:12.5px}" +
    ".note{font-size:12px;opacity:.6;text-align:center}" +
    ".row{flex:0 0 auto;display:flex;gap:8px;padding:10px;border-top:1px solid rgba(107,79,42,.25)}" +
    ".row input{flex:1;min-width:0;padding:9px 11px;border:1px solid rgba(107,79,42,.35);border-radius:8px;" +
    "font:15px system-ui,sans-serif;background:#fff;color:var(--pb-fg)}" +
    ".row button{padding:9px 14px;border:0;border-radius:8px;background:var(--pb-accent);color:#fff;" +
    "font:600 14px system-ui,sans-serif;cursor:pointer}" +
    "@media (max-width:600px){.fab{right:14px;bottom:14px;width:44px;height:44px;font-size:20px;line-height:44px}" +
    ".panel{right:14px;bottom:14px;width:calc(100vw - 28px);height:min(70vh,calc(100vh - 28px))}}";

  function init() {
    if (global.__pagebot) return global.__pagebot;

    var chunks = null, index = null;
    function ensureIndex() {
      if (!index) { chunks = extractChunks(); index = buildIndex(chunks); }
      return index;
    }

    var host = document.createElement("div");
    host.setAttribute("data-pagebot-ignore", "");
    document.body.appendChild(host);
    var sh = host.attachShadow({ mode: "open" });

    var style = document.createElement("style");
    style.textContent = ":host{--pb-accent:" + CFG.accent + ";--pb-bg:" + CFG.panelBg +
      ";--pb-fg:" + CFG.textColor + "}" + CSS;
    sh.appendChild(style);

    var fab = document.createElement("button");
    fab.className = "fab";
    fab.type = "button";
    fab.textContent = CFG.launcherLabel;
    fab.title = CFG.launcherTitle;
    fab.setAttribute("aria-label", CFG.launcherTitle);
    sh.appendChild(fab);

    var panel = document.createElement("div");
    panel.className = "panel";
    panel.innerHTML =
      '<div class="hd"><span class="t"></span><button class="x" type="button" aria-label="Close">&times;</button></div>' +
      '<div class="log"></div>' +
      '<div class="row"><input type="text" /><button class="go" type="button">Ask</button></div>';
    sh.appendChild(panel);
    panel.querySelector(".t").textContent = CFG.title;

    var log = panel.querySelector(".log"),
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
        docked.id = "pagebot-launcher";
        docked.textContent = CFG.launcherLabel;
        docked.title = CFG.launcherTitle;
        docked.setAttribute("aria-label", CFG.launcherTitle);
        docked.setAttribute("data-pagebot-ignore", "");
        holder.insertBefore(docked, holder.firstChild);
        fab.classList.add("docked");
      }
    }

    function scroll() { log.scrollTop = log.scrollHeight; }

    function add(cls, text) {
      var d = document.createElement("div");
      d.className = "msg " + cls;
      d.textContent = text;
      log.appendChild(d); scroll();
      return d;
    }

    function addSource(hit) {
      var d = document.createElement("div");
      d.className = "src";
      if (hit.chunk.heading) {
        var h = document.createElement("span");
        h.className = "h";
        h.textContent = hit.chunk.heading;
        d.appendChild(h);
      }
      var body = document.createElement("span");
      var s = snippet(hit.chunk.text, hit.stems);
      var want = new Set(hit.stems);
      if (s.head) body.appendChild(document.createTextNode("\u2026 "));
      s.words.forEach(function (w, i) {
        if (i) body.appendChild(document.createTextNode(" "));
        if (want.has(stem(normalise(w)))) {
          var m = document.createElement("mark");
          m.textContent = w;
          body.appendChild(m);
        } else {
          body.appendChild(document.createTextNode(w));
        }
      });
      if (s.tail) body.appendChild(document.createTextNode(" \u2026"));
      d.appendChild(body);

      var jump = document.createElement("span");
      jump.className = "jump";
      jump.setAttribute("role", "button");
      jump.tabIndex = 0;
      jump.textContent = "jump to it \u2197";
      jump.addEventListener("click", function () { flash(hit.chunk.el); });
      jump.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); flash(hit.chunk.el); }
      });
      d.appendChild(document.createElement("br"));
      d.appendChild(jump);

      log.appendChild(d); scroll();
    }

    function ask() {
      var q = input.value.trim();
      if (!q) return;
      input.value = "";
      add("me", q);
      var hits = search(ensureIndex(), q);
      if (!hits.length) {
        add("bot", "Nothing on this page matches that. Try the words the page itself would use.");
        return;
      }
      add("bot", hits.length === 1 ? "This looks like the relevant part:" : "The closest parts of this page:");
      hits.slice(0, CFG.results).forEach(addSource);
    }

    function open() {
      ensureIndex();
      panel.classList.add("open");
      fab.style.display = "none";
      if (docked) docked.style.display = "none";
      if (!log.childNodes.length) add("bot", CFG.greeting);
      input.focus();
    }
    function close() {
      panel.classList.remove("open");
      fab.style.display = "";
      if (docked) docked.style.display = "";
    }

    fab.addEventListener("click", open);
    if (docked) docked.addEventListener("click", open);
    panel.querySelector(".x").addEventListener("click", close);
    go.addEventListener("click", ask);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") ask();
      else if (e.key === "Escape") close();
    });

    global.__pagebot = {
      open: open, close: close,
      search: function (q, k) { return search(ensureIndex(), q, k); },
      get chunks() { ensureIndex(); return chunks; },
      reindex: function () { index = null; return ensureIndex(); }
    };
    return global.__pagebot;
  }

  var API = { tokenize: tokenize, stem: stem, extractChunks: extractChunks,
              buildIndex: buildIndex, search: search, snippet: snippet, init: init, config: CFG };
  global.PageBot = API;
  if (typeof module !== "undefined" && module.exports) module.exports = API;

  if (typeof document !== "undefined" && CFG.autoInit) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { init(); });
    else init();
  }
})(typeof window !== "undefined" ? window : globalThis);
