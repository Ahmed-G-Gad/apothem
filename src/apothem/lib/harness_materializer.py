# SPDX-License-Identifier: MIT

"""Shared building blocks for per-harness materializers.

These helpers cover profile-to-Markdown field extraction and the legacy
managed-YAML body shape retained for compatibility tests. Current harness
materializers that target strict vendor schemas should emit only documented
keys instead of using the generic managed body.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

import yaml

from apothem.lib.profile import DEFAULT_LANGUAGE, DEFAULT_STYLE, coerce_profile

# Canonical sentinel pair delimiting the Apothem-managed block inside an
# operator-owned Markdown instruction anchor (AGENTS.md, GEMINI.md, QWEN.md,
# copilot-instructions.md, and the project-scope rule files). The pair is the
# stable, documented merge boundary each harness dossier references: Apothem
# owns only the bytes between the sentinels; operator prose outside is
# preserved verbatim. Changing these strings would orphan every previously
# installed managed block, so they are a frozen contract.
APOTHEM_BLOCK_BEGIN: Final[str] = "<!-- BEGIN APOTHEM MANAGED BLOCK -->"
APOTHEM_BLOCK_END: Final[str] = "<!-- END APOTHEM MANAGED BLOCK -->"


def wrap_managed_block(body: str) -> str:
    """Return *body* wrapped in the canonical Apothem managed-block sentinels.

    The wrapped form is the unit Apothem writes into an operator-owned
    Markdown anchor. The body is stripped of surrounding blank lines so the
    block is byte-stable across re-installs (idempotency depends on the
    wrapped form being identical for identical bodies).
    """
    return f"{APOTHEM_BLOCK_BEGIN}\n{body.strip()}\n{APOTHEM_BLOCK_END}\n"


def extract_managed_block(text: str) -> str | None:
    """Return the managed-block region found in *text*, or ``None``.

    A well-formed block (begin sentinel followed by an end sentinel) returns
    both sentinels and the body between them, exactly as in *text*. An *orphan*
    begin sentinel with no following end sentinel (a truncated or
    operator-mangled block) returns the degenerate region from the begin
    sentinel to end-of-text, so :func:`merge_managed_block` REPLACES it in place
    rather than appending a second block. Appending on an orphan would leave a
    two-begin file whose next merge swallows the operator text trapped between
    the orphan begin and the appended block — so the orphan is reclaimed on the
    first merge instead (operator prose *before* the orphan begin is always
    preserved; the caller writes a backup of the prior file). ``None`` only when
    no begin sentinel is present at all.
    """
    begin = text.find(APOTHEM_BLOCK_BEGIN)
    if begin == -1:
        return None
    end = text.find(APOTHEM_BLOCK_END, begin + len(APOTHEM_BLOCK_BEGIN))
    if end == -1:
        return text[begin:]
    return text[begin : end + len(APOTHEM_BLOCK_END)]


def merge_managed_block(existing: str, body: str) -> str:
    """Merge an Apothem managed block carrying *body* into *existing* text.

    Three cases, all preserving operator prose:

    - *existing* is empty — return the wrapped block alone.
    - *existing* already carries a managed block — replace that block in
      place, leaving operator prose before and after it untouched.
    - *existing* carries no managed block — append the wrapped block after
      the operator's content, separated by one blank line.

    The merge is idempotent: re-merging the same *body* into text that
    already carries the resulting block returns byte-identical output.
    """
    wrapped = wrap_managed_block(body)
    if not existing.strip():
        return wrapped
    current_block = extract_managed_block(existing)
    if current_block is not None:
        return existing.replace(current_block, wrapped.rstrip("\n"), 1)
    separator = "" if existing.endswith("\n") else "\n"
    return f"{existing}{separator}\n{wrapped}"


def remove_managed_block(existing: str) -> str:
    """Return *existing* with the Apothem managed block surgically removed.

    The inverse of :func:`merge_managed_block`: strips the managed block (and the
    blank-line separator the merge inserted around it) while preserving operator
    prose before and after it. When the remainder is whitespace-only — i.e. the
    anchor was Apothem-only — returns the empty string so the caller can delete
    the now-empty file rather than leaving a stub. Returns *existing* unchanged
    when it carries no managed block (including a degenerate orphan-begin block,
    which :func:`extract_managed_block` reclaims).

    Round-trips byte-for-byte for the canonical case: an operator prose block
    ending in a single newline, merged-then-removed, returns the original.
    """
    block = extract_managed_block(existing)
    if block is None:
        return existing
    index = existing.find(block)
    before = existing[:index].rstrip("\n")
    after = existing[index + len(block) :].lstrip("\n")
    if before and after:
        remainder = f"{before}\n\n{after}"
    elif before:
        remainder = f"{before}\n"
    else:
        remainder = after
    return "" if not remainder.strip() else remainder


@dataclass(frozen=True)
class MarkdownProfileFields:
    """The profile fields the Markdown-output adapters render into their body.

    Carries the full identity (name/role/email/website/github), both
    preference scalars (language/style), the seriousness band, the rules
    list (+ its pre-rendered block), and the opted-in enforcement flags. The
    optional fields default to absent so an empty profile renders cleanly; the
    projection seam omits any field with no value.
    """

    name: str
    role: str
    language: str
    rules: list[str]
    seriousness: str
    extra_rules_block: str
    style: str = DEFAULT_STYLE
    email: str | None = None
    website: str | None = None
    github: str | None = None
    enforcement: Mapping[str, bool] = field(default_factory=dict)


def extract_markdown_fields(profile: dict[str, Any]) -> MarkdownProfileFields:
    """Extract the canonical Markdown-output field set from *profile*.

    The defaults are delegated to the canonical profile model so Markdown
    helpers and schema-backed profile loading cannot drift. Accepts either a
    raw profile dict or a ``CanonicalProfile.for_harness`` projection.
    """
    canonical = coerce_profile(profile)
    normalized = canonical.to_dict()
    identity = normalized["identity"]
    preferences = normalized["preferences"]
    rules: list[str] = normalized["rules"]
    return MarkdownProfileFields(
        name=identity["name"],
        role=identity["role"],
        language=preferences["language"],
        rules=rules,
        seriousness=normalized["seriousness"],
        extra_rules_block=_render_extra_rules_block(rules),
        style=preferences["style"],
        email=identity.get("email"),
        website=identity.get("website"),
        github=identity.get("github"),
        enforcement=dict(normalized["enforcement"]),
    )


def _render_extra_rules_block(rules: list[str]) -> str:
    """Format the optional ``## Custom Rules`` Markdown block.

    Empty when *rules* is empty; otherwise a two-newline-separated
    section header followed by a bullet list of rules.
    """
    if not rules:
        return ""
    body = "\n".join(f"- {r}" for r in rules)
    return f"\n\n## Custom Rules\n\n{body}"


def build_yaml_managed_config(profile: dict[str, Any], header: str) -> str:
    """Render the canonical ``apothem_managed`` YAML config body.

    Retained for compatibility with earlier generic materializers. The body
    carries the apothem-managed sentinel, the full identity + preferences
    sub-dicts (with their per-key defaults), the seriousness band, and an
    optional rules list.
    """
    normalized = coerce_profile(profile).to_dict()
    identity = normalized["identity"]
    preferences = normalized["preferences"]
    rules: list[str] = normalized["rules"]

    config: dict[str, Any] = {
        "apothem_managed": True,
        "identity": {
            "name": identity.get("name", ""),
            "role": identity.get("role", ""),
            "email": identity.get("email", ""),
        },
        "preferences": {
            "language": preferences.get("language", DEFAULT_LANGUAGE),
            "style": preferences.get("style", DEFAULT_STYLE),
        },
        "apothem_support": "apothem",
        "seriousness": normalized["seriousness"],
    }
    if rules:
        config["rules"] = rules

    return header + yaml.safe_dump(config, default_flow_style=False, allow_unicode=True)
