# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The Claude Code install writes each rule the way Claude Code reads it.

Two properties of the ``claude_rules`` emission are pinned here: the copy drops
the closing ``## Bindings`` section (maintainer text that would otherwise load
into every session) and keeps everything else, and a reinstall over the files
an earlier release wrote leaves nothing stale. Platform-neutral on purpose: the
end-to-end test in ``test_claude_rules_paths.py`` runs only on POSIX.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from apothem.conformity import (
    always_on_budget_grep as budget,
)
from apothem.conformity import (
    binding_five_direction_grep,
    binding_reciprocity_corpus_grep,
)
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_converters import (
    _antigravity_rule_text,
    _claude_rule_text,
)
from apothem.lib.claude_skill_split import without_bindings
from apothem.lib.frontmatter import field_value
from tests._shared.claude_rule_scope import loads_at_launch_text

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_RULES = _PKG / "rules"
_NOT_RULES = frozenset({"README.md", "AGENTS.md"})
_SHIPPED = sorted(p for p in _RULES.glob("*.md") if p.name not in _NOT_RULES)

_FENCE = re.compile(r"^ {0,3}(```|~~~)")
_BINDINGS = re.compile(r"^##\s+Bindings\b")

_BINDINGS_SECTION = (
    "## Bindings (§0.j five-direction)\n\n"
    "- **Drives →** the downstream surface.\n"
    "- **Cross-bound with ↔** `rules/other.md` (a sibling).\n"
)


def _rule(
    tmp_path: Path,
    body: str,
    *,
    path_filter: str = "",
    always: bool = True,
    name: str = "r",
) -> Path:
    path = tmp_path / f"{name}.md"
    path.write_text(
        "---\n"
        f'name: "{name}"\n'
        'description: "A rule."\n'
        f'pathFilter: "{path_filter}"\n'
        f"alwaysApply: {'true' if always else 'false'}\n"
        "---\n\n<!-- SPDX-License-Identifier: MIT -->\n\n" + body,
        encoding="utf-8",
    )
    return path


def _frontmatter(text: str) -> dict[str, object]:
    assert text.startswith("---\n"), text[:80]
    loaded = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    assert isinstance(loaded, dict)
    return loaded


def _real_bindings_headings(text: str) -> list[str]:
    """Return the ``## Bindings`` headings of *text* that sit outside a fence."""
    found: list[str] = []
    fenced = False
    for line in text.split("\n"):
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and _BINDINGS.match(line):
            found.append(line)
    return found


# --------------------------------------------------------------------------
# The pure emission
# --------------------------------------------------------------------------


def test_the_bindings_section_is_dropped_and_the_body_kept(tmp_path: Path) -> None:
    source = _rule(tmp_path, "# Rule\n\nBody text.\n\n" + _BINDINGS_SECTION)
    rendered = _claude_rule_text(source)
    assert "Bindings" not in rendered
    assert "Drives" not in rendered
    assert rendered.endswith("# Rule\n\nBody text.\n")
    # Only the Bindings section differs from the source.
    original = source.read_text(encoding="utf-8")
    assert original.startswith(rendered.rstrip("\n"))


def test_a_scoped_rule_gets_paths_and_loses_bindings(tmp_path: Path) -> None:
    source = _rule(
        tmp_path,
        "# Rule\n\nBody.\n\n" + _BINDINGS_SECTION,
        path_filter="**/*.py, **/pyproject.toml",
        always=False,
    )
    rendered = _claude_rule_text(source)
    assert _frontmatter(rendered)["paths"] == ["**/*.py", "**/pyproject.toml"]
    assert "Bindings" not in rendered
    assert rendered.endswith("Body.\n")


def test_a_section_that_follows_bindings_is_kept(tmp_path: Path) -> None:
    body = (
        "# Rule\n\nBody.\n\n"
        + _BINDINGS_SECTION
        + "\n## Recommended Next Step\n\nNaming the next step.\n"
    )
    rendered = _claude_rule_text(_rule(tmp_path, body))
    assert "Drives" not in rendered
    assert rendered.endswith("## Recommended Next Step\n\nNaming the next step.\n")


def test_a_fenced_bindings_example_is_kept(tmp_path: Path) -> None:
    body = (
        "# Rule\n\nThe shape:\n\n```markdown\n"
        + _BINDINGS_SECTION
        + "```\n\nMore body.\n\n"
        + _BINDINGS_SECTION
    )
    rendered = _claude_rule_text(_rule(tmp_path, body))
    assert rendered.count("## Bindings") == 1
    assert "```markdown\n## Bindings" in rendered
    assert rendered.endswith("More body.\n")


def test_a_rule_without_bindings_is_unchanged(tmp_path: Path) -> None:
    source = _rule(tmp_path, "# Rule\n\nBody.\n")
    assert _claude_rule_text(source) == source.read_text(encoding="utf-8")


def test_text_without_frontmatter_is_returned_as_is(tmp_path: Path) -> None:
    path = tmp_path / "plain.md"
    path.write_text("# Plain\n\n" + _BINDINGS_SECTION, encoding="utf-8")
    assert _claude_rule_text(path) == path.read_text(encoding="utf-8")


def test_the_source_file_is_not_modified(tmp_path: Path) -> None:
    source = _rule(tmp_path, "# Rule\n\nBody.\n\n" + _BINDINGS_SECTION)
    before = source.read_bytes()
    _claude_rule_text(source)
    assert source.read_bytes() == before


def test_the_other_harnesses_keep_the_section(tmp_path: Path) -> None:
    source = _rule(tmp_path, "# Rule\n\nBody.\n\n" + _BINDINGS_SECTION)
    assert "## Bindings" in _antigravity_rule_text(source)
    shipped = _RULES / "definitiveness.md"
    assert "## Bindings" in _antigravity_rule_text(shipped)


# --------------------------------------------------------------------------
# Every shipped rule
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", _SHIPPED, ids=lambda p: p.stem)
def test_every_shipped_rule_renders_without_its_bindings(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    rendered = _claude_rule_text(path)
    assert _real_bindings_headings(source), "every shipped rule closes with Bindings"
    assert _real_bindings_headings(rendered) == []
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")
    # The kept text is the source minus the section, nothing else: the bodies
    # match, and the frontmatter differs only by the added ``paths:`` list.
    kept = without_bindings(source).rstrip("\n") + "\n"
    assert rendered.split("\n---\n", 1)[1] == kept.split("\n---\n", 1)[1]
    scoped = bool((field_value(path, "pathFilter") or "").strip())
    assert ("paths" in _frontmatter(rendered)) is scoped


# --------------------------------------------------------------------------
# A real install
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def claude_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("home") / ".claude"
    with pytest.MonkeyPatch.context() as patch:
        # Keep the install's backups out of the real home directory.
        patch.setattr(install_driver, "BACKUP_ROOT", tmp_path_factory.mktemp("backups"))
        install_driver.run_install("claude_code", harness_root=root)
    return root


def test_the_install_writes_every_rule_in_its_shipped_form(claude_root: Path) -> None:
    installed = {p.name: p for p in (claude_root / "rules").glob("*.md")}
    assert set(installed) == {p.name for p in _SHIPPED}
    for source in _SHIPPED:
        text = installed[source.name].read_text(encoding="utf-8")
        assert text == _claude_rule_text(source), source.name
        assert _real_bindings_headings(text) == [], source.name


def test_the_installed_tree_passes_the_binding_validators(claude_root: Path) -> None:
    five = binding_five_direction_grep.check(claude_root)
    assert five.passed, [(f.path, f.detail) for f in five.findings]
    assert five.inspected > len(_SHIPPED)
    corpus = binding_reciprocity_corpus_grep.check(claude_root)
    assert corpus.passed
    assert corpus.inspected == len(_SHIPPED)


def test_only_the_always_on_rules_load_at_launch(claude_root: Path) -> None:
    # Claude Code loads a rule at launch when it has no ``paths`` list or the
    # list is unconditional (``**`` alone), so a bare "paths" check is not enough.
    loaded = sorted(
        p.stem
        for p in (claude_root / "rules").glob("*.md")
        if loads_at_launch_text(p.read_text(encoding="utf-8"))
    )
    always_on = sorted(
        p.stem
        for p in _SHIPPED
        if (field_value(p, "alwaysApply") or "").strip().lower() == "true"
    )
    assert loaded == always_on


def test_the_launch_set_fits_the_byte_ceiling(claude_root: Path) -> None:
    sizes = {
        p.stem: len(p.read_text(encoding="utf-8").split("\n---\n", 1)[1].encode())
        for p in (claude_root / "rules").glob("*.md")
        if loads_at_launch_text(p.read_text(encoding="utf-8"))
    }
    assert len(sizes) == 5, sizes
    assert sum(sizes.values()) <= budget.MAX_ALWAYS_ON_LOADED_BYTES, sizes
    assert sizes["apothem-rule-index"] <= budget.MAX_INDEX_LOADED_BYTES, sizes


# --------------------------------------------------------------------------
# Pointers that survive the Bindings cut
# --------------------------------------------------------------------------


def _parent_of(stem: str, stems: list[str]) -> str | None:
    """Return the rule whose name is *stem* minus its last ``-aspect`` suffix."""
    candidates = [s for s in stems if s != stem and stem.startswith(s + "-")]
    return max(candidates, key=len) if candidates else None


def test_every_companion_is_still_named_in_its_parents_claude_copy() -> None:
    # The Claude Code copy drops the Bindings section, which is where a parent
    # may be the only place that names a companion. A companion the copy no
    # longer names is unreachable from its parent when no path matches.
    stems = [p.stem for p in _SHIPPED]
    lost = []
    for stem in stems:
        parent = _parent_of(stem, stems)
        if parent is None:
            continue
        copy = _claude_rule_text(_RULES / f"{parent}.md")
        if stem not in copy:
            lost.append(f"{parent} -> {stem}")
    assert not lost, (
        "add a (Companion Sub-Rule Anchor) line to the parent body: " + ", ".join(lost)
    )


# --------------------------------------------------------------------------
# Migration: a reinstall over what an earlier release wrote
# --------------------------------------------------------------------------


def _earlier_release_text(source: Path) -> str:
    """Render *source* as the release before this one did.

    The whole file, Bindings included, with a ``paths:`` list added only for a
    rule that had a ``pathFilter`` (the always-on rules were copied verbatim).
    """
    text = source.read_text(encoding="utf-8")
    path_filter = (field_value(source, "pathFilter") or "").strip()
    if not path_filter:
        return text
    end = text.index("\n---\n", 4)
    globs = [item.strip() for item in path_filter.split(",") if item.strip()]
    paths = "paths:\n" + "".join(f'  - "{glob}"\n' for glob in globs)
    return text[: end + 1] + paths + text[end + 1 :]


def test_a_reinstall_over_earlier_copies_leaves_nothing_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backups = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backups)
    root = tmp_path / ".claude"
    rules = root / "rules"
    rules.mkdir(parents=True)
    for source in _SHIPPED:
        (rules / source.name).write_text(
            _earlier_release_text(source), encoding="utf-8", newline="\n"
        )
    operator = rules / "my-own-rule.md"
    operator.write_text("# Mine\n\nKeep me.\n", encoding="utf-8")

    run = install_driver.run_install("claude_code", harness_root=root)

    rule_results = [r for r in run.results if r.operation == "claude_rules"]
    assert rule_results
    assert {r.outcome for r in rule_results} <= {"created", "updated", "unchanged"}
    # Every Apothem rule is now exactly the shipped form.
    for source in _SHIPPED:
        text = (rules / source.name).read_text(encoding="utf-8")
        assert text == _claude_rule_text(source), source.name
        assert _real_bindings_headings(text) == [], source.name
    # Nothing was left over, and nothing of the operator's was touched.
    assert {p.name for p in rules.iterdir()} == {
        *(p.name for p in _SHIPPED),
        operator.name,
    }
    assert operator.read_text(encoding="utf-8") == "# Mine\n\nKeep me.\n"
    # Each copy the install rewrote was backed up first, with its old bytes.
    updated = {Path(r.path).name for r in rule_results if r.outcome == "updated"}
    assert updated
    saved = {p.name: p for p in backups.rglob("*.md")}
    assert updated <= set(saved)
    for name in sorted(updated)[:5]:
        assert saved[name].read_text(encoding="utf-8") == _earlier_release_text(
            _RULES / name
        )


def test_a_second_install_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    root = tmp_path / ".claude"
    install_driver.run_install("claude_code", harness_root=root)
    again = install_driver.run_install("claude_code", harness_root=root)
    rule_results = [r for r in again.results if r.operation == "claude_rules"]
    assert rule_results
    assert {r.outcome for r in rule_results} == {"unchanged"}


# REUSE-IgnoreEnd
