# SPDX-License-Identifier: MIT

"""Every converted cohort declares what happens to each source field.

A harness whose registry cell for a cohort is ``converted`` rewrites the source
files into its own format, and some source fields have no native home. Each
such harness's ``capabilities.yml`` carries ``conversion_losses``: for every
converted cohort, every frontmatter key the source corpus uses maps to one of

- ``native:<field>`` — the harness reads it under that field (or file);
- ``sidecar:<path>`` — it is expressed in a generated file beside the target;
- ``filename`` — the emitted file or directory name carries it;
- ``inlined`` — it moves into the prompt or body text the model reads;
- ``ignored`` — it stays in the emitted file but the harness does not read it;
- ``dropped`` — it is not emitted.

The declarations are checked against real renders, so a converter change that
drops or adds a field fails here until the map is updated.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

try:  # tomllib is stdlib from Python 3.11; pytest and mypy bring tomli on 3.10.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from apothem.harnesses._shared import install_driver_converters as conv
from apothem.lib.harness_registry import iter_harness_entries
from apothem.lib.propagation import load_manifest

_REPO = Path(__file__).resolve().parents[2]
_PKG = _REPO / "src" / "apothem"
_COHORT_SOURCES = {"commands": "commands/", "agents": "agents/", "rules": "rules/"}
_VALUE = re.compile(r"^(native:\S+|sidecar:\S+|filename|inlined|ignored|dropped)$")


def _members(cohort: str) -> list[Path]:
    return sorted(
        p
        for p in (_PKG / cohort).glob("*.md")
        if p.name not in {"README.md", "AGENTS.md"}
    )


def _source_keys(cohort: str) -> set[str]:
    keys: set[str] = set()
    for path in _members(cohort):
        text = path.read_text(encoding="utf-8")
        keys |= set(yaml.safe_load(text[4 : text.index("\n---\n", 4)]))
    return keys


def _converted() -> list[tuple[str, str, Path]]:
    rows = []
    for entry in iter_harness_entries():
        for cohort, status in sorted(entry.capability_status.items()):
            if status == "converted" and cohort in _COHORT_SOURCES:
                rows.append(
                    (entry.package_key, cohort, _REPO / entry.capabilities_path)
                )
    return rows


_CONVERTED = _converted()


def _losses(capabilities: Path) -> dict[str, dict[str, str]]:
    data = yaml.safe_load(capabilities.read_text(encoding="utf-8"))
    losses = data.get("conversion_losses")
    assert isinstance(losses, dict), f"{capabilities}: no conversion_losses map"
    return losses


def test_converted_cells_exist() -> None:
    assert len(_CONVERTED) >= 8


@pytest.mark.parametrize(("harness", "cohort", "caps"), _CONVERTED)
def test_every_source_key_is_declared(harness: str, cohort: str, caps: Path) -> None:
    declared = _losses(caps).get(cohort)
    assert isinstance(declared, dict), f"{harness}: no conversion_losses.{cohort}"
    assert set(declared) == _source_keys(cohort), harness
    for key, value in declared.items():
        assert _VALUE.match(str(value)), f"{harness}.{cohort}.{key}: {value!r}"


def _mode(harness: str, cohort: str) -> str:
    for entry in load_manifest()[harness].install:
        if entry.source == _COHORT_SOURCES[cohort]:
            return entry.mode
    raise AssertionError(f"{harness} has no {cohort} install entry")


def _render(harness: str, mode: str, path: Path) -> tuple[set[str], str, set[str]]:
    """Return (emitted top-level keys, prompt/body text, sidecar paths)."""
    renderers: dict[str, Callable[[Path], str]] = {
        "gemini_commands": conv._gemini_command_text,
        "codex_agents": conv._codex_agent_text,
        "markdown_commands": conv._native_markdown_command_text,
        "gemini_agents": conv._gemini_agent_text,
        "qwen_agents": conv._qwen_agent_text,
        "opencode_agents": conv._opencode_agent_text,
        "antigravity_agents": conv._antigravity_agent_text,
        "antigravity_rules": conv._antigravity_rule_text,
    }
    sidecars: set[str] = set()
    if mode == "command_skills":
        files = conv._command_skill_files(
            path, harness_name=harness, install_root=Path("/root")
        )
        text = files.pop("SKILL.md").decode("utf-8")
        sidecars = set(files)
    else:
        text = renderers[mode](path)
    if text.startswith("---\n"):
        end = text.index("\n---\n", 4)
        return set(yaml.safe_load(text[4:end])), text[end + 5 :], sidecars
    data = tomllib.loads(text)
    body = str(data.get("prompt", data.get("developer_instructions", "")))
    return set(data), body, sidecars


@pytest.mark.parametrize(("harness", "cohort", "caps"), _CONVERTED)
def test_declarations_match_the_render(harness: str, cohort: str, caps: Path) -> None:
    declared = _losses(caps)[cohort]
    mode = _mode(harness, cohort)
    renders = [_render(harness, mode, path) for path in _members(cohort)]
    all_keys = set().union(*(keys for keys, _, _ in renders))
    all_sidecars = set().union(*(side for _, _, side in renders))
    for source_key, value in declared.items():
        if value == "dropped":
            assert source_key not in all_keys, (harness, source_key)
        elif value == "ignored":
            assert source_key in all_keys, (harness, source_key)
        elif value.startswith("native:"):
            native = value.split(":", 1)[1]
            if "/" not in native and "." not in native:
                assert native in all_keys, (harness, source_key, native)
        elif value.startswith("sidecar:"):
            assert value.split(":", 1)[1].split("#", 1)[0] in all_sidecars
    for _, body, _ in renders:
        assert not body.lstrip().startswith("---"), (
            f"{harness}: body opens with frontmatter"
        )


def test_gemini_command_prompts_carry_no_frontmatter() -> None:
    for path in _members("commands"):
        prompt = tomllib.loads(conv._gemini_command_text(path))["prompt"]
        assert not prompt.startswith("---"), path.name
        assert not prompt.startswith("<!--"), path.name
        head = prompt.split("\n# ", 1)[0]
        for key in ("disable-model-invocation:", "allowed-tools:", "portability:"):
            assert key not in head, (path.name, key)
