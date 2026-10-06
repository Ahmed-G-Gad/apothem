# SPDX-License-Identifier: MIT

"""Module-boundary pins for the install_driver decomposition.

These tests fail loudly if the decomposed install driver silently re-forms into
a god-object, if the public re-export surface regresses, if a concern-module
balloons past the size ceiling, or if the intra-package import graph grows a
cycle. They are the structural counterpart to the behavior-diff oracle in
``test_install_driver_behavior_diff.py`` (which pins runtime behavior).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver

SHARED = Path(install_driver.__file__).resolve().parent
SHIM = SHARED / "install_driver.py"

# The decomposition's concern-modules. Adding or removing one is a deliberate
# structural change that must update this pin.
EXPECTED_MODULES = {
    "install_driver_types",
    "install_driver_pathsafety",
    "install_driver_backup",
    "install_driver_converters",
    "install_driver_layout",
    "install_driver_merge",
    "install_driver_jsonmerge",
    "install_driver_ownership",
    "install_driver_removal",
    "install_driver_reversal",
    "install_driver_retention",
    "install_driver_planvalidation",
    "install_driver_preview",
    "install_driver_treeops",
    "install_driver_apply",
    "install_driver_materialize",
    "install_driver_lifecycle",
}

# Per-module soft ceiling. The decomposition target is <=~600 lines; the pin
# allows a small margin so cosmetic edits don't trip it, but a module growing
# back toward god-object size fails. The shim is held much tighter.
MODULE_LINE_CEILING = 700
SHIM_LINE_CEILING = 320

# Symbols consumers reach through the shim by module-qualified or by-name access
# (public __all__ plus the internal seams adapters/tests depend on). The shim
# MUST keep all of them resolvable from the prior import path.
CONSUMER_PRIVATE_SURFACE = {
    "_OUTCOMES",
    "_capability_projection_results",
    "_compensating_rollback",
    "_directory_contents_equal",
    "_dispatch_install_entry",
    "_install_lock_path",
    "_is_apothem_hook",
    "_merge_json_values",
    "_write_file_atomically",
    "_filesystem_is_case_insensitive",
    "_materialize_data_surfaces",
    "_validate_target_path",
    "_within_allowed_root",
    "project_profile_document",
    "render_content_tokens",
}

# External names the shim re-exports as module attributes for consumers that
# access install_driver.<name> (not part of __all__ but historically reachable).
EXTERNAL_REEXPORTS = {"install_ledger", "load_manifest", "resolve_target"}


def _concern_modules() -> dict[str, Path]:
    return {path.stem: path for path in SHARED.glob("install_driver_*.py")}


def test_concern_module_set_is_pinned() -> None:
    assert set(_concern_modules()) == EXPECTED_MODULES


def test_shim_re_exports_full_public_surface() -> None:
    for name in install_driver.__all__:
        assert hasattr(install_driver, name), f"shim lost public symbol {name}"
    assert len(install_driver.__all__) == 56


def test_shim_exposes_consumer_private_surface() -> None:
    missing = sorted(
        name
        for name in CONSUMER_PRIVATE_SURFACE | EXTERNAL_REEXPORTS
        if not hasattr(install_driver, name)
    )
    assert not missing, f"shim no longer exposes consumer-reached symbols: {missing}"


def test_shim_is_a_thin_re_export_not_a_god_object() -> None:
    tree = ast.parse(SHIM.read_text(encoding="utf-8"))
    defs = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    assert not defs, (
        f"shim must hold no defs/classes (re-export only); found {[d.name for d in defs]}"
    )
    assert SHIM.read_text(encoding="utf-8").count("\n") <= SHIM_LINE_CEILING


@pytest.mark.parametrize(("stem", "path"), sorted(_concern_modules().items()))
def test_module_under_size_ceiling(stem: str, path: Path) -> None:
    lines = path.read_text(encoding="utf-8").count("\n")
    assert lines <= MODULE_LINE_CEILING, (
        f"{stem} grew to {lines} lines (ceiling {MODULE_LINE_CEILING})"
    )


def test_intra_package_import_graph_is_acyclic() -> None:
    modules = _concern_modules()
    graph: dict[str, set[str]] = {stem: set() for stem in modules}
    for stem, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.level == 1
                and node.module in modules
            ):
                graph[stem].add(node.module)
    # DFS cycle detection.
    color = dict.fromkeys(modules, 0)

    def visit(u: str, stack: list[str]) -> list[str] | None:
        color[u] = 1
        for v in sorted(graph[u]):
            if color[v] == 1:
                return [*stack, u, v]
            if color[v] == 0:
                found = visit(v, [*stack, u])
                if found:
                    return found
        color[u] = 2
        return None

    for stem in sorted(modules):
        if color[stem] == 0:
            cycle = visit(stem, [])
            assert cycle is None, f"import cycle: {' -> '.join(cycle)}"
