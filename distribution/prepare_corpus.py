"""Stage the corpus inside the distributable packages before building.

An installed server has no repo to walk up to, so at release time the
committed corpus (with its manifest — provenance travels with the copy) and
the canonical patterns.yaml are copied into the packages; both servers fall
back to the packaged copy when no repo corpus is found. The copies are
gitignored and exist only between `prepare` and `clean` — the committed
corpus stays the single source of truth.

Usage: python distribution/prepare_corpus.py prepare|clean
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "corpus"
PY_PKG = REPO / "packages" / "server-py" / "src" / "mcp_server_kleidiai"
TS_PKG = REPO / "packages" / "server-ts"

STAGED = [
    PY_PKG / "_corpus",
    TS_PKG / "corpus",
    TS_PKG / "patterns.yaml",
]


def prepare() -> None:
    """Copy the corpus (with manifest) and patterns.yaml into both packages."""
    clean()
    shutil.copytree(CORPUS, PY_PKG / "_corpus")
    shutil.copytree(CORPUS, TS_PKG / "corpus")
    shutil.copy2(PY_PKG / "patterns.yaml", TS_PKG / "patterns.yaml")
    for p in STAGED:
        print(f"staged {p.relative_to(REPO)}")


def clean() -> None:
    """Remove every staged copy; a no-op when nothing is staged."""
    for p in STAGED:
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def main() -> int:
    """Dispatch prepare|clean from argv; print usage otherwise."""
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "prepare":
        prepare()
    elif mode == "clean":
        clean()
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
