# SPDX-License-Identifier: MIT

"""Shared byte-identical normalization primitives for the behavior-diff oracles.

Both ``_cli_oracle.py`` (DX-2) and ``_install_driver_oracle.py`` (DX-1) tokenize
machine-specific values out of captured output so their committed golden corpora
under ``tests/fixtures/behavior-diff/`` are byte-reproducible across runs and
machines. The two oracles historically re-implemented the same regex constants,
the same JSON-recursion shape, and the same path-collapse tail near-verbatim.

This module holds ONLY the pieces that are byte-identical between the two
oracles, so hoisting them changes no normalization semantics:

- the timestamp / ULID / resolved-interpreter regex constants, and
- a parametrized ``normalize_obj`` (recurses a JSON-like structure applying a
  caller-supplied per-string normalizer) and ``collapse_token_paths`` (the
  backslash-path collapse tail, parametrized on the token alternation).

The oracles keep their own ``_path_variants`` / ``_normalize_text`` because
those genuinely differ (the CLI oracle tokenizes ``<HOME>`` and the live
interpreter version/platform and adds a double-backslash path variant; the
install-driver oracle tokenizes ``<BACKUP_TS>`` distinctly). Folding those
divergent bodies together would change captured bytes, so they stay local.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

# Shared tokens emitted by both oracles for the same machine-specific values.
TOK_ROOT = "<ROOT>"
TOK_SRC = "<APOTHEM_SRC>"
TOK_PYBIN = "<PYTHON_BIN>"
TOK_INSTALL_ID = "<INSTALL_ID>"
TOK_TIMESTAMP = "<TIMESTAMP>"

# Backup-directory stamp (``YYYYMMDDThhmmssZ``) and ISO-8601 timestamps.
_TS_RE = re.compile(r"\b\d{8}T\d{6}Z\b")
_ISO_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z")
# ULID (26-char Crockford base32) — install ids and backup ids.
_ULID_RE = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
# Match a quoted *resolved interpreter path* (a path-separator precedes
# "python"), e.g. "C:/.../python.exe" or "/usr/bin/python3" — the value an
# adapter resolves ${PYTHON_BIN} to at install time. A bare command word like
# "python3" carries no separator, so it is left intact: replacing it would
# mangle the surrounding JSON string.
_PYBIN_RE = re.compile(r'"[^"\n]*[/\\][Pp]ython[0-9.]*(?:\.exe)?"')
# The same path inside a JSON string that is itself carried in JSON (the
# unified diff of settings.json that ``diff --format json`` prints): its quotes
# arrive escaped as \" and the pattern above, anchored on a bare quote, misses
# it, which put the capturing interpreter's own path into the golden. A match
# cannot cross a string boundary, since every escaped quote holds a bare one.
_PYBIN_ESCAPED_RE = re.compile(r'\\"[^"\n]*?[/\\][Pp]ython[0-9.]*(?:\.exe)?\\"')


def tokenize_python_bin(text: str) -> str:
    """Replace every resolved interpreter path in *text* with the PYBIN token.

    Covers a path between bare quotes and one between escaped quotes, keeping
    the surrounding quote form so the text stays valid JSON.
    """
    text = _PYBIN_RE.sub(f'"{TOK_PYBIN}"', text)
    return _PYBIN_ESCAPED_RE.sub(lambda _match: f'\\"{TOK_PYBIN}\\"', text)


def normalize_obj(
    obj: Any,  # noqa: ANN401  # Any: recurses over arbitrary JSON-like envelopes
    normalize_text: Callable[[str], str],
) -> Any:  # noqa: ANN401  # Any: mirrors the recursed structure's element type
    """Recurse a JSON-like structure, applying *normalize_text* to every string.

    Byte-identical to the per-oracle ``_normalize_obj`` bodies: strings are
    normalized, dicts and lists are rebuilt in place, and every other scalar is
    returned unchanged. The caller passes a partially-applied ``_normalize_text``
    (already bound to its ``home=`` / ``root=`` context), so the recursion is
    scope-agnostic.
    """
    if isinstance(obj, str):
        return normalize_text(obj)
    if isinstance(obj, dict):
        return {key: normalize_obj(value, normalize_text) for key, value in obj.items()}
    if isinstance(obj, list):
        return [normalize_obj(item, normalize_text) for item in obj]
    return obj


def collapse_token_paths(text: str, token_alternation: str) -> str:
    """Collapse a tokenized path's trailing backslash segments to POSIX slashes.

    After the leading directory (``<HOME>`` / ``<ROOT>`` / ``<APOTHEM_SRC>``) is
    tokenized, a Windows capture still carries backslash-separated tail segments
    (``<ROOT>\\backups\\...``). This rewrites those tails to forward slashes and
    squeezes runs of slashes so a Windows capture and a POSIX capture are
    byte-identical. *token_alternation* is the regex alternation of the tokens
    the caller emits (e.g. ``"HOME|ROOT|APOTHEM_SRC"``), so each oracle collapses
    exactly the tokens it produces and no others.
    """
    return re.sub(
        r"<(?:" + token_alternation + r")>(?:\\[^\\\"\s]*)+",
        lambda m: re.sub(r"/+", "/", m.group(0).replace("\\", "/")),
        text,
    )
