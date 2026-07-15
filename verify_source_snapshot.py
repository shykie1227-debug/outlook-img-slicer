"""Verify that a copied release tree exactly matches a clean Git commit."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo


def verify_source_snapshot(root: Path, expected_sha: str) -> None:
    expected = expected_sha.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise RuntimeError("expected SHA must contain 40 hexadecimal characters")

    repository = Repo(str(root))
    actual = repository.head().decode("ascii").lower()
    if actual != expected:
        raise RuntimeError(f"source commit mismatch: expected {expected}, got {actual}")

    status = porcelain.status(str(root))
    staged = any(status.staged.values())
    if staged or status.unstaged or status.untracked:
        raise RuntimeError("source snapshot contains uncommitted or untracked files")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("expected_sha")
    args = parser.parse_args()
    verify_source_snapshot(args.root, args.expected_sha)
    print(f"Verified clean source snapshot: {args.expected_sha.lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
