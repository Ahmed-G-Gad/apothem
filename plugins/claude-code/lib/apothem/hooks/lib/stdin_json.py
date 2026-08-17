# SPDX-License-Identifier: MIT

"""Shared hook stdin JSON reader.

Four hook entry points read the harness's PreToolUse / PostToolUse /
statusline stdin payload. This is the canonical reader for that sequence.

Consumed by ``emit_hook_context`` only. ``askuserquestion_validator``,
``proactive_compaction_tracker`` and ``session_end_gate`` still carry a local
``_read_payload`` copy: they sit in ``hooks/`` rather than ``hooks/lib/`` and
set up no path to import from here, so adopting this reader means adding that
bootstrap to three entry points that run on every tool call — a change worth
reviewing rather than slipping in. Their bodies are otherwise identical to
this one and are kept deliberately in step; drift between them is the defect
this module exists to prevent, and it has happened once already (they caught
only ``OSError`` where this catches ``ValueError`` too).

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
