#!/usr/bin/env python3
"""
patch_exported_wiki.py
----------------------
One-off maintenance script: applies the "move translate + search buttons to
the top-right" change to the wiki HTML files that were ALREADY exported.

WHY THIS EXISTS
    wiki/templates/default_colored.html only affects pages exported *after*
    it changes. The site already has ~630 exported pages carrying the older
    chrome (globe docked in the bottom-right .floating-btns stack). Rather
    than require a full re-export just to reposition two buttons, this script
    rewrites those exported files in place with exactly the same edits that
    were made to the template.

    It is safe to re-run: files already carrying the new markup are skipped.
    Every file must match all expected patterns or it is left untouched and
    reported, so a page with unexpected markup can never be half-patched.

USAGE
    python3 patch_exported_wiki.py --dry-run     # report only
    python3 patch_exported_wiki.py               # apply
"""

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
WIKI_DIR = os.path.join("wiki", "vimwiki_html")

# Inline SVG line icons (Apple/SF-Symbols style): stroke-only, no fill, sized
# and coloured entirely by CSS via stroke="currentColor".
GLOBE_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/>'
    '<path d="M3 12h18"/>'
    '<path d="M5.3 6.5c1.9 1 4.2 1.6 6.7 1.6s4.8-.6 6.7-1.6"/>'
    '<path d="M5.3 17.5c1.9-1 4.2-1.6 6.7-1.6s4.8.6 6.7 1.6"/></svg>'
)
SEARCH_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<circle cx="11" cy="11" r="6.5"/><path d="M16.3 16.3 21 21"/></svg>'
)

# Each entry is (old, new). All of them must be present in a file for it to be
# patched; otherwise the file is skipped and reported.
REPLACEMENTS = [

    # 1. CSS — one canonical parchment URL instead of a per-section relative
    #    path, so the browser fetches and caches it once for the whole site.
    (
        """        body {
            background-image: url('../Images/parchment.jpg');""",
        """        body {
            /* Absolute, not '../Images/parchment.jpg': the relative form
               resolved to a different copy of the same image in every section
               folder, so the browser cached (and re-downloaded) it once per
               section. One canonical URL = fetched once for the whole site. */
            background-image: url('/wiki/vimwiki_html/Images/parchment.jpg');""",
    ),
]

ALREADY_DONE_MARKER = "url('/wiki/vimwiki_html/Images/parchment.jpg')"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = os.path.join(REPO_ROOT, WIKI_DIR)
    patched = skipped_done = skipped_bad = 0
    problems = []

    for root, _dirs, files in os.walk(base):
        for fn in sorted(files):
            if not fn.lower().endswith(".html"):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, REPO_ROOT)
            with open(path, "r", encoding="utf-8", errors="surrogateescape") as fh:
                text = fh.read()

            if ALREADY_DONE_MARKER in text:
                skipped_done += 1
                continue
            if "btn-globe" not in text:
                # Not a page built from this template (or an old export that
                # predates the translate feature entirely).
                skipped_bad += 1
                problems.append((rel, "no globe button - not from this template"))
                continue

            missing = [i for i, (old, _new) in enumerate(REPLACEMENTS, 1) if old not in text]
            if missing:
                skipped_bad += 1
                problems.append((rel, "missing pattern(s) %s" % missing))
                continue

            new_text = text
            for old, new in REPLACEMENTS:
                # count=1: each pattern occurs exactly once per page.
                new_text = new_text.replace(old, new, 1)

            if not args.dry_run:
                with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
                    fh.write(new_text)
            patched += 1

    print("patched:            %d" % patched)
    print("skipped (already):  %d" % skipped_done)
    print("skipped (mismatch): %d" % skipped_bad)
    if problems:
        print("\nfiles left untouched:")
        for rel, why in problems[:40]:
            print("  %s  (%s)" % (rel, why))
        if len(problems) > 40:
            print("  ... and %d more" % (len(problems) - 40))
    if args.dry_run:
        print("\n(dry run - nothing written)")


if __name__ == "__main__":
    sys.exit(main())
