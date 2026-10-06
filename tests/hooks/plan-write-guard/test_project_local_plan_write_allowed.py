# SPDX-License-Identifier: MIT

"""A write outside the protected plans-discipline regions passes through
silently — under the Plans-Locality mandate the sole canonical destination
for plan artifacts is ``<project-root>/.apothem/plans/``, and a legacy
``<project-root>/.plans/`` tree is redirect-recommended to it.

The plan-write-guard hook declares the catch-all ``Allow`` class for
writes whose target falls outside the protected predicate classes
(global ``~/.claude/.plans/`` redirect-required, non-``.plans/`` global
soft-flag). Ordinary project-local writes fall under this allow class.
"""

from __future__ import annotations


def test_allow_class_declared(write_plan_guard_text: str) -> None:
    """The verdict matrix declares the catch-all Allow class."""
    assert "**Allow**" in write_plan_guard_text
    assert "Allow** unchanged" in write_plan_guard_text


def test_allow_class_is_default(write_plan_guard_text: str) -> None:
    """Any write not under the redirect-required / soft-flag classes is Allow."""
    assert "Any other write" in write_plan_guard_text


def test_redirect_target_is_project_local(write_plan_guard_text: str) -> None:
    """The guard text names the legacy project-local .plans/ tree it redirects."""
    assert "<project-root>/.plans/" in write_plan_guard_text


def test_settings_json_wires_plan_guard_on_write(
    settings_json: dict[str, object],
) -> None:
    """The settings file wires the plan-write-guard on Write matcher."""
    pretooluse = settings_json["hooks"]["PreToolUse"]  # type: ignore[index]
    write_matcher = next(m for m in pretooluse if m["matcher"] == "Write")
    hook_args = [" ".join(h.get("args", [])) for h in write_matcher["hooks"]]
    assert any("pretooluse-write-plan-guard" in args for args in hook_args), (
        "Write matcher missing plan-write-guard wiring"
    )


def test_settings_json_wires_plan_guard_on_all_four_matchers(
    settings_json: dict[str, object],
) -> None:
    """The settings file wires the plan-write-guard on all four matchers."""
    pretooluse = settings_json["hooks"]["PreToolUse"]  # type: ignore[index]
    matchers_with_plan_guard: set[str] = set()
    for matcher_block in pretooluse:
        for hook in matcher_block["hooks"]:
            args = " ".join(hook.get("args", []))
            if (
                "pretooluse-write-plan-guard" in args
                or "pretooluse-bash-plan-guard" in args
            ):
                matchers_with_plan_guard.add(matcher_block["matcher"])
    assert matchers_with_plan_guard == {
        "Write",
        "Edit",
        "NotebookEdit",
        "Bash|PowerShell",
    }
