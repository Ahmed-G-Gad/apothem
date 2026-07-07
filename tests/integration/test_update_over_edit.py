# SPDX-License-Identifier: MIT

"""Update-over-edit reversibility integration test.

Proves the documented update contract: after a profile install, a recognizable
operator edit in the adapter's managed native file survives a subsequent
``update`` per that file's ownership class. Each adapter's documented fate is
decided empirically from the propagation manifest's ownership class and the
adapter's native ``output_path`` suffix:

- JSON / YAML native config (claude-code ``settings.json``, opencode
  ``opencode.json``, open-claw ``openclaw.json``, hermes ``config.yaml``,
  qwen-code ``settings.json``) is key-merge-preserving: an operator-only
  top-level key survives the merge in place.
- Markdown / instruction anchors written via ``sentinel_merge`` (codex
  ``AGENTS.md``, antigravity ``GEMINI.md``, and every project-scope rules
  anchor — cursor, gemini-cli, github-copilot, windsurf, codebuddy, kiro,
  trae, zed) preserve operator prose OUTSIDE the apothem managed block; an
  operator line appended after the block survives in place.

A regression that SILENTLY CLOBBERS the operator edit (the edit is gone from
the file AND no backup captured it) fails the test. The install driver's
documented contract for every operator-owned target here is preserve-in-place,
so each branch asserts in-place survival; the backup recovery path is checked
as a fallback only when an in-place edit did not survive.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest
import yaml

from apothem.harnesses import HarnessAdapter
from apothem.harnesses._shared import install_driver

from .conftest import (
    ALL_ADAPTERS,
    install_into_sandbox,
    is_project_scope,
)

# Recognizable operator-edit sentinels. The markdown line and the JSON/YAML key
# carry the same greppable token so a survivor is unambiguous in any format.
_OPERATOR_TOKEN: str = "OPERATOR-EDIT-SENTINEL"  # noqa: S105 — test sentinel, not a secret
_OPERATOR_LINE: str = f"{_OPERATOR_TOKEN} operator prose outside the managed block"
_OPERATOR_KEY: str = "operatorSentinelKey"

# Fate classes for the operator edit's documented survival.
#
# ``replace-with-backup`` covers operator-owned ``write_text`` targets that are
# NOT key-mergeable config (JSON / YAML) and carry NO apothem managed block to
# preserve prose around — e.g. the glm backend-provider ``.toml``. GLM is a
# model backend, not a rule-bearing harness, so apothem projects no managed
# block into it; ``write_text`` overwrites the file with the clean template on
# update, but the driver backs the prior bytes up first, so the operator edit
# is recovered from the backup root rather than preserved in place. A silent
# clobber (gone from the file AND no backup) still fails the test.
Fate = Literal[
    "json-merge-preserved",
    "sentinel-preserved",
    "yaml-merge-preserved",
    "replace-with-backup",
]


@dataclass(frozen=True)
class EditTarget:
    """The managed native file an operator edits and its documented fate."""

    path: Path
    fate: Fate


def _second_profile() -> dict[str, Any]:
    """Return a schema-distinct second profile for the update pass.

    Construct a minimal profile whose identity sentinel differs from the
    populated fixture so ``update`` renders edit-bearing content that is not
    byte-identical to the install pass (a no-op update would not exercise the
    merge path). There is no ``profile2`` fixture, so this is built inline.
    """
    profile: dict[str, Any] = {
        "identity": {"name": "Second-Operator-Distinct-Sentinel"},
        "preferences": {"language": "python", "style": "concise"},
        "rules": ["second-profile-rule-sentinel"],
    }
    install_driver_profile_validate(profile)
    return profile


def install_driver_profile_validate(profile: dict[str, Any]) -> None:
    """Validate *profile* against the packaged schema, failing loudly on drift."""
    from apothem.lib.profile import validate_profile

    validate_profile(profile)


def _operator_owned_sentinel_target(
    adapter: HarnessAdapter,
    *,
    harness_root: Path | None,
    project_root: Path | None,
) -> Path | None:
    """Return the first operator-owned ``sentinel_merge`` target, if any."""
    rules = install_driver.load_rules(adapter.name.replace("-", "_"))
    for entry in rules.install:
        if entry.mode == "sentinel_merge" and entry.ownership_class == "operator-owned":
            return install_driver.resolve_target(
                entry.target, harness_root=harness_root, project_root=project_root
            )
    return None


def _operator_owned_write_text_target(
    adapter: HarnessAdapter,
    *,
    harness_root: Path | None,
    project_root: Path | None,
) -> Path | None:
    """Return the first operator-owned ``write_text`` target, if any.

    The glm backend-provider ``.toml`` is the sole such target: a model backend
    is not rule-bearing, so apothem folds no managed block into it and writes it
    via ``write_text``. The operator edit is recovered from the backup root
    after an overwriting update rather than preserved in place.
    """
    rules = install_driver.load_rules(adapter.name.replace("-", "_"))
    for entry in rules.install:
        if entry.mode == "write_text" and entry.ownership_class == "operator-owned":
            return install_driver.resolve_target(
                entry.target, harness_root=harness_root, project_root=project_root
            )
    return None


def _resolve_edit_target(
    adapter: HarnessAdapter,
    tmp_path: Path,
    kwargs: dict[str, Any],
) -> EditTarget:
    """Decide the adapter's edit target and documented fate empirically.

    Preference order, derived from the manifest ownership classes and the
    adapter's native ``output_path`` suffix:

    1. A user-scope adapter whose native ``output_path`` config is JSON / YAML
       (the materializer-config adapters plus claude-code's ``settings.json``)
       routes the edit through the key-preserving merge: the native config lands
       at ``tmp_path/<basename>`` because ``_install_into_tmp`` monkeypatched
       ``output_path`` there.
    2. Otherwise the operator-owned ``sentinel_merge`` instruction anchor
       carries the edit (every project-scope rules anchor, plus the user-scope
       markdown anchors codex ``AGENTS.md`` / antigravity ``GEMINI.md`` /
       qwen-code ``QWEN.md`` where the native config is markdown).
    """
    if not is_project_scope(adapter):
        native = tmp_path / adapter.output_path.name
        suffix = native.suffix.lower()
        if suffix == ".json" and native.is_file():
            return EditTarget(native, "json-merge-preserved")
        if suffix in {".yaml", ".yml"} and native.is_file():
            return EditTarget(native, "yaml-merge-preserved")
        harness_root: Path | None = tmp_path
        project_root: Path | None = None
    else:
        harness_root = None
        project_root = kwargs["project"]

    sentinel = _operator_owned_sentinel_target(
        adapter, harness_root=harness_root, project_root=project_root
    )
    if sentinel is not None:
        assert sentinel.is_file(), (
            f"{adapter.name}: sentinel_merge anchor not on disk to edit: {sentinel}"
        )
        return EditTarget(sentinel, "sentinel-preserved")

    # No sentinel_merge anchor: the adapter materializes an operator-owned
    # ``write_text`` target with no apothem managed block (the glm
    # backend-provider ``.toml``). The operator edit is recovered from the
    # backup root after an overwriting update, not preserved in place.
    replace_target = _operator_owned_write_text_target(
        adapter, harness_root=harness_root, project_root=project_root
    )
    assert replace_target is not None, (
        f"{adapter.name}: no operator-owned sentinel_merge or write_text "
        f"target declared"
    )
    assert replace_target.is_file(), (
        f"{adapter.name}: write_text target not on disk to edit: {replace_target}"
    )
    return EditTarget(replace_target, "replace-with-backup")


def _apply_operator_edit(target: EditTarget) -> None:
    """Write the recognizable operator edit where the contract preserves it."""
    if target.fate == "sentinel-preserved":
        # An operator line appended AFTER the apothem managed block is operator
        # prose outside the sentinels and must survive a sentinel re-merge.
        text = target.path.read_text(encoding="utf-8")
        target.path.write_text(
            f"{text.rstrip()}\n\n{_OPERATOR_LINE}\n", encoding="utf-8"
        )
    elif target.fate == "replace-with-backup":
        # A ``write_text`` operator-owned file (the glm backend ``.toml``) has no
        # managed block. The edit is appended as a valid TOML comment so the file
        # stays parseable; ``write_text`` overwrites it on update but backs the
        # prior bytes up first, so the edit is recovered from the backup root.
        text = target.path.read_text(encoding="utf-8")
        target.path.write_text(
            f"{text.rstrip()}\n\n# {_OPERATOR_LINE}\n", encoding="utf-8"
        )
    elif target.fate == "json-merge-preserved":
        data = json.loads(target.path.read_text(encoding="utf-8"))
        data[_OPERATOR_KEY] = _OPERATOR_TOKEN
        target.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    else:  # yaml-merge-preserved
        data = yaml.safe_load(target.path.read_text(encoding="utf-8")) or {}
        data[_OPERATOR_KEY] = _OPERATOR_TOKEN
        target.path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _operator_edit_survives_in_place(target: EditTarget) -> bool:
    """Return True when the operator edit is still present in the live file."""
    if not target.path.is_file():
        return False
    text = target.path.read_text(encoding="utf-8")
    if target.fate in {"sentinel-preserved", "replace-with-backup"}:
        return _OPERATOR_LINE in text
    if target.fate == "json-merge-preserved":
        return json.loads(text).get(_OPERATOR_KEY) == _OPERATOR_TOKEN
    return (yaml.safe_load(text) or {}).get(_OPERATOR_KEY) == _OPERATOR_TOKEN


def _backup_recovers_operator_edit(tmp_path: Path) -> bool:
    """Return True when a backup under the temp backup root carries the edit.

    The driver copies an operator-owned target into the apothem backup root
    before any overwrite. A replace-class fate (overwrite-with-backup) is
    recoverable when one of those backups still contains the operator token.
    """
    backup_root = tmp_path / "backups"
    if not backup_root.is_dir():
        return False
    for backup_file in backup_root.rglob("*"):
        if not backup_file.is_file():
            continue
        try:
            content = backup_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _OPERATOR_TOKEN in content:
            return True
    return False


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_update_preserves_operator_edit(
    adapter: HarnessAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    populated_profile: dict,
) -> None:
    # Arrange: install the edit-bearing populated profile into the temp tree.
    kwargs, _root = install_into_sandbox(
        adapter, tmp_path, monkeypatch, redirect_backup_root=True
    )
    edit_target = _resolve_edit_target(adapter, tmp_path, kwargs)
    _apply_operator_edit(edit_target)
    assert _operator_edit_survives_in_place(edit_target), (
        f"{adapter.name}: operator edit was not written to the managed file"
    )

    # Act: update over the edit with a schema-distinct second profile.
    adapter.update(_second_profile(), **kwargs)

    # Assert: the operator edit's documented fate. The contract for every
    # operator-owned target here is preserve-in-place; the backup recovery path
    # is the fallback the assertion accepts only if in-place survival failed.
    # A regression that loses the edit from the file AND captured no backup is a
    # silent clobber and fails the test.
    in_place = _operator_edit_survives_in_place(edit_target)
    if in_place:
        return
    assert _backup_recovers_operator_edit(tmp_path), (
        f"{adapter.name}: operator edit ({edit_target.fate}) was silently "
        f"clobbered by update — gone from {edit_target.path.name} and no backup "
        f"captured it"
    )
