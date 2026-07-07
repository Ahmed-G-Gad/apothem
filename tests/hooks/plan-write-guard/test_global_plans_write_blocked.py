# SPDX-License-Identifier: MIT

"""A write whose target resolves under ``~/.claude/.plans/`` from a
downstream-project context is flagged redirect-required.

The plan-write-guard hook context declares the redirect-required verdict for
any target path under the global ``~/.claude/.plans/`` tree when the active
project root is NOT ``~/.claude/`` itself. The verdict surfaces a
`structured inquiry` with the redirect-to-project-plans option as the
recommended path. Per the EN-1 advisory posture, the hook reports the verdict
and recommends the redirect; it does not block the tool call. Mechanical
enforcement of Plans-Locality runs in CI.
"""

from __future__ import annotations


def test_redirect_required_class_declared(write_plan_guard_text: str) -> None:
    """The Write/Edit/NotebookEdit guard declares the redirect-required class."""
    assert "**Redirect-required**" in write_plan_guard_text
    assert "~/.claude/.plans/" in write_plan_guard_text


def test_redirect_required_recommended_option_present(
    write_plan_guard_text: str,
) -> None:
    """The redirect-required structured inquiry delegates to the canonical option-set.

    The option labels (redirect-to-project-plans recommended / cancel) live
    in the canonical Plans-Locality option-set rather than inline in the
    hook message; the message references the canonical §5.9.1 variant.
    """
    assert "interactive-questions-canonical-shapes.md" in write_plan_guard_text
    assert "5.9.1" in write_plan_guard_text


def test_redirect_required_cancel_option_present(write_plan_guard_text: str) -> None:
    """The redirect-required action delegates to the canonical option-set."""
    block_section_index = write_plan_guard_text.index(
        "**Action — redirect-required path.**"
    )
    soft_flag_section_index = write_plan_guard_text.index(
        "**Action — soft-flag path.**"
    )
    redirect_body = write_plan_guard_text[block_section_index:soft_flag_section_index]
    # The cancel option lives in the canonical option-set the redirect-required
    # action references (the 2-option redirect-required variant at §5.9.1).
    assert "5.9.1" in redirect_body


def test_redirect_required_path_class_includes_nested_plans(
    write_plan_guard_text: str,
) -> None:
    """The verdict matrix names ``~/.claude/<anything>/.plans/`` under redirect-required."""
    assert "~/.claude/<anything>/.plans/" in write_plan_guard_text
