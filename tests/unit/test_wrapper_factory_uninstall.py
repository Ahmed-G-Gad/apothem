# SPDX-License-Identifier: MIT

"""Behavior tests for the wrapper-factory uninstall shims.

Covers the H2 project-scope uninstall factory: the direct-module-call fallback
must derive the project root from the adapter's declared ``relative_target``
component count, not a hardcoded ``parents[N]`` magic index, so a manifest
target-depth change can never silently derive the wrong root.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.wrapper_factories import make_project_scope_uninstall


def _record_project_root(monkeypatch: pytest.MonkeyPatch) -> list[Path | None]:
    """Patch ``run_uninstall`` to record the ``project_root`` it receives."""
    seen: list[Path | None] = []

    def fake_run_uninstall(
        harness_name: str,
        *,
        harness_root: Path | None = None,
        project_root: Path | None = None,
    ) -> None:
        seen.append(project_root)

    monkeypatch.setattr(install_driver, "run_uninstall", fake_run_uninstall)
    return seen


@pytest.mark.parametrize(
    "relative_target",
    [
        Path(".cursor") / "rules" / "apothem-rules.mdc",  # depth 3
        Path(".github") / "copilot-instructions.md",  # depth 2
        Path("GEMINI.md"),  # depth 1
        Path(".rules"),  # depth 1 (flat dotfile)
        Path("a") / "b" / "c" / "d" / "target.md",  # depth 5 (future manifest depth)
    ],
)
def test_direct_call_derives_project_root_from_relative_target(
    relative_target: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A direct module call (no ``project``) recovers the exact project root.

    The factory ascends ``len(relative_target.parts)`` parents from the resolved
    on-disk target — the same path the adapter's ``resolve_output_path`` joins
    onto the project root — so the derived root equals the project root for any
    target depth, with no hardcoded index to keep in sync.
    """
    seen = _record_project_root(monkeypatch)
    uninstall = make_project_scope_uninstall(
        "some_harness", relative_target=relative_target
    )

    project_root = tmp_path / "operator-project"
    resolved_target = project_root / relative_target

    uninstall(resolved_target)

    assert seen == [project_root]


def test_direct_call_root_is_independent_of_a_hardcoded_depth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two targets at different depths both recover the same project root.

    This is the regression guard for the retired ``output_path.parents[N]``
    fallback: a single hardcoded index cannot be correct for both a depth-2 and
    a depth-4 target, but deriving depth from ``relative_target`` is correct for
    both — proving the derivation is not a fixed magic depth.
    """
    project_root = tmp_path / "operator-root"

    shallow = Path(".github") / "instructions.md"  # depth 2
    deep = Path(".tool") / "nested" / "rules" / "apothem.md"  # depth 4

    seen = _record_project_root(monkeypatch)

    make_project_scope_uninstall("shallow_harness", relative_target=shallow)(
        project_root / shallow
    )
    make_project_scope_uninstall("deep_harness", relative_target=deep)(
        project_root / deep
    )

    assert seen == [project_root, project_root]


def test_explicit_project_takes_precedence_over_derivation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the CLI supplies ``project``, the derivation is bypassed entirely.

    The supplied root is threaded straight through regardless of what
    ``output_path`` would derive, matching the adapter-path contract.
    """
    seen = _record_project_root(monkeypatch)
    relative_target = Path(".cursor") / "rules" / "apothem-rules.mdc"
    uninstall = make_project_scope_uninstall("cursor", relative_target=relative_target)

    explicit = tmp_path / "explicit-project"
    # An output_path that would derive a *different* root if the fallback fired.
    misleading_output = tmp_path / "somewhere" / "else" / relative_target

    uninstall(misleading_output, project=explicit)

    assert seen == [explicit]
