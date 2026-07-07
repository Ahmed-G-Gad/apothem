# SPDX-License-Identifier: MIT

"""Assert the plan workflow routes durable outputs under suite-local _outputs/.

The suite-local output convention requires writeful plan commands to place
their durable, operator-facing emissions under each suite's own ``_outputs/``
directory (``<suite>/_outputs/`` or the ``{suite}/_outputs/`` placeholder
form) rather than at an ad-hoc or global location. This is a content/spec
assertion against the command definition files: ``plan-audit`` persists a
bounded audit report and ``plan-execute`` mirrors phase reports, both under
a suite-local ``_outputs/`` path. Deterministic — reads the command files
and checks the routing language is present and suite-scoped.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_COMMANDS_DIR: Final[Path] = _REPO_ROOT / "src" / "apothem" / "commands"

# The seven planning stages are first-class top-level commands, each
# independently invocable (the /plan decomposition).
_PLAN_AUDIT: Final[Path] = _COMMANDS_DIR / "plan-audit.md"
_PLAN_EXECUTE: Final[Path] = _COMMANDS_DIR / "plan-execute.md"

# Either the angle-bracket prose form `<suite>/_outputs/` or the brace
# placeholder form `{suite}/_outputs/` is a suite-local output route.
_SUITE_LOCAL_OUTPUTS_RE: Final[re.Pattern[str]] = re.compile(r"[<{]suite[>}]/_outputs/")


def test_command_files_exist() -> None:
    assert _PLAN_AUDIT.is_file(), _PLAN_AUDIT
    assert _PLAN_EXECUTE.is_file(), _PLAN_EXECUTE


def test_plan_audit_routes_outputs_to_suite_local_dir() -> None:
    body = _PLAN_AUDIT.read_text(encoding="utf-8")
    assert _SUITE_LOCAL_OUTPUTS_RE.search(body), (
        "plan-audit must route its durable audit report under <suite>/_outputs/"
    )
    # The audit report is the concrete durable emission routed there.
    assert "audit-report-" in body
    assert "_outputs/audit-report-" in body


def test_plan_execute_routes_outputs_to_suite_local_dir() -> None:
    body = _PLAN_EXECUTE.read_text(encoding="utf-8")
    assert _SUITE_LOCAL_OUTPUTS_RE.search(body), (
        "plan-execute must mirror operator-facing reports under {suite}/_outputs/"
    )
    # The operator-facing phase mirror is the concrete emission routed there.
    assert "_outputs/" in body
    assert "REPORT.md" in body


def test_both_commands_use_consistent_suite_local_convention() -> None:
    # Neither command may route durable outputs to a global or ad-hoc
    # location. Every `_outputs/` reference is either bare prose (e.g.
    # "details go to `_outputs/`") or carries the suite-local placeholder
    # prefix; none is rooted at a global directory such as `.plans/_outputs/`.
    for path in (_PLAN_AUDIT, _PLAN_EXECUTE):
        body = path.read_text(encoding="utf-8")
        assert "_outputs/" in body, path
        # The full suite-local path form must appear at least once.
        assert _SUITE_LOCAL_OUTPUTS_RE.search(body), path
        # No `_outputs/` reference is rooted at a global plans directory.
        assert ".plans/_outputs/" not in body, path
        # Every path-prefixed `_outputs/` (a slash immediately before
        # `_outputs/`) must be the suite-local placeholder form.
        for match in re.finditer(r"[^\s`]*/_outputs/", body):
            token = match.group()
            assert _SUITE_LOCAL_OUTPUTS_RE.search(token), (
                f"{path}: non-suite-local outputs route {token!r}"
            )
