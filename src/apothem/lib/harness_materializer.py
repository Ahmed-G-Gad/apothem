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

from apothem.lib.frontmatter import split_frontmatter
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


def defuse_sentinels(body: str) -> str:
    """Return *body* with any embedded managed-block sentinel neutralized.

    Profile text (rules, identity strings) reaches the body verbatim. A literal
    sentinel inside it would end the block early (or open a second one), and
    uninstall would then keep the tail as if it were operator prose. Each
    sentinel's opening ``<!--`` is written as the entity ``&lt;!--``: the text
    still reads the same, but it no longer matches the frozen sentinel strings.
    """
    for sentinel in (APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END):
        body = body.replace(sentinel, "&lt;" + sentinel[1:])
    return body


def wrap_managed_block(body: str) -> str:
    """Return *body* wrapped in the canonical Apothem managed-block sentinels.

    The wrapped form is the unit Apothem writes into an operator-owned
    Markdown anchor. The body is stripped of surrounding blank lines so the
    block is byte-stable across re-installs (idempotency depends on the
    wrapped form being identical for identical bodies). Sentinels inside the
    body are neutralized first, so profile text cannot split the block.
    """
    safe = defuse_sentinels(body.strip())
    return f"{APOTHEM_BLOCK_BEGIN}\n{safe}\n{APOTHEM_BLOCK_END}\n"


_FENCES: Final[tuple[str, ...]] = ("```", "~~~")


def _scan_markers(
    text: str, *, fences: bool
) -> tuple[list[tuple[str, int, int]], bool]:
    """Return the marker lines in *text* and whether a fence stays open at the end.

    Each marker is ``(marker, start, end)``; see :func:`_marker_lines`.
    """
    found: list[tuple[str, int, int]] = []
    fence = ""
    offset = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        lead = body.lstrip(" ")
        indent = len(body) - len(lead)
        if fence:
            if indent <= 3 and lead.startswith(fence):
                fence = ""
        elif fences and indent <= 3 and lead.startswith(_FENCES):
            fence = lead[:3]
        elif (token := body.strip()) in (APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END):
            start = offset + body.index(token)
            found.append((token, start, start + len(token)))
        offset += len(line)
    return found, bool(fence)


def _marker_lines(text: str) -> list[tuple[str, int, int]]:
    """Return the markers in *text* that Apothem could have written.

    A marker counts only as a whole line of its own (spaces aside) outside a
    fenced code block, which is how Apothem writes it: a marker an operator
    quotes in a sentence or in a code example is their text. A fence left open
    at the end of the text marks nothing for certain, so then fences are not
    taken into account at all.
    """
    found, unclosed = _scan_markers(text, fences=True)
    if unclosed:
        found, _ = _scan_markers(text, fences=False)
    return found


def _block_span(text: str) -> tuple[int, int] | None:
    """Return where the first whole managed block in *text* starts and ends.

    The block is the first END marker together with the nearest BEGIN marker
    before it (see :func:`_marker_lines` for what counts as a marker).
    """
    begin: int | None = None
    for marker, start, end in _marker_lines(text):
        if marker == APOTHEM_BLOCK_BEGIN:
            begin = start
        elif begin is not None:
            return begin, end
    return None


def complete_managed_block(text: str) -> str | None:
    """Return the managed block in *text* only when it has both sentinels.

    The block is the first end sentinel together with the nearest begin
    sentinel before it, returned with both, exactly as in *text*. A sentinel
    counts only as a whole line of its own outside a fenced code block (see
    :func:`_marker_lines`), so one an operator quotes is their text. So a begin
    sentinel left without its end above a whole block is not taken as the start
    of the block, and the text after it stays. A begin sentinel with no end
    sentinel after it (a block cut short or edited by hand) returns ``None``:
    nothing shows where Apothem's text stops and the operator's starts, so no
    install, update or uninstall cuts the text after it (see
    :func:`has_stray_begin`).
    """
    span = _block_span(text)
    return None if span is None else text[span[0] : span[1]]


def has_stray_begin(text: str) -> bool:
    """Return True when *text* holds a begin sentinel that starts no whole block.

    Each end sentinel closes the nearest begin sentinel before it; a begin
    sentinel left open is stray: a block that lost its end sentinel, or a
    marker line the operator wrote (see :func:`_marker_lines`). Install and
    update keep the text after it and write a block of their own apart from it,
    and verify reports the file.
    """
    open_begin = False
    for marker, _start, _end in _marker_lines(text):
        if marker == APOTHEM_BLOCK_BEGIN:
            if open_begin:
                return True
            open_begin = True
        else:
            open_begin = False
    return open_begin


def extract_managed_block(text: str) -> str | None:
    """Return the managed-block region found in *text*, or ``None``.

    A whole block (see :func:`complete_managed_block`) is returned as it is.
    A begin sentinel with no end sentinel after it returns the region from that
    sentinel to the end of the text, so callers can tell such a marker is there
    (an uninstall names the file; an install keeps the text). Nothing removes
    or replaces that region. ``None`` only when no begin sentinel is present.
    """
    span = _block_span(text)
    if span is not None:
        return text[span[0] : span[1]]
    begins = [
        start
        for marker, start, _ in _marker_lines(text)
        if marker == APOTHEM_BLOCK_BEGIN
    ]
    return text[begins[0] :] if begins else None


def merge_managed_block(existing: str, body: str) -> str:
    """Merge an Apothem managed block carrying *body* into *existing* text.

    Three cases, all preserving operator prose:

    - *existing* is empty — return the wrapped block alone.
    - *existing* already carries a whole managed block — replace that block
      in place, leaving operator prose before and after it untouched.
    - *existing* carries no whole managed block — append the wrapped block
      after the operator's content, separated by one blank line. A begin
      sentinel with no end after it is such a case: its text is kept, and the
      next merge finds the appended block by its own sentinels.

    The merge is idempotent: re-merging the same *body* into text that
    already carries the resulting block returns byte-identical output.

    A *body* that opens with YAML frontmatter (the rule-file templates whose
    activation keys a harness reads from byte 0) is emitted frontmatter first;
    see :func:`_merge_frontmatter_block`.
    """
    body_parts = split_frontmatter(body)
    if body_parts is not None:
        return _merge_frontmatter_block(existing, *body_parts)
    wrapped = wrap_managed_block(body)
    if not existing.strip():
        return wrapped
    span = _block_span(existing)
    if span is not None:
        # Spliced by position: a copy of the block the operator quotes in a
        # code example above it must stay as it is.
        return existing[: span[0]] + wrapped.rstrip("\n") + existing[span[1] :]
    separator = "" if existing.endswith("\n") else "\n"
    return f"{existing}{separator}\n{wrapped}"


def _owned_frontmatter_split(text: str) -> tuple[str, str] | None:
    """Return ``(frontmatter, rest)`` when *text* has the frontmatter-first shape.

    The shape is a byte-0 frontmatter block immediately followed by the BEGIN
    sentinel, with no blank line between them. Only
    :func:`_merge_frontmatter_block` writes it, so the frontmatter is Apothem's.
    An operator file with its own frontmatter that later received an appended
    block always has a blank line (and usually prose) before the sentinel, so it
    never matches.
    """
    parts = split_frontmatter(text)
    if parts is None or parts[1].split("\n", 1)[0].strip() != APOTHEM_BLOCK_BEGIN:
        return None
    return parts


def _merge_frontmatter_block(existing: str, frontmatter: str, body: str) -> str:
    """Merge a frontmatter-carrying managed body, keeping the frontmatter first.

    Emits ``frontmatter``, then the BEGIN sentinel, *body* and the END sentinel,
    then any operator prose. Three cases for *existing*:

    - It already has the frontmatter-first shape: Apothem's frontmatter and
      block are both replaced; operator prose after the block is kept.
    - It opens with the operator's own frontmatter: that frontmatter governs the
      file, so the block (without Apothem's frontmatter) is folded in as for a
      plain body.
    - Anything else (empty, operator prose, or a legacy install whose
      frontmatter sat inside the block): any existing block is removed and the
      frontmatter-first unit is written at the top, with the operator prose
      moved below it.
    """
    owned = _owned_frontmatter_split(existing)
    if owned is None and split_frontmatter(existing) is not None:
        return merge_managed_block(existing, body)
    remainder = owned[1] if owned is not None else existing
    operator = _remove_block(remainder)
    head = frontmatter if frontmatter.endswith("\n") else f"{frontmatter}\n"
    emitted = head + wrap_managed_block(body)
    if operator.strip():
        emitted += f"\n{operator}"
    return emitted


def remove_managed_block(existing: str) -> str:
    """Return *existing* with the Apothem managed block surgically removed.

    The inverse of :func:`merge_managed_block`: strips the managed block (and the
    blank-line separator the merge inserted around it) while preserving operator
    prose before and after it. When the remainder is whitespace-only — i.e. the
    anchor was Apothem-only — returns the empty string so the caller can delete
    the now-empty file rather than leaving a stub. Returns *existing* unchanged
    when it carries no complete managed block: a begin sentinel with no end
    sentinel after it stays, with any text below it, since nothing shows where
    the block ended (see :func:`complete_managed_block`).

    Round-trips byte-for-byte for the canonical case: an operator prose block
    ending in a single newline, merged-then-removed, returns the original.

    For the frontmatter-first shape (Apothem's frontmatter directly followed by
    the block), the frontmatter is removed together with the block. The first
    whole block goes, and so does each later exact copy of it (a block pasted
    in twice); any other whole block, such as a marker pair the operator
    quotes, stays.
    """
    first = complete_managed_block(existing)
    text = _remove_block(existing)
    while first is not None and complete_managed_block(text) == first:
        text = _remove_block(text)
    return text


def _remove_block(existing: str) -> str:
    """Return *existing* without the block *find* locates in it.

    Only the first whole block goes (see :func:`complete_managed_block`); the
    frontmatter merge uses it so a second block, or a marker pair the
    operator quotes, stays. See :func:`remove_managed_block`.
    """
    owned = _owned_frontmatter_split(existing)
    if owned is not None:
        rest = _remove_block(owned[1])
        # No block to take out after Apothem's frontmatter: keep the file whole.
        return existing if rest == owned[1] else rest
    span = _block_span(existing)
    if span is None:
        return existing
    before = existing[: span[0]].rstrip("\n")
    after = existing[span[1] :].lstrip("\n")
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
