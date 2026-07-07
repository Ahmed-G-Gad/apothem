# SPDX-License-Identifier: MIT

"""Verify the PEP-517 sdist + wheel payload contract.

Builds the sdist and wheel locally with ``python -m build`` and inspects
the archive payloads directly; no registry is involved.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Final

import pytest

from apothem.lib.harness_registry import HARNESS_REGISTRY

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
PROJECT_NAME: Final[str] = "apothem"
SDIST_SUFFIX: Final[str] = ".tar.gz"
WHEEL_SUFFIX: Final[str] = ".whl"
# A PEP 440-ish version token: a release segment plus optional pre/post/dev/
# local suffixes. The version value itself is single-sourced in
# pyproject.toml and is not duplicated into this test.
_VERSION_TOKEN: Final[re.Pattern[str]] = re.compile(
    r"-(\d+(?:\.\d+)*(?:[._-]?(?:a|b|rc|alpha|beta|dev|post)\d*)*(?:\+[\w.]+)?)-?"
)


def _source_payloads() -> set[str]:
    required = {
        "src/apothem/agents/README.md",
        "src/apothem/commands/plan-spec.md",
        "src/apothem/commands/plan-execute.md",
        "src/apothem/rules/context-management.md",
        "src/apothem/skills/plan-suite/SKILL.md",
        "src/apothem/templates/master-index-template.md",
        "src/apothem/output-styles/forensic-auditor.md",
        "src/apothem/statuslines/README.md",
        "src/apothem/hooks/lib/bootstrap.sh",
        "src/apothem/hooks/messages/pretooluse-write-header-guard.md",
        "src/apothem/lib/propagation-manifest.yaml",
        "src/apothem/schemas/profile.schema.json",
    }
    for entry in HARNESS_REGISTRY:
        required.add(entry.capabilities_path)
        required.add(entry.standard_pin_path)
        for source in entry.template_sources:
            required.add(f"src/apothem/{source}")
    # Vendored runtime data (critical C5 guard): every non-.py file the vendored
    # jsonschema stack loads at runtime — per-draft metaschema.json AND the
    # EXTENSIONLESS vocabulary files (schemas/<draft>/vocabularies/<name>). Drawn
    # from the source tree so the guard tracks the full set, not a stale list;
    # a built wheel that drops these crashes on first profile validation.
    schemas_dir = REPO_ROOT / "src/apothem/_vendor/jsonschema_specifications/schemas"
    for data_file in schemas_dir.rglob("*"):
        if data_file.is_file():
            required.add(data_file.relative_to(REPO_ROOT).as_posix())
    return required


def _wheel_payload_name(source_path: str) -> str:
    return source_path.removeprefix("src/")


def _sdist_member_names(sdist: Path) -> set[str]:
    with tarfile.open(sdist, "r:gz") as archive:
        names = set()
        for name in archive.getnames():
            _root, _separator, relative = name.partition("/")
            if relative:
                names.add(relative)
        return names


def _build_dist(tmp_path: Path) -> Path:
    if importlib.util.find_spec("build") is None:
        pytest.skip("python build module unavailable on this host")
    out = tmp_path / "dist-build"
    cmd = [sys.executable, "-m", "build", "--outdir", str(out), str(REPO_ROOT)]
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.fail(
            "build failed "
            f"(exit {completed.returncode}); stderr: {completed.stderr[:1000]}"
        )
    return out


def _find_artifact(out: Path, suffix: str) -> Path:
    matches = sorted(out.glob(f"*{suffix}"))
    if not matches:
        pytest.fail(f"no {suffix} artifact under {out}")
    return matches[0]


def test_sdist_and_wheel_payload_contract(tmp_path: Path) -> None:
    built_dist = _build_dist(tmp_path)
    sdist = _find_artifact(built_dist, SDIST_SUFFIX)
    assert sdist.is_file()
    assert PROJECT_NAME in sdist.name
    assert _VERSION_TOKEN.search(sdist.name), (
        f"sdist name lacks a valid version segment: {sdist.name}"
    )

    wheel = _find_artifact(built_dist, WHEEL_SUFFIX)
    assert wheel.is_file()
    assert PROJECT_NAME.replace("-", "_") in wheel.name
    assert _VERSION_TOKEN.search(wheel.name), (
        f"wheel name lacks a valid version segment: {wheel.name}"
    )

    with zipfile.ZipFile(wheel) as archive:
        wheel_names = set(archive.namelist())

    required = _source_payloads()
    missing_wheel = sorted(
        _wheel_payload_name(path)
        for path in required
        if _wheel_payload_name(path) not in wheel_names
    )
    assert not missing_wheel, (
        f"wheel missing registry or materialization payloads: {missing_wheel}"
    )

    sdist_names = _sdist_member_names(sdist)
    missing_sdist = sorted(path for path in required if path not in sdist_names)
    assert not missing_sdist, (
        f"sdist missing registry or materialization payloads: {missing_sdist}"
    )
