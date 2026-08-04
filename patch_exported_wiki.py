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

# Each entry is (old, new). All of them must be present in a file for it to be
# patched; otherwise the file is skipped and reported.
REPLACEMENTS = [

    # 1. CSS — add the top-right stack, and its mobile sizing.
    (
        """        .floating-btns button:hover { opacity: 1; transform: translateY(-2px); }
        #btn-top { display: none; }   /* revealed after scrolling down */
        @media (max-width: 600px) {
            .floating-btns { right: 14px; bottom: 14px; }
            .floating-btns button { width: 44px; height: 44px; font-size: 20px; line-height: 44px; }
        }""",
        """        .floating-btns button:hover { opacity: 1; transform: translateY(-2px); }
        #btn-top { display: none; }   /* revealed after scrolling down */
        /* Top-right button stack: site-wide tools (translate + search), kept
           separate from the bottom-right stack above, which holds per-page
           navigation (back / top / ask-this-page). The search launcher is
           inserted here at runtime by search.js. */
        .top-right-btns {
            position: fixed;
            top: 16px;
            right: 24px;
            display: flex;
            flex-direction: row;
            gap: 10px;
            z-index: 1500;
        }
        .top-right-btns button {
            width: 48px;
            height: 48px;
            border: 2px solid rgba(255, 255, 255, 0.85);
            border-radius: 50%;
            background: #6b4f2a;
            color: #fff;
            font-size: 20px;
            line-height: 44px;
            text-align: center;
            padding: 0;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
            transition: transform 0.2s;
        }
        .top-right-btns button:hover { transform: translateY(-2px); }
        @media (max-width: 600px) {
            .floating-btns { right: 14px; bottom: 14px; }
            .floating-btns button { width: 44px; height: 44px; font-size: 20px; line-height: 44px; }
            .top-right-btns { top: 12px; right: 14px; gap: 8px; }
            .top-right-btns button { width: 44px; height: 44px; font-size: 18px; line-height: 40px; }
        }""",
    ),

    # 2. CSS — the language panel now drops down from the top, not up from the bottom.
    (
        """        #translate-panel {
            display: none;
            flex-direction: column;
            position: fixed;
            right: 24px;
            bottom: 84px;""",
        """        #translate-panel {
            display: none;
            flex-direction: column;
            position: fixed;
            right: 24px;
            top: 72px;""",
    ),
    (
        "            #translate-panel { right: 14px; bottom: 74px; width: 220px; max-height: 300px; }",
        "            #translate-panel { right: 14px; top: 64px; width: 220px; max-height: 300px; }",
    ),

    # 3. HTML — move the globe out of the bottom stack into a new top-right one.
    (
        """    <div class="floating-btns">
        <button id="btn-back" type="button" title="Go back" aria-label="Go back">&#8592;</button>
        <button id="btn-top" type="button" title="Back to top" aria-label="Back to top">&#8593;</button>
        <button id="btn-globe" type="button" title="Translate this page" aria-label="Translate this page">&#127760;</button>
    </div>
""",
        """    <div class="floating-btns">
        <button id="btn-back" type="button" title="Go back" aria-label="Go back">&#8592;</button>
        <button id="btn-top" type="button" title="Back to top" aria-label="Back to top">&#8593;</button>
    </div>

    <!-- Top-right buttons: site-wide tools — search (docked here at runtime by
         search.js) and translate. Kept out of the bottom-right stack above,
         which is for navigating within the current page. -->
    <div class="top-right-btns">
        <button id="btn-globe" type="button" title="Translate this page" aria-label="Translate this page">&#127760;</button>
    </div>
""",
    ),

    # 4. JS — dock the search launcher into the top-right stack instead.
    #    Anchored on window.SEARCH_CONFIG so PAGEBOT_CONFIG's own
    #    launcherSelector: '.floating-btns' is left alone.
    (
        """         The launcher is docked into the same .floating-btns stack. -->
    <script>
        window.SEARCH_CONFIG = {
            launcherSelector: '.floating-btns',""",
        """         The launcher is docked into the top-right stack, next to translate,
         since both are site-wide rather than per-page tools. -->
    <script>
        window.SEARCH_CONFIG = {
            launcherSelector: '.top-right-btns',""",
    ),
]

ALREADY_DONE_MARKER = 'class="top-right-btns"'


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
