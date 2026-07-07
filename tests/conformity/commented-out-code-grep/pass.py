# SPDX-License-Identifier: MIT

"""Sample module — every comment is why-not-what prose.

Why-not-what comments are welcome; commented-out logic is not. This
fixture's comments explain intent or invariants without disabling
executable lines.
"""

# This module is the PASS fixture for the commented-out-code grep.
# The grep walks comment runs and only flags those whose stripped
# bodies look like code; pure prose runs (such as this header block)
# pass clean.

from __future__ import annotations

# The constant below is named rather than inlined because three call
# sites depend on the same value, and the rule's M13.10 magic-number
# discipline forbids the literal repetition.
DEFAULT_TIMEOUT_SECONDS = 30


def fetch(url: str) -> str:
    """Return the response body for a URL.

    The function name is intent-revealing; no commented-out alternative
    implementation lurks in the body.
    """
    return f"<response from {url}>"
