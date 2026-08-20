#!/bin/sh -e
# Checkout of ARM-software/kleidiai for the port, pinned to the same commit
# the corpus docs were fetched at (corpus/manifest.yaml) so the code the
# agent reads matches the docs it retrieves.
KLEIDIAI_COMMIT=b87ef9c94f45f11c81a6b1fdaed1b2b45ea58c0c

cd "$(dirname "$0")"
mkdir -p third_party
if [ ! -d third_party/kleidiai/.git ]; then
    git clone https://github.com/ARM-software/kleidiai.git third_party/kleidiai
fi
git -C third_party/kleidiai checkout --quiet "$KLEIDIAI_COMMIT" 2>/dev/null || {
    git -C third_party/kleidiai fetch --quiet origin "$KLEIDIAI_COMMIT"
    git -C third_party/kleidiai checkout --quiet "$KLEIDIAI_COMMIT"
}
echo "kleidiai @ $(git -C third_party/kleidiai rev-parse HEAD)"
