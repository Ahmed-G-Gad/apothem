# SPDX-License-Identifier: MIT

"""Behavioral coverage for the cross-file binding-reciprocity corpus walk.

The corpus matcher walks a ``rules/*.md`` tree and reports every ``↔``
half-edge: rule A cites ``rules/B.md`` under ``Cross-bound with ↔`` but rule B
does not cite ``rules/A.md`` back under the same direction. A reciprocal pair
passes; a half-edge is reported with both file paths. Only rule-to-rule ``↔``
edges count — a citation to a non-rule surface or to a name absent from the
corpus is out of scope, and a ``Drives →`` / ``Driven by ←`` directional
citation is not a ``↔`` edge. The matcher is blocking: the corpus ships with
every ↔ edge closed, so a finding fails the check and the CLI exits non-zero.

Fixtures are synthetic ``rules/*.md`` files in a tmp dir (the matcher resolves
the corpus at ``<root>/src/apothem/rules`` or ``<root>/rules``); the tests write
the ``rules/`` layout so no repo state is touched.
"""

from __future__ import annotations

from pathlib import Path

from apothem.conformity._grep_base import EXIT_FAIL, EXIT_PASS
from apothem.conformity.binding_reciprocity_corpus_grep import _main, check


def _rule(*bindings_lines: str) -> str:
    """Render a minimal rule body carrying a Bindings section."""
    return "\n".join(
        [
            "# Rule: Sample",
            "",
            "Body prose.",
            "",
            "## Bindings (§0.j five-direction)",
            "",
            *bindings_lines,
            "",
        ]
    )


def _write_corpus(root: Path, rules: dict[str, str]) -> None:
    """Materialize a synthetic ``<root>/rules/<name>.md`` corpus."""
    rules_dir = root / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    for name, body in rules.items():
        (rules_dir / f"{name}.md").write_text(body, encoding="utf-8")


def test_reciprocal_cross_bound_pair_passes(tmp_path: Path) -> None:
    # A ↔ B and B ↔ A — a closed symmetric edge, no half-edge.
    _write_corpus(
        tmp_path,
        {
            "alpha": _rule("- **Cross-bound with ↔** `rules/beta.md` (sibling)."),
            "beta": _rule("- **Cross-bound with ↔** `rules/alpha.md` (sibling)."),
        },
    )
    result = check(tmp_path)
    assert result.passed, [f.detail for f in result.findings]
    assert result.findings == []
    assert result.advisory is False


def test_half_edge_is_reported(tmp_path: Path) -> None:
    # A ↔ B but B does not cite A back anywhere — a ↔ half-edge.
    _write_corpus(
        tmp_path,
        {
            "alpha": _rule("- **Cross-bound with ↔** `rules/beta.md` (sibling)."),
            "beta": _rule("- **Drives →** some downstream artifact."),
        },
    )
    result = check(tmp_path)
    assert not result.passed
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.source == "rules/alpha.md"
    assert finding.target == "rules/beta.md"


def test_citation_back_in_other_direction_is_still_a_half_edge(tmp_path: Path) -> None:
    # B cites A, but under `Drives →`, not `Cross-bound with ↔`. The ↔ relation
    # is self-reciprocal (§2): the reciprocal must be in the ↔ direction too.
    _write_corpus(
        tmp_path,
        {
            "alpha": _rule("- **Cross-bound with ↔** `rules/beta.md` (sibling)."),
            "beta": _rule("- **Drives →** `rules/alpha.md` downstream."),
        },
    )
    result = check(tmp_path)
    assert not result.passed
    assert any(
        f.source == "rules/alpha.md" and f.target == "rules/beta.md"
        for f in result.findings
    )


def test_non_rule_cross_bound_citation_is_ignored(tmp_path: Path) -> None:
    # A ↔ a non-rule surface (a conformity matcher, a skill) — those carry no
    # Bindings section and are not subject to reciprocity, so no half-edge.
    _write_corpus(
        tmp_path,
        {
            "alpha": _rule(
                "- **Cross-bound with ↔** `conformity/orphan_output_grep.py` "
                "(mechanical arm); `skills/workflow/SKILL.md` (reachable capability)."
            ),
        },
    )
    result = check(tmp_path)
    assert result.passed, [f.detail for f in result.findings]


def test_cross_bound_citation_to_absent_rule_is_ignored(tmp_path: Path) -> None:
    # A ↔ `rules/ghost.md` where ghost is not in the corpus (a stale/renamed
    # target the naming/link matchers own) — out of scope here, no half-edge.
    _write_corpus(
        tmp_path,
        {
            "alpha": _rule("- **Cross-bound with ↔** `rules/ghost.md` (missing)."),
        },
    )
    result = check(tmp_path)
    assert result.passed, [f.detail for f in result.findings]


def test_self_citation_is_not_a_half_edge(tmp_path: Path) -> None:
    # A rule citing itself under ↔ is not a binding (the matrix diagonal is —);
    # it must not be flagged as a half-edge against itself.
    _write_corpus(
        tmp_path,
        {
            "alpha": _rule("- **Cross-bound with ↔** `rules/alpha.md` (self)."),
        },
    )
    result = check(tmp_path)
    assert result.passed, [f.detail for f in result.findings]


def test_fenced_example_bindings_block_is_not_the_real_section(tmp_path: Path) -> None:
    # A rule quoting an EXAMPLE `## Bindings` block inside a fence must have its
    # REAL Bindings section read, not the fenced example. Here the fenced example
    # cites `rules/ghost.md`, but the real section reciprocates `rules/beta.md`.
    alpha_body = "\n".join(
        [
            "# Rule: Alpha",
            "",
            "Illustrating the shape:",
            "",
            "```markdown",
            "## Bindings (§0.j five-direction)",
            "",
            "- **Cross-bound with ↔** `rules/ghost.md` (example only)",
            "```",
            "",
            "## Bindings (§0.j five-direction)",
            "",
            "- **Cross-bound with ↔** `rules/beta.md` (real sibling).",
            "",
        ]
    )
    _write_corpus(
        tmp_path,
        {
            "alpha": alpha_body,
            "beta": _rule("- **Cross-bound with ↔** `rules/alpha.md` (real sibling)."),
        },
    )
    result = check(tmp_path)
    # The real ↔ edge alpha<->beta is closed; the fenced ghost citation is not
    # read, so it produces no half-edge.
    assert result.passed, [f.detail for f in result.findings]


def test_missing_corpus_passes(tmp_path: Path) -> None:
    # No rules tree under root — nothing to walk, a clean pass.
    result = check(tmp_path)
    assert result.passed
    assert result.advisory is False


def test_src_layout_corpus_is_resolved(tmp_path: Path) -> None:
    # The repo-checkout layout (src/apothem/rules) is resolved as well as the
    # installed layout (rules).
    rules_dir = tmp_path / "src" / "apothem" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "alpha.md").write_text(
        _rule("- **Cross-bound with ↔** `rules/beta.md` (sibling)."),
        encoding="utf-8",
    )
    (rules_dir / "beta.md").write_text(
        _rule("- **Drives →** downstream."),
        encoding="utf-8",
    )
    result = check(tmp_path)
    assert not result.passed
    assert result.findings[0].source == "rules/alpha.md"


def test_cli_exit_codes_follow_the_verdict(tmp_path: Path) -> None:
    # Blocking posture: the CLI mirrors the standard grep exit contract —
    # EXIT_PASS on a clean walk, EXIT_FAIL on any half-edge finding.
    _write_corpus(
        tmp_path,
        {
            "alpha": _rule("- **Cross-bound with ↔** `rules/beta.md` (sibling)."),
            "beta": _rule("- **Drives →** downstream."),
        },
    )
    exit_code = _main(["binding_reciprocity_corpus_grep", str(tmp_path)])
    assert exit_code == EXIT_FAIL

    (tmp_path / "rules" / "beta.md").write_text(
        _rule("- **Cross-bound with ↔** `rules/alpha.md` (sibling)."),
        encoding="utf-8",
    )
    exit_code = _main(["binding_reciprocity_corpus_grep", str(tmp_path)])
    assert exit_code == EXIT_PASS
