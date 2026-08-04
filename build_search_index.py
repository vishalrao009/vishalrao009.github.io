#!/usr/bin/env python3
"""
build_search_index.py
----------------------
Builds wiki/assets/search-index.json: a single JSON file listing every
searchable page on the site (url, title, and a text excerpt). The site-wide
search box (wiki/assets/search.js, wired up on every page) fetches this file
once and ranks pages against the visitor's query with BM25, entirely in the
browser — no server, no API.

WHY A SEPARATE INDEX FILE INSTEAD OF SEARCHING LIVE PAGES?
    The search box needs to look across all ~400+ pages at once, not just the
    one the visitor is on (that's what the existing "Ask this page" button
    already does, per-page). Fetching every page over the network on every
    keystroke isn't practical, so instead this script pre-extracts a text
    excerpt from each page, once, into one compact JSON file the browser can
    fetch and search entirely client-side.

USAGE
    Run it from the repo root after you regenerate/upload the wiki HTML,
    same as update_whats_new.py:
        python3 build_search_index.py
    Then commit wiki/assets/search-index.json together with the changed HTML.

    Options:
        --max-chars N   text excerpt length per page (default 2500)
        --dry-run       print what would be indexed without writing the file
"""

import argparse
import html
import json
import os
import re
import sys

# ---- configuration ---------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
WIKI_DIR = os.path.join("wiki", "vimwiki_html")
OUT_PATH = os.path.join("wiki", "assets", "search-index.json")

# Folders that are never indexed:
#   /old_wiki/   — a deprecated, largely-duplicate copy of the wiki
#   /encrypted/  — password-protected content; must not leak into a public
#                  search index
#   /Images/, /images/, /diary/images/ — media folders, not content pages
EXCLUDE_DIR_PARTS = ("/old_wiki/", "/encrypted/", "/Images/", "/images/", "/diary/images/")

# Root-level pages to include. The repo root also has several dated/backup
# copies (index_0721.html, old_index.html, "index (9).html", ...) that were
# never linked from anywhere and shouldn't show up in search results, so this
# is an explicit whitelist rather than "every .html file in the root".
ROOT_PAGES = ["index.html", "author.html", "resources.html"]

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
# Bounded first choice: stop at the floating-buttons / script markers that
# follow the real article body in every page, so button labels, the
# breadcrumb script, and Google Translate/search widget chrome never leak
# into the indexed text. Falls back to "rest of file" if a page doesn't
# follow that layout.
CONTENT_RE_BOUNDED = re.compile(
    r'<div id="content"[^>]*>(.*?)<div class="floating-btns',
    re.IGNORECASE | re.DOTALL)
CONTENT_RE_LOOSE = re.compile(r'<div id="content"[^>]*>(.*)', re.IGNORECASE | re.DOTALL)
CONTAINER_RE_BOUNDED = re.compile(
    r'<div class="container"[^>]*>(.*?)<script src="script\.js"',
    re.IGNORECASE | re.DOTALL)
CONTAINER_RE_LOOSE = re.compile(r'<div class="container"[^>]*>(.*)', re.IGNORECASE | re.DOTALL)
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
BAD_TITLES = {"", "index", "contents"}


# ---- helpers ---------------------------------------------------------------

def clean_text(s):
    s = SCRIPT_STYLE_RE.sub(" ", s)
    s = COMMENT_RE.sub(" ", s)
    s = TAG_RE.sub(" ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def page_title(raw_html, url):
    m = TITLE_RE.search(raw_html)
    if m:
        t = clean_text(m.group(1))
        if t.lower() not in BAD_TITLES:
            return t
    m = H1_RE.search(raw_html)
    if m:
        t = clean_text(m.group(1))
        if t.lower() not in BAD_TITLES:
            return t
    name = os.path.basename(url)
    if re.match(r"^index\.html?$", name, re.IGNORECASE):
        name = os.path.basename(os.path.dirname(url)) or name
    name = re.sub(r"\.html?$", "", name, flags=re.IGNORECASE)
    return name.replace("_", " ").strip() or "Page"


def page_body(raw_html, max_chars):
    # Prefer the actual article body over chrome (breadcrumb, floating
    # buttons, footer nav): vimwiki pages wrap it in <div id="content">,
    # the hand-written root pages use <div class="container">.
    m = (CONTENT_RE_BOUNDED.search(raw_html) or CONTENT_RE_LOOSE.search(raw_html)
         or CONTAINER_RE_BOUNDED.search(raw_html) or CONTAINER_RE_LOOSE.search(raw_html))
    section = m.group(1) if m else raw_html
    text = clean_text(section)
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text


def should_skip_wiki(url):
    probe = "/" + url
    return any(part in probe for part in EXCLUDE_DIR_PARTS)


def collect_pages(max_chars):
    pages = []

    for fn in ROOT_PAGES:
        full = os.path.join(REPO_ROOT, fn)
        if not os.path.isfile(full):
            continue
        with open(full, "r", encoding="utf-8", errors="surrogateescape") as fh:
            raw = fh.read()
        pages.append({
            "url": "/" + fn,
            "title": page_title(raw, fn),
            "text": page_body(raw, max_chars),
        })

    base = os.path.join(REPO_ROOT, WIKI_DIR)
    for root, _dirs, files in os.walk(base):
        for fn in sorted(files):
            if not fn.lower().endswith(".html"):
                continue
            full = os.path.join(root, fn)
            url = os.path.relpath(full, REPO_ROOT).replace(os.sep, "/")
            if should_skip_wiki(url):
                continue
            with open(full, "r", encoding="utf-8", errors="surrogateescape") as fh:
                raw = fh.read()
            text = page_body(raw, max_chars)
            if not text:
                continue
            pages.append({
                "url": "/" + url,
                "title": page_title(raw, url),
                "text": text,
            })

    pages.sort(key=lambda p: p["url"])
    return pages


# ---- main -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-chars", type=int, default=2500,
                     help="text excerpt length per page (default 2500)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pages = collect_pages(args.max_chars)
    print("Indexed %d page(s)." % len(pages))

    payload = json.dumps(pages, ensure_ascii=False, separators=(",", ":"))
    size_kb = len(payload.encode("utf-8")) / 1024
    print("Index size: %.1f KB" % size_kb)

    out = os.path.join(REPO_ROOT, OUT_PATH)
    if args.dry_run:
        print("(dry run — %s not written)" % OUT_PATH)
        return
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(payload)
        fh.write("\n")
    print("Wrote %s" % OUT_PATH)


if __name__ == "__main__":
    sys.exit(main())
