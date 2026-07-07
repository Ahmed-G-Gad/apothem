# SPDX-License-Identifier: MIT

"""Shared hook stdin JSON reader.

The four hook entry points that read the harness's PreToolUse / PostToolUse /
statusline stdin payload each hand-rolled the same read-and-parse sequence with
divergent exception handling. This is the one canonical reader they consume so
the read path cannot drift between them.

Contract (fail-open, matching the hooks' never-crash discipline):

* stdin attached to a terminal (interactive run, no piped payload) → ``None``.
* a read error (``OSError`` / ``ValueError``) → ``None``.
* empty / whitespace-only input → ``None``.
* malformed JSON → ``None``.
* a parsed JSON value that is not an object → ``None``.
* a parsed JSON object → the ``dict``.

The reader is deliberately dependency-free stdlib so a standalone hook script
that adds ``hooks/lib`` to ``sys.path`` can import it without the ``apothem``
package on a plugin-alone install.
"""

from __future__ import annotations

import json
import sys


def read_stdin_json() -> dict[str, object] | None:
    """Read and parse the hook's stdin JSON payload; fail-open to ``None``.

    Returns the parsed object when stdin carries a JSON object, else ``None``
    (terminal stdin, read error, empty input, malformed JSON, or a non-object
    JSON value).
    """
    try:
        if sys.stdin.isatty():
            return None
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return None
    if not raw or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None
