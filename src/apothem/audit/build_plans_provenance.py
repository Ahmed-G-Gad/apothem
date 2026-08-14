# SPDX-License-Identifier: MIT

"""Per-suite, per-file provenance for every plan-suite under the legacy ``.plans/`` tree.

Why this tool exists. The plans-discipline restoration moves plan suites
into the host projects they actually describe, leaving the user-config
root free of plan-product. Each plan-suite has a respective destination
project; this scanner reads the inventory's plan-artifact records,
walks every plan file, captures provenance signals (frontmatter,
repository URLs, absolute paths, file references, framework
signatures), aggregates them at the suite level, and resolves a
suite-level destination + confidence that every file in the suite
inherits. The output is consumed by the migration-confirmation pass
that follows.

How destinations resolve. A suite's destination is decided once at the
suite level using two complementary signals: the suite name's prefix
(``claude-*`` and ``agent-home-*`` describe the user-config ecosystem
itself; ``dc-kit-mini-*`` describes the dc-kit-mini project; ``dc-kit-
ieee`` describes the dc-kit IEEE-deliverable work hosted in the dc-kit
repository), and aggregate body signals across the suite's files
(repository URLs, absolute paths, ecosystem-class path mentions). The
suite-name heuristic is authoritative when it fires; body signals
break ties for suites whose name carries no recognized prefix. A
known-projects file may augment the heuristic: when present, the
operator's project list extends the matching surface; when absent,
the body-derived signals stand alone.

The recursive case. A plan suite can describe the very ecosystem it
lives in; moving that suite would amputate the migration tool's own
working directory. Records belonging to that suite carry
``confidence: recursive-self`` and a destination of "stay in place;
gitignore the .plans directory at the cleanup phase". The
migration-confirmation pass auto-confirms recursive-self records.

The ecosystem-archive case. Three sibling suites (``agent-home-
hardening``, ``claude-conformance``, ``claude-validity-elevation``)
also describe the user-config ecosystem but predate this suite. They
share the recursive-self semantics (same destination = stay in place
under gitignore) and inherit ``confidence: high`` — the suite name
plus the body content's eco-self signal density resolve the
destination unambiguously without operator confirmation, but the
literal recursive-self label is reserved for the suite running the
migration.

Inputs. ``--inventory`` (default ``.audit/inventory.json``); ``--root``
(default ``.``); ``--known-projects`` (default
``src/apothem/audit/known-projects.txt``; absent file is tolerated and the
auto-derivation pass populates it from the body signals it observes).

Outputs. ``.audit/plans-provenance.json`` (machine-readable) and
``.audit/plans-provenance.md`` (human-readable mirror with aggregate
stats, per-suite tables, recursive-case annotation, orphan-candidate
list).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Filename derivation lives in ``plan_filename``: the slug rule, the H1
# reader, and the title precedence between them. Public names, because
# ``_record_for`` calls them.
# ---------------------------------------------------------------------------
from apothem.audit.plan_filename import (
    h1_of,
    proposed_filename,
)

# ---------------------------------------------------------------------------
# Frontmatter parsing lives in ``plan_frontmatter``: the grammar plus the
# two readers over it. Public names, because other stages import them.
# ---------------------------------------------------------------------------
from apothem.audit.plan_frontmatter import (
    parse_frontmatter,
    strip_frontmatter,
)

# ---------------------------------------------------------------------------
# The confidence ladder, destination text, plan extensions, suite-name
# hints, and ecosystem-self marker live in
# ``plans_provenance_vocabulary`` — the terms downstream consumers read.
# The detection regexes stay below: private machinery, not contract.
# ---------------------------------------------------------------------------
from apothem.audit.plans_provenance_vocabulary import (
    ALL_CONFIDENCES,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_RECURSIVE_SELF,
    CONFIDENCE_UNMAPPABLE,
    ECOSYSTEM_DESTINATION_TEXT,
    ECOSYSTEM_SELF_MARKER,
    PLAN_EXTENSIONS,
    RECURSIVE_SELF_SUITE,
    SUITE_NAME_HINTS,
)

# Repository-URL patterns. GitHub and GitLab cover the migration
# corpus; additional hosts can be added without breaking downstream
# consumers because the JSON output is a list, not a tagged union.
_REPO_URL_RE: Final[re.Pattern[str]] = re.compile(
    r"https?://(?:github|gitlab)\.com/[\w./-]+",
    re.IGNORECASE,
)

# Absolute-path heuristics. POSIX home-shaped paths plus the canonical
# Windows ``C:\Users\`` prefix.
_ABS_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:/Users/|/home/|C:\\Users\\)[\w./\\-]+",
)

# Ecosystem-class path mentions. References to ecosystem-class folders
# inside a harness config root (e.g., ``~/.claude/``) are the strongest
# body-level eco-self signal.
_ECO_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:~/\.claude/|/\.claude/|\bCLAUDE\.md\b|\b(?:rules|commands"
    r"|agents|skills|hooks|output-styles|statusline|mcp)/)"
)

# Framework signature heuristics.
_FRAMEWORK_SIGNATURES: Final[tuple[str, ...]] = (
    "pyproject.toml",
    "setup.cfg",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "pom.xml",
    "build.gradle",
)
_FRAMEWORK_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:" + "|".join(re.escape(s) for s in _FRAMEWORK_SIGNATURES) + r")\b"
)

# File-reference heuristics. A path-shaped token with at least one
# slash and a recognized source-file extension.
_FILE_REF_RE: Final[re.Pattern[str]] = re.compile(
    r"\b[\w./-]+\.(?:py|js|ts|tsx|rs|go|java|rb|sh|md|yml|yaml|json|toml|ini)\b"
)


@dataclass
class Signals:
    """Per-file body-scan signal set."""

    repo_urls: list[str] = field(default_factory=list)
    abs_paths: list[str] = field(default_factory=list)
    file_refs: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    eco_path_hits: int = 0


@dataclass
class SuiteVerdict:
    """The suite-level destination + confidence + rationale fragments
    every file in the suite inherits.

    The verdict is computed once per suite from the suite-name
    heuristic plus the aggregated body signals; the per-file records
    surface the verdict alongside their individual signal sets.
    """

    suite: str
    file_count: int
    destination: str
    confidence: str
    rationale: list[str]
    aggregate_repo_urls: list[str]
    aggregate_abs_paths: list[str]
    eco_signal_density: float


@dataclass
class ProvenanceRecord:
    """Provenance record for a single plan file.

    The shape is the source of truth for the JSON envelope: every field
    here surfaces in the output document with an identical key.
    """

    path: str
    suite: str
    mtime: str
    sha256: str
    line_count: int
    frontmatter_project: str | None
    signals: Signals
    inferred_destination: str
    confidence: str
    proposed_destination_filename: str
    notes: list[str] = field(default_factory=list)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _scan_signals(content: str) -> Signals:
    body = strip_frontmatter(content)
    return Signals(
        repo_urls=sorted(set(_REPO_URL_RE.findall(body))),
        abs_paths=sorted(set(_ABS_PATH_RE.findall(body))),
        file_refs=sorted(set(_FILE_REF_RE.findall(body)))[:50],
        frameworks=sorted(set(_FRAMEWORK_RE.findall(body))),
        eco_path_hits=len(_ECO_PATH_RE.findall(body)),
    )


def _suite_of(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    if len(parts) >= 2 and parts[0] == ".plans":
        return parts[1]
    return ""


def _suite_name_hint(suite: str) -> str | None:
    """Apply the suite-name prefix table; returns the destination
    marker the prefix maps to, or None when no prefix matches."""
    for prefix, target in SUITE_NAME_HINTS:
        if suite == prefix or suite.startswith(prefix):
            return target
    return None


def _load_known_projects(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    out: list[dict[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            out.append({"name": key.strip(), "ref": value.strip()})
        else:
            name = re.sub(r"\.git$", "", line.rstrip("/").split("/")[-1])
            out.append({"name": name, "ref": line})
    return out


def _matches_project(value: str, project: dict[str, str]) -> bool:
    name = project["name"].lower()
    ref = project["ref"].lower()
    val = value.lower()
    if name and name in val:
        return True
    return bool(ref and ref in val)


def _aggregate_suite(
    suite: str,
    file_signals: list[Signals],
) -> tuple[list[str], list[str], float]:
    """Aggregate per-file signals to the suite level.

    Returns ``(repo_urls, abs_paths, eco_density)``. Eco density is
    ``hits / files``: at >= 0.5 the suite is dominantly an
    ecosystem-self artifact; the destination resolution reads it as
    a tie-breaker against ambiguous suite names.
    """
    urls: set[str] = set()
    paths: set[str] = set()
    eco_total = 0
    for sig in file_signals:
        urls.update(sig.repo_urls)
        paths.update(sig.abs_paths)
        eco_total += min(sig.eco_path_hits, 10)
    density = eco_total / max(len(file_signals) * 10, 1)
    return sorted(urls), sorted(paths), density


def _resolve_suite(
    suite: str,
    file_count: int,
    aggregate_urls: list[str],
    aggregate_paths: list[str],
    eco_density: float,
    known_projects: list[dict[str, str]],
) -> SuiteVerdict:
    """Compute the suite-level destination + confidence.

    A ladder of nine rungs, tried in order, and the order carries the
    design: the earlier a rung sits, the stronger the evidence it reads.
    The recursive-self suite comes first because moving it would amputate
    the migration's own working tree, and no later signal may override
    that. Suite-name prefixes come next, because a name is an authoring
    decision while body signals are inference. Body signals decide only
    when no name hint fired, and among them a repository URL outranks an
    absolute path — a URL names a project, a path merely mentions one.
    The floor is an explicit ``<unmappable>`` verdict rather than a guess,
    so an undecidable suite reaches the operator as a question.

    Each rung decides just two things — where the suite goes and how much
    that answer is trusted — and appends its reasoning to the shared
    rationale, which travels with the verdict so the record shows its
    work.
    """
    rationale: list[str] = []

    def verdict(destination: str, confidence: str) -> SuiteVerdict:
        """Build a verdict from the two fields a rung actually decides.

        Everything else is invariant for this call: the suite identity, the
        aggregates it was handed, and the rationale list the rungs append to.
        Closing over them keeps each rung down to its decision, and removes
        the way a rung could drift from its siblings by restating one of the
        shared fields differently.
        """
        return SuiteVerdict(
            suite=suite,
            file_count=file_count,
            destination=destination,
            confidence=confidence,
            rationale=rationale,
            aggregate_repo_urls=aggregate_urls,
            aggregate_abs_paths=aggregate_paths,
            eco_signal_density=eco_density,
        )

    if suite == RECURSIVE_SELF_SUITE:
        rationale.append(
            "this suite hardens the very ecosystem it lives in;"
            " moving it would amputate the migration's working tree"
        )
        return verdict(ECOSYSTEM_DESTINATION_TEXT, CONFIDENCE_RECURSIVE_SELF)

    hint = _suite_name_hint(suite)
    if hint == ECOSYSTEM_SELF_MARKER:
        rationale.append(
            f"suite name '{suite}' carries an ecosystem-prefix"
            " (claude- / agent-home-); the suite describes the"
            " user-config root itself and shares the recursive-self"
            " destination semantics"
        )
        rationale.append(
            f"body eco-signal density {eco_density:.2f} corroborates"
            " the suite-name hint"
        )
        return verdict(ECOSYSTEM_DESTINATION_TEXT, CONFIDENCE_HIGH)

    if hint is not None:
        # Resolve the named project against the known-projects list.
        # Exact-name match wins over substring containment so a hint
        # of ``dc-kit-mini`` does not collapse onto a known-project
        # entry named ``dc-kit`` via substring overlap.
        exact = next(
            (p for p in known_projects if p["name"].lower() == hint.lower()),
            None,
        )
        substring = next(
            (
                p
                for p in known_projects
                if p["name"].lower() != hint.lower() and _matches_project(hint, p)
            ),
            None,
        )
        match = exact or substring
        if match is not None:
            kind = "exact" if exact else "substring"
            rationale.append(
                f"suite name '{suite}' maps to known project"
                f" '{match['name']}' via the suite-name prefix table"
                f" ({kind} match)"
            )
            return verdict(match["name"], CONFIDENCE_HIGH)
        rationale.append(
            f"suite name '{suite}' maps to project '{hint}' via the"
            " suite-name prefix table; no known-projects entry yet"
            " carries the matching name, so confidence sits at"
            " medium pending known-projects ratification"
        )
        return verdict(hint, CONFIDENCE_MEDIUM)

    # No suite-name hint fired. Fall through to body signals.
    if eco_density >= 0.5:
        rationale.append(
            f"body eco-signal density {eco_density:.2f} above the"
            " 0.50 threshold; routes to the user-config ecosystem"
            " stay-in-place destination"
        )
        return verdict(ECOSYSTEM_DESTINATION_TEXT, CONFIDENCE_MEDIUM)

    for url in aggregate_urls:
        for proj in known_projects:
            if _matches_project(url, proj):
                rationale.append(
                    f"aggregate repository URL '{url}' matches known"
                    f" project '{proj['name']}'"
                )
                return verdict(proj["name"], CONFIDENCE_HIGH)
    if aggregate_urls:
        rationale.append(
            f"aggregate repository URL '{aggregate_urls[0]}'"
            " recognizable but unmatched against known-projects"
        )
        return verdict(aggregate_urls[0], CONFIDENCE_MEDIUM)

    for ap in aggregate_paths:
        for proj in known_projects:
            if _matches_project(ap, proj):
                rationale.append(
                    f"aggregate absolute path '{ap}' contains known"
                    f" project basename '{proj['name']}'"
                )
                return verdict(proj["name"], CONFIDENCE_MEDIUM)

    rationale.append(
        "no suite-name hint, no eco-density majority, no body URL or"
        " absolute-path match against known-projects; suite is"
        " unmappable pending operator disposition"
    )
    return verdict("<unmappable>", CONFIDENCE_UNMAPPABLE)


def _derive_known_projects(
    body_urls: set[str],
    body_paths: set[str],
) -> list[dict[str, str]]:
    """Auto-derive a known-projects entry list from observed signals.

    The auto-derivation populates a ``src/apothem/audit/known-projects.txt``
    template only when the operator has not supplied one. Two signal
    classes contribute: repository URLs (the project name is the
    second URL segment, with ``.git`` suffixes stripped) and absolute
    paths whose immediate parent is a recognized projects root (the
    project name is the segment immediately following the root).

    The auto-derivation deliberately discards nested paths under a
    project root: a body reference to ``/Users/<name>/Projects/dc-kit-
    mini/docs/index.md`` contributes one entry for ``dc-kit-mini`` and
    suppresses every deeper segment, because nested files are not
    themselves projects and would confuse the suite-name match step.
    """
    projects: list[dict[str, str]] = []
    seen_names: set[str] = set()

    # Recognized project-root prefixes. A path qualifies as a project
    # candidate only when its segment immediately follows one of these
    # roots; nested segments are suppressed.
    # Path-prefix patterns derived from the running operator's home
    # directory at call time; no hardcoded username, so the same
    # scanner works for any operator on any host. The fallbacks cover
    # the macOS / Linux / Windows shapes Python's ``Path.home()``
    # produces; both POSIX and Windows separators are emitted so a
    # cross-platform body reference matches whichever form the source
    # used.
    home = Path.home()
    home_posix = home.as_posix()
    home_windows = str(home).replace("/", "\\")
    project_roots: tuple[tuple[str, str], ...] = (
        (f"{home_posix}/Projects/", "/"),
        (f"{home_windows}\\Projects\\", "\\"),
    )

    for url in sorted(body_urls):
        m = re.match(
            r"https?://(?:github|gitlab)\.com/([\w-]+)/([\w.-]+)",
            url,
            re.IGNORECASE,
        )
        if not m:
            continue
        repo_name = re.sub(r"\.git$", "", m.group(2))
        if repo_name.lower() in seen_names:
            continue
        seen_names.add(repo_name.lower())
        projects.append(
            {"name": repo_name, "ref": url.split("/blob/")[0]},
        )

    for ap in sorted(body_paths):
        for root, sep in project_roots:
            idx = ap.find(root)
            if idx < 0:
                continue
            tail = ap[idx + len(root) :]
            terminal = tail.split(sep, 1)[0]
            if not terminal or terminal.startswith("."):
                continue
            if terminal.lower() in seen_names:
                continue
            seen_names.add(terminal.lower())
            full_path = ap[: idx + len(root)] + terminal
            projects.append({"name": terminal, "ref": full_path})
            break

    return projects


def _record_for(
    rel: str,
    inventory_record: dict[str, Any],
    root: Path,
    suite_verdict: SuiteVerdict,
) -> ProvenanceRecord:
    path = root / rel
    suite = _suite_of(rel)
    content = _read_text(path)
    fm = parse_frontmatter(content)
    signals = _scan_signals(content)
    h1 = h1_of(content)
    mtime = inventory_record.get("mtime", "")
    if not mtime and path.exists():
        mtime = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    sha = inventory_record.get("sha256")
    if not sha and path.exists():
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
    line_count = inventory_record.get("line-count")
    if line_count is None:
        line_count = len(content.splitlines())
    fm_project = fm.get("project")
    if (
        suite == RECURSIVE_SELF_SUITE
        or suite_verdict.destination == ECOSYSTEM_DESTINATION_TEXT
    ):
        proposed = "n/a (stay-in-place)"
    else:
        proposed = proposed_filename(path, mtime, fm, h1)
    return ProvenanceRecord(
        path=rel,
        suite=suite,
        mtime=mtime,
        sha256=sha or "",
        line_count=int(line_count or 0),
        frontmatter_project=fm_project,
        signals=signals,
        inferred_destination=suite_verdict.destination,
        confidence=suite_verdict.confidence,
        proposed_destination_filename=proposed,
        notes=list(suite_verdict.rationale),
    )


def _emit_json(
    records: list[ProvenanceRecord],
    suite_verdicts: dict[str, SuiteVerdict],
    inventory_sha: str,
    out: Path,
) -> None:
    by_suite_block: dict[str, dict[str, Any]] = {}
    for suite, verdict in sorted(suite_verdicts.items()):
        by_suite_block[suite] = {
            "file-count": verdict.file_count,
            "destination": verdict.destination,
            "confidence": verdict.confidence,
            "rationale": verdict.rationale,
            "aggregate-repo-urls": verdict.aggregate_repo_urls,
            "aggregate-abs-paths": verdict.aggregate_abs_paths,
            "eco-signal-density": round(verdict.eco_signal_density, 3),
        }
    by_confidence_total: dict[str, int] = dict.fromkeys(ALL_CONFIDENCES, 0)
    for r in records:
        by_confidence_total[r.confidence] += 1
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "scanner": "build_plans_provenance",
        "inventory-source-sha256": inventory_sha,
        "suite-count": len(suite_verdicts),
        "file-count": len(records),
        "by-confidence": by_confidence_total,
        "suites": by_suite_block,
        "files": [_record_to_dict(r) for r in records],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _record_to_dict(r: ProvenanceRecord) -> dict[str, Any]:
    return {
        "path": r.path,
        "suite": r.suite,
        "mtime": r.mtime,
        "sha256": r.sha256,
        "line-count": r.line_count,
        "frontmatter-project": r.frontmatter_project,
        "signals": asdict(r.signals),
        "inferred-destination": r.inferred_destination,
        "confidence": r.confidence,
        "proposed-destination-filename": r.proposed_destination_filename,
        "notes": r.notes,
    }


def _emit_markdown(
    records: list[ProvenanceRecord],
    suite_verdicts: dict[str, SuiteVerdict],
    out: Path,
) -> None:
    total = len(records)
    by_confidence: dict[str, int] = dict.fromkeys(ALL_CONFIDENCES, 0)
    for r in records:
        by_confidence[r.confidence] += 1
    orphans = [r for r in records if r.confidence == CONFIDENCE_UNMAPPABLE]

    lines: list[str] = []
    lines.append("# Plans Provenance — Per-Suite, Per-File Map")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append("## Aggregate Stats")
    lines.append("")
    lines.append(f"- **Total suites:** {len(suite_verdicts)}")
    lines.append(f"- **Total plan files:** {total}")
    lines.append("- **By confidence:**")
    for c in ALL_CONFIDENCES:
        lines.append(f"  - `{c}`: {by_confidence[c]}")
    lines.append("")

    lines.append("## Suite-Level Verdicts")
    lines.append("")
    lines.append("| Suite | Files | Confidence | Destination |")
    lines.append("|-------|-------|------------|-------------|")
    for suite, verdict in sorted(suite_verdicts.items()):
        suite_disp = suite.replace("|", "\\|")
        dest_disp = verdict.destination.replace("|", "\\|")
        lines.append(
            f"| `{suite_disp}` | {verdict.file_count} |"
            f" `{verdict.confidence}` | {dest_disp} |"
        )
    lines.append("")

    lines.append("## Per-Suite Tables")
    lines.append("")
    by_suite: dict[str, list[ProvenanceRecord]] = {}
    for r in records:
        by_suite.setdefault(r.suite or "<root>", []).append(r)
    for suite in sorted(by_suite):
        suite_records = sorted(by_suite[suite], key=lambda r: r.path)
        suite_verdict = suite_verdicts.get(suite)
        lines.append(f"### `{suite}`")
        lines.append("")
        if suite_verdict is not None:
            lines.append(
                f"_Confidence: `{suite_verdict.confidence}`. Destination:"
                f" {suite_verdict.destination}._"
            )
            lines.append("")
            lines.append("**Rationale:**")
            lines.append("")
            for fragment in suite_verdict.rationale:
                lines.append(f"- {fragment}")
            lines.append("")
        lines.append("| Path | Proposed filename |")
        lines.append("|------|-------------------|")
        for r in suite_records:
            path_disp = r.path.replace("|", "\\|")
            file_disp = r.proposed_destination_filename.replace("|", "\\|")
            lines.append(f"| `{path_disp}` | `{file_disp}` |")
        lines.append("")

    lines.append("## Recursive-Case Annotation")
    lines.append("")
    recursive = [
        v for v in suite_verdicts.values() if v.confidence == CONFIDENCE_RECURSIVE_SELF
    ]
    if recursive:
        v = recursive[0]
        lines.append(
            f"The suite `{v.suite}` describes the very ecosystem it"
            f" lives in ({v.file_count} files); the migration leaves"
            " it in place and the cleanup phase adds `.plans/` to the"
            " repository's `.gitignore` so the directory carries no"
            " plan-product through publication."
        )
    else:
        lines.append("_No recursive-self records._")
    lines.append("")

    lines.append("## Orphan Candidates")
    lines.append("")
    if orphans:
        lines.append(
            f"{len(orphans)} file(s) with `confidence: unmappable`."
            " The migration-confirmation pass routes these to the"
            " operator for explicit disposition."
        )
        lines.append("")
        for r in sorted(orphans, key=lambda r: r.path):
            lines.append(f"- `{r.path}`")
    else:
        lines.append("_No orphan candidates surfaced._")
    lines.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def _filter_plan_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return every plan-artifact record from the inventory.

    Every plan-artifact participates in the migration, including the
    non-narrative classes (JSON outputs, log captures, scratch
    fixtures): the migration moves a suite as a unit, not as a curated
    text-only subset. Body-scan signals are produced only for the
    text-readable extensions (see :data:`PLAN_EXTENSIONS`); records
    outside that set still inherit their suite's verdict and surface
    in the per-file table with empty signal sets.
    """
    return [r for r in records if r.get("class") == "plan-artifact"]


def _is_text_readable(rel: str) -> bool:
    """Predicate guarding the body-scan pass against binary or
    non-text plan-artifact records."""
    return Path(rel).suffix.lower() in PLAN_EXTENSIONS


def _write_known_projects_template(
    path: Path,
    derived: list[dict[str, str]],
) -> None:
    """Persist the auto-derived known-projects entries to the operator-
    editable file.

    The file is overwritten only when it does not already exist; an
    operator-edited list is never replaced. The header explains the
    auto-derivation so the operator can amend the entries with project
    names that match their own checkout layout.
    """
    if path.exists():
        return
    lines: list[str] = [
        "# src/apothem/audit/known-projects.txt",
        "#",
        "# Auto-derived from plan-suite body content. Each line is either a bare URL,",
        "# a bare absolute path, or a name=reference pair. Lines starting with #",
        "# are comments. Edit freely; re-run the provenance scanner to refresh",
        "# .audit/plans-provenance.{json,md}.",
        "",
    ]
    for proj in derived:
        lines.append(f"{proj['name']}={proj['ref']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Scan every plan-suite file, resolve per-suite destinations, and emit the provenance documents.

    Runs the three passes end to end: scan each plan file's body signals,
    auto-derive known-projects when none is supplied, aggregate and resolve a
    destination + confidence per suite, then build per-file records inheriting
    the suite verdict and write ``plans-provenance.json`` / ``.md``.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(".audit/inventory.json"),
    )
    parser.add_argument("--root", type=Path, default=Path())
    parser.add_argument(
        "--known-projects",
        type=Path,
        default=Path("src/apothem/audit/known-projects.txt"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path(".audit/plans-provenance.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path(".audit/plans-provenance.md"),
    )
    args = parser.parse_args(argv)

    if not args.inventory.exists():
        print(
            f"error: inventory not found at {args.inventory}",
            file=sys.stderr,
        )
        return 1

    raw = args.inventory.read_bytes()
    inventory_sha = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    inventory_records = payload.get("files", [])
    plan_records = _filter_plan_records(inventory_records)

    # First pass: scan every file's signals.
    scanned: dict[str, list[tuple[dict[str, Any], Signals]]] = {}
    aggregate_urls: set[str] = set()
    aggregate_paths: set[str] = set()
    for inv in plan_records:
        rel = inv["path"]
        suite = _suite_of(rel)
        if not suite:
            continue
        if _is_text_readable(rel):
            content = _read_text(args.root / rel)
            signals = _scan_signals(content)
        else:
            signals = Signals()
        scanned.setdefault(suite, []).append((inv, signals))
        aggregate_urls.update(signals.repo_urls)
        aggregate_paths.update(signals.abs_paths)

    # Auto-derive known-projects entries when the operator file is
    # absent; persist the template for operator review.
    initial_known = _load_known_projects(args.known_projects)
    if not initial_known:
        derived = _derive_known_projects(aggregate_urls, aggregate_paths)
        if derived:
            _write_known_projects_template(args.known_projects, derived)
        known_projects = derived
    else:
        known_projects = initial_known

    # Second pass: aggregate per-suite signals and resolve verdicts.
    suite_verdicts: dict[str, SuiteVerdict] = {}
    for suite, entries in scanned.items():
        sigs = [s for _, s in entries]
        urls, paths, density = _aggregate_suite(suite, sigs)
        suite_verdicts[suite] = _resolve_suite(
            suite,
            len(entries),
            urls,
            paths,
            density,
            known_projects,
        )

    # Third pass: build per-file records that inherit the suite verdict.
    records: list[ProvenanceRecord] = []
    for suite, entries in scanned.items():
        verdict = suite_verdicts[suite]
        for inv, _ in entries:
            records.append(
                _record_for(inv["path"], inv, args.root, verdict),
            )

    _emit_json(records, suite_verdicts, inventory_sha, args.output_json)
    _emit_markdown(records, suite_verdicts, args.output_md)

    by_conf: dict[str, int] = dict.fromkeys(ALL_CONFIDENCES, 0)
    for r in records:
        by_conf[r.confidence] += 1
    summary = ", ".join(f"{k}={v}" for k, v in by_conf.items() if v)
    print(
        f"build_plans_provenance: {len(records)} plan file(s) across"
        f" {len(suite_verdicts)} suite(s) [{summary}];"
        f" known-projects entries: {len(known_projects)}"
    )
    for suite, verdict in sorted(suite_verdicts.items()):
        print(
            f"  {suite} ({verdict.file_count} files):"
            f" {verdict.confidence} -> {verdict.destination[:80]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ---------------------------------------------------------------------------
# Public surface. This module is the entry point for the header-coverage
# pipeline; the names below are re-exported from the sibling modules that own
# them (``header_vocabulary`` / ``header_banner`` / ``header_variants`` /
# ``header_detect``). Declaring them here keeps the unused-import rule from
# deleting a re-export whose importers live in other files.
# ---------------------------------------------------------------------------
__all__ = [
    "ProvenanceRecord",
    "Signals",
    "SuiteVerdict",
    "_load_known_projects",
    "_matches_project",
    "_suite_of",
    "main",
]
