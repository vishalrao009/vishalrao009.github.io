#!/usr/bin/env bash
# EatNmove release bumper.
#   Usage:  ./bump.sh 2026.09.19l
# Sets APP_VERSION (calorie_counter.html) and "version" (version.json) to the
# SAME string you pass, and increments CACHE_VERSION (sw.js) by one (v20 -> v21).
# Keeping the first two identical is what the app relies on to know it is
# up to date; the cache bump forces old fonts/icons to refresh.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
V="$1"

if [ -z "$V" ]; then
  echo "usage: ./bump.sh <version>    e.g.  ./bump.sh 2026.09.19l"
  echo "current:"
  grep -o 'APP_VERSION = "[^"]*"' "$DIR/calorie_counter.html" | head -1
  grep -o '"version": "[^"]*"'   "$DIR/version.json"
  grep -o 'CACHE_VERSION = "[^"]*"' "$DIR/sw.js" | head -1
  exit 1
fi

# 1) the number Settings shows
V="$V" perl -pi -e 's/(var APP_VERSION = ")[^"]*(";)/$1$ENV{V}$2/' "$DIR/calorie_counter.html"
# 2) what the server advertises - must match APP_VERSION
V="$V" perl -pi -e 's/("version": ")[^"]*(",)/$1$ENV{V}$2/' "$DIR/version.json"
# 3) cache number, auto-incremented
perl -0777 -pi -e 's/(const CACHE_VERSION = "v)(\d+)(")/$1.($2+1).$3/e' "$DIR/sw.js"

echo "bumped to:"
grep -o 'APP_VERSION = "[^"]*"' "$DIR/calorie_counter.html" | head -1
grep -o '"version": "[^"]*"'   "$DIR/version.json"
grep -o 'CACHE_VERSION = "[^"]*"' "$DIR/sw.js" | head -1

# sanity: the two version strings must be identical
A="$(grep -o 'APP_VERSION = "[^"]*"' "$DIR/calorie_counter.html" | head -1 | sed 's/.*"\(.*\)"/\1/')"
B="$(grep -o '"version": "[^"]*"' "$DIR/version.json" | sed 's/.*"\(.*\)"/\1/')"
if [ "$A" != "$B" ]; then
  echo "WARNING: APP_VERSION ($A) and version.json ($B) do not match!"
  exit 1
fi

echo
echo "next:  git add -A && git commit -m update && git push"
