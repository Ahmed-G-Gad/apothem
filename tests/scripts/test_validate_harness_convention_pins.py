# SPDX-License-Identifier: MIT

"""Tests for the harness convention pin validator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import validate_harness_convention_pins as vhcp  # noqa: E402

_VENDOR_URL = "https://docs.vendor-tool.dev/config"


def _pin_text(
    snapshot_date: str, extra: str = "", vendor_url: str | None = _VENDOR_URL
) -> str:
    source = f"- Vendor source: <{vendor_url}>\n" if vendor_url else ""
    return (
        "# Pin\n\n"
        "## Snapshot\n\n"
        f"- Snapshot date: {snapshot_date}\n"
        f"- Adapter source: `src/apothem/harnesses/test/`\n"
        "- Evidence level: adapter-local projection.\n"
        f"{source}"
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


def _run(tmp_path: Path, pin_text: str, today: str = "2026-05-23") -> tuple[int, dict]:
    _write_harness(tmp_path, "codex", "2026-05-22", pin_text=pin_text)
    output = tmp_path / "report.json"
    rc = vhcp.main(
        [
            "--harnesses-root",
            str(tmp_path),
            "--today",
            today,
            "--output",
            str(output),
        ]
    )
    return rc, json.loads(output.read_text(encoding="utf-8"))


def test_pin_without_a_vendor_url_returns_drift(tmp_path: Path) -> None:
    rc, payload = _run(tmp_path, _pin_text("2026-05-22", vendor_url=None))

    assert rc == 2
    assert "no absolute vendor URL" in payload["drifted_harnesses"][0]["reason"]


@pytest.mark.parametrize(
    "url",
    [
        "https://apothem.ahmedgad.com/docs/harnesses/codex",
        "https://github.com/ahmed-g-gad/apothem/blob/0123456789abcdef/README.md",
        "https://example.com/docs",
    ],
)
def test_project_and_placeholder_urls_are_not_vendor_urls(
    tmp_path: Path, url: str
) -> None:
    rc, payload = _run(tmp_path, _pin_text("2026-05-22", vendor_url=url))

    assert rc == 2
    assert "no absolute vendor URL" in payload["drifted_harnesses"][0]["reason"]


def _targets(*lines: str) -> str:
    return "\n## Discovery Targets\n\n" + "".join(f"{line}\n" for line in lines)


def test_overdue_discovery_target_returns_drift(tmp_path: Path) -> None:
    pin = _pin_text(
        "2026-05-22",
        extra=_targets(
            "- Discovery target: skills by 2026-12-31 — decide later.",
            "- Discovery target: mcp_servers by 2026-05-01 — decide MCP.",
        ),
    )
    rc, payload = _run(tmp_path, pin)

    assert rc == 2
    drift = payload["drifted_harnesses"][0]
    assert drift["reason"] == (
        "discovery target for mcp_servers is overdue (due 2026-05-01)"
    )


def test_future_discovery_target_passes(tmp_path: Path) -> None:
    pin = _pin_text(
        "2026-05-22",
        extra=_targets("- Discovery target: mcp_servers by 2026-05-23 — today."),
    )
    rc, payload = _run(tmp_path, pin)

    assert rc == 0
    assert payload["checked_harnesses"][0]["discovery_targets"] == {
        "mcp_servers": "2026-05-23"
    }


def test_malformed_discovery_target_returns_drift(tmp_path: Path) -> None:
    pin = _pin_text(
        "2026-05-22",
        extra=_targets("- Discovery target: mcp_servers by 2026-13-40 — typo."),
    )
    rc, payload = _run(tmp_path, pin)

    assert rc == 2
    assert payload["drifted_harnesses"][0]["reason"] == (
        "discovery target for mcp_servers has an invalid date: 2026-13-40"
    )


def test_discovery_target_line_without_a_date_returns_drift(tmp_path: Path) -> None:
    pin = _pin_text(
        "2026-05-22",
        extra=_targets("- Discovery target: mcp_servers — no date given."),
    )
    rc, payload = _run(tmp_path, pin)

    assert rc == 2
    assert "Discovery target line" in payload["drifted_harnesses"][0]["reason"]


def test_repository_pins_pass_on_their_refresh_date(tmp_path: Path) -> None:
    # The committed pins pass the vendor-URL and discovery-target checks.
    # The date is fixed so this test never ages; CI runs the validator with
    # the real date on every pull request, weekly, and before a release.
    rc = vhcp.main(
        [
            "--harnesses-root",
            str(_REPO_ROOT / "src" / "apothem" / "harnesses"),
            "--today",
            "2026-10-03",
            "--output",
            str(tmp_path / "report.json"),
        ]
    )
    assert rc == 0
