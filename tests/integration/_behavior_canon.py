# SPDX-License-Identifier: MIT

"""Cross-platform canonicalization for the behavior-diff golden comparison.

Left unpinned, Rich renders CLI output against the live console width, so it
bakes the *real* temporary-home path length into table column widths and
free-text wrap points. A Windows runner's
``C:\\Users\\runner\\AppData\\Local\\Temp\\...`` home is far longer than a Linux
runner's ``/tmp/...``, so an unpinned capture matches only the host that
captured it. Path separators (``\\`` vs ``/``), line endings (CRLF vs LF), the
legacy-Windows box substitution, and platform-dependent array ordering diverge
the same way.

The oracles pin those dimensions at capture time (``_cli_oracle`` and
``_install_driver_oracle``), so a fresh capture is byte-identical on Windows
and Linux and ``scripts/dev/regen-behavior-goldens.py`` produces no churn
between them. This module stays as the comparison-side tolerance, so a corpus
captured before those pins, or a working tree with CRLF endings, still
compares equal.

These helpers normalize exactly those platform-divergent dimensions while
preserving the content the regression guard must still catch (every command's
text, every value, every structural element). Each artifact class gets the
lightest transform that makes it portable:

- :func:`canon_file` — rendered config / script files: line-endings only. Their
  content is byte-identical across platforms once the oracle has tokenized the
  machine-specific paths, so whitespace and separators inside code / config are
  preserved exactly.
- :func:`canon_render` — Rich-rendered CLI captures: line-endings, JSON-escaped
  Windows separators, and collapsed horizontal-padding runs (the column width
  that bakes in the real path length).
- :func:`canon_ledger` — JSONL install ledgers: line-endings plus a deep array
  sort, so a platform-dependent target ordering is not read as drift.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Box-drawing normalization. Rich renders tables with its default HEAVY_HEAD
# box on a full-unicode console (Linux CI: ``┏ ━ ┳ ┓ ┣ ┫``) but DOWNGRADES to
# the light / safe box on a legacy or restricted console (Windows: ``┌ ─ ┬ ┐
# ├ ┤``) — so the very box CODEPOINTS differ by platform, not just the rule
# width (which also varies, since Rich sizes columns and borders to the real
# pre-tokenization path length). Map every box-drawing char (U+2500-U+257F,
# UTF-8 ``e2 94 xx`` / ``e2 95 xx``) to a space, then collapse fill runs: heavy,
# light, and double box all canonicalize identically, while each cell's CONTENT
# and its boundaries (always ≥ 1 separating space) survive.
_BOX = re.compile(rb"\xe2(?:\x94[\x80-\xbf]|\x95[\x80-\xbf])")
_SPACE_RUN = re.compile(rb"[ \t]{2,}")

# Click probes the runtime bash version (a `bash --version` subprocess) when it
# generates `completion bash`, and PREPENDS this notice when bash < 4.4 — which
# is exactly macOS's system bash 3.2. The notice is environment-dependent (it
# reflects the runner's bash, not the apothem CLI), so strip it with its
# trailing escaped newline before comparing, so the generated script that
# follows is what's diffed.
_BASH_COMPAT_NOTICE = (
    b"Shell completion is not supported for Bash versions older than 4.4.\\n"
)

# A Windows path separator surfaces in the captures as a RUN of backslash bytes
# at varying JSON-escape depth: ``\\`` (2 bytes) inside a Rich-table cell (one
# json.dumps), ``\\\\`` (4 bytes) inside the ``--json`` capture's nested-JSON
# stdout (two json.dumps). Collapsing ANY run of 2+ backslashes to a single
# ``/`` matches the Linux capture's lone forward slash at every depth, while a
# lone backslash (a JSON escape — ``\n`` / ``\"`` / ``\t``) is never matched and
# is left intact.
_BS_RUN = re.compile(rb"\\{2,}")


def _line_endings(raw: bytes) -> bytes:
    """Normalize CRLF / lone-CR to LF so a Windows working tree matches Linux."""
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canon_file(raw: bytes) -> bytes:
    """Line-ending normalization only — for rendered config / script files."""
    return _line_endings(raw)


def canon_render(raw: bytes) -> bytes:
    """Full canonicalization for Rich-rendered CLI captures.

    Normalizes line-endings, collapses any run of 2+ backslashes (a path
    separator at any JSON-escape depth) to ``/`` without touching single
    backslash escapes (``\\n`` / ``\\"`` / ``\\t``), maps every box-drawing
    char to a space (so Rich's platform-dependent heavy-vs-light box does not
    register as drift), and collapses the resulting fill runs so the table
    column width — which Rich sizes to the real (pre-tokenization) path length —
    does not register as drift either.
    """
    text = _line_endings(raw).replace(_BASH_COMPAT_NOTICE, b"")
    text = _BS_RUN.sub(b"/", text)
    return _SPACE_RUN.sub(b" ", _BOX.sub(b" ", text))


def _deep_sort(obj: Any) -> Any:  # noqa: ANN401  # Any: recurses over arbitrary JSON-like structures
    if isinstance(obj, dict):
        return {key: _deep_sort(value) for key, value in obj.items()}
    if isinstance(obj, list):
        sorted_items = [_deep_sort(item) for item in obj]
        return sorted(
            sorted_items,
            key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False),
        )
    return obj


def canon_ledger(raw: bytes) -> bytes:
    """Canonicalize a JSONL ledger: line-endings + deep-sorted arrays.

    Each record is re-serialized with sorted keys and recursively sorted arrays,
    so a platform-dependent ``targets`` ordering collapses to a single canonical
    form. A line that does not parse as JSON falls back to render-canon.
    """
    out_lines: list[bytes] = []
    for line in _line_endings(raw).split(b"\n"):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            out_lines.append(canon_render(line))
            continue
        out_lines.append(
            json.dumps(_deep_sort(obj), sort_keys=True, ensure_ascii=False).encode(
                "utf-8"
            )
        )
    return b"\n".join(out_lines) + b"\n" if out_lines else b""


def first_diff(golden: bytes, actual: bytes, *, window: int = 90) -> str:
    """ASCII-safe repr of the first byte where two canon'd blobs diverge.

    A diagnostic aid for cross-platform golden drift: names the offset plus a
    window of both sides (``repr`` escapes non-ASCII), so a CI failure reports
    the exact divergence rather than only the file slug.
    """
    limit = min(len(golden), len(actual))
    index = 0
    while index < limit and golden[index] == actual[index]:
        index += 1
    lo = max(0, index - 15)
    return (
        f"@byte {index} (len golden={len(golden)} actual={len(actual)}) "
        f"golden={golden[lo : index + window]!r} actual={actual[lo : index + window]!r}"
    )
