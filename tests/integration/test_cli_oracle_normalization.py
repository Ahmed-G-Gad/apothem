# SPDX-License-Identifier: MIT

"""Path tokenization in the CLI behavior-diff oracle is order-independent.

The oracle replaces three machine-specific roots with stable tokens: the
scratch home, the system temp root, and the apothem package source root. A
checkout that lives under the temp directory (a cloud session, a CI scratch
clone, an agent worktree under ``$TMPDIR``) nests the source root inside the
temp root. Replacing the temp root first then rewrites every source path to
``<ROOT>/...`` and the golden comparison drifts for a reason unrelated to the
change under test. The most specific (longest) path must win.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver

from . import _cli_oracle
from ._oracle_norm import TOK_SRC


def test_source_root_under_temp_root_keeps_source_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A source root nested in the temp root still tokenizes as the source."""
    temp_root = tmp_path / "tmp"
    source_root = temp_root / "clone" / "src" / "apothem"
    source_root.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temp_root))
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", source_root)

    text = f'"source": "{source_root}/harnesses/claude_code/templates/settings.json"'
    normalized = _cli_oracle._normalize_text(text, home=home)

    assert normalized == (
        f'"source": "{TOK_SRC}/harnesses/claude_code/templates/settings.json"'
    )


def test_home_under_temp_root_keeps_home_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The scratch home (always under the temp root) keeps its own token."""
    temp_root = tmp_path / "tmp"
    home = temp_root / "dx2-cli-x" / "home"
    home.mkdir(parents=True)
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temp_root))

    normalized = _cli_oracle._normalize_text(f"{home}/.claude/settings.json", home=home)

    assert normalized == f"{_cli_oracle.TOK_HOME}/.claude/settings.json"
