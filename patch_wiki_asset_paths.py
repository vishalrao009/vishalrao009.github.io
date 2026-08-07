#!/usr/bin/env python3
"""
patch_wiki_asset_paths.py
-------------------------
Makes PDFs (and any other non-wiki attachment) actually work on the deployed
site, and keeps them working across future re-exports.

THE PROBLEM
    Vimwiki resolves links and image transclusions against the *source* wiki
    tree, not the exported HTML tree. So a page written as

        [[local:PDFs/Notes.pdf|Notes]]
        {{Images/fig.png}}

    exports to

        href="../../../../phd_work/notes/vimwiki/Lecture_notes/PDFs/Notes.pdf"
        src="../../../../phd_work/notes/vimwiki/Lecture_notes/Images/fig.png"

    Those paths point back into ~/Documents/phd_work, which is not part of the
    published site, so every such link 404s once deployed. Separately, vimwiki
    appends ".html" to ANY [[bracket link]] even when the target already has an
    extension, turning [[PDFs/Notes.pdf]] into "PDFs/Notes.pdf.html".

THE FIX (two halves)
    1. COPY  - the asset files themselves are copied from the source wiki tree
       into the matching folder of the exported tree, so they ship with the site.
    2. REWRITE - a small script is injected into every exported page (and into
       wiki/templates/*.html, so future exports carry it automatically) which,
       on load, rewrites any URL still pointing at the source tree into a
       site-absolute /wiki/vimwiki_html/... path, and strips the bogus trailing
       ".html" from attachment links.

    Doing the rewrite in the template rather than by editing hrefs in place is
    what makes this survive `:VimwikiAll2HTML` - a fresh export regenerates the
    HTML but keeps the template's script block.

USAGE
    python3 patch_wiki_asset_paths.py --dry-run    # report only
    python3 patch_wiki_asset_paths.py              # apply
"""

import argparse
import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(REPO_ROOT, "wiki", "vimwiki_html")
TEMPLATE_DIR = os.path.join(REPO_ROOT, "wiki", "templates")

# Source wiki tree on this machine (where the .wiki files live).
# Override with WIKI_SOURCE=/path/to/vimwiki if it lives somewhere else.
SOURCE_WIKI = os.environ.get(
    "WIKI_SOURCE", os.path.expanduser("~/Documents/phd_work/notes/vimwiki"))

# Folder names that hold attachments and should be mirrored into the export.
# Matched case-insensitively, because macOS is case-insensitive and the source
# folder is actually named "images" on disk - but the published site is served
# from Linux (case-SENSITIVE) and the committed folder is "Images", so the
# destination is always written with the canonical casing spelled here.
ASSET_DIRS = ("PDFs", "Images")

# Inserted immediately before the TikZJax block so it runs with the other
# post-processing scripts at the end of <body>.
ANCHOR = ('    <!-- 1. Turn vimwiki {{{class="tikz"}}} blocks into TikZJax '
          'script tags (must run BEFORE tikzjax.js) -->')

MARKER = "vimwiki-asset-path-fix"

SNIPPET = '''    <!-- 0. Repair asset paths (''' + MARKER + ''').
         Vimwiki resolves {{...}} images and local:/file: links against the
         SOURCE wiki tree (.../phd_work/notes/vimwiki/...), which does not exist
         on the deployed site, and it appends ".html" to any [[link]] even when
         the target already has an extension. Both are repaired here so the
         fix survives every re-export instead of needing a manual patch. -->
    <script>
    (function () {
        var ROOT = '/wiki/vimwiki_html/';
        var NEEDLE = 'notes/vimwiki/';
        var ATTACH = /\\.(pdf|png|jpe?g|gif|svg|webp|zip|txt|csv|tex|docx?|xlsx?|pptx?)\\.html$/i;
        function fix(url) {
            if (!url || /^(https?:|mailto:|#|data:)/i.test(url)) return url;
            var i = url.indexOf(NEEDLE);
            if (i !== -1) url = ROOT + url.slice(i + NEEDLE.length);
            return url.replace(ATTACH, '.$1');
        }
        function sweep(sel, attr) {
            document.querySelectorAll(sel).forEach(function (el) {
                var v = el.getAttribute(attr), n = fix(v);
                if (n !== v) el.setAttribute(attr, n);
            });
        }
        sweep('a[href]', 'href');
        sweep('img[src]', 'src');
    })();
    </script>
'''


def copy_assets(dry_run):
    """Mirror PDFs/ and Images/ from the source wiki tree into the export tree."""
    copied, skipped = 0, 0
    if not os.path.isdir(SOURCE_WIKI):
        print("source wiki tree not found: %s (skipping asset copy)" % SOURCE_WIKI)
        return copied, skipped
    canonical = {d.lower(): d for d in ASSET_DIRS}
    for root, dirs, files in os.walk(SOURCE_WIKI):
        base = os.path.basename(root)
        if base.lower() not in canonical:
            continue
        # Rewrite the last path component to the canonical casing so the
        # published (case-sensitive) paths always agree with the HTML.
        rel = os.path.relpath(root, SOURCE_WIKI)
        rel = os.path.join(os.path.dirname(rel), canonical[base.lower()])
        dst_dir = os.path.join(EXPORT_DIR, rel)
        for fn in sorted(files):
            if fn.startswith("."):
                continue
            src = os.path.join(root, fn)
            dst = os.path.join(dst_dir, fn)
            if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
                skipped += 1
                continue
            if not dry_run:
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(src, dst)
            print("  copy %s" % os.path.join(rel, fn))
            copied += 1
    return copied, skipped


def inject(path, dry_run):
    """Insert the path-repair script into one HTML file. Returns a status string."""
    with open(path, "r", encoding="utf-8", errors="surrogateescape") as fh:
        text = fh.read()
    if MARKER in text:
        return "already"
    if ANCHOR not in text:
        return "no-anchor"
    text = text.replace(ANCHOR, SNIPPET + ANCHOR, 1)
    if not dry_run:
        with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write(text)
    return "patched"


def walk_html(base, dry_run, label):
    counts = {"patched": 0, "already": 0, "no-anchor": 0}
    problems = []
    for root, _dirs, files in os.walk(base):
        for fn in sorted(files):
            if not fn.lower().endswith(".html"):
                continue
            path = os.path.join(root, fn)
            status = inject(path, dry_run)
            counts[status] += 1
            if status == "no-anchor":
                problems.append(os.path.relpath(path, REPO_ROOT))
    print("[%s] patched=%d already=%d no-anchor=%d"
          % (label, counts["patched"], counts["already"], counts["no-anchor"]))
    for p in problems[:10]:
        print("    no anchor: %s" % p)
    if len(problems) > 10:
        print("    ... and %d more" % (len(problems) - 10))
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("1. copying attachments into the exported tree")
    copied, skipped = copy_assets(args.dry_run)
    print("   copied=%d up-to-date=%d" % (copied, skipped))

    print("2. injecting the path-repair script")
    walk_html(TEMPLATE_DIR, args.dry_run, "templates")
    walk_html(EXPORT_DIR, args.dry_run, "exported html")

    if args.dry_run:
        print("\n(dry run - nothing written)")


if __name__ == "__main__":
    sys.exit(main())
