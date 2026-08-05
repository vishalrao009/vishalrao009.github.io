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

    # 1. CSS — also hide Google's "Translated to … / Show original" banner,
    #    which is injected as a top-level <iframe class="skiptranslate">.
    (
        """        /* Google Translate: the widget itself stays hidden. We drive it entirely
           through our own globe button + language panel below. Suppress every
           bit of Google's own chrome in all cases — banner, floating balloon,
           feedback tab, and the "suggest a better translation" hover tooltip —
           none of it should ever surface. */
        #google_translate_element { display: none !important; }
        .goog-te-gadget { display: none !important; }
        body { top: 0px !important; }
        .goog-te-banner-frame,""",
        """        /* Google Translate: the widget itself stays hidden. We drive it entirely
           through our own globe button + language panel below. Suppress every
           bit of Google's own chrome in all cases — the "Translated to … /
           Show original" top banner, the floating balloon, the feedback tab,
           and the "suggest a better translation" hover tooltip. None of it
           should ever surface; the visitor switches back to English from our
           own globe menu instead.

           The banner is injected as a top-level <iframe class="skiptranslate">,
           which is why hiding only the .goog-te-* classes wasn't enough. */
        #google_translate_element { display: none !important; }
        .goog-te-gadget { display: none !important; }
        iframe.skiptranslate,
        .skiptranslate > iframe,
        .goog-te-banner-frame,""",
    ),
    (
        """        .goog-tooltip:hover {
            display: none !important;
            visibility: hidden !important;
        }
        .goog-text-highlight { background: none !important; box-shadow: none !important; }""",
        """        .goog-tooltip:hover {
            display: none !important;
            visibility: hidden !important;
        }
        /* Google pushes the page down with an inline body { top: 40px;
           position: relative } to make room for that banner. !important here
           outranks its inline style, so the layout never shifts. */
        body {
            top: 0px !important;
            position: static !important;
        }
        .goog-text-highlight { background: none !important; box-shadow: none !important; }""",
    ),
]

ALREADY_DONE_MARKER = "iframe.skiptranslate,"


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
