# SPDX-License-Identifier: MIT

"""A write of plan-shaped content to a non-``.plans/`` global-ecosystem
location triggers the soft-flag verdict.

Filename heuristics (``*plan*.md`` / ``*notes*.md`` / ``*draft*.md``) and
plan-shaped frontmatter markers route the write through a
`structured inquiry` proposing redirection. The soft-flag option set is
distinct from the redirect-required set: it offers ``write-as-proposed`` for
false-positive cases. Per the EN-1 advisory posture, the hook reports the
soft-flag verdict and recommends redirection; it does not block.
"""

from __future__ import annotations


def test_soft_flag_class_declared(write_plan_guard_text: str) -> None:
    """The verdict matrix declares the soft-flag class."""
    assert "**Soft-flag**" in write_plan_guard_text


def test_soft_flag_filename_heuristics_named(write_plan_guard_text: str) -> None:
    """The soft-flag predicate names the canonical filename heuristics."""
    assert "*plan*.md" in write_plan_guard_text
    assert "*notes*.md" in write_plan_guard_text
    assert "*draft*.md" in write_plan_guard_text


def test_soft_flag_frontmatter_signature_named(write_plan_guard_text: str) -> None:
    """The soft-flag predicate names the plan-shaped frontmatter markers."""
    for marker in ("name:", "phases:", "master-plan:", "phase-id:"):
        assert marker in write_plan_guard_text, f"missing frontmatter marker: {marker}"


def test_soft_flag_offers_write_as_proposed_escape_hatch(
    write_plan_guard_text: str,
) -> None:
    """The soft-flag action delegates to the canonical soft-flag option-set.

    The 3-option soft-flag set (redirect-to-project-plans recommended /
    write-as-proposed escape hatch / cancel) lives in the canonical
    Plans-Locality option-set at §5.9.2; the message references it rather
    than inlining the labels.
    """
    soft_section_index = write_plan_guard_text.index("**Action — soft-flag path.**")
    fail_disposition_index = write_plan_guard_text.index("**Fail-disposition.**")
    soft_section_body = write_plan_guard_text[soft_section_index:fail_disposition_index]
    assert "interactive-questions-canonical-shapes.md" in soft_section_body
    assert "5.9.2" in soft_section_body
