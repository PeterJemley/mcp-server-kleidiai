#!/bin/sh -e
# Cross-SDK parity gate: the Python and TypeScript servers must expose the
# same tool contract, the same retrieval behavior (top-1 doc on every eval
# question), and the same pattern/planner content. Run from anywhere; CI
# runs it in the schema-sync job.
#
# Env: PYTHON (default: the server-py venv python), NODE (default: node).
cd "$(dirname "$0")"
REPO_ROOT=$(cd ../.. && pwd)
PYTHON=${PYTHON:-"$REPO_ROOT/packages/server-py/.venv/bin/python"}
NODE=${NODE:-node}
TS_DIST="$REPO_ROOT/packages/server-ts/dist/scripts"

if [ ! -d "$TS_DIST" ]; then
    echo "TS build missing — run: cd packages/server-ts && npm run build" >&2
    exit 1
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail=0
for pair in "contract dump_contract.py dump-contract.js" \
            "top1 dump_top1.py dump-top1.js" \
            "patterns dump_patterns.py dump-patterns.js"; do
    set -- $pair
    name=$1; py=$2; ts=$3
    "$PYTHON" "$py" > "$TMP/$name.py.out"
    "$NODE" "$TS_DIST/$ts" > "$TMP/$name.ts.out"
    if diff -u "$TMP/$name.py.out" "$TMP/$name.ts.out" > "$TMP/$name.diff"; then
        echo "parity OK: $name"
    else
        echo "PARITY FAILURE: $name" >&2
        cat "$TMP/$name.diff" >&2
        fail=1
    fi
done
exit $fail
