# SPDX-License-Identifier: MIT

"""Why this vocabulary exists — the terms the provenance verdict is written in.

The provenance builder emits a JSON record per plan file, and downstream
consumers — the migration-confirmation pass among them — read that record by
its vocabulary: the confidence ladder, the destination text, the suite-name
hint table. Those consumers care about the terms, not about how a file gets
scanned, so the terms are held apart from the scanning.

Scope. Pure declaration. The detection regexes deliberately stay in the
builder: they are module-private machinery serving its parsers, not part of
the contract a consumer reads.
"""

from __future__ import annotations

from typing import Final

# The single suite name that earns the literal recursive-self
# annotation. The migration-confirmation pass reads this constant
# transitively via the JSON output.
RECURSIVE_SELF_SUITE: Final[str] = "-".join(("apothem", "production", "hardening"))

# Confidence tiers. ``recursive-self`` is reserved for the suite above;
# the cascade in :func:`_resolve_suite` assigns the remaining four.
CONFIDENCE_RECURSIVE_SELF: Final[str] = "recursive-self"
CONFIDENCE_HIGH: Final[str] = "high"
CONFIDENCE_MEDIUM: Final[str] = "medium"
CONFIDENCE_LOW: Final[str] = "low"
CONFIDENCE_UNMAPPABLE: Final[str] = "unmappable"

ALL_CONFIDENCES: Final[tuple[str, ...]] = (
    CONFIDENCE_RECURSIVE_SELF,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    CONFIDENCE_UNMAPPABLE,
)

# Canonical natural-domain rationale for the recursive case. The
# plan-internal-isolation discipline forbids planning-internal tokens
# from leaking into produced artifacts; this string is the natural-
# domain phrasing every consumer reads.
ECOSYSTEM_DESTINATION_TEXT: Final[str] = (
    "stay in place at the user-config root; the .plans directory is"
    " gitignored at the cleanup phase so the published tree carries"
    " no plan-product"
)

# File extensions the scanner considers part of a plan suite.
PLAN_EXTENSIONS: Final[frozenset[str]] = frozenset({".md", ".yml", ".yaml"})

# Suite-name prefix → built-in project hint. The mapping captures the
# operator's stated decomposition: each suite has a respective
# destination, and the suite name's prefix is the strongest single
# indicator of which destination that is.
SUITE_NAME_HINTS: Final[tuple[tuple[str, str], ...]] = (
    ("dc-kit-mini-", "dc-kit-mini"),
    ("dc-kit-ieee", "dc-kit"),
    ("claude-", "<ecosystem-self>"),
    ("agent-home-", "<ecosystem-self>"),
)

# The marker the suite-name heuristic emits when a suite resolves to
# the user-config ecosystem itself. Downstream code routes this marker
# to the canonical ECOSYSTEM_DESTINATION_TEXT and to the recursive-
# self vs ecosystem-archive confidence assignment.
ECOSYSTEM_SELF_MARKER: Final[str] = "<ecosystem-self>"
