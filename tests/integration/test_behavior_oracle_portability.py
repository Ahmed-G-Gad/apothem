# SPDX-License-Identifier: MIT

"""The behavior-diff oracles capture the same bytes on Windows and Linux.

``scripts/dev/regen-behavior-goldens.py`` rewrites the committed corpus from
these oracles, so any machine-dependent byte in a capture becomes churn in an
unrelated change-set. Observed sources: Rich's legacy-console box substitution,
native backslash separators in relative paths, a case-insensitive ledger target
order, table widths that track the temp-path length, ``FORCE_COLOR``, Click's
probe of the host's bash, the operator's ``CODEX_HOME``, JSON- and
markup-escaped spellings of machine paths, a platform release that contains the
engine version, and free-threaded or debug interpreter names. The comparison
layer (``_behavior_canon``) tolerates several of these, so these tests compare
captures against the committed golden exactly, with those conditions applied on
any host.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import click
import pytest
import rich.console
import rich.markup
from click.shell_completion import BashComplete

import apothem.cli

from . import _cli_oracle
from . import _install_driver_oracle as install_oracle
from ._oracle_norm import TOK_PYBIN, tokenize_python_bin

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "behavior-diff"
_MATRIX = {slug: (argv, seed) for slug, argv, seed in _cli_oracle.matrix()}


def test_windows_relative_output_path_is_captured_with_forward_slashes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A relative output path printed with backslashes is stored with slashes."""
    adapter = SimpleNamespace(
        output_path=PureWindowsPath(".cursor/rules/apothem-rules.mdc")
    )
    monkeypatch.setattr(apothem.cli, "_all_adapters", lambda: ([adapter], []))
    _cli_oracle._relative_output_path_spellings.cache_clear()
    try:
        cell = _cli_oracle._normalize_text(
            "│ .cursor\\rules\\apothem-rules.mdc │", home=tmp_path
        )
        raw_json = _cli_oracle._normalize_text(
            '{"output_path": ".cursor\\\\rules\\\\apothem-rules.mdc"}', home=tmp_path
        )
        escape = _cli_oracle._normalize_text('"note": ".cursor\\nrules"', home=tmp_path)
    finally:
        _cli_oracle._relative_output_path_spellings.cache_clear()

    assert cell == "│ .cursor/rules/apothem-rules.mdc │"
    assert raw_json == '{"output_path": ".cursor/rules/apothem-rules.mdc"}'
    assert escape == '"note": ".cursor\\nrules"'


@pytest.mark.parametrize("slug", sorted(_MATRIX))
def test_cli_capture_ignores_console_environment_and_host_tools(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, slug: str
) -> None:
    """No console, color, temp-root, Codex-home or host-bash trait reaches a capture.

    ``tmp_path`` is already longer than the temp root of any machine that
    captures the golden, so the scratch home under it exercises the
    column-width pin without padding that could push the install rows past the
    Windows path limit.
    """
    monkeypatch.setattr(rich.console, "detect_legacy_windows", lambda: True)
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-elsewhere"))
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp_root))

    def old_bash_notice() -> None:
        click.echo(
            "Shell completion is not supported for Bash versions older than 4.4.",
            err=True,
        )

    monkeypatch.setattr(BashComplete, "_check_version", staticmethod(old_bash_notice))
    argv, seed = _MATRIX[slug]

    _cli_oracle.capture_one(tmp_path / "cli", slug, argv, seed_profile=seed)

    captured = json.loads(
        (tmp_path / "cli" / f"{slug}.json").read_text(encoding="utf-8")
    )
    golden = json.loads((GOLDEN / "cli" / f"{slug}.json").read_text(encoding="utf-8"))
    assert captured == golden


def test_escaped_spellings_of_a_machine_path_are_tokenized(tmp_path: Path) -> None:
    """The JSON-escaped and Rich-markup-escaped spellings of the home tokenize too."""
    home = tmp_path / "jos\u00e9 [ci]"
    home.mkdir()
    settings = home / ".claude" / "settings.json"
    json_stdout = json.dumps({"output_path": str(settings)})
    markup_cell = rich.markup.escape(str(settings))

    assert "\\u00e9" in json_stdout
    assert _cli_oracle._normalize_text(json_stdout, home=home) == (
        '{"output_path": "<HOME>/.claude/settings.json"}'
    )
    assert _cli_oracle._normalize_text(markup_cell, home=home) == (
        "<HOME>/.claude/settings.json"
    )


@pytest.mark.parametrize(
    "release",
    [f"Darwin 2{_cli_oracle._VERSION}", f"Linux {_cli_oracle._VERSION}-45-generic"],
)
def test_platform_release_containing_the_engine_version_is_tokenized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: str
) -> None:
    """A release that contains the engine version stays one platform token."""
    monkeypatch.setattr(_cli_oracle, "_PLATFORM", release)
    text = f"Apothem v{_cli_oracle._VERSION}\nPlatform:  {release}"

    assert _cli_oracle._normalize_text(text, home=tmp_path) == (
        "Apothem v<VERSION>\nPlatform:  <PLATFORM>"
    )


def test_versions_inside_a_longer_number_are_left_alone(tmp_path: Path) -> None:
    """A digit after, or a digit or dot before, the version blocks the token."""
    pyver = _cli_oracle._PYVER
    for text in (f"{pyver}0", f"1{pyver}", f"1.{pyver}"):
        assert _cli_oracle._normalize_text(text, home=tmp_path) == text
    assert _cli_oracle._normalize_text(f"Python {pyver}.", home=tmp_path) == (
        "Python <PYVER>."
    )


@pytest.mark.parametrize(
    "interpreter",
    [
        "/usr/bin/python3",
        "C:/Python314/python.exe",
        "/usr/bin/python3.14t",
        "C:/Python314/python3.14t.exe",
        "C:/Python313/python_d.exe",
        "C:/Python314/python3.14t_d.exe",
        "/usr/bin/python3.13d",
        "/usr/bin/python3.12-dbg",
        "/opt/python/bin/python3.13-nogil",
        "C:/Python313/pythonw.exe",
        "C:/Python314/pythonw3.14t.exe",
        "/usr/bin/pypy3.10",
    ],
)
def test_interpreter_paths_of_every_build_are_tokenized(interpreter: str) -> None:
    """Free-threaded, debug, nogil, pythonw and PyPy interpreters all tokenize."""
    assert tokenize_python_bin(f'"{interpreter}"') == f'"{TOK_PYBIN}"'
    assert tokenize_python_bin(f'\\"{interpreter}\\"') == f'\\"{TOK_PYBIN}\\"'


@pytest.mark.parametrize(
    "path", ["/x/skills/python-testing", "/x/pythonista", "/x/python3.14tx"]
)
def test_paths_that_only_resemble_an_interpreter_are_kept(path: str) -> None:
    """A quoted path that does not end in an interpreter name is left alone."""
    assert tokenize_python_bin(f'"{path}"') == f'"{path}"'


def test_ledger_targets_are_stored_in_code_point_order() -> None:
    """Windows and POSIX install orders store the same target order."""
    names = ["NOTICE.md", "__init__.py", "advisory-finding.schema.json"]
    posix_order = sorted(names)
    windows_order = sorted(names, key=str.lower)
    assert windows_order != posix_order

    def record(order: list[str]) -> dict[str, object]:
        return {
            "kind": "install",
            "targets": [
                {"path": f"<ROOT>/.apothem/support/schemas/{name}"} for name in order
            ],
        }

    assert install_oracle._sort_ledger_targets(record(windows_order)) == record(
        posix_order
    )
    assert install_oracle._sort_ledger_targets(record(posix_order)) == record(
        posix_order
    )


@pytest.mark.parametrize("name", install_oracle.REAL_SUBSET)
def test_real_install_ledger_and_envelope_match_golden_exactly(
    tmp_path: Path, name: str
) -> None:
    """A real-install capture keeps the committed ledger order and envelope bytes."""
    out = tmp_path / "corpus"
    install_oracle.capture(out, fast_adapters=[], real_adapters=[name])

    def records(path: Path) -> list[object]:
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    golden = GOLDEN / "install_driver"
    assert records(out / "ledger" / f"{name}.jsonl") == records(
        golden / "ledger" / f"{name}.jsonl"
    )
    assert json.loads(
        (out / "envelope" / f"{name}.json").read_text(encoding="utf-8")
    ) == json.loads((golden / "envelope" / f"{name}.json").read_text(encoding="utf-8"))
