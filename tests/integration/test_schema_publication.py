# SPDX-License-Identifier: MIT

"""Packaged JSON schemas are served at their ``$id`` URLs.

Each ``src/apothem/schemas/*.schema.json`` declares
``$id: https://apothem.ahmedgad.com/schemas/<file>``, and the site is the
documented host, but nothing published the files, so the URLs returned 404
and editors could not validate ``profile.yaml``. The static-site workflow now
copies the packaged schemas into ``site/dist/schemas/``. This test runs that
workflow step's script against a scratch tree and checks the staged bytes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "publish-static-site.yml"
_SCHEMAS = _REPO_ROOT / "src" / "apothem" / "schemas"
_SITE_HOST = "https://apothem.ahmedgad.com/"


def _workflow() -> dict:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _schema_step() -> dict:
    steps = _workflow()["jobs"]["build"]["steps"]
    matches = [
        step for step in steps if "site/dist/schemas" in str(step.get("run", ""))
    ]
    assert len(matches) == 1, "expected one step staging schemas into site/dist/schemas"
    return matches[0]


def test_schema_changes_trigger_a_site_publish() -> None:
    triggers = _workflow().get("on", _workflow().get(True))
    assert "src/apothem/schemas/**" in triggers["push"]["paths"]


_BASH = find_test_bash()


@pytest.mark.skipif(_BASH is None, reason=SKIP_REASON)
def test_publish_step_serves_every_schema_at_its_id(tmp_path: Path) -> None:
    (tmp_path / "src" / "apothem").mkdir(parents=True)
    shutil.copytree(_SCHEMAS, tmp_path / "src" / "apothem" / "schemas")
    (tmp_path / "site" / "dist").mkdir(parents=True)

    subprocess.run(
        [_BASH, "-c", _schema_step()["run"]], cwd=tmp_path, check=True, timeout=60
    )

    packaged = sorted(_SCHEMAS.glob("*.schema.json"))
    assert packaged
    for schema in packaged:
        schema_id = json.loads(schema.read_text(encoding="utf-8"))["$id"]
        assert schema_id.startswith(_SITE_HOST)
        served = tmp_path / "site" / "dist" / schema_id.removeprefix(_SITE_HOST)
        assert served.read_bytes() == schema.read_bytes(), schema.name
