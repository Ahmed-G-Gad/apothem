# SPDX-License-Identifier: MIT

"""Strip maintainer-only text from a hook message before it reaches the model.

Why this module exists. Every hook message file under ``hooks/messages/`` opens
with the single-line SPDX license comment, and the conformity gate expects a
closing ``## Bindings`` section that records the message's place in the rule
graph. Both serve maintainers and the gate, which read the source file. Neither
helps the model, and every byte a hook injects is paid on the turn it fires. The
emitters (``emit_hook_context``, ``session_end_gate``,
``session_start_bootstrap``) pass message bodies through this one function, so
the rule cannot drift between them. Stdlib-only: the hook runtime ships without
the ``apothem`` package on plugin-alone installs.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["strip_maintainer_text"]

_COMMENT_OPEN: Final[str] = "<!--"
_COMMENT_CLOSE: Final[str] = "-->"
_BINDINGS_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+Bindings\b")


def _is_maintainer_comment(line: str) -> bool:
    """Return whether *line* is one whole HTML comment and nothing else.

    The length floor keeps the opener and the closer from sharing characters:
    ``<!-->`` starts with one and ends with the other, yet it is not a comment.
    """
    stripped = line.strip()
    return (
        len(stripped) >= len(_COMMENT_OPEN) + len(_COMMENT_CLOSE)
        and stripped.startswith(_COMMENT_OPEN)
        and stripped.endswith(_COMMENT_CLOSE)
    )


def strip_maintainer_text(text: str) -> str:
    """Return *text* without single-line HTML comments and the Bindings section.

    Everything from a ``## Bindings`` heading onward is dropped: the section is
    the closing block of a message file by convention. Leading and trailing
    blank lines are trimmed.
    """
    kept: list[str] = []
    for line in text.splitlines():
        if _BINDINGS_HEADING_RE.match(line):
            break
        if _is_maintainer_comment(line):
            continue
        kept.append(line)
    return "\n".join(kept).strip()
