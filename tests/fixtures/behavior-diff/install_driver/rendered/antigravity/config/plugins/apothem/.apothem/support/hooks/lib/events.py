# SPDX-License-Identifier: MIT

"""Single source of truth for the supported hook-event vocabulary.

Both ``hooks/dispatch.py`` and ``hooks/emit_hook_context.py`` import
their event-vocabulary sets from this module. Future event additions
land here only; both consumers re-derive at import time.

Two sets are exposed:

* ``SUPPORTED_EVENTS`` — the whitelist of every hook event the
  dispatcher accepts. Adding an event here makes it routable; removing
  it forces a ``ValueError`` on dispatch attempt. Events listed here
  that are not yet wired in a harness settings file are accepted for
  forward compatibility — the dispatcher routes them the moment a
  settings entry materializes.

* ``HOOK_SPECIFIC_OUTPUT_EVENTS`` — the subset of ``SUPPORTED_EVENTS``
  whose envelope schema accepts the ``hookSpecificOutput`` shape.
  Events outside this subset (currently ``PreCompact`` and
  ``PostCompact``) fail strict schema validation on that shape and
  must use the top-level ``systemMessage`` field instead.
"""

from __future__ import annotations

from typing import Final

SUPPORTED_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "SessionStart",
        "PreCompact",
        "PostCompact",
        "Stop",
        "PreToolUse",
        "PostToolUse",
        "UserPromptSubmit",
        "Notification",
    }
)

HOOK_SPECIFIC_OUTPUT_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "SessionStart",
        "Stop",
        "PreToolUse",
        "PostToolUse",
        "UserPromptSubmit",
        "Notification",
    }
)
