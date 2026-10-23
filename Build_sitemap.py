#!/usr/bin/env python3
"""
Build sitemap.xml for vishalrao.in.

Walks the deployed site directory, finds every .html file, and writes a
sitemap listing them with their last-modified dates.

Run it from wherever your built site lives:

    python3 build_sitemap.py /path/to/site

It writes sitemap.xml into that same directory.

IMPORTANT — URL form must match rel=canonical exactly. A sitemap that lists
".../Page.html" while the page's own canonical says ".../Page" (or vice versa)
tells Google two different things about the same document, which is worse than
having no sitemap. Your wiki template sets canonical to
location.origin + location.pathname, i.e. the .html path exactly as served, so
that is what this script emits. The single exception is the root index.html:
your homepage declares <link rel="canonical" href="https://vishalrao.in/">, so
it is emitted as the bare "/" to match.
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from urllib.parse import quote

BASE_URL = "https://vishalrao.in"

# Directories never worth indexing: assets, version control, build leftovers.
SKIP_DIRS = {".git", ".github", "assets", "node_modules", "__pycache__"}

# Individual files to leave out (404 pages, templates, partials).
SKIP_FILES = {"404.html", "template.html", "default_colored.html"}

# Paths relative to the site root to leave out: old copies of the homepage
# (duplicates of "/") and the staticrypt password page (nothing to index).
# An entry ending in "/" skips that whole folder.
SKIP_PATHS = {
    "index (9).html",
    "index_0721.html",
    "index_unecrypted.html",
    "old_index.html",
    "encrypted/",
}


def git_ignored(root):
    """Return root-relative paths that .gitignore excludes (tracked or not).

    Those files are not meant to be published, so they must not be listed.
    If root is not a git repo or git is missing, return an empty set and warn.
    """
    try:
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "-z", "--cached", "--others",
             "--ignored", "--exclude-standard"],
            capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        print("Warning: could not ask git for ignored files; "
              ".gitignore is NOT applied.", file=sys.stderr)
        return set()
    return {p for p in out.decode("utf-8").split("\0") if p}


def skipped(rel, ignored):
    if rel in ignored or rel in SKIP_PATHS:
        return True
    return any(p.endswith("/") and rel.startswith(p) for p in SKIP_PATHS)


def collect(root):
    """Yield (url_path, mtime) for every publishable .html file under root."""
    ignored = git_ignored(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames)
                       if d not in SKIP_DIRS and not d.startswith(".")]
        for name in sorted(filenames):
            if not name.endswith(".html") or name in SKIP_FILES:
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if skipped(rel, ignored):
                continue
            # Root index.html is served as "/" and declares that canonical.
            # Nested index.html files are left as-is, because the wiki
            # template's JS canonical uses the literal served pathname.
            path = "/" if rel == "index.html" else "/" + rel
            # Percent-encode spaces and other unsafe characters; "/" is safe.
            yield quote(path, safe="/"), os.path.getmtime(full)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    if not os.path.isdir(root):
        sys.exit("Not a directory: " + root)

    entries = sorted(collect(root))
    if not entries:
        sys.exit("No .html files found under " + root)

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, mtime in entries:
        lastmod = datetime.fromtimestamp(mtime, timezone.utc).strftime("%Y-%m-%d")
        lines.append("  <url>")
        lines.append("    <loc>" + escape(BASE_URL + path) + "</loc>")
        lines.append("    <lastmod>" + lastmod + "</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")

    out = os.path.join(root, "sitemap.xml")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("Wrote {} with {} URLs".format(out, len(entries)))


if __name__ == "__main__":
    main()
