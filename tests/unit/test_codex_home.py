# SPDX-License-Identifier: MIT

"""The Codex home lookup takes ``CODEX_HOME`` the way Codex does.

Codex reads the variable with ``PathBuf::from`` (``find_codex_home`` in
``codex-rs/utils/home-dir/src/lib.rs``): it treats an empty value as unset,
does not expand a leading ``~`` and resolves a relative value against the
current folder. The engine's lookup and the conformity gate's copy of it must
agree with Codex, or an install writes to a folder Codex never reads.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.conformity import gate
from apothem.lib.codex_home import codex_home


def test_unset_codex_home_is_the_dot_codex_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CODEX_HOME", raising=False)
    assert codex_home(tmp_path) == tmp_path / ".codex"


def test_an_empty_codex_home_counts_as_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_HOME", "")
    assert codex_home(tmp_path) == tmp_path / ".codex"


def test_an_absolute_codex_home_is_used_as_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "elsewhere"))
    assert codex_home(Path.home()) == tmp_path / "elsewhere"


def test_a_leading_tilde_is_not_expanded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEX_HOME", "~/codex")
    assert codex_home(Path.home()) == tmp_path / "~" / "codex"


def test_a_relative_codex_home_is_under_the_current_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEX_HOME", "codex-home")
    assert codex_home(Path.home()) == tmp_path / "codex-home"


@pytest.mark.parametrize("value", ["~/codex", "codex-home", ""])
def test_the_gate_scope_matches_the_engine_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(gate.SCOPE_ENV_VAR, raising=False)
    monkeypatch.setenv("CODEX_HOME", value)
    assert gate._default_scopes()[1] == codex_home(Path.home())
