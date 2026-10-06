# SPDX-License-Identifier: MIT

"""Guard docs frontmatter examples against the real artifact frontmatter contract.

Why this guard exists. The docs site teaches operators to author their own
rules and agents by showing copy-paste frontmatter examples inside fenced
``yaml`` / ``markdown`` code blocks. When those examples drift from the keys a
real shipped artifact actually carries, an operator who copies them produces an
artifact the conformity gate rejects. That exact drift was just repaired across
``usage/writing-rules.mdx``, ``examples/custom-rule.mdx``, and
``usage/using-agents.mdx`` (invented ``scope`` / ``path-filter`` / ``portability``
on rules; ``model`` / ``allowed-tools`` on agents). This test is the regression
guard for that class.

What the contract is, and where it comes from. The guard does not hard-code key
literals — it derives the contract from the canonical sources so it tracks them
as they evolve:

* **Rules.** ``frontmatter_grep.REQUIRED_KEYS["rules"]`` ({name, description,
  alwaysApply}) plus the one allow-list key a rule legitimately carries,
  ``pathFilter`` (verified present in ``frontmatter_grep.KEY_ALLOW_LIST``). Each
  rule example is run through ``frontmatter_grep.check`` against a synthetic
  ``rules/`` path — the same required-key + key-shape contract the PreToolUse
  validator enforces — and then held to a strict "only these keys" check that
  ``check`` alone does not provide (``check`` accepts any superficially
  kebab-case key, so ``scope`` / ``portability`` slip past it).

* **Agents.** ``frontmatter_grep.REQUIRED_KEYS["agents"]`` ({name, description})
  plus the union of top-level keys actually used by the shipped agents under
  ``src/apothem/agents/*.md``. ``frontmatter_grep.check`` is deliberately *not*
  reused for agents: its kebab-case rule rejects the real agent schema's
  camelCase keys (``disallowedTools`` / ``maxTurns`` / ``permissionMode``), and
  its allow-list still admits ``model`` — so it would both reject valid agent
  examples and pass the exact ``model`` drift this guard must catch. The shipped
  agents are the authoritative agent contract.

Scope. The guard covers every *single-class* author-your-own surface that shows
one canonical per-class frontmatter example: the copy-paste tutorials under
``usage/`` and ``examples/`` plus the single-class reference pages
``reference/rules.mdx``, ``reference/agents.mdx``, ``reference/commands.mdx``,
and ``reference/skills.mdx``. Rule contracts derive from the validator's
required-key set, agent contracts from the shipped ``src/apothem/agents/``
union, and command/skill contracts from ``command.schema.json`` /
``skill.schema.json`` (both ``additionalProperties: false``). The *multi-class* schema
pages — ``reference/frontmatter-schema.mdx``, ``reference/artifact-schema.mdx``,
and ``developer-guide.mdx`` — document every artifact class at once (CLAUDE.md
root config, commands, skills, optional ``version`` / ``updated`` / ``scope`` /
``portability`` fields) and are intentionally out of scope; holding their
broader, multi-class examples to the minimal single-class contract would be
wrong. (A page whose filename names no class — ``how-to-guides.mdx`` and the
multi-class schema pages — is skipped by ``_classify_page`` regardless, so the
explicit exclusion list is belt-and-suspenders for the multi-class pages.)

Locale subtrees. The 11 translation subtrees carry byte-identical copies of the
code blocks, so a separate parity test asserts each locale's frontmatter blocks
match EN, not re-validating the contract eleven more times.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Iterator
from typing import NamedTuple

import pytest

from apothem.conformity import frontmatter_grep

# --- Repository anchors (this file lives at tests/unit/docs/) ---------------
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOCS_ROOT = _REPO_ROOT / "site" / "content" / "docs"
_AGENTS_ROOT = _REPO_ROOT / "src" / "apothem" / "agents"
_SCHEMAS_ROOT = _REPO_ROOT / "src" / "apothem" / "schemas"

# The 11 translation subtrees, skipped by the EN scan and parity-checked
# separately. (The set is the locale cohort the docs tree ships.)
_LOCALES = frozenset(
    {"ar", "de", "es", "fr", "hi", "id", "ja", "ko", "pt-br", "ru", "zh-cn"}
)

# The multi-class schema pages document every artifact class at once (CLAUDE.md
# root config, commands, skills, optional version/updated/scope/portability), so
# the minimal single-class copy-paste contract does not apply to them. The
# single-class reference pages (reference/rules.mdx, reference/agents.mdx) show
# one canonical per-class example and ARE in scope. (Multi-class pages also fail
# _classify_page on filename, so this list is belt-and-suspenders.)
_SCHEMA_REFERENCE_DIRS: frozenset[str] = frozenset()
_SCHEMA_REFERENCE_FILES = frozenset(
    {
        "developer-guide.mdx",
        "reference/frontmatter-schema.mdx",
        "reference/artifact-schema.mdx",
    }
)

# Fenced code-block languages that carry a frontmatter example.
_FRONTMATTER_FENCES = frozenset({"yaml", "markdown"})

# Anti-vacuous-pass anchors: the guard MUST keep finding these examples. If a
# glob or filter refactor drops them, the discovery test fails loudly instead
# of passing on an empty set.
_KNOWN_RULE_PAGES = frozenset(
    {
        "usage/writing-rules.mdx",
        "examples/custom-rule.mdx",
        "reference/rules.mdx",
    }
)
_KNOWN_AGENT_PAGES = frozenset({"usage/using-agents.mdx", "reference/agents.mdx"})
_KNOWN_COMMAND_PAGES = frozenset({"reference/commands.mdx"})
_KNOWN_SKILL_PAGES = frozenset({"reference/skills.mdx"})

# The exact drift just repaired, named explicitly for a sharp failure message.
# (These are redundant with the strict "only allowed keys" subset check below;
# they exist so a re-introduced drift names itself in the assertion output.)
_FORBIDDEN_RULE_KEYS = frozenset({"scope", "path-filter", "portability", "implements"})
_FORBIDDEN_AGENT_KEYS = frozenset({"model", "allowed-tools", "allowedTools"})
# Command drift: camelCase keys, a `type` marker, and `effort` (forbidden by
# command.schema.json `additionalProperties: false`).
_FORBIDDEN_COMMAND_KEYS = frozenset(
    {
        "type",
        "argumentHint",
        "allowedTools",
        "agentModel",
        "model",
        "disallowedTools",
        "effort",
    }
)
# Skill drift: a `type` marker, the hyphenated `user-invocable` (the source
# corpus and its docs use the camelCase `userInvocable`; `user-invocable` is the
# spelling the Claude Code emission writes), and keys forbidden by
# skill.schema.json.
_FORBIDDEN_SKILL_KEYS = frozenset(
    {"type", "user-invocable", "detection-signals", "relatedSkills", "portability"}
)


class _Example(NamedTuple):
    """One frontmatter example extracted from a fenced docs code block."""

    page_rel: str  # docs-root-relative POSIX path, e.g. "usage/writing-rules.mdx"
    cls: str  # "rules" | "agents"
    block_index: int  # index of the code block within the page
    keys: tuple[str, ...]  # top-level frontmatter keys, in document order
    body: str  # the raw code-block body (a "---"-delimited frontmatter doc)


# --- Parsing helpers --------------------------------------------------------


def _iter_code_blocks(text: str) -> Iterator[tuple[str | None, list[str]]]:
    """Yield ``(language, body_lines)`` for every fenced code block in *text*.

    A line whose stripped form opens with three backticks toggles a block. The
    info string's first token is the language; the closing fence yields the
    collected body. Robust to info strings carrying a title (``yaml title=...``).
    """
    in_block = False
    lang: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if in_block:
                yield lang, buf
                in_block = False
                lang = None
                buf = []
            else:
                info = line.lstrip()[3:].strip()
                lang = info.split()[0].lower() if info else None
                in_block = True
                buf = []
            continue
        if in_block:
            buf.append(line)


def _frontmatter_blocks(path: pathlib.Path) -> list[tuple[str | None, tuple[str, ...]]]:
    """Return the frontmatter-bearing code blocks of *path* as comparable tuples.

    A block is frontmatter-bearing when its first non-blank body line is the
    ``---`` delimiter. The returned ``(language, body)`` tuples are the unit of
    the EN-vs-locale byte-parity comparison.
    """
    blocks: list[tuple[str | None, tuple[str, ...]]] = []
    for lang, body in _iter_code_blocks(path.read_text(encoding="utf-8")):
        non_blank = [line for line in body if line.strip()]
        if non_blank and non_blank[0].strip() == "---":
            blocks.append((lang, tuple(body)))
    return blocks


def _classify_page(page_rel: str) -> str | None:
    """Classify a page as authoring rules or agents from its subject, or None.

    Page subject — not the example keys, which are exactly what drifts — is the
    reliable signal: a page titled "writing rules" documents rule examples even
    when one has drifted, which is when the guard must still validate it as a rule.
    """
    lowered = page_rel.lower()
    if "agent" in lowered:
        return "agents"
    if "rule" in lowered:
        return "rules"
    if "command" in lowered:
        return "commands"
    if "skill" in lowered:
        return "skills"
    return None


def _in_scope_pages() -> list[tuple[pathlib.Path, str]]:
    """Return ``(path, artifact_class)`` for every in-scope EN authoring page."""
    if not _DOCS_ROOT.is_dir():
        return []
    pages: list[tuple[pathlib.Path, str]] = []
    for path in sorted(_DOCS_ROOT.rglob("*")):
        if path.suffix not in {".md", ".mdx"}:
            continue
        rel = path.relative_to(_DOCS_ROOT)
        if rel.parts[0] in _LOCALES:
            continue
        if rel.parts[0] in _SCHEMA_REFERENCE_DIRS:
            continue
        rel_posix = rel.as_posix()
        if rel_posix in _SCHEMA_REFERENCE_FILES:
            continue
        cls = _classify_page(rel_posix)
        if cls is not None:
            pages.append((path, cls))
    return pages


def _real_agent_keys() -> frozenset[str]:
    """Union of top-level frontmatter keys across the shipped agent definitions.

    Parsed with ``frontmatter_grep``'s own extractor + key parser so the derived
    agent contract tracks the validator's notion of a top-level key exactly.
    """
    keys: set[str] = set()
    if not _AGENTS_ROOT.is_dir():
        return frozenset()
    for path in sorted(_AGENTS_ROOT.glob("*.md")):
        if path.name == "README.md":
            continue
        yaml_block, _ = frontmatter_grep._extract_frontmatter(
            path.read_text(encoding="utf-8")
        )
        if yaml_block is None:
            continue
        keys.update(frontmatter_grep._parse_keys(yaml_block))
    return frozenset(keys)


def _schema_keys(schema_filename: str) -> tuple[frozenset[str], frozenset[str]]:
    """Return ``(required, allowed)`` key sets from a per-class JSON Schema.

    ``command.schema.json`` and ``skill.schema.json`` both set
    ``additionalProperties: false``, so the allowed set is exactly the declared
    ``properties`` — the contract a copy-paste example must not exceed — and the
    required set is the ``required`` array a valid example must cover. Deriving
    both from the schema means the guard tracks the schema as it evolves rather
    than hard-coding key literals.
    """
    data = json.loads((_SCHEMAS_ROOT / schema_filename).read_text(encoding="utf-8"))
    return frozenset(data["required"]), frozenset(data["properties"])


def _schema_one_of(schema_filename: str) -> tuple[frozenset[str], ...]:
    """Return the key groups a schema's top-level ``oneOf`` requires one of.

    ``skill.schema.json`` requires exactly one spelling of the
    user-invocability flag (``userInvocable`` in the source corpus,
    ``user-invocable`` in the Claude Code emission), expressed as
    ``oneOf: [{required: [a]}, {required: [b]}]``; this yields ``{a, b}``.
    """
    data = json.loads((_SCHEMAS_ROOT / schema_filename).read_text(encoding="utf-8"))
    branches = data.get("oneOf", [])
    if not branches:
        return ()
    return (frozenset(key for branch in branches for key in branch["required"]),)


def _collect_examples() -> list[_Example]:
    """Extract every rule/agent frontmatter example from the in-scope EN pages."""
    examples: list[_Example] = []
    for path, cls in _in_scope_pages():
        page_rel = path.relative_to(_DOCS_ROOT).as_posix()
        for index, (lang, body) in enumerate(
            _iter_code_blocks(path.read_text(encoding="utf-8"))
        ):
            if lang not in _FRONTMATTER_FENCES:
                continue
            joined = "\n".join(body)
            yaml_block, _ = frontmatter_grep._extract_frontmatter(joined)
            if yaml_block is None:
                continue
            keys = frontmatter_grep._parse_keys(yaml_block)
            examples.append(_Example(page_rel, cls, index, tuple(keys), joined))
    return examples


# --- Derived contracts and example corpus (built once at collection) --------

# Rules: required keys (from the validator) plus the one allow-listed rule key.
_RULE_ALLOWED = frozenset(frontmatter_grep.REQUIRED_KEYS["rules"]) | {"pathFilter"}

# Agents: required keys (from the validator) plus the union of keys the shipped
# agents actually use — the authoritative agent contract.
_AGENT_REAL_KEYS = _real_agent_keys()
_AGENT_ALLOWED = frozenset(frontmatter_grep.REQUIRED_KEYS["agents"]) | _AGENT_REAL_KEYS

# Commands and skills: required + allowed sets derived directly from the
# per-class JSON Schemas (both `additionalProperties: false`), so the strict
# subset check tracks the schema rather than a hard-coded key list.
_COMMAND_REQUIRED, _COMMAND_ALLOWED = _schema_keys("command.schema.json")
_SKILL_REQUIRED, _SKILL_ALLOWED = _schema_keys("skill.schema.json")
_SKILL_ONE_OF = _schema_one_of("skill.schema.json")

_EXAMPLES = _collect_examples()
_RULE_EXAMPLES = [ex for ex in _EXAMPLES if ex.cls == "rules"]
_AGENT_EXAMPLES = [ex for ex in _EXAMPLES if ex.cls == "agents"]
_COMMAND_EXAMPLES = [ex for ex in _EXAMPLES if ex.cls == "commands"]
_SKILL_EXAMPLES = [ex for ex in _EXAMPLES if ex.cls == "skills"]


def _ids(examples: list[_Example]) -> list[str]:
    return [f"{ex.page_rel}::block{ex.block_index}" for ex in examples]


# --- Tests ------------------------------------------------------------------


def test_pathfilter_is_an_allowed_rule_key() -> None:
    """Anchor the one assumption the rule allowed-set adds beyond the validator.

    The rule allowed-set is ``REQUIRED_KEYS["rules"]`` plus ``pathFilter``; if the
    validator ever drops ``pathFilter`` from its allow-list, this surfaces it so
    the guard's assumption is revisited, not left silently stale.
    """
    assert "pathFilter" in frontmatter_grep.KEY_ALLOW_LIST


def test_guard_discovers_the_known_example_pages() -> None:
    """Fail loudly if the docs scan finds no examples on the expected pages.

    Without this anchor a broken glob or over-broad exclusion would make every
    parametrized contract test collect zero cases and pass vacuously.
    """
    assert _DOCS_ROOT.is_dir(), f"docs root not found at {_DOCS_ROOT}"
    found = {ex.page_rel for ex in _EXAMPLES}
    expected = (
        _KNOWN_RULE_PAGES
        | _KNOWN_AGENT_PAGES
        | _KNOWN_COMMAND_PAGES
        | _KNOWN_SKILL_PAGES
    )
    missing = expected - found
    assert not missing, (
        "frontmatter-example guard discovered no examples on expected page(s): "
        f"{sorted(missing)} - the docs glob or in-scope filter has drifted, which "
        "would let the contract tests pass vacuously"
    )


def test_real_agent_key_union_is_sound() -> None:
    """The agent contract source (shipped agents) must be present and model-free.

    ``model`` absence reflects the agnostic-posture rule (shipped agents preset no
    model); were a shipped agent to introduce it, the docs agent examples would
    lose their model-free basis, and this assertion surfaces that shift.
    """
    assert _AGENT_REAL_KEYS, f"no agent frontmatter keys found under {_AGENTS_ROOT}"
    assert {"name", "description", "tools"} <= _AGENT_REAL_KEYS
    assert "model" not in _AGENT_REAL_KEYS
    assert "allowed-tools" not in _AGENT_REAL_KEYS


@pytest.mark.parametrize("ex", _RULE_EXAMPLES, ids=_ids(_RULE_EXAMPLES))
def test_rule_frontmatter_examples_match_real_contract(ex: _Example) -> None:
    """Every rule example uses only {name, description, alwaysApply, pathFilter}."""
    keyset = set(ex.keys)

    # 1) Canonical required-key + key-shape contract, via the actual validator.
    #    Catches a missing required key (the just-fixed examples dropped `name`
    #    and `alwaysApply`) and any non-kebab, non-allow-listed key.
    result = frontmatter_grep.check(ex.body, pathlib.Path("rules", "_docs_example.md"))
    assert result.passed, (
        f"{ex.page_rel} block {ex.block_index}: frontmatter_grep.check rejected the "
        f"rule example: {[finding.detail for finding in result.findings]}"
    )

    # 2) Strict "only these keys": catches superficially-valid kebab keys that
    #    check() admits but the rule contract does not (scope, path-filter, ...).
    extra = keyset - _RULE_ALLOWED
    assert not extra, (
        f"{ex.page_rel} block {ex.block_index}: rule example carries non-contract "
        f"key(s) {sorted(extra)}; allowed = {sorted(_RULE_ALLOWED)}"
    )

    # 3) Named-drift sentinel for the exact keys this guard was authored against.
    drift = keyset & _FORBIDDEN_RULE_KEYS
    assert not drift, (
        f"{ex.page_rel} block {ex.block_index}: re-introduced invented rule key(s) "
        f"{sorted(drift)} - use {sorted(_RULE_ALLOWED)} (see frontmatter-schema.mdx)"
    )


@pytest.mark.parametrize("ex", _AGENT_EXAMPLES, ids=_ids(_AGENT_EXAMPLES))
def test_agent_frontmatter_examples_match_real_contract(ex: _Example) -> None:
    """Every agent example uses only keys the shipped src/apothem/agents/ use."""
    keyset = set(ex.keys)

    # Required keys present (from the validator's agent required-set).
    missing = set(frontmatter_grep.REQUIRED_KEYS["agents"]) - keyset
    assert not missing, (
        f"{ex.page_rel} block {ex.block_index}: agent example missing required "
        f"key(s) {sorted(missing)}"
    )

    # Strict "only these keys": the contract is the real shipped-agent key union,
    # not frontmatter_grep.check (whose allow-list still admits `model`).
    extra = keyset - _AGENT_ALLOWED
    assert not extra, (
        f"{ex.page_rel} block {ex.block_index}: agent example carries key(s) "
        f"{sorted(extra)} not used by any shipped agent in src/apothem/agents/; "
        f"allowed = {sorted(_AGENT_ALLOWED)}"
    )

    # Named-drift sentinel for the exact keys this guard was authored against.
    drift = keyset & _FORBIDDEN_AGENT_KEYS
    assert not drift, (
        f"{ex.page_rel} block {ex.block_index}: re-introduced non-agent key(s) "
        f"{sorted(drift)} - agents use `tools`, never `model` / `allowed-tools`"
    )


def test_command_and_skill_schema_contracts_are_sound() -> None:
    """The command/skill contract sources (JSON Schemas) must be present and sane.

    Guards the derivation: a missing/renamed schema or a required key absent from
    properties would make the contract tests pass vacuously or raise; this anchors
    the camelCase `userInvocable` and hyphenated `allowed-tools` the examples use.
    """
    assert _COMMAND_REQUIRED, "command.schema.json required set empty"
    assert _COMMAND_ALLOWED, "command.schema.json properties set empty"
    assert _COMMAND_REQUIRED <= _COMMAND_ALLOWED
    assert _SKILL_REQUIRED, "skill.schema.json required set empty"
    assert _SKILL_ALLOWED, "skill.schema.json properties set empty"
    assert _SKILL_REQUIRED <= _SKILL_ALLOWED
    assert "allowed-tools" in _COMMAND_REQUIRED
    assert "portability" in _COMMAND_REQUIRED
    assert "archetype" in _SKILL_REQUIRED
    # The user-invocability flag is required in exactly one spelling.
    assert frozenset({"userInvocable", "user-invocable"}) in _SKILL_ONE_OF


@pytest.mark.parametrize("ex", _COMMAND_EXAMPLES, ids=_ids(_COMMAND_EXAMPLES))
def test_command_frontmatter_examples_match_real_contract(ex: _Example) -> None:
    """Every command example carries exactly the command.schema.json key set."""
    keyset = set(ex.keys)

    # Required keys present (from command.schema.json `required`).
    missing = _COMMAND_REQUIRED - keyset
    assert not missing, (
        f"{ex.page_rel} block {ex.block_index}: command example missing required "
        f"key(s) {sorted(missing)}; required = {sorted(_COMMAND_REQUIRED)}"
    )

    # Strict "only these keys": command.schema.json is additionalProperties:false.
    extra = keyset - _COMMAND_ALLOWED
    assert not extra, (
        f"{ex.page_rel} block {ex.block_index}: command example carries key(s) "
        f"{sorted(extra)} not in command.schema.json; allowed = {sorted(_COMMAND_ALLOWED)}"
    )

    # Named-drift sentinel for the camelCase / `type` / `effort` drift.
    drift = keyset & _FORBIDDEN_COMMAND_KEYS
    assert not drift, (
        f"{ex.page_rel} block {ex.block_index}: re-introduced non-command key(s) "
        f"{sorted(drift)} - use {sorted(_COMMAND_ALLOWED)} (see command.schema.json)"
    )


@pytest.mark.parametrize("ex", _SKILL_EXAMPLES, ids=_ids(_SKILL_EXAMPLES))
def test_skill_frontmatter_examples_match_real_contract(ex: _Example) -> None:
    """Every skill example carries the skill.schema.json key set (camelCase)."""
    keyset = set(ex.keys)

    # Required keys present (from skill.schema.json `required`).
    missing = _SKILL_REQUIRED - keyset
    assert not missing, (
        f"{ex.page_rel} block {ex.block_index}: skill example missing required "
        f"key(s) {sorted(missing)}; required = {sorted(_SKILL_REQUIRED)}"
    )
    for group in _SKILL_ONE_OF:
        assert len(keyset & group) == 1, (
            f"{ex.page_rel} block {ex.block_index}: skill example must carry "
            f"exactly one of {sorted(group)}"
        )

    # Strict "only these keys": skill.schema.json is additionalProperties:false.
    extra = keyset - _SKILL_ALLOWED
    assert not extra, (
        f"{ex.page_rel} block {ex.block_index}: skill example carries key(s) "
        f"{sorted(extra)} not in skill.schema.json; allowed = {sorted(_SKILL_ALLOWED)}"
    )

    # Named-drift sentinel for the `type` / `user-invocable` / `detection-signals` drift.
    drift = keyset & _FORBIDDEN_SKILL_KEYS
    assert not drift, (
        f"{ex.page_rel} block {ex.block_index}: re-introduced non-skill key(s) "
        f"{sorted(drift)} - use {sorted(_SKILL_ALLOWED)} (camelCase `userInvocable`)"
    )


@pytest.mark.parametrize(
    "page_rel",
    sorted({ex.page_rel for ex in _EXAMPLES}),
)
def test_locale_frontmatter_blocks_match_en(page_rel: str) -> None:
    """Each locale's frontmatter code blocks are byte-identical to EN.

    The fix that corrects an EN example must propagate to all 11 locales; a
    locale left stale would re-expose the drift to that audience. Code blocks are
    not translated, so byte-equality is the correct contract.
    """
    en_blocks = _frontmatter_blocks(_DOCS_ROOT / page_rel)
    assert en_blocks, f"{page_rel}: no frontmatter code blocks found in EN"
    for locale in sorted(_LOCALES):
        locale_path = _DOCS_ROOT / locale / page_rel
        assert locale_path.exists(), (
            f"{locale}/{page_rel}: locale page is missing - translation parity broken"
        )
        assert _frontmatter_blocks(locale_path) == en_blocks, (
            f"{locale}/{page_rel}: frontmatter code block(s) drift from EN; code "
            "blocks must be byte-identical across all locales"
        )
