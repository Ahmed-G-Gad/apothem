# SPDX-License-Identifier: MIT

"""``apothem install`` over a JSONC / JSON5 operator config (roadmap R-09).

OpenCode, Qwen Code and Open-Claw read configs that may carry comments or
JSON5 syntax. Install must either keep every operator key with the file's
bytes intact, or exit non-zero with ``config.unparseable`` and write nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.schemas import profile_minimal_path

_JSONC_OPENCODE = '{\n  // operator note\n  "model": "anthropic/operator-model",\n}\n'
_JSONC_QWEN = '{\n  /* mine */\n  "model": {"name": "operator-model"},\n}\n'
_JSON5_OPENCLAW = "// gateway\n{\n  gateway: { port: 18789, },\n}\n"


def _install(harness: str) -> tuple[int, dict[str, object]]:
    result = CliRunner().invoke(
        main,
        [
            "install",
            "--harness",
            harness,
            "--profile",
            str(profile_minimal_path()),
            "--json",
        ],
    )
    return result.exit_code, json.loads(result.output)


@pytest.mark.parametrize(
    ("harness", "relative", "seed"),
    [
        ("opencode", ".config/opencode/opencode.json", _JSONC_OPENCODE),
        ("qwen-code", ".qwen/settings.json", _JSONC_QWEN),
    ],
)
def test_install_refuses_commented_config_and_writes_nothing(
    harness: str,
    relative: str,
    seed: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    config = home / relative
    config.parent.mkdir(parents=True)
    config.write_text(seed, encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    exit_code, envelope = _install(harness)

    assert exit_code != 0
    error = envelope["error"]
    assert isinstance(error, dict)
    assert error["code"] == "config.unparseable"
    assert "re-run" in str(error["fix"])
    assert config.read_text(encoding="utf-8") == seed
    # Nothing else under the harness root: the refusal precedes every write.
    assert sorted(p.name for p in config.parent.iterdir()) == [config.name]


def test_install_leaves_json5_openclaw_config_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    config = home / ".openclaw" / "openclaw.json"
    config.parent.mkdir(parents=True)
    config.write_text(_JSON5_OPENCLAW, encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    exit_code, envelope = _install("open-claw")

    assert exit_code == 0, envelope
    assert config.read_text(encoding="utf-8") == _JSON5_OPENCLAW
    # verify reads the JSON5 file as a valid config, not a corrupt one.
    verify = CliRunner().invoke(main, ["verify", "--harness", "open-claw", "--json"])
    assert verify.exit_code == 0, verify.output
