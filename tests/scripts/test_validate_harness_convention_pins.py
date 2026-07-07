# SPDX-License-Identifier: MIT

"""Tests for the harness convention pin validator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import validate_harness_convention_pins as vhcp  # noqa: E402


def _pin_text(snapshot_date: str, extra: str = "") -> str:
    return (
        "# Pin\n\n"
        "## Snapshot\n\n"
        f"- Snapshot date: {snapshot_date}\n"
        f"- Adapter source: `src/apothem/harnesses/test/`\n"
        "- Evidence level: adapter-local projection.\n"
        "\n"
        "## Recommended Postfix Rendering\n\n"
        "- Status: supported as plain text.\n"
        "\n"
        "## Long Context and Compaction\n\n"
        "- Status: profile-managed.\n"
        "\n"
        "## Large-Codebase Practice Projection\n\n"
        "- Layered context: declared in capabilities.yml.\n"
        f"{extra}"
    )


def _write_harness(
    root: Path,
    name: str,
    snapshot_date: str | None,
    *,
    pin_text: str | None = None,
) -> None:
    harness = root / name
    harness.mkdir()
    harness.joinpath("capabilities.yml").write_text(
        'standard_convention_pin: "STANDARD-CONVENTION-PIN.md"\n',
        encoding="utf-8",
    )
    if snapshot_date is None:
        return
    harness.joinpath("STANDARD-CONVENTION-PIN.md").write_text(
        pin_text if pin_text is not None else _pin_text(snapshot_date),
        encoding="utf-8",
    )


def test_current_pin_passes(tmp_path: Path) -> None:
    _write_harness(tmp_path, "codex", "2026-05-22")
    output = tmp_path / "report.json"

    rc = vhcp.main(
        [
            "--harnesses-root",
            str(tmp_path),
            "--today",
            "2026-05-23",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 0
    assert payload["passed"] is True
    assert payload["harness_count"] == 1
    assert payload["drifted_harnesses"] == []


def test_stale_pin_returns_drift_payload(tmp_path: Path) -> None:
    _write_harness(tmp_path, "cursor", "2026-01-01")
    output = tmp_path / "report.json"

    rc = vhcp.main(
        [
            "--harnesses-root",
            str(tmp_path),
            "--today",
            "2026-05-23",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 2
    assert payload["passed"] is False
    assert payload["drifted_harnesses"][0]["harness"] == "cursor"
    assert "older than 90 days" in payload["drifted_harnesses"][0]["reason"]


def test_missing_pin_returns_drift_payload(tmp_path: Path) -> None:
    _write_harness(tmp_path, "windsurf", None)
    output = tmp_path / "report.json"

    rc = vhcp.main(
        [
            "--harnesses-root",
            str(tmp_path),
            "--today",
            "2026-05-23",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 2
    assert payload["drifted_harnesses"][0]["reason"] == (
        "standard convention pin is missing"
    )


def test_missing_required_pin_field_returns_drift_payload(tmp_path: Path) -> None:
    _write_harness(
        tmp_path,
        "codex",
        "2026-05-22",
        pin_text="# Pin\n\n- Snapshot date: 2026-05-22\n",
    )
    output = tmp_path / "report.json"

    rc = vhcp.main(
        [
            "--harnesses-root",
            str(tmp_path),
            "--today",
            "2026-05-23",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 2
    assert "missing required field" in payload["drifted_harnesses"][0]["reason"]


def test_branch_pointed_pin_url_returns_drift_payload(tmp_path: Path) -> None:
    _write_harness(
        tmp_path,
        "codex",
        "2026-05-22",
        pin_text=_pin_text(
            "2026-05-22",
            extra=(
                "\n- Vendor URL: "
                "https://github.com/example/tool/blob/main/docs/config.md\n"
            ),
        ),
    )
    output = tmp_path / "report.json"

    rc = vhcp.main(
        [
            "--harnesses-root",
            str(tmp_path),
            "--today",
            "2026-05-23",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 2
    assert "branch-pointed" in payload["drifted_harnesses"][0]["reason"]


def test_missing_root_returns_error(tmp_path: Path) -> None:
    rc = vhcp.main(["--harnesses-root", str(tmp_path / "missing")])

    assert rc == 1
