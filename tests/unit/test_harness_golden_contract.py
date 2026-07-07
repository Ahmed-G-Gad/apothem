# SPDX-License-Identifier: MIT

"""Registry-driven golden and idempotence tests for all harnesses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.lib.harness_registry import (
    HARNESS_REGISTRY,
    HarnessRegistryEntry,
    load_adapter_class,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN_PLANS = _REPO_ROOT / "tests" / "fixtures" / "harness-golden-plans.json"
_SOURCE_MARKER = "/src/apothem/"


def _golden_plans() -> dict[str, list[dict[str, str]]]:
    return json.loads(_GOLDEN_PLANS.read_text(encoding="utf-8"))


def _normalize_plan(
    entry: HarnessRegistryEntry,
    *,
    harness_root: Path,
    project_root: Path,
) -> list[dict[str, str]]:
    if entry.scope == "project":
        plan = install_driver.build_plan(entry.package_key, project_root=project_root)
        root = project_root.resolve(strict=False).as_posix()
    else:
        plan = install_driver.build_plan(entry.package_key, harness_root=harness_root)
        root = harness_root.resolve(strict=False).as_posix()

    normalized: list[dict[str, str]] = []
    for item in plan:
        source = item["source"].replace("\\", "/")
        if _SOURCE_MARKER in source:
            source = source.split(_SOURCE_MARKER, 1)[1]
        target = item["target"].replace("\\", "/").replace(root, "<ROOT>")
        normalized.append(
            {
                "mode": item["mode"],
                "source": source.rstrip("/"),
                "target": target.rstrip("/"),
            }
        )
    return normalized


def _file_snapshot(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    if not root.exists():
        return snapshot
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _user_output_target(adapter: object, root: Path) -> Path:
    output_path = adapter.output_path
    assert isinstance(output_path, Path)
    return root / output_path.name


def test_golden_plan_fixture_covers_exact_registry() -> None:
    assert tuple(_golden_plans()) == tuple(
        entry.public_id for entry in HARNESS_REGISTRY
    )


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda entry: entry.public_id)
def test_harness_install_plan_matches_golden_fixture(
    entry: HarnessRegistryEntry, tmp_path: Path
) -> None:
    harness_root = tmp_path / "user-root"
    project_root = tmp_path / "project-root"

    assert (
        _normalize_plan(
            entry,
            harness_root=harness_root,
            project_root=project_root,
        )
        == _golden_plans()[entry.public_id]
    )


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda entry: entry.public_id)
def test_harness_dry_run_writes_nothing(
    entry: HarnessRegistryEntry, tmp_path: Path
) -> None:
    root = tmp_path / entry.package_key
    if entry.scope == "project":
        root.mkdir()
        run = install_driver.run_install(
            entry.package_key,
            project_root=root,
            dry_run=True,
        )
    else:
        run = install_driver.run_install(
            entry.package_key,
            harness_root=root,
            dry_run=True,
        )

    assert run.dry_run is True
    assert run.files_written == []
    assert _file_snapshot(root) == {}


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda entry: entry.public_id)
def test_adapter_install_is_idempotent_for_every_harness(
    entry: HarnessRegistryEntry,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sandbox = tmp_path / entry.package_key
    adapter = load_adapter_class(entry)()

    if entry.scope == "project":
        project = sandbox / "project"
        project.mkdir(parents=True)
        adapter.install({}, project=project)
        first = _file_snapshot(sandbox)
        adapter.install({}, project=project)
    else:
        harness_root = sandbox / "root"
        output_target = _user_output_target(adapter, harness_root)
        monkeypatch.setattr(
            type(adapter),
            "output_path",
            property(lambda self, target=output_target: target),
        )
        adapter.install({})
        first = _file_snapshot(sandbox)
        adapter.install({})

    assert _file_snapshot(sandbox) == first
