# SPDX-License-Identifier: MIT

"""Dual-shape schema-anchor resolution for the conformity matchers.

The conformity package ships beside its ``schemas/`` sibling in two
layouts: the repo checkout (``src/apothem/{conformity,schemas}``) and the
installed tree (``<install-root>/apothem/{conformity,schemas}``). Every
schema / fixture anchor resolves one parent hop above the matcher module
(``parents[1] / "schemas"``) so the same code loads its data files in both
shapes. These tests assert the anchor in the repo checkout and in a
simulated installed tree.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_PACKAGE_DIR: Final[Path] = _REPO_ROOT / "src" / "apothem"
_CONFORMITY_DIR: Final[Path] = _PACKAGE_DIR / "conformity"
_SCHEMAS_DIR: Final[Path] = _PACKAGE_DIR / "schemas"

_CANONICAL_SPDX_LINE: Final[str] = "# SPDX-License-Identifier: MIT"


def _load_module(name: str, path: Path) -> ModuleType:
    """Load a matcher module from an explicit file path (orchestrator parity)."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None, f"cannot load {path}"
    assert spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def _simulate_installed_tree(tmp_path: Path) -> Path:
    """Copy conformity + schemas to ``<tmp>/apothem/{conformity,schemas}``."""
    install_root = tmp_path / "apothem"
    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copytree(_CONFORMITY_DIR, install_root / "conformity", ignore=ignore)
    shutil.copytree(_SCHEMAS_DIR, install_root / "schemas", ignore=ignore)
    return install_root


def test_repo_checkout_schemas_dir_resolves() -> None:
    """In the repo checkout, SCHEMAS_DIR lands on src/apothem/schemas."""
    module = _load_module(
        "file_header_grep_repo_shape", _CONFORMITY_DIR / "file_header_grep.py"
    )
    assert module.SCHEMAS_DIR == _SCHEMAS_DIR
    assert (module.SCHEMAS_DIR / "authorship-header.txt").is_file()
    assert (module.SCHEMAS_DIR / "header-exceptions.txt").is_file()


def test_repo_checkout_denylist_anchor_resolves() -> None:
    """The reference-token denylist anchor sits in the same schemas sibling."""
    module = _load_module(
        "reference_token_grep_repo_shape", _CONFORMITY_DIR / "reference_token_grep.py"
    )
    assert module._DENYLIST_PATH == _SCHEMAS_DIR / "reference-token-denylist.txt"
    assert module._DENYLIST_PATH.is_file()


def test_repo_checkout_frontmatter_value_schema_anchor_resolves() -> None:
    """The frontmatter-value matcher anchors its SCHEMAS_DIR on the schemas sibling."""
    module = _load_module(
        "frontmatter_value_grep_repo_shape",
        _CONFORMITY_DIR / "frontmatter_value_grep.py",
    )
    assert module.SCHEMAS_DIR == _SCHEMAS_DIR
    assert (module.SCHEMAS_DIR / "agent.schema.json").is_file()
    assert (module.SCHEMAS_DIR / "command.schema.json").is_file()
    assert (module.SCHEMAS_DIR / "skill.schema.json").is_file()


def test_installed_tree_schemas_dir_resolves(tmp_path: Path) -> None:
    """In the installed tree, SCHEMAS_DIR lands on <install-root>/schemas."""
    install_root = _simulate_installed_tree(tmp_path)
    module = _load_module(
        "file_header_grep_installed_shape",
        install_root / "conformity" / "file_header_grep.py",
    )
    expected_schemas_dir = (install_root / "schemas").resolve()
    assert expected_schemas_dir == module.SCHEMAS_DIR
    hash_line, spdx_text = module._load_banner()
    assert hash_line == _CANONICAL_SPDX_LINE
    assert spdx_text == "SPDX-License-Identifier: MIT"
    assert module._load_exception_globs(), "exception globs failed to load"


def test_installed_tree_header_check_functions(tmp_path: Path) -> None:
    """The header check runs end-to-end from the installed tree."""
    install_root = _simulate_installed_tree(tmp_path)
    module = _load_module(
        "file_header_grep_installed_check",
        install_root / "conformity" / "file_header_grep.py",
    )
    sample = tmp_path / "sample.py"
    sample.write_text("x = 1\n", encoding="utf-8")
    result = module.check("x = 1\n", sample)
    assert result.passed is False
    assert result.findings
    assert result.findings[0].rule == "HEADER_ABSENT"

    canonical = f"{_CANONICAL_SPDX_LINE}\n\nx = 1\n"
    result_ok = module.check(canonical, sample)
    assert result_ok.passed is True
