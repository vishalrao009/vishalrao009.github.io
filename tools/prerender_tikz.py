#!/usr/bin/env python3
"""
Pre-render <pre class="tikz"> blocks to inline SVG at build time.

Why: TikZJax renders TikZ in the browser, but to do so it must first download
~10.9 MB (a 9.8 MB gzipped TeX memory dump + a 612 KB WASM binary + 459 KB of
JS), served from S3 with no Cache-Control header, and it then compiles every
diagram *sequentially* in a single WASM instance. On a page with 30+ diagrams
the last one lands tens of seconds after the text. Compiling once here with
latex + dvisvgm turns each diagram into a ~5 KB inline SVG that is present the
moment the HTML parses -- and lets the page skip the 10.9 MB download entirely.

The script is idempotent: a block it has already rendered is marked
data-prerendered and is skipped on later runs. Every TikZ source it consumes is
archived to wiki/assets/tikz-sources.json first, so nothing is lost.

Usage:
    python3 tools/prerender_tikz.py [--jobs N] [--only SUBSTRING] [--dry-run]
"""

import argparse
import concurrent.futures
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_ROOT = os.path.join(ROOT, "wiki", "vimwiki_html")
ARCHIVE = os.path.join(ROOT, "wiki", "assets", "tikz-sources.json")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "prerender_tikz")

# Only <pre class="tikz"> ... </pre> with a body. The bare opening tag also
# appears inside a JS comment in every page's loader; requiring a closing tag
# and a \begin{tikzpicture} keeps us off it.
BLOCK_RE = re.compile(r'<pre class="tikz">(.*?)</pre>', re.S)

DOC_TEMPLATE = r"""\documentclass[dvisvgm,border=2pt]{standalone}
\usepackage{tikz}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{pifont}
%% A handful of diagrams label steps with circled characters typed directly as
%% Unicode. 8-bit latex has no glyph for those, so map them explicitly. \mbox
%% keeps them valid inside a math-mode node too.
\DeclareUnicodeCharacter{2460}{\mbox{\ding{172}}}
\DeclareUnicodeCharacter{2461}{\mbox{\ding{173}}}
\DeclareUnicodeCharacter{2462}{\mbox{\ding{174}}}
\DeclareUnicodeCharacter{2463}{\mbox{\ding{175}}}
\DeclareUnicodeCharacter{2464}{\mbox{\ding{176}}}
\DeclareUnicodeCharacter{24D0}{\mbox{\textcircled{\scriptsize a}}}
\DeclareUnicodeCharacter{24D1}{\mbox{\textcircled{\scriptsize b}}}
\DeclareUnicodeCharacter{24D2}{\mbox{\textcircled{\scriptsize c}}}
\DeclareUnicodeCharacter{24D3}{\mbox{\textcircled{\scriptsize d}}}
%(preamble)s
\begin{document}
%(body)s
\end{document}
"""

# The in-browser fallback loader that replaces the unconditional TikZJax tags.
LOADER = """    <!-- 1. TikZ diagrams are pre-rendered to inline SVG at build time by
         tools/prerender_tikz.py. This only handles blocks that are *not* yet
         pre-rendered (e.g. a page edited by hand since the last build): it
         converts them for TikZJax and pulls TikZJax in on demand. When every
         block is pre-rendered -- the normal case -- nothing below the first
         line runs, and the page skips TikZJax's ~10.9 MB download. -->
    <script>
        (function () {
            var pending = document.querySelectorAll('pre.tikz:not([data-prerendered])');
            if (!pending.length) return;
            pending.forEach(function (pre) {
                var s = document.createElement('script');
                s.type = 'text/tikz';
                s.textContent = pre.textContent; // browser decodes HTML entities here
                pre.textContent = '';
                pre.appendChild(s); // keep <pre class="tikz"> as the container so its
                                    // text-align:center still applies to the SVG tikzjax inserts
            });
            var css = document.createElement('link');
            css.rel = 'stylesheet';
            css.href = 'https://tikzjax.com/v1/fonts.css';
            document.head.appendChild(css);
            var js = document.createElement('script');
            js.src = 'https://tikzjax.com/v1/tikzjax.js';
            document.body.appendChild(js);
        })();
    </script>
"""

OLD_CONVERTER_RE = re.compile(
    r'[ \t]*<!-- 1\. Turn vimwiki .*?-->\s*<script>\s*document\.querySelectorAll\(\'pre\.tikz\'\).*?</script>\n',
    re.S,
)
OLD_TIKZJAX_RE = re.compile(
    r'[ \t]*<!-- 3\. TikZJax:[^\n]*-->\n[ \t]*<script src="https://tikzjax\.com/v1/tikzjax\.js"></script>\n'
)
OLD_FONTS_CSS_RE = re.compile(
    r'[ \t]*<!-- TikZJax fonts[^\n]*-->\n'
    r'[ \t]*<link rel="stylesheet" type="text/css" href="https://tikzjax\.com/v1/fonts\.css">\n'
)


def split_preamble(src):
    """Everything before the first \\begin{tikzpicture} is preamble material
    (\\usetikzlibrary, \\definecolor, \\tikzset ...); the rest is the picture."""
    i = src.find(r"\begin{tikzpicture}")
    if i == -1:
        return None, None
    return src[:i].strip(), src[i:].strip()


def prefix_ids(svg, pfx):
    """dvisvgm emits ids like 'page1' and glyph ids like 'g0-88'. Those repeat
    across every diagram, and a duplicate id in one document makes every
    xlink:href='#g0-88' resolve to the first match -- i.e. the wrong glyph. So
    namespace every id per diagram."""
    ids = {m.group(2) for m in re.finditer(r"""\bid=(["'])(.*?)\1""", svg)}
    if not ids:
        return svg

    def rep_id(m):
        q, v = m.group(1), m.group(2)
        return "id=%s%s%s%s" % (q, pfx, v, q) if v in ids else m.group(0)

    def rep_href(m):
        a, q, v = m.group(1), m.group(2), m.group(3)
        return "%s=%s#%s%s%s" % (a, q, pfx, v, q) if v in ids else m.group(0)

    def rep_url(m):
        v = m.group(1)
        return "url(#%s%s)" % (pfx, v) if v in ids else m.group(0)

    svg = re.sub(r"""\bid=(["'])(.*?)\1""", rep_id, svg)
    svg = re.sub(r"""\b((?:xlink:)?href)=(["'])#(.*?)\2""", rep_href, svg)
    svg = re.sub(r"url\(#([^)]+)\)", rep_url, svg)
    return svg


def render(src):
    """TikZ source -> inline SVG string. Raises RuntimeError with the TeX log
    excerpt on failure."""
    digest = hashlib.sha1(src.encode("utf-8")).hexdigest()
    cached = os.path.join(CACHE, digest + ".svg")
    if os.path.exists(cached):
        with open(cached, encoding="utf-8") as fh:
            return fh.read()

    preamble, body = split_preamble(src)
    if body is None:
        raise RuntimeError("no \\begin{tikzpicture} in block")

    tmp = tempfile.mkdtemp(prefix="tikz-")
    try:
        tex = os.path.join(tmp, "j.tex")
        with open(tex, "w", encoding="utf-8") as fh:
            fh.write(DOC_TEMPLATE % {"preamble": preamble, "body": body})
        r = subprocess.run(
            ["latex", "-interaction=nonstopmode", "-halt-on-error",
             "-no-shell-escape", "j.tex"],
            cwd=tmp, capture_output=True, text=True, timeout=90,
        )
        dvi = os.path.join(tmp, "j.dvi")
        if r.returncode != 0 or not os.path.exists(dvi):
            log = ""
            logp = os.path.join(tmp, "j.log")
            if os.path.exists(logp):
                lines = open(logp, encoding="utf-8", errors="replace").read().splitlines()
                err = [i for i, l in enumerate(lines) if l.startswith("!")]
                if err:
                    log = "\n".join(lines[err[0]:err[0] + 6])
            raise RuntimeError("latex failed: " + (log or r.stdout[-400:]))

        svgp = os.path.join(tmp, "j.svg")
        r = subprocess.run(
            ["dvisvgm", "--no-fonts", "--relative", "--exact",
             "--output=" + svgp, dvi],
            cwd=tmp, capture_output=True, text=True, timeout=90,
        )
        if r.returncode != 0 or not os.path.exists(svgp):
            raise RuntimeError("dvisvgm failed: " + (r.stderr or r.stdout)[-400:])

        svg = open(svgp, encoding="utf-8").read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg)
    svg = re.sub(r"<!--.*?-->\s*", "", svg, flags=re.S)
    svg = prefix_ids(svg.strip(), "t%s-" % digest[:8])

    os.makedirs(CACHE, exist_ok=True)
    with open(cached, "w", encoding="utf-8") as fh:
        fh.write(svg)
    return svg


def find_files(only=None):
    out = []
    for dp, _, fn in os.walk(HTML_ROOT):
        for f in sorted(fn):
            if not f.endswith(".html"):
                continue
            p = os.path.join(dp, f)
            if only and only not in p:
                continue
            with open(p, encoding="utf-8", errors="replace") as fh:
                if BLOCK_RE.search(fh.read()):
                    out.append(p)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", help="only files whose path contains this")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = find_files(args.only)
    print("files with tikz blocks: %d" % len(files), flush=True)

    # ---- collect every distinct source, archive, then render in parallel ----
    per_file = {}
    for p in files:
        s = open(p, encoding="utf-8").read()
        srcs = [html.unescape(b).strip() for b in BLOCK_RE.findall(s)]
        per_file[p] = srcs

    archive = {}
    if os.path.exists(ARCHIVE):
        archive = json.load(open(ARCHIVE, encoding="utf-8"))
    for p, srcs in per_file.items():
        rel = os.path.relpath(p, ROOT)
        for s in srcs:
            archive.setdefault(hashlib.sha1(s.encode("utf-8")).hexdigest(),
                               {"source": s, "seen_in": []})
    for p, srcs in per_file.items():
        rel = os.path.relpath(p, ROOT)
        for s in srcs:
            e = archive[hashlib.sha1(s.encode("utf-8")).hexdigest()]
            if rel not in e["seen_in"]:
                e["seen_in"].append(rel)
    if not args.dry_run:
        os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
        with open(ARCHIVE, "w", encoding="utf-8") as fh:
            json.dump(archive, fh, indent=1, ensure_ascii=False, sort_keys=True)

    uniq = sorted({s for srcs in per_file.values() for s in srcs})
    print("distinct diagrams: %d (total blocks %d)"
          % (len(uniq), sum(len(v) for v in per_file.values())), flush=True)

    rendered, failed = {}, {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(render, s): s for s in uniq}
        for fut in concurrent.futures.as_completed(futs):
            s = futs[fut]
            done += 1
            try:
                rendered[s] = fut.result()
            except Exception as e:
                failed[s] = str(e)
            if done % 25 == 0 or done == len(uniq):
                print("  rendered %d/%d (%d failed)"
                      % (done, len(uniq), len(failed)), flush=True)

    if failed:
        print("\n!! %d diagram(s) failed to compile:" % len(failed), flush=True)
        for s, e in list(failed.items())[:10]:
            print("  --- %s\n      %s" % (s.splitlines()[0][:90], e.replace("\n", "\n      ")))

    if args.dry_run:
        print("\ndry run: no files written")
        return 0 if not failed else 1

    # ---- rewrite the HTML ----
    changed = 0
    for p, srcs in per_file.items():
        s = open(p, encoding="utf-8").read()
        orig = s
        n_ok = 0

        # A page may use the very same diagram twice. The cached SVG's ids are
        # namespaced by source hash, so two copies would share ids -- invalid,
        # and <use href='#...'> would bind to whichever came first. Give every
        # repeat occurrence a second, occurrence-scoped prefix.
        seen = {}

        def sub(m):
            nonlocal n_ok
            src = html.unescape(m.group(1)).strip()
            svg = rendered.get(src)
            if svg is None:
                return m.group(0)  # leave it for the in-browser fallback
            i = seen.get(src, 0)
            seen[src] = i + 1
            if i:
                svg = prefix_ids(svg, "r%d-" % i)
            n_ok += 1
            return '<pre class="tikz" data-prerendered="1">\n%s\n</pre>' % svg

        s = BLOCK_RE.sub(sub, s)

        # Swap the unconditional TikZJax tags for the on-demand loader.
        if OLD_CONVERTER_RE.search(s):
            s = OLD_CONVERTER_RE.sub(LOADER, s, count=1)
        s = OLD_TIKZJAX_RE.sub("", s)
        s = OLD_FONTS_CSS_RE.sub("", s)

        if s != orig:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(s)
            changed += 1
            print("  %-70s %d/%d inlined" % (os.path.relpath(p, ROOT)[-70:], n_ok, len(srcs)), flush=True)

    print("\ndone: %d files rewritten, %d diagrams failed" % (changed, len(failed)), flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
