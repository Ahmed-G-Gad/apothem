# SPDX-License-Identifier: MIT

"""The Claude Code emission folds Apothem's extra keys under ``metadata``."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared.install_driver_converters import (
    _native_skill_emission,
    claude_code_skill_text,
)
from apothem.lib.claude_skill_frontmatter import (
    METADATA_KEYS,
    fold_apothem_metadata,
)
from apothem.lib.frontmatter import split_frontmatter

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_COMMANDS = sorted(p for p in (_PKG / "commands").glob("*.md") if p.name != "README.md")
_SKILLS = sorted((_PKG / "skills").glob("*/SKILL.md"))


def _doc(frontmatter: str, body: str = "\n# Title\n\nBody.\n") -> str:
    return f"---\n{frontmatter}---\n{body}"


def _load(text: str) -> dict[str, object]:
    parts = split_frontmatter(text)
    assert parts is not None
    block = parts[0]
    loaded = yaml.safe_load(block[4 : block.rindex("---")])
    assert isinstance(loaded, dict)
    return loaded


def test_fold_moves_keys_in_fixed_order_before_the_closing_fence() -> None:
    text = _doc(
        'name: "x"\nportability: "universal"\nupdated: "2026-10-02"\n'
        'version: "0.1.0"\ndescription: "d"\narchetype: "workflow-template"\n'
    )
    assert fold_apothem_metadata(text) == _doc(
        'name: "x"\ndescription: "d"\nmetadata:\n  version: "0.1.0"\n'
        '  updated: "2026-10-02"\n  archetype: "workflow-template"\n'
        '  portability: "universal"\n'
    )


def test_fold_quotes_every_value_as_a_string() -> None:
    text = _doc("version: 1.0\nupdated: 2026-10-02\nportability: 'uni''versal'\n")
    folded = fold_apothem_metadata(text)
    metadata = _load(folded)["metadata"]
    assert metadata == {
        "version": "1.0",
        "updated": "2026-10-02",
        "portability": "uni'versal",
    }


def test_fold_is_idempotent() -> None:
    text = _doc('name: "x"\nversion: "1"\narchetype: "a"\n')
    once = fold_apothem_metadata(text)
    assert fold_apothem_metadata(once) == once


def test_fold_touches_only_unindented_keys() -> None:
    text = _doc('name: "x"\nnested:\n  version: "9"\nversion: "1"\n')
    folded = fold_apothem_metadata(text)
    assert _load(folded)["nested"] == {"version": "9"}
    assert _load(folded)["metadata"] == {"version": "1"}


def test_fold_leaves_the_body_untouched() -> None:
    body = "\nversion: not frontmatter\n---\n\n## H\n"
    folded = fold_apothem_metadata(_doc('version: "1"\n', body))
    assert folded.endswith(body)


def test_fold_returns_text_without_frontmatter_or_foldable_keys() -> None:
    assert fold_apothem_metadata("# Just a body\n") == "# Just a body\n"
    plain = _doc('name: "x"\ndescription: "d"\n')
    assert fold_apothem_metadata(plain) == plain


def test_fold_leaves_block_scalar_and_empty_values_in_place() -> None:
    text = _doc('version: "1"\nupdated: >\n  folded\narchetype:\n')
    folded = fold_apothem_metadata(text)
    assert "updated: >\n  folded\n" in folded
    assert "archetype:\n" in folded
    assert _load(folded)["metadata"] == {"version": "1"}


def test_fold_rejects_an_existing_metadata_key() -> None:
    text = _doc('version: "1"\nmetadata:\n  a: "b"\n')
    with pytest.raises(ValueError, match="metadata"):
        fold_apothem_metadata(text)


def test_existing_metadata_without_fold_keys_is_not_an_error() -> None:
    text = _doc('metadata:\n  a: "b"\n')
    assert fold_apothem_metadata(text) == text


def test_user_invocable_rename_composes_with_the_fold() -> None:
    text = _doc('name: "x"\nversion: "1"\nuserInvocable: false\n')
    emitted = claude_code_skill_text(text)
    fields = _load(emitted)
    assert fields["user-invocable"] is False
    assert "userInvocable" not in fields
    assert fields["metadata"] == {"version": "1"}


def test_other_harnesses_keep_the_source_keys() -> None:
    text = _doc('name: "x"\nversion: "1"\nuserInvocable: false\n')
    for harness in ("opencode", "codex", "cursor"):
        assert _native_skill_emission(harness, text)[0] == text


def _unfold(emitted: str) -> dict[str, object]:
    fields = _load(emitted)
    metadata = fields.pop("metadata", {})
    assert isinstance(metadata, dict)
    if "user-invocable" in fields:
        fields["userInvocable"] = fields.pop("user-invocable")
    fields.update(metadata)
    return fields


@pytest.mark.parametrize(
    "path", [*_COMMANDS, *_SKILLS], ids=lambda p: p.parent.name + "/" + p.name
)
def test_corpus_fold_keeps_every_key_and_value(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    emitted = claude_code_skill_text(source)
    fields = _load(emitted)
    for key in METADATA_KEYS:
        assert key not in fields
    metadata = fields["metadata"]
    assert isinstance(metadata, dict)
    assert all(isinstance(v, str) for v in metadata.values())
    assert list(metadata) == [k for k in METADATA_KEYS if k in metadata]
    assert _unfold(emitted) == _load(source)
    assert emitted.endswith(split_frontmatter(source)[1])  # type: ignore[index]
