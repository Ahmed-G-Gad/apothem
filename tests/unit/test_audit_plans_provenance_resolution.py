# SPDX-License-Identifier: MIT

"""Characterization coverage for the provenance resolution core.

``_resolve_suite`` decides, once per suite, where every file in that suite is
headed and how much the tool trusts the answer. It is a nine-rung ladder — the
recursive-self suite, the ecosystem-prefix hint, an exact known-project match,
a substring one, an unratified hint, an eco-density majority, a URL match, an
unmatched URL, an absolute-path match, and finally the unmappable floor — and
each rung returns a different destination/confidence pair.

Before these tests the whole ladder was dark: not one rung executed under the
suite. That matters more here than in most modules, because the rungs are
*ordered* — the behavior worth pinning is not what each rung returns on its
own but which rung wins when several could fire. Each test below therefore
sets up a case where a lower rung would also match, and asserts the higher one
takes it.

These are characterization tests: they pin current behavior, not a
specification. Where the current answer is arguably the wrong one, the
docstring says so rather than quietly blessing it.
"""

from __future__ import annotations

from pathlib import Path

from apothem.audit.build_plans_provenance import (
    Signals,
    SuiteVerdict,
    _aggregate_suite,
    _filter_plan_records,
    _is_text_readable,
    _resolve_suite,
    _scan_signals,
    _suite_name_hint,
)
from apothem.audit.plans_provenance_vocabulary import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_RECURSIVE_SELF,
    CONFIDENCE_UNMAPPABLE,
    ECOSYSTEM_DESTINATION_TEXT,
    ECOSYSTEM_SELF_MARKER,
    RECURSIVE_SELF_SUITE,
)

KNOWN = [
    {"name": "dc-kit-mini", "ref": "https://example.invalid/owner/dc-kit-mini"},
    {"name": "dc-kit", "ref": "https://example.invalid/owner/dc-kit"},
]


def resolve(
    suite: str = "some-suite",
    urls: list[str] | None = None,
    paths: list[str] | None = None,
    density: float = 0.0,
    known: list[dict[str, str]] | None = None,
) -> SuiteVerdict:
    """Call ``_resolve_suite`` with everything but the case under test held flat.

    The ladder takes six positional arguments and every test varies one or two
    of them; naming the defaults once keeps each test's setup down to the
    signal it is actually exercising.
    """
    return _resolve_suite(
        suite,
        3,
        urls or [],
        paths or [],
        density,
        KNOWN if known is None else known,
    )


# --- signal scanning --------------------------------------------------------


def test_scan_signals_reads_the_body_not_the_frontmatter() -> None:
    """Frontmatter is stripped before the body patterns run.

    A repository URL declared in frontmatter is metadata about the plan, not
    evidence of what the plan describes, so it must not become a signal.
    """
    content = (
        "---\nproject: https://github.com/owner/declared\n---\n"
        "see https://github.com/owner/referenced for the code\n"
    )

    signals = _scan_signals(content)

    assert signals.repo_urls == ["https://github.com/owner/referenced"]


def test_scan_signals_deduplicates_and_sorts_each_signal_class() -> None:
    """Repeating a URL does not make its suite look more confident."""
    body = "https://github.com/o/b and https://github.com/o/a and again o/b\n"

    signals = _scan_signals("https://github.com/o/b " + body)

    assert signals.repo_urls == [
        "https://github.com/o/a",
        "https://github.com/o/b",
    ]


def test_scan_signals_caps_file_references_at_fifty() -> None:
    """A file-reference flood is truncated rather than carried whole.

    The cap keeps one sprawling index file from dominating the JSON output;
    the references are evidence of a project, and fifty is enough to judge.
    """
    body = " ".join(f"src/module{i}.py" for i in range(120))

    assert len(_scan_signals(body).file_refs) == 50


def test_scan_signals_counts_ecosystem_hits_without_deduplicating() -> None:
    """Eco hits are a density measure, so repeats are the point."""
    single = _scan_signals("see rules/\n").eco_path_hits
    doubled = _scan_signals("see rules/ and rules/\n").eco_path_hits

    assert doubled == single * 2


# --- suite-name hints -------------------------------------------------------


def test_suite_name_hint_maps_a_known_prefix_to_its_project() -> None:
    """The prefix table resolves a suite name to its destination marker."""
    assert _suite_name_hint("dc-kit-mini-hardening") == "dc-kit-mini"


def test_suite_name_hint_maps_ecosystem_prefixes_to_the_self_marker() -> None:
    """Both ecosystem prefixes collapse onto one marker."""
    assert _suite_name_hint("claude-conformance") == ECOSYSTEM_SELF_MARKER
    assert _suite_name_hint("agent-home-hardening") == ECOSYSTEM_SELF_MARKER


def test_suite_name_hint_returns_none_for_an_unrecognized_name() -> None:
    """An unprefixed suite name yields no hint, so body signals decide."""
    assert _suite_name_hint("some-other-suite") is None


# --- aggregation ------------------------------------------------------------


def test_aggregate_suite_unions_urls_and_paths_across_files() -> None:
    """Signals from every file in the suite merge into one sorted set."""
    urls, paths, _ = _aggregate_suite(
        "s",
        [
            Signals(repo_urls=["https://b.invalid"], abs_paths=["/home/x"]),
            Signals(repo_urls=["https://a.invalid"], abs_paths=["/home/x"]),
        ],
    )

    assert urls == ["https://a.invalid", "https://b.invalid"]
    assert paths == ["/home/x"]


def test_aggregate_suite_caps_each_files_eco_contribution_at_ten() -> None:
    """One eco-dense file cannot carry a suite over the density threshold.

    The per-file cap is what makes density a measure of how *many* files are
    ecosystem-flavoured rather than how loud the loudest one is.
    """
    _, _, capped = _aggregate_suite("s", [Signals(eco_path_hits=500)])
    _, _, exact = _aggregate_suite("s", [Signals(eco_path_hits=10)])

    assert capped == exact == 1.0


def test_aggregate_suite_of_no_files_is_zero_density_not_a_crash() -> None:
    """An empty suite divides by the guarded denominator, not by zero."""
    assert _aggregate_suite("s", []) == ([], [], 0.0)


# --- resolution ladder, in precedence order ---------------------------------


def test_recursive_self_suite_outranks_every_other_signal() -> None:
    """The suite running the migration stays put no matter what it contains.

    Handed a URL that matches a known project — which would otherwise resolve
    high-confidence to that project — the recursive-self rung still wins.
    Moving this suite would amputate the migration's own working tree.
    """
    verdict = resolve(
        suite=RECURSIVE_SELF_SUITE,
        urls=["https://example.invalid/owner/dc-kit"],
        density=1.0,
    )

    assert verdict.destination == ECOSYSTEM_DESTINATION_TEXT
    assert verdict.confidence == CONFIDENCE_RECURSIVE_SELF


def test_ecosystem_prefix_resolves_high_even_with_zero_eco_density() -> None:
    """The suite-name prefix is authoritative; density only corroborates.

    Note the rationale still reports the density as corroboration even when
    it is 0.00 and corroborates nothing — pinned as current, not endorsed.
    """
    verdict = resolve(suite="claude-conformance", density=0.0)

    assert verdict.destination == ECOSYSTEM_DESTINATION_TEXT
    assert verdict.confidence == CONFIDENCE_HIGH
    assert "0.00 corroborates" in " ".join(verdict.rationale)


def test_an_exact_known_project_match_beats_a_substring_one() -> None:
    """``dc-kit-mini`` must not collapse onto ``dc-kit`` by containment.

    Both registry entries match the hint by substring; only the exact-name
    rung distinguishes them, and it is the reason that rung exists.
    """
    verdict = resolve(suite="dc-kit-mini-hardening")

    assert verdict.destination == "dc-kit-mini"
    assert verdict.confidence == CONFIDENCE_HIGH
    assert "(exact match)" in " ".join(verdict.rationale)


def test_a_substring_match_resolves_high_when_no_exact_entry_exists() -> None:
    """Without the exact entry, the shorter project name does swallow the hint.

    This is the collapse the rung above prevents, shown happening: the hint is
    ``dc-kit-mini`` and the only registered project is ``dc-kit``, whose name
    is contained in the hint, so it matches. Note the direction — containment
    runs project-name-inside-hint, so a *shorter* registered name captures a
    longer hint and never the reverse.
    """
    verdict = resolve(
        suite="dc-kit-mini-hardening",
        known=[{"name": "dc-kit", "ref": ""}],
    )

    assert verdict.destination == "dc-kit"
    assert verdict.confidence == CONFIDENCE_HIGH
    assert "(substring match)" in " ".join(verdict.rationale)


def test_an_unratified_hint_resolves_medium_to_the_hint_itself() -> None:
    """A hint with no registry entry still routes, at reduced confidence.

    The destination is the hint text rather than a ratified project name,
    which is precisely what the medium tier is signalling to the operator.
    """
    verdict = resolve(suite="dc-kit-mini-hardening", known=[])

    assert verdict.destination == "dc-kit-mini"
    assert verdict.confidence == CONFIDENCE_MEDIUM


def test_eco_density_majority_decides_when_no_hint_fires() -> None:
    """At or above 0.50 the body signals alone route to stay-in-place."""
    verdict = resolve(density=0.5)

    assert verdict.destination == ECOSYSTEM_DESTINATION_TEXT
    assert verdict.confidence == CONFIDENCE_MEDIUM


def test_eco_density_just_below_the_threshold_does_not_decide() -> None:
    """The 0.50 boundary is inclusive below and exclusive above it."""
    assert resolve(density=0.49).confidence == CONFIDENCE_UNMAPPABLE


def test_a_url_matching_a_known_project_resolves_high() -> None:
    """A body URL naming a registered project is a high-confidence route."""
    verdict = resolve(urls=["https://example.invalid/owner/dc-kit"])

    assert verdict.destination == "dc-kit"
    assert verdict.confidence == CONFIDENCE_HIGH


def test_an_unmatched_url_becomes_the_destination_at_medium() -> None:
    """An unrecognized URL is surfaced verbatim rather than discarded.

    The operator gets something actionable — the URL itself — instead of an
    unmappable verdict that throws away the one signal the scan did find.
    """
    verdict = resolve(urls=["https://example.invalid/owner/unknown-thing"])

    assert verdict.destination == "https://example.invalid/owner/unknown-thing"
    assert verdict.confidence == CONFIDENCE_MEDIUM


def test_an_absolute_path_match_resolves_medium_below_urls() -> None:
    """A path mention is weaker evidence than a URL, and ranks below it."""
    verdict = resolve(paths=["/home/dev/dc-kit/notes.md"])

    assert verdict.destination == "dc-kit"
    assert verdict.confidence == CONFIDENCE_MEDIUM


def test_no_signal_at_all_falls_to_the_unmappable_floor() -> None:
    """The floor is an explicit verdict, not a crash or a silent default."""
    verdict = resolve()

    assert verdict.destination == "<unmappable>"
    assert verdict.confidence == CONFIDENCE_UNMAPPABLE


def test_every_verdict_carries_the_aggregates_it_was_given() -> None:
    """The inputs travel with the verdict so the record can show its work."""
    verdict = resolve(urls=["https://example.invalid/x"], paths=["/home/y"])

    assert verdict.aggregate_repo_urls == ["https://example.invalid/x"]
    assert verdict.aggregate_abs_paths == ["/home/y"]
    assert verdict.file_count == 3


# --- record filtering -------------------------------------------------------


def test_filter_plan_records_keeps_every_plan_artifact_class() -> None:
    """Non-narrative plan artifacts are kept: a suite migrates as a unit."""
    records = [
        {"path": "a.md", "class": "plan-artifact"},
        {"path": "b.json", "class": "plan-artifact"},
        {"path": "c.py", "class": "source"},
    ]

    assert [r["path"] for r in _filter_plan_records(records)] == ["a.md", "b.json"]


def test_is_text_readable_admits_the_plan_extensions_case_insensitively() -> None:
    """The suffix check is lowercased, so ``.MD`` reads as markdown."""
    assert _is_text_readable("notes.md")
    assert _is_text_readable("config.YAML")
    assert not _is_text_readable("capture.log")
    assert not _is_text_readable(str(Path("dir") / "archive.zip"))
