# SPDX-License-Identifier: MIT

"""No package reaches another top-level package's underscore-prefixed names.

A name with a leading underscore is private to its package. When the CLI, the
benchmarks, or the entry module needs a helper that lives in another top-level
package (``apothem.harnesses``, ``apothem.lib``, ``apothem.cli``, ...), that
helper is a public seam and carries a public name; the private spelling may
survive as an alias for older importers, but no first-party code uses it across
a package boundary.

The scan walks every module under ``src/apothem`` (the vendored tree excluded)
and flags two shapes that cross a top-level package boundary:

- ``from apothem.<pkg>.<module> import _name``
- ``<module alias>._name``, where the alias is bound by ``import``,
  ``from ... import <module>``, or ``importlib.import_module("apothem...")``.

Underscore-prefixed *module paths* (``apothem.harnesses._shared``) are not
names and are out of scope; dunder names are never private.
"""

from __future__ import annotations

import ast
from pathlib import Path

import apothem

SRC_ROOT = Path(apothem.__file__).resolve().parent.parent


def _module_name(path: Path, src_root: Path) -> str:
    parts = list(path.relative_to(src_root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _top_package(module: str) -> str:
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else ""


def _is_private(name: str) -> bool:
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _is_module(name: str, src_root: Path) -> bool:
    base = src_root.joinpath(*name.split("."))
    return base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()


def _resolve_from(node: ast.ImportFrom, current: str, is_package: bool) -> str | None:
    if node.level == 0:
        return node.module
    base = current.split(".")
    if not is_package:
        base = base[:-1]
    if node.level > 1:
        base = base[: -(node.level - 1)]
    if node.module:
        base = [*base, node.module]
    return ".".join(base)


def _import_module_target(node: ast.Assign) -> str | None:
    call = node.value
    if not (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "import_module"
        and call.args
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
    ):
        return None
    target = call.args[0].value
    return target if target.startswith("apothem") else None


def _module_aliases(
    tree: ast.AST, current: str, is_package: bool, src_root: Path
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not alias.name.startswith("apothem"):
                    continue
                if alias.asname:
                    aliases[alias.asname] = alias.name
                else:
                    aliases[alias.name.split(".")[0]] = alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            target = _resolve_from(node, current, is_package)
            if not target or not target.startswith("apothem"):
                continue
            for alias in node.names:
                full = f"{target}.{alias.name}"
                if _is_module(full, src_root):
                    aliases[alias.asname or alias.name] = full
        elif isinstance(node, ast.Assign):
            target = _import_module_target(node)
            if target is None:
                continue
            for name in node.targets:
                if isinstance(name, ast.Name):
                    aliases[name.id] = target
    return aliases


def _attribute_target(node: ast.Attribute, aliases: dict[str, str]) -> str | None:
    chain: list[str] = []
    value = node.value
    while isinstance(value, ast.Attribute):
        chain.append(value.attr)
        value = value.value
    if not isinstance(value, ast.Name) or value.id not in aliases:
        return None
    return ".".join([aliases[value.id], *reversed(chain)])


def cross_package_private_names(src_root: Path) -> list[str]:
    """Return ``module:line target.name`` for each cross-package private reach."""
    hits: set[str] = set()
    for path in sorted((src_root / "apothem").rglob("*.py")):
        if "_vendor" in path.parts:
            continue
        current = _module_name(path, src_root)
        is_package = path.name == "__init__.py"
        own_package = _top_package(current)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = _module_aliases(tree, current, is_package, src_root)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                target = _resolve_from(node, current, is_package)
                if not target or not target.startswith("apothem"):
                    continue
                if _top_package(target) == own_package:
                    continue
                for alias in node.names:
                    if _is_private(alias.name) and not _is_module(
                        f"{target}.{alias.name}", src_root
                    ):
                        hits.add(f"{current}:{node.lineno} {target}.{alias.name}")
            elif isinstance(node, ast.Attribute) and _is_private(node.attr):
                target = _attribute_target(node, aliases)
                if (
                    target is not None
                    and _is_module(target, src_root)
                    and _top_package(target) != own_package
                ):
                    hits.add(f"{current}:{node.lineno} {target}.{node.attr}")
    return sorted(hits)


def test_no_cross_package_private_names() -> None:
    hits = cross_package_private_names(SRC_ROOT)
    assert not hits, (
        "these modules reach another top-level package's private names; give "
        "the helper a public name (keep the private one as an alias if older "
        f"importers need it): {hits}"
    )


def test_scan_flags_a_cross_package_private_import(tmp_path: Path) -> None:
    """The scan is not vacuous: it catches both shapes in a synthetic tree."""
    pkg = tmp_path / "apothem"
    (pkg / "lib").mkdir(parents=True)
    (pkg / "cli").mkdir()
    for init in (pkg, pkg / "lib", pkg / "cli"):
        (init / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "lib" / "helpers.py").write_text(
        "def _hidden():\n    return 1\n\n\ndef shown():\n    return 2\n",
        encoding="utf-8",
    )
    (pkg / "lib" / "peer.py").write_text(
        "from apothem.lib.helpers import _hidden\n", encoding="utf-8"
    )
    (pkg / "cli" / "command.py").write_text(
        "from apothem.lib.helpers import _hidden, shown\n"
        "from apothem.lib import helpers\n"
        "helpers._hidden()\n"
        "helpers.shown()\n",
        encoding="utf-8",
    )

    hits = cross_package_private_names(tmp_path)

    assert hits == [
        "apothem.cli.command:1 apothem.lib.helpers._hidden",
        "apothem.cli.command:3 apothem.lib.helpers._hidden",
    ]
