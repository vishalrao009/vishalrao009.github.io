#!/usr/bin/env python3
"""
update_whats_new.py
-------------------
Maintains the "Recently added" panels on resources.html (Resources section)
and author.html (Blogs section). Each entry is listed as

    <page title> (7 Aug 2026)

where the date is the page's first-seen date from the manifest (see below),
wrapped in a <span class="new-date"> so it can be styled independently.

WHY A MANIFEST INSTEAD OF FILE DATES?
    You regenerate every wiki HTML file each time you publish, so file
    modification times all change together and cannot tell us what is new.
    Instead we keep a small manifest, updates.json, that records the FIRST
    date each page URL was ever seen. Regenerating the HTML never touches the
    manifest, so those dates are stable. Only a URL that has never been seen
    before is treated as new. On a page's first appearance we date it from
    your git history (the commit that first added the file); if it isn't in
    git yet, we use today's date.

USAGE
    Run it from the repo root after you regenerate/upload, before committing:
        python3 update_whats_new.py
    Then commit updates.json together with the changed HTML.

    Options:
        --max N     how many items to list per panel (default 6)
        --dry-run   print what would change without writing files
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys

# ---- configuration ---------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
WIKI_DIR = os.path.join("wiki", "vimwiki_html")
MANIFEST = "updates.json"

# Folders we never advertise as "new". Add or remove entries to taste.
#   "/Research_work/diary/" holds ~120 daily research logs; excluded so they
#   don't bury your actual notes. Blogs/diary (your blog posts) is kept.
EXCLUDE_DIR_PARTS = (
    "/old_wiki/", "/encrypted/", "/Images/", "/images/",
    "/diary/images/", "/Research_work/diary/",
)
# Filenames that are noise rather than content.
EXCLUDE_FILENAMES = {"diary.html"}
# Filename patterns (regex) to skip — e.g. machine-generated parameter dumps.
EXCLUDE_FILENAME_RES = (re.compile(r"\.param\.html$", re.IGNORECASE),)

# Which section each page belongs to, and which page shows that section.
#   Resources panel  -> resources.html
#   Blogs panel      -> author.html
TARGETS = {
    "Resources": "resources.html",
    "Blogs": "author.html",
}

H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


# ---- helpers ---------------------------------------------------------------

def clean_text(s):
    s = TAG_RE.sub("", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


BAD_TITLES = {"", "index", "contents"}

# Diary pages are named after their date, so vimwiki sets <title> to e.g.
# "2026-08-06". That makes a useless label in the panel (and the panel already
# prints the date separately in brackets), so for date-named pages we use the
# entry's own heading instead - "The Debate of Ashtavakra and Bandi (6 Aug 2026)"
# rather than "2026-08-06 (6 Aug 2026)".
DATE_TITLE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def first_heading(content):
    """First <h1> that isn't vimwiki's auto-generated "Contents" heading."""
    for m in H1_RE.finditer(content):
        t = clean_text(m.group(1))
        if t.lower() not in BAD_TITLES:
            return t
    return ""


def page_title(path, url):
    try:
        with open(path, "r", encoding="utf-8", errors="surrogateescape") as fh:
            c = fh.read()
    except OSError:
        c = ""
    # Prefer <title>: vimwiki sets it to the real page name, whereas the first
    # <h1> is usually the auto-generated "Contents" table-of-contents heading.
    m = TITLE_RE.search(c)
    t = clean_text(m.group(1)) if m else ""
    if DATE_TITLE_RE.match(t):
        # Date-named page: prefer its heading, but keep the date if it has none.
        return first_heading(c) or t
    if t.lower() not in BAD_TITLES:
        return t
    h = first_heading(c)
    if h:
        return h
    # fall back to the file/folder name
    name = os.path.basename(url)
    if re.match(r"^index\.html?$", name, re.IGNORECASE):
        name = os.path.basename(os.path.dirname(url))
    name = re.sub(r"\.html?$", "", name, flags=re.IGNORECASE)
    return name.replace("_", " ").strip() or "Page"


def section_for(url):
    return "Blogs" if "/Blogs/" in url else "Resources"


def git_first_add_map():
    """Map every path -> date it was first added to git (one git pass).

    Using per-file `git log` is far too slow across hundreds of files, so we
    walk the whole history once (oldest commit first) and record the first
    time each path appears with an 'A' (added) status.
    """
    result = {}
    try:
        # --no-renames is essential: git's default rename detection reports a
        # moved file as "R" (rename), which --diff-filter=A would exclude,
        # silently dropping every file that was ever reorganised. With
        # --no-renames each file's current path registers as an add ("A").
        out = subprocess.run(
            ["git", "log", "--reverse", "--diff-filter=A", "--no-renames",
             "--name-only", "--format=C%as"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        ).stdout
    except FileNotFoundError:
        return result
    cur = None
    for line in out.splitlines():
        if line.startswith("C") and re.match(r"^C\d{4}-\d{2}-\d{2}$", line):
            cur = line[1:]
        elif line.strip() and cur:
            path = line.strip()
            if path not in result:  # --reverse => first sighting is earliest
                result[path] = cur
    return result


def collect_pages():
    pages = {}  # url -> title
    base = os.path.join(REPO_ROOT, WIKI_DIR)
    for root, _dirs, files in os.walk(base):
        for fn in files:
            if not fn.lower().endswith(".html"):
                continue
            if fn in EXCLUDE_FILENAMES:
                continue
            if any(rx.search(fn) for rx in EXCLUDE_FILENAME_RES):
                continue
            full = os.path.join(root, fn)
            url = os.path.relpath(full, REPO_ROOT).replace(os.sep, "/")
            probe = "/" + url
            if any(part in probe for part in EXCLUDE_DIR_PARTS):
                continue
            pages[url] = page_title(full, url)
    return pages


def fmt_date(iso):
    try:
        d = dt.date.fromisoformat(iso)
        return d.strftime("%-d %b %Y")
    except ValueError:
        return iso


def render_panel(items):
    if not items:
        return '<p class="new-empty">Nothing new just yet.</p>'
    lines = ["<ul>"]
    for url, title, date in items:
        # The date is the first-seen date from the manifest, not the file's
        # mtime, so it stays put when you regenerate the wiki. Wrapped in a
        # span so it can be styled (muted/smaller) without touching this script.
        lines.append(
            '<li><a href="/{url}">{title}</a> '
            '<span class="new-date">({date})</span></li>'.format(
                url=html.escape(url, quote=True),
                title=html.escape(title),
                date=html.escape(fmt_date(date)),
            )
        )
    lines.append("</ul>")
    return "\n".join(lines)


def inject(section, block, dry_run):
    target = os.path.join(REPO_ROOT, TARGETS[section])
    with open(target, "r", encoding="utf-8", errors="surrogateescape") as fh:
        c = fh.read()
    pat = re.compile(
        r"(<!-- WHATS_NEW:" + re.escape(section) + r" START.*?-->)(.*?)"
        r"(<!-- WHATS_NEW:" + re.escape(section) + r" END -->)",
        re.DOTALL,
    )
    if not pat.search(c):
        print("  ! markers for %s not found in %s" % (section, TARGETS[section]))
        return False
    new_c = pat.sub(lambda m: m.group(1) + "\n" + block + "\n" + m.group(3), c)
    if new_c == c:
        print("  = %s already up to date" % TARGETS[section])
        return False
    if dry_run:
        print("  ~ would update %s" % TARGETS[section])
        return False
    with open(target, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(new_c)
    print("  + updated %s" % TARGETS[section])
    return True


# ---- main ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=6, help="items per panel")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    today = dt.date.today().isoformat()

    # load manifest
    mpath = os.path.join(REPO_ROOT, MANIFEST)
    manifest = {}
    if os.path.exists(mpath):
        try:
            with open(mpath, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
        except (OSError, ValueError):
            manifest = {}

    pages = collect_pages()
    print("Scanned %d content pages." % len(pages))

    first_add = git_first_add_map()

    new_count = 0
    for url, title in pages.items():
        entry = manifest.get(url)
        if entry is None:
            date = first_add.get(url) or today
            manifest[url] = {"date": date, "title": title, "section": section_for(url)}
            new_count += 1
        else:
            # refresh label/section, keep the original first-seen date
            entry["title"] = title
            entry["section"] = section_for(url)
    print("Newly tracked pages this run: %d" % new_count)

    # save manifest (only for pages that still exist, keep it tidy)
    manifest = {u: manifest[u] for u in manifest if u in pages}
    if not args.dry_run:
        with open(mpath, "w", encoding="utf-8") as fh:
            json.dump(dict(sorted(manifest.items())), fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    # build and inject each panel
    for section in TARGETS:
        items = [
            (u, manifest[u]["title"], manifest[u]["date"])
            for u in manifest if manifest[u]["section"] == section
        ]
        # newest first; tie-break by title
        items.sort(key=lambda x: (x[2], x[1]), reverse=True)
        items.sort(key=lambda x: x[2], reverse=True)
        items = items[: args.max]
        print("%s panel: %d item(s)" % (section, len(items)))
        inject(section, render_panel(items), args.dry_run)

    if args.dry_run:
        print("\n(dry run — no files written)")


if __name__ == "__main__":
    sys.exit(main())
