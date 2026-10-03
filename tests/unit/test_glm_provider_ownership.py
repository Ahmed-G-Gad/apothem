# SPDX-License-Identifier: MIT

"""The GLM provider file is the operator's once it exists.

``<project>/.apothem/providers/glm.toml`` is a TOML file Apothem cannot merge
into, so install writes the template only when the file is absent and never
overwrites it afterwards. Uninstall deletes it only when Apothem created it and
it still matches the template; an operator's file (pre-existing or edited) is
left byte-identical. GLM projects no profile content, so a clean install reads
as in-sync rather than drifted.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.harnesses.claude_code import ClaudeCodeAdapter
from apothem.harnesses.glm import GlmAdapter
from apothem.schemas import profile_minimal_path

_OPERATOR_TOML = '[provider]\nname = "GLM (Z.ai)"\n\n[models]\ndefault = "glm-op"\n'


def _provider(project: Path) -> Path:
    return project / ".apothem" / "providers" / "glm.toml"


def _template_text() -> str:
    rules = install_driver.load_rules("glm")
    return install_driver.resolve_source(rules.install[0].source).read_text(
        encoding="utf-8"
    )


def test_update_keeps_operator_edits(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = GlmAdapter()
    adapter.install({}, project=project)
    provider = _provider(project)
    edited = provider.read_text(encoding="utf-8") + 'operator_key = "kept"\n'
    provider.write_text(edited, encoding="utf-8")

    adapter.update({}, project=project)

    assert provider.read_text(encoding="utf-8") == edited


def test_preexisting_provider_file_survives_install_and_uninstall(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    provider = _provider(project)
    provider.parent.mkdir(parents=True)
    provider.write_text(_OPERATOR_TOML, encoding="utf-8")
    adapter = GlmAdapter()

    adapter.install({}, project=project)
    assert provider.read_text(encoding="utf-8") == _OPERATOR_TOML

    adapter.uninstall(project=project)
    assert provider.read_text(encoding="utf-8") == _OPERATOR_TOML


def test_preexisting_copy_of_the_template_is_not_deleted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    provider = _provider(project)
    provider.parent.mkdir(parents=True)
    provider.write_text(_template_text(), encoding="utf-8")
    adapter = GlmAdapter()

    adapter.install({}, project=project)
    adapter.uninstall(project=project)

    assert provider.read_text(encoding="utf-8") == _template_text()


def test_uninstall_removes_an_unedited_file_apothem_created(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = GlmAdapter()
    adapter.install({}, project=project)
    assert _provider(project).is_file()

    adapter.uninstall(project=project)

    assert not _provider(project).exists()


def test_uninstall_keeps_an_edited_file_apothem_created(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = GlmAdapter()
    adapter.install({}, project=project)
    provider = _provider(project)
    provider.write_text(_OPERATOR_TOML, encoding="utf-8")

    adapter.uninstall(project=project)

    assert provider.read_text(encoding="utf-8") == _OPERATOR_TOML


def test_clean_install_verifies_in_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    profile = str(profile_minimal_path())
    runner = CliRunner()
    install = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "glm",
            "--project",
            str(project),
            "--profile",
            profile,
        ],
    )
    assert install.exit_code == 0, install.output

    verify = runner.invoke(
        main,
        [
            "verify",
            "--harness",
            "glm",
            "--project",
            str(project),
            "--profile",
            profile,
            "--json",
        ],
    )

    assert verify.exit_code == 0, verify.output


def test_missing_profile_anchor_still_reads_as_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A harness that projects the profile still drifts when its anchor is gone."""
    settings = tmp_path / ".claude" / "settings.json"
    monkeypatch.setattr(
        ClaudeCodeAdapter, "output_path", property(lambda self: settings)
    )
    profile = {"identity": {"name": "Probe"}}
    ClaudeCodeAdapter().install(profile)
    (settings.parent / "CLAUDE.md").unlink()

    results = install_driver.check_fidelity(
        "claude_code", harness_root=settings.parent, profile=profile
    )

    assert not install_driver.fidelity_is_faithful(results)
