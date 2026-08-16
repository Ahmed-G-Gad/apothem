# SPDX-License-Identifier: MIT

"""Unit tests for the ``is_installed`` presence predicate.

Regression coverage for the false-positive that reported
``claude-code installed=True verified=False drift`` on a machine where no
Apothem engine install existed. The adapters keyed presence off
``output_path.exists()``, and Claude Code writes its own
``~/.claude/settings.json`` (plugin registrations, notification preferences),
so the anchor existed on any machine that had ever run the harness. Paired with
a correctly-failing ``verify()``, that rendered as ``drift`` — inviting a
remediating uninstall whose target is the operator's own settings file.

``is_installed`` must answer "did Apothem install here?", not "does this
harness exist on this machine?".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses.claude_code import ClaudeCodeAdapter
from apothem.harnesses.cursor import CursorAdapter
from apothem.harnesses.hermes import HermesAdapter
from apothem.lib.harness_materializer import wrap_managed_block
from apothem.lib.harness_registry import iter_harness_entries, load_adapter_class

# A realistic bare Claude Code settings.json: written by the harness itself,
# carrying zero Apothem-authored keys.
_VENDOR_SETTINGS = json.dumps(
    {
        "enabledPlugins": {"some-marketplace-plugin": True},
        "extraKnownMarketplaces": {},
    }
)


def _anchor_at(adapter: object, target: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point *adapter*'s ``output_path`` at *target* for the duration of a test."""
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))


def test_bare_vendor_settings_json_reports_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reported bug: a vendor-written settings.json is not an Apothem install.

    This is the exact machine state from the report — ``~/.claude/settings.json``
    present, every Apothem-owned manifest target absent.
    """
    root = tmp_path / ".claude"
    root.mkdir()
    (root / "settings.json").write_text(_VENDOR_SETTINGS, encoding="utf-8")

    adapter = ClaudeCodeAdapter()
    _anchor_at(adapter, root / "settings.json", monkeypatch)

    # The anchor exists — the old predicate would have returned True here.
    assert adapter.output_path.exists()
    assert adapter.is_installed() is False


def test_operator_authored_shared_dirs_are_not_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``agents/`` and ``skills/`` are harness-native surfaces, not Apothem proof.

    Claude Code supports user-authored agents and skills at the harness root, so
    those directories can exist with no Apothem install behind them. Only
    Apothem's own ``.apothem/`` subtree counts.
    """
    root = tmp_path / ".claude"
    (root / "agents").mkdir(parents=True)
    (root / "skills").mkdir()
    (root / "rules").mkdir()
    (root / "settings.json").write_text(_VENDOR_SETTINGS, encoding="utf-8")

    adapter = ClaudeCodeAdapter()
    _anchor_at(adapter, root / "settings.json", monkeypatch)

    assert adapter.is_installed() is False


def test_apothem_support_subtree_reports_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A populated Apothem support subtree is positive proof of an install."""
    root = tmp_path / ".claude"
    hooks = root / ".apothem" / "support" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "dispatch.py").write_text("# hook\n", encoding="utf-8")
    (root / "settings.json").write_text(_VENDOR_SETTINGS, encoding="utf-8")

    adapter = ClaudeCodeAdapter()
    _anchor_at(adapter, root / "settings.json", monkeypatch)

    assert adapter.is_installed() is True


def test_empty_support_shell_after_uninstall_reports_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty ``.apothem/`` directories left by uninstall are not an install.

    Uninstall reverses tree targets child-by-child so operator-authored
    siblings survive, which leaves every Apothem tree target behind as an empty
    directory. Existence alone would report a fully uninstalled harness as
    still installed, so evidence requires actual content.
    """
    root = tmp_path / ".claude"
    for leaf in ("templates", "hooks", "conformity", "schemas"):
        (root / ".apothem" / "support" / leaf).mkdir(parents=True)
    (root / "settings.json").write_text(_VENDOR_SETTINGS, encoding="utf-8")

    adapter = ClaudeCodeAdapter()
    _anchor_at(adapter, root / "settings.json", monkeypatch)

    assert (root / ".apothem" / "support" / "hooks").is_dir()
    assert adapter.is_installed() is False


def test_partial_install_still_reports_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A half-removed install stays installed+unverified — genuine drift.

    The predicate is existential precisely so real degradation keeps surfacing
    as ``drift``; only an untouched harness home collapses to ``absent``.
    """
    root = tmp_path / ".claude"
    schemas = root / ".apothem" / "support" / "schemas"
    schemas.mkdir(parents=True)
    (schemas / "authorship-header.txt").write_text("SPDX\n", encoding="utf-8")
    (root / "settings.json").write_text(_VENDOR_SETTINGS, encoding="utf-8")

    adapter = ClaudeCodeAdapter()
    _anchor_at(adapter, root / "settings.json", monkeypatch)

    assert adapter.is_installed() is True
    assert adapter.verify() is False


def test_native_config_adapter_ignores_vendor_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rendered native config alone does not prove an install (hermes)."""
    root = tmp_path / ".hermes"
    root.mkdir()
    (root / "config.yaml").write_text("model: something\n", encoding="utf-8")

    adapter = HermesAdapter()
    _anchor_at(adapter, root / "config.yaml", monkeypatch)

    assert adapter.output_path.exists()
    assert adapter.is_installed() is False

    rules = root / ".apothem" / "support" / "rules"
    rules.mkdir(parents=True)
    (rules / "session-closure.md").write_text("# rule\n", encoding="utf-8")
    assert adapter.is_installed() is True


def test_project_scope_requires_managed_block(tmp_path: Path) -> None:
    """A project anchor counts only when it carries the Apothem managed block.

    The rules-only project harnesses declare a single ``sentinel_merge`` target,
    so an operator-authored file at the same path must not read as installed.
    """
    adapter = CursorAdapter()
    rules = tmp_path / ".cursor" / "rules"
    rules.mkdir(parents=True)
    anchor = rules / "apothem-rules.mdc"

    anchor.write_text("my own cursor rules\n", encoding="utf-8")
    assert adapter.is_installed(project=tmp_path) is False

    anchor.write_text(
        "my own cursor rules\n" + wrap_managed_block("projected profile body"),
        encoding="utf-8",
    )
    assert adapter.is_installed(project=tmp_path) is True


def test_project_scope_without_project_reports_not_installed() -> None:
    """A project-scope adapter with no ``--project`` cannot resolve a target."""
    assert CursorAdapter().is_installed() is False


@pytest.mark.parametrize("entry", iter_harness_entries(), ids=lambda e: e.public_id)
def test_every_adapter_reports_absent_on_pristine_root(
    entry: object, tmp_path: Path
) -> None:
    """No registered adapter claims an install on an empty root.

    Fleet-wide guard against the presence-anchor class of bug: whatever an
    adapter's ``output_path`` points at, an untouched root is ``absent``.
    """
    adapter = load_adapter_class(entry)()  # type: ignore[arg-type]
    if getattr(adapter, "requires_project", False):
        assert adapter.is_installed(project=tmp_path) is False
    else:
        assert (
            install_driver.detect_install(
                entry.package_key,  # type: ignore[attr-defined]
                harness_root=tmp_path,
            )
            is False
        )
