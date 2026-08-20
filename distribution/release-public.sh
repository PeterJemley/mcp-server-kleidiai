#!/bin/sh -e
# Publish a curated snapshot of this repo's HEAD to the public release repo.
#
# The private repo (full history, session handoff, working notes) is the
# development archive; the release repo receives deliberate snapshot commits
# with fresh history — every public commit is a reviewed release action.
# Decided 2026-08-20 during the pre-publication review.
#
# The content guard is the pre-publication constraint living where the work
# happens: the push refuses if the constructed tree matches any pattern in
# the (private, never-released) guard list. Add patterns there as review
# discovers new classes.
#
# Usage: distribution/release-public.sh "Release commit message"

RELEASE_REPO="https://github.com/PeterJemley/mcp-server-kleidiai.git"
AUTHOR_NAME="Peter Jemley"
AUTHOR_EMAIL="fibonaccicube@gmail.com"
# Files tracked in the archive repo but never released.
EXCLUDES="where-to-begin.md distribution/release-guard-patterns.txt"

MSG=${1:?"usage: $0 \"Release commit message\""}
cd "$(dirname "$0")/.."
REPO_ROOT=$(pwd)
GUARD="$REPO_ROOT/distribution/release-guard-patterns.txt"

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "working tree not clean — commit to the archive repo first" >&2
    exit 1
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

git archive HEAD | tar -x -C "$TMP"
for f in $EXCLUDES; do rm -f "$TMP/$f"; done

fail=0
while IFS= read -r pat; do
    [ -n "$pat" ] || continue
    if grep -ril "$pat" "$TMP" >/dev/null 2>&1; then
        echo "CONTENT GUARD: forbidden pattern present in release tree; files:" >&2
        grep -ril "$pat" "$TMP" >&2
        fail=1
    fi
done < "$GUARD"
[ "$fail" -eq 0 ] || exit 1

cd "$TMP"
git init -q
git remote add release "$RELEASE_REPO"
# Preserve the release repo's prior snapshots, if any.
if git fetch -q release main 2>/dev/null; then
    git reset -q --soft FETCH_HEAD
fi
git add -A
GIT_AUTHOR_NAME="$AUTHOR_NAME" GIT_AUTHOR_EMAIL="$AUTHOR_EMAIL" \
GIT_COMMITTER_NAME="$AUTHOR_NAME" GIT_COMMITTER_EMAIL="$AUTHOR_EMAIL" \
    git commit -q -m "$MSG"
git push -q release HEAD:main
echo "released: $(git rev-parse --short HEAD) -> $RELEASE_REPO"
