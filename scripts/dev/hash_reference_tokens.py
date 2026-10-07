# SPDX-License-Identifier: MIT

"""Print reference-token denylist entries for tokens read without echoing them.

The reference-token denylist (``src/apothem/schemas/reference-token-denylist.txt``)
stores a SHA-256 digest of each token rather than the token, so Apothem does not
ship the tokens in readable, searchable form. A digest does not hide a token: a
short name can be recovered by exhaustive search, or confirmed by hashing a
guess. This script is the one place a maintainer turns a token into an entry.

Keep a token out of shell history and process listings. Never pass it as an
argument or through ``echo``; use one of these instead:

- Run the script in a terminal with no redirect. It prompts for each token
  without echoing it; an empty answer ends the list.
- Redirect standard input from a file kept outside the repository, one token
  per line, and delete the file afterwards.

Usage::

    python scripts/dev/hash_reference_tokens.py
    python scripts/dev/hash_reference_tokens.py < ~/private/new-tokens.txt
    python scripts/dev/hash_reference_tokens.py --check < ~/private/new-tokens.txt

The script prints one entry per token in the order the data file keeps:
``word`` entries first, then ``literal`` entries by length, each group sorted
by digest. Paste them into the data file below its header.

``--check`` prints nothing on success and exits 1 when a token has no entry in
the denylist (``--denylist``, default the committed file), so a reviewer can
confirm a change without the tokens appearing in the diff.

Exit codes: ``0`` success, ``1`` a ``--check`` token is missing, ``2`` a token
has neither accepted shape, no token was given, or the denylist is unreadable.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (_REPO_ROOT / "src" / "apothem" / "_vendor", _REPO_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from apothem.conformity.reference_token_grep import (  # noqa: E402
    _DENYLIST_PATH,
    digest_entry,
)


def _sort_key(entry: str) -> tuple[int, int, str]:
    """Order word entries first, then literal entries by length, then digest."""
    parts = entry.split()
    if parts[0] == "word":
        return (0, 0, parts[-1])
    return (1, int(parts[1]), parts[-1])


def _read_tokens() -> list[str]:
    """Return the tokens from a hidden prompt on a terminal, else from stdin."""
    if sys.stdin.isatty():
        tokens: list[str] = []
        while True:
            token = getpass.getpass("token (empty to finish): ").strip()
            if not token:
                return tokens
            tokens.append(token)
    return [line.strip() for line in sys.stdin if line.strip()]


def main(argv: list[str] | None = None) -> int:
    """Entry point; see the module docstring for the contract."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when a token has no entry in the denylist",
    )
    parser.add_argument(
        "--denylist",
        type=Path,
        default=_DENYLIST_PATH,
        help="denylist file that --check reads (default: the committed file)",
    )
    args = parser.parse_args(argv)
    tokens = _read_tokens()
    if not tokens:
        print("error: no tokens given", file=sys.stderr)
        return 2
    entries: list[str] = []
    for index, token in enumerate(tokens, start=1):
        try:
            entries.append(digest_entry(token))
        except ValueError as exc:
            print(f"error: token {index}: {exc}", file=sys.stderr)
            return 2
    if args.check:
        try:
            text = args.denylist.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot read {args.denylist}: {exc}", file=sys.stderr)
            return 2
        committed = {line.strip() for line in text.splitlines()}
        missing = [i for i, e in enumerate(entries, start=1) if e not in committed]
        for index in missing:
            print(f"missing: token {index} has no denylist entry", file=sys.stderr)
        return 1 if missing else 0
    for entry in sorted(set(entries), key=_sort_key):
        print(entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
