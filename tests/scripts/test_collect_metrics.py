# SPDX-License-Identifier: MIT

"""Unit tests for the CI metrics collector, ``scripts/dev/collect_metrics.py``.

The collector writes the per-commit metrics artifact: line + branch coverage per
package with floors, the always-on instruction bytes each harness loads at
launch after an isolated install, CLI cold start, and end-to-end hook latency.
The tests pin the parts whose mistakes would be silent: the coverage arithmetic
and package attribution, the floor check, each harness's launch-surface rule
(which files count, which do not), the mapping of hook-benchmark results to
values or recorded null reasons, and the artifact's key set.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import collect_metrics as cm  # noqa: E402

from apothem.lib.harness_registry import SUPPORTED_HARNESS_IDS  # noqa: E402

# The collector reads pyproject.toml with the stdlib TOML reader (3.11+); the
# CI metrics job runs on 3.12. The pure helpers below run on every Python.
_needs_tomllib = pytest.mark.skipif(
    sys.version_info < (3, 11), reason="tomllib is stdlib from Python 3.11"
)


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


# --------------------------------------------------------------------------
# Coverage per package
# --------------------------------------------------------------------------


def _summary(lines: int, covered: int, branches: int, covered_branches: int) -> dict:
    return {
        "summary": {
            "num_statements": lines,
            "covered_lines": covered,
            "num_branches": branches,
            "covered_branches": covered_branches,
        }
    }


def test_coverage_per_package_uses_lines_plus_branches() -> None:
    report = {
        "files": {
            "src/apothem/cli/main.py": _summary(80, 70, 20, 10),
            "src/apothem/lib/x.py": _summary(20, 20, 0, 0),
            "src/apothem/conformity/gate.py": _summary(50, 40, 10, 5),
            "src/apothem/audit/scan.py": _summary(10, 1, 0, 0),
            "src/apothem/benchmarks/bench_hooks.py": _summary(10, 0, 0, 0),
        }
    }
    packages = {
        "engine": ("src/apothem/cli", "src/apothem/lib"),
        "conformity": ("src/apothem/conformity",),
        "audit": ("src/apothem/audit",),
    }

    result = cm.coverage_by_package(report, packages)

    assert result == {
        "engine": round(100 * (70 + 10 + 20) / (80 + 20 + 20), 2),
        "conformity": round(100 * (40 + 5) / (50 + 10), 2),
        "audit": 10.0,
    }


def test_statement_only_coverage_ignores_branches() -> None:
    report = {"files": {"src/apothem/audit/a.py": _summary(10, 8, 10, 0)}}
    packages = {"audit": ("src/apothem/audit",)}

    assert cm.coverage_by_package(report, packages) == {"audit": 40.0}
    assert cm.coverage_by_package(report, packages, branches=False) == {"audit": 80.0}


def test_coverage_accepts_absolute_and_windows_paths() -> None:
    report = {"files": {"C:\\w\\src\\apothem\\audit\\a.py": _summary(4, 2, 0, 0)}}
    assert cm.coverage_by_package(report, {"audit": ("src/apothem/audit",)}) == {
        "audit": 50.0
    }


def test_package_with_no_measured_files_is_none() -> None:
    assert cm.coverage_by_package({"files": {}}, {"audit": ("src/apothem/audit",)}) == {
        "audit": None
    }


@_needs_tomllib
def test_floors_come_from_pyproject() -> None:
    packages, floors = cm.coverage_config(_REPO_ROOT / "pyproject.toml")

    assert set(packages) == {"engine", "conformity", "audit"}
    assert "src/apothem/cli" in packages["engine"]
    assert packages["conformity"] == ("src/apothem/conformity",)
    assert floors["engine"] == 80
    assert set(floors) == {"engine", "conformity", "audit"}


def test_floor_violations_name_the_package() -> None:
    violations = cm.floor_violations(
        {"engine": 90.0, "conformity": 83.9, "audit": None},
        {"engine": 80, "conformity": 84, "audit": 73},
    )
    assert violations == ["conformity 83.9 < floor 84", "audit not measured (floor 73)"]


# --------------------------------------------------------------------------
# Always-on launch surfaces
# --------------------------------------------------------------------------


def test_every_registered_harness_has_a_documented_rule() -> None:
    assert set(cm.LAUNCH_SURFACES) == set(SUPPORTED_HARNESS_IDS)
    for harness, (rule, _surfaces) in cm.LAUNCH_SURFACES.items():
        assert rule.strip(), harness


def test_claude_code_counts_unscoped_rules_and_claude_md(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    always = '---\nname: "a"\nalwaysApply: true\n---\nbody\n'
    scoped = '---\nname: "b"\npaths:\n  - "src/**"\n---\nbody\n'
    _write(
        home,
        {
            ".claude/CLAUDE.md": "managed block\n",
            ".claude/rules/a.md": always,
            ".claude/rules/b.md": scoped,
            ".claude/skills/x/SKILL.md": "not loaded in full\n",
        },
    )
    project.mkdir()

    size, files = cm.measure_surfaces("claude-code", home, project)

    assert files == 2
    assert size == _size("managed block\n") + _size(always)


def test_cursor_counts_always_apply_rules_only(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    on = "<!-- BEGIN -->\n---\nalwaysApply: true\n---\nbody\n"
    off = "---\nalwaysApply: false\nglobs: '*.py'\n---\nbody\n"
    _write(project, {".cursor/rules/on.mdc": on, ".cursor/rules/off.mdc": off})
    home.mkdir()

    assert cm.measure_surfaces("cursor", home, project) == (_size(on), 1)


def test_zed_reads_only_the_first_matching_instruction_file(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(project, {".rules": "first\n", "AGENTS.md": "shadowed\n"})
    home.mkdir()

    assert cm.measure_surfaces("zed", home, project) == (_size("first\n"), 1)


# Each kind's file has its own size, so the counted bytes show which kind loaded.
_HERMES_KINDS = {
    ".hermes.md": "h\n",
    "AGENTS.md": "agents.md\n",
    "CLAUDE.md": "claude.md file\n",
    ".cursorrules": "cursor rules file\n",
}


@pytest.mark.parametrize("first", list(_HERMES_KINDS))
def test_hermes_loads_only_the_first_kind_of_project_context(
    tmp_path: Path, first: str
) -> None:
    # Every kind from `first` on is present; only `first` loads, with SOUL.md.
    home, project = tmp_path / "home", tmp_path / "project"
    _write(home, {".hermes/SOUL.md": "soul\n"})
    names = list(_HERMES_KINDS)
    _write(project, {name: _HERMES_KINDS[name] for name in names[names.index(first) :]})

    assert cm.measure_surfaces("hermes", home, project) == (
        _size("soul\n") + _size(_HERMES_KINDS[first]),
        2,
    )


def test_hermes_reads_hermes_md_without_a_dot_hermes_md(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _write(project, {"HERMES.md": "upper case\n", "AGENTS.md": "agents\n"})

    assert cm.measure_surfaces("hermes", home, project) == (_size("upper case\n"), 1)


def test_hermes_skips_an_empty_file_but_an_empty_hermes_md_hides_hermes_md(
    tmp_path: Path,
) -> None:
    # The first of .hermes.md and HERMES.md that exists is the only candidate of
    # its kind: an empty .hermes.md skips the kind, and AGENTS.md loads.
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _write(
        project,
        {".hermes.md": " \n", "HERMES.md": "hidden file\n", "AGENTS.md": "agents\n"},
    )

    assert cm.measure_surfaces("hermes", home, project) == (_size("agents\n"), 1)


def test_hermes_takes_agents_override_md_before_agents_md(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _write(project, {"AGENTS.override.md": "override\n", "AGENTS.md": "base\n"})

    assert cm.measure_surfaces("hermes", home, project) == (_size("override\n"), 1)


def test_hermes_skips_an_empty_agents_override_md(tmp_path: Path) -> None:
    # Unlike Codex, Hermes takes the first non-empty name in a folder.
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _write(project, {"AGENTS.override.md": "", "AGENTS.md": "agents\n"})

    assert cm.measure_surfaces("hermes", home, project) == (_size("agents\n"), 1)


@pytest.mark.parametrize("name", ["agents.md", "claude.md"])
def test_hermes_reads_the_lowercase_names(tmp_path: Path, name: str) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _write(project, {name: "lower case\n"})

    assert cm.measure_surfaces("hermes", home, project) == (_size("lower case\n"), 1)


def test_hermes_skips_an_empty_claude_md_for_a_lowercase_claude_md(
    tmp_path: Path,
) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _write(project, {"CLAUDE.md": ""})
    if (project / "claude.md").exists():
        pytest.skip("this file system does not tell CLAUDE.md and claude.md apart")
    _write(project, {"claude.md": "lower case\n"})

    assert cm.measure_surfaces("hermes", home, project) == (_size("lower case\n"), 1)


def test_hermes_reads_cursor_rules_only_at_the_top_of_their_folder(
    tmp_path: Path,
) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _write(project, {".cursor/rules/a.mdc": "aa\n", ".cursor/rules/sub/b.mdc": "bbb\n"})

    assert cm.measure_surfaces("hermes", home, project) == (_size("aa\n"), 1)


def test_hermes_loads_every_cursor_rules_file_together(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _write(
        project,
        {
            ".cursorrules": "r\n",
            ".cursor/rules/a.mdc": "aa\n",
            ".cursor/rules/b.mdc": "bbb\n",
            ".cursor/rules/empty.mdc": "",
        },
    )

    assert cm.measure_surfaces("hermes", home, project) == (
        _size("r\n") + _size("aa\n") + _size("bbb\n"),
        3,
    )


def test_codex_counts_the_global_and_the_project_agents_md(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(home, {".codex/AGENTS.md": "global\n"})
    _write(project, {"AGENTS.md": "project\n"})

    assert cm.measure_surfaces("codex", home, project) == (
        _size("global\n") + _size("project\n"),
        2,
    )


def test_codex_takes_an_override_before_agents_md(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(
        home, {".codex/AGENTS.override.md": "g-over\n", ".codex/AGENTS.md": "global\n"}
    )
    _write(project, {"AGENTS.override.md": "p-over\n", "AGENTS.md": "project\n"})

    assert cm.measure_surfaces("codex", home, project) == (
        _size("g-over\n") + _size("p-over\n"),
        2,
    )


def test_codex_skips_an_empty_global_override_but_not_an_empty_project_one(
    tmp_path: Path,
) -> None:
    # In the home folder an empty override falls through to AGENTS.md. In a
    # project folder the first file that exists is the only candidate, so an
    # empty override there loads nothing and hides the AGENTS.md beside it.
    home, project = tmp_path / "home", tmp_path / "project"
    _write(home, {".codex/AGENTS.override.md": " \n", ".codex/AGENTS.md": "global\n"})
    _write(project, {"AGENTS.override.md": "", "AGENTS.md": "hidden\n"})

    assert cm.measure_surfaces("codex", home, project) == (_size("global\n"), 1)


@_needs_tomllib
def test_codex_reads_fallback_names_and_the_byte_limit_from_config_toml(
    tmp_path: Path,
) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(
        home,
        {
            ".codex/config.toml": (
                'project_doc_fallback_filenames = ["../x.md", "TEAM_GUIDE.md"]\n'
                "project_doc_max_bytes = 25\n"
            ),
            ".codex/AGENTS.md": "global file, longer than the limit\n",
        },
    )
    # A fallback entry that is not a plain file name is ignored, so the 20-byte
    # file outside the project does not count; TEAM_GUIDE.md is capped at 25 and
    # the global file is not capped.
    _write(tmp_path, {"x.md": "outside the project\n"})
    _write(project, {"TEAM_GUIDE.md": "team guide, longer than the limit\n"})

    assert cm.measure_surfaces("codex", home, project) == (
        _size("global file, longer than the limit\n") + 25,
        2,
    )


@_needs_tomllib
def test_codex_reads_no_project_file_when_the_limit_is_zero(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(
        home,
        {
            ".codex/config.toml": "project_doc_max_bytes = 0\n",
            ".codex/AGENTS.md": "global\n",
        },
    )
    _write(project, {"AGENTS.md": "project\n"})

    assert cm.measure_surfaces("codex", home, project) == (_size("global\n"), 1)


def test_codex_reports_an_unreadable_config_as_an_error_for_its_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Without tomllib (Python 3.10), collect() records a null for Codex, as it
    # does for any RuntimeError, instead of ending the whole run.
    monkeypatch.setitem(sys.modules, "tomllib", None)
    home, project = tmp_path / "home", tmp_path / "project"
    _write(home, {".codex/config.toml": "project_doc_max_bytes = 4\n"})
    project.mkdir()

    with pytest.raises(RuntimeError, match=r"needs Python 3\.11\+"):
        cm.measure_surfaces("codex", home, project)


def test_codex_caps_project_files_at_32_kib_by_default(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _write(project, {"AGENTS.md": "x" * 40_000 + "\n"})

    assert cm.measure_surfaces("codex", home, project) == (32 * 1024, 1)


def test_opencode_resolves_instruction_globs(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    config = {"instructions": ["~/.config/opencode/support/rules/*.md"]}
    _write(
        home,
        {
            ".config/opencode/opencode.json": json.dumps(config),
            ".config/opencode/support/rules/a.md": "aaaa\n",
            ".config/opencode/support/rules/b.md": "bb\n",
            ".config/opencode/support/other.md": "not matched\n",
        },
    )
    project.mkdir()

    assert cm.measure_surfaces("opencode", home, project) == (_size("aaaa\nbb\n"), 2)


def test_qwen_uses_the_configured_context_file_name(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(
        home,
        {
            ".qwen/settings.json": json.dumps({"context": {"fileName": ["CTX.md"]}}),
            ".qwen/CTX.md": "context\n",
            ".qwen/QWEN.md": "not the configured name\n",
        },
    )
    project.mkdir()

    assert cm.measure_surfaces("qwen-code", home, project) == (_size("context\n"), 1)


def test_unloaded_support_trees_count_zero(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(home, {".hermes/apothem/rules/00-apothem-profile.md": "profile rule\n"})
    project.mkdir()

    assert cm.measure_surfaces("hermes", home, project) == (0, 0)


def test_hermes_skips_a_blank_soul_md(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(home, {".hermes/SOUL.md": " \n\n"})
    project.mkdir()

    assert cm.measure_surfaces("hermes", home, project) == (0, 0)


def test_claude_code_reads_claude_local_md(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _write(project, {"CLAUDE.local.md": "local\n", "AGENTS.md": "agents\n"})

    # CLAUDE.local.md is a CLAUDE file, so AGENTS.md is not read.
    assert cm.measure_surfaces("claude-code", home, project) == (_size("local\n"), 1)


def test_claude_code_reads_agents_md_only_without_a_project_claude_file(
    tmp_path: Path,
) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    # A user-level CLAUDE.md does not block the fallback.
    _write(home, {".claude/CLAUDE.md": "user\n"})
    _write(project, {"AGENTS.md": "agents\n", ".claude/AGENTS.md": "nested\n"})

    assert cm.measure_surfaces("claude-code", home, project) == (
        _size("user\n") + _size("agents\n") + _size("nested\n"),
        3,
    )

    _write(project, {".claude/CLAUDE.md": "claude\n"})

    assert cm.measure_surfaces("claude-code", home, project) == (
        _size("user\n") + _size("claude\n"),
        2,
    )


def test_codebuddy_skips_disabled_and_conditional_rules(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    on = "---\ndescription: on\n---\nrule\n"
    always = "---\nalwaysApply: true\n---\nalways\n"
    _write(
        home,
        {
            ".codebuddy/CODEBUDDY.md": "user memory\n",
            ".codebuddy/rules/nested/on.md": on,
        },
    )
    _write(
        project,
        {
            ".codebuddy/rules/off.md": "---\nenabled: false\n---\noff\n",
            ".codebuddy/rules/paths.md": "---\nalwaysApply: false\n---\npaths\n",
            ".codebuddy/rules/always.md": always,
            "CODEBUDDY.local.md": "local\n",
        },
    )

    assert cm.measure_surfaces("codebuddy", home, project) == (
        _size("user memory\n") + _size(on) + _size(always) + _size("local\n"),
        4,
    )


@pytest.mark.parametrize(
    ("present", "loaded"),
    [
        (("CODEBUDDY.md", ".codebuddy/CODEBUDDY.md", "AGENTS.md"), "CODEBUDDY.md"),
        ((".codebuddy/CODEBUDDY.md", "AGENTS.md"), ".codebuddy/CODEBUDDY.md"),
        (("AGENTS.md",), "AGENTS.md"),
    ],
)
def test_codebuddy_reads_one_project_memory_file(
    tmp_path: Path, present: tuple[str, ...], loaded: str
) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _write(project, {name: f"{name}\n" for name in present})

    assert cm.measure_surfaces("codebuddy", home, project) == (_size(f"{loaded}\n"), 1)


def test_kimi_code_reads_the_cross_tool_file_and_skips_blank_files(
    tmp_path: Path,
) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(
        home,
        {
            ".kimi-code/AGENTS.md": "global\n",
            ".agents/AGENTS.md": "\n",
            ".agents/agents.md": "cross tool\n",
        },
    )
    _write(project, {"AGENTS.md": "project\n", ".kimi-code/AGENTS.md": "  \n"})

    assert cm.measure_surfaces("kimi-code", home, project) == (
        _size("global\n") + _size("cross tool\n") + _size("project\n"),
        3,
    )


def test_antigravity_reads_the_agents_folder_and_caps_each_file(
    tmp_path: Path,
) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(home, {".gemini/GEMINI.md": "x" * 30_000})
    always = "---\ntrigger: always_on\n---\nrule\n"
    _write(
        project,
        {
            ".agents/AGENTS.md": "agents\n",
            ".agents/rules/always.md": always,
            ".agents/rules/manual.md": "---\ntrigger: manual\n---\nmanual\n",
        },
    )

    assert cm.measure_surfaces("antigravity", home, project) == (
        24_000 + _size("agents\n") + _size(always),
        3,
    )


def test_antigravity_does_not_count_the_old_plugin_folder(
    tmp_path: Path,
) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(
        home,
        {
            ".gemini/antigravity-cli/plugins/apothem/rules/r.md": (
                "---\ntrigger: always_on\n---\nrule\n"
            )
        },
    )
    project.mkdir()

    assert cm.measure_surfaces("antigravity", home, project) == (0, 0)


_AG_PLUGINS = ".gemini/config/plugins/"
# A license comment line, split so license scanners do not read it as the
# header of this file.
_AG_COMMENT = "<!-- SPDX" + "-License-Identifier: MIT -->\n"
_AG_ALWAYS = "---\ntrigger: always_on\n---\n" + _AG_COMMENT + "r\n"


def test_antigravity_counts_always_on_plugin_rules(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    rules = _AG_PLUGINS + "apothem/rules/"
    _write(
        home,
        {
            _AG_PLUGINS + "apothem/plugin.json": "{}\n",
            rules + "always.md": _AG_ALWAYS,
            rules + "scoped.md": (
                "---\ntrigger: glob\ndescription: Python\nglobs: '*.py'\n---\nscoped\n"
            ),
            rules + "decide.md": (
                "---\ntrigger: model_decision\ndescription: When asked\n---\nd\n"
            ),
            rules + "manual.md": "---\ntrigger: manual\n---\nmanual\n",
            rules + "late.md": (_AG_COMMENT + "---\ntrigger: always_on\n---\n"),
            rules + "nested/deep.md": _AG_ALWAYS,
        },
    )
    project.mkdir()

    assert cm.measure_surfaces("antigravity", home, project) == (_size(_AG_ALWAYS), 1)


def test_antigravity_counts_each_plugin_and_its_rules_anchor(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    anchor = "Plugin-wide guidance without frontmatter.\n"
    _write(
        home,
        {
            _AG_PLUGINS + "one/plugin.json": '{"name": "one"}\n',
            _AG_PLUGINS + "one/rules/AGENTS.md": anchor,
            _AG_PLUGINS + "one/rules/GEMINI.md": "not loaded beside AGENTS.md\n",
            _AG_PLUGINS + "two/plugin.json": '{"name": "two"}\n',
            _AG_PLUGINS + "two/rules/GEMINI.md": anchor,
            _AG_PLUGINS + "two/rules/always.md": _AG_ALWAYS,
        },
    )
    project.mkdir()

    assert cm.measure_surfaces("antigravity", home, project) == (
        2 * _size(anchor) + _size(_AG_ALWAYS),
        3,
    )


def test_antigravity_skips_a_folder_without_a_manifest_or_marked_disabled(
    tmp_path: Path,
) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(
        home,
        {
            _AG_PLUGINS + "loose/rules/AGENTS.md": "no plugin.json\n",
            _AG_PLUGINS + "loose/rules/always.md": _AG_ALWAYS,
            _AG_PLUGINS + "off/plugin.json": '{"name": "off", "disabled": true}\n',
            _AG_PLUGINS + "off/rules/always.md": _AG_ALWAYS,
        },
    )
    project.mkdir()

    assert cm.measure_surfaces("antigravity", home, project) == (0, 0)


@_needs_tomllib
def test_an_unreadable_launch_file_records_a_null(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(harness: str) -> tuple[int, int]:
        raise PermissionError(f"cannot read a {harness} rule")

    monkeypatch.setattr(cm, "install_and_measure", fail)
    out = tmp_path / "metrics.json"
    cm.main(
        [
            "--harness",
            "antigravity",
            "--skip-coldstart",
            "--skip-hooks",
            "--out",
            str(out),
        ]
    )
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["always_on_bytes"]["antigravity"] is None
    assert "cannot read" in data["nulls"]["always_on_bytes.antigravity"]


def test_open_claw_reads_the_bootstrap_files_in_order_with_caps(
    tmp_path: Path,
) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    project.mkdir()
    workspace = ".openclaw/workspace/"
    _write(
        home,
        {
            workspace + "AGENTS.md": "a" * 25_000,
            workspace + "SOUL.md": " \n",
            workspace + "USER.md": "é" * 5_000,
            workspace + "notes.md": "not a bootstrap file\n",
        },
    )

    # AGENTS.md is cut at 20,000 characters, SOUL.md is blank, and USER.md is
    # cut at 4,000 characters of two bytes each.
    assert cm.measure_surfaces("open-claw", home, project) == (20_000 + 8_000, 2)


def test_open_claw_stops_at_the_total_budget(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    project.mkdir()
    workspace = ".openclaw/workspace/"
    _write(
        home,
        {
            workspace + "AGENTS.md": "a" * 20_000,
            workspace + "SOUL.md": "s" * 20_000,
            workspace + "IDENTITY.md": "i" * 19_950,
            # 50 characters are left, fewer than the 64 OpenClaw needs to go on.
            workspace + "MEMORY.md": "memory\n",
        },
    )

    assert cm.measure_surfaces("open-claw", home, project) == (59_950, 3)


# --------------------------------------------------------------------------
# Hook latency mapping
# --------------------------------------------------------------------------


def test_hook_results_map_to_values_or_null_reasons() -> None:
    report = {
        "chains": {
            "PreToolUse:Write": {
                "status": "pass",
                "median_sum_ms": 412.5,
                "injected_chars": 7779,
                "detail": "ok",
            },
            "Stop": {
                "status": "error",
                "median_sum_ms": None,
                "injected_chars": None,
                "detail": "exit 126 (not executable) running as registered",
            },
        }
    }
    nulls: dict[str, str] = {}

    latency, injected = cm.hook_metrics(report, nulls)

    assert latency == {"PreToolUse:Write": 412.5, "Stop": None}
    assert injected == {"PreToolUse:Write": 7779, "Stop": None}
    assert nulls == {
        "hook_e2e_ms.Stop": "exit 126 (not executable) running as registered"
    }


# --------------------------------------------------------------------------
# The artifact
# --------------------------------------------------------------------------


@_needs_tomllib
@pytest.mark.skipif(sys.platform == "win32", reason="isolated POSIX install run")
def test_artifact_carries_every_key_with_a_value_or_a_reason(tmp_path: Path) -> None:
    out = tmp_path / "metrics.json"

    code = cm.main(
        ["--harness", "cursor", "--skip-hooks", "--skip-coldstart", "--out", str(out)]
    )

    assert code == 0
    metrics = json.loads(out.read_text(encoding="utf-8"))
    assert metrics["schema_version"] == 1
    assert set(metrics["coverage"]) == {"engine", "conformity", "audit"}
    assert set(metrics["coverage_lines"]) == {"engine", "conformity", "audit"}
    assert set(metrics["always_on_bytes"]) == set(SUPPORTED_HARNESS_IDS)
    assert metrics["always_on_bytes"]["cursor"] > 0
    assert metrics["always_on_files"]["cursor"] == 1
    assert metrics["always_on_bytes"]["codex"] is None
    assert "always_on_bytes.codex" in metrics["nulls"]
    assert metrics["cli_coldstart_ms"] is None
    assert "cli_coldstart_ms" in metrics["nulls"]
    assert metrics["hook_e2e_ms"] == {}
    assert "hook_e2e_ms" in metrics["nulls"]
    assert "coverage.engine" in metrics["nulls"]
    assert set(metrics["rules"]["always_on_bytes"]) == set(SUPPORTED_HARNESS_IDS)
