# SPDX-License-Identifier: MIT

"""Uninstall, verify, fidelity, and the pure build_plan entrypoint."""

from __future__ import annotations

import contextlib
import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from apothem.harnesses._shared import install_driver
from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    defuse_sentinels,
    extract_managed_block,
)
from apothem.lib.install_ledger import LedgerRecord
from apothem.lib.propagation import (
    InstallEntry,
    resolve_target,
)

from .install_driver_blocks import (
    install_may_be_open,
    stray_begin_at,
    stray_begin_files,
    stray_begin_warnings,
)
from .install_driver_datahome import (
    _data_home_for,
    _remove_data_home,
)
from .install_driver_evidence import _entry_proves_install, _unfinished_here
from .install_driver_expected import expected_lookup
from .install_driver_hookfile import (
    HOOK_FILE_MODE,
    registration_present,
    release_native_hooks,
)
from .install_driver_merge import render_content_tokens
from .install_driver_outcome import (
    last_uninstall_finished,
    left_behind,
    left_unfinished,
    record_uninstall,
)
from .install_driver_pathsafety import (
    _allowed_write_root,
    _root_for,
    _stale_path_proves_install,
)
from .install_driver_planvalidation import (
    _generated_targets_for_entry,
    _projected_profile_body,
    user_level_entry_ok,
)
from .install_driver_removal import (
    _remove_unlisted_anchors,
    _surgical_remove_from_target,
)
from .install_driver_retention import BOLT_ON_ANCHORS, apply_retention
from .install_driver_shared import UserLevelGate, locked_for_harness
from .install_driver_treeops import remove_created_dirs
from .install_driver_types import (
    MaterializationError,
    MaterializationResult,
    MaterializationRun,
    _path_text,
    backup_session,
    resolve_source,
    skills_sharing_command_target,
)
from .install_driver_written import kept_file_warnings, remove_written


def _native_config_parses(target: Path) -> bool:
    """Return True unless *target* is a structurally invalid JSON/YAML file.

    Only ``.json``/``.yaml``/``.yml`` targets are parsed; other suffixes (e.g.
    Markdown anchors) pass trivially. A ``.json`` target may be JSONC or JSON5
    (OpenCode and OpenClaw read those dialects, and install leaves such a file
    in place when it has nothing to change). A present-but-corrupt config reads
    as not-installed.
    """
    from apothem.lib import lenient_json

    suffix = target.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        return True
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    try:
        if suffix == ".json":
            lenient_json.loads(text)
        else:
            yaml.safe_load(text)
    except (lenient_json.LenientJSONError, yaml.YAMLError):
        return False
    return True


def verify_install(
    harness_name: str,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    native_config: Path | None = None,
) -> bool:
    """Return True when every manifest install-list target is present + valid.

    Walks the harness's manifest install list and resolves each target against
    the supplied root: ``write_text``/``sentinel_merge`` targets must be
    non-empty regular files, ``replace_tree`` targets must be directories, and
    every other mode (tree merges, cohort conversions) must exist. JSON/YAML
    config targets are additionally parsed — a corrupt config reads as
    not-installed. *native_config* (the adapter's dynamically-rendered config
    file, which is not a manifest entry) is checked the same way when supplied.
    A user-level entry passes when its folders are in place whichever harness
    wrote them (see :func:`user_level_entry_ok`). A file this install keeps a
    managed block in fails it while it holds a BEGIN marker that starts no
    whole block (see :func:`stray_begin_files`): install and update keep such a
    marker, so only the operator can clear it. Returns False on the first
    unsatisfied target.
    """
    rules = install_driver.load_rules(harness_name)
    if native_config is not None:
        if not native_config.is_file() or native_config.stat().st_size <= 0:
            return False
        if not _native_config_parses(native_config):
            return False
    for entry in rules.install:
        target = resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        if entry.mode in {"write_text", "sentinel_merge", HOOK_FILE_MODE}:
            if not target.is_file() or target.stat().st_size <= 0:
                return False
            if not _native_config_parses(target) or not registration_present(
                entry, target, project_scope=harness_root is None
            ):
                return False
        elif entry.user_level:
            if not user_level_entry_ok(
                entry,
                rules,
                root=_root_for(harness_root, project_root),
                harness_root=harness_root,
                project_root=project_root,
                harness_name=harness_name,
            ):
                return False
        elif entry.mode == "replace_tree":
            if not target.is_dir():
                return False
        elif not target.exists():
            return False
    return not stray_begin_files(
        harness_name, harness_root=harness_root, project_root=project_root
    )


def detect_install(
    harness_name: str,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
) -> bool:
    """Return True when this root carries positive evidence of an Apothem install.

    This is the ``is_installed()`` predicate. It answers "did Apothem install
    here?" — deliberately NOT "does this harness exist on the machine?". Keying
    presence off an adapter's ``output_path`` conflates the two whenever that
    anchor is a vendor-owned file the harness creates for itself (Claude Code
    writes ``~/.claude/settings.json`` for its own plugin registrations), which
    reported ``installed=True`` on a machine Apothem had never touched. Paired
    with a correctly-failing :func:`verify_install`, that rendered as ``drift``
    — inviting a remediating uninstall against the operator's own settings file.

    The walk is existential: ANY unambiguous Apothem artifact under this root
    means installed. That keeps a genuinely half-removed tree reporting
    ``installed=True`` + ``verified=False`` — real drift — while an untouched
    harness home reports absent. See
    :func:`install_driver_evidence._entry_proves_install` for what counts as
    evidence and why the weaker signals are excluded. A stale-sweep path of an
    earlier layout that still holds Apothem's files counts too (see
    :func:`_stale_path_proves_install`). So does an uninstall that did not
    finish (see :func:`install_driver_evidence._unfinished_here`), so a second
    run can complete it.
    """
    rules = install_driver.load_rules(harness_name)
    root = _root_for(harness_root, project_root)
    install_open = functools.partial(install_may_be_open, harness_name, root)
    if any(
        _entry_proves_install(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            install_open=install_open,
        )
        for entry in rules.install
    ) or any(_stale_path_proves_install(root / legacy) for legacy in rules.stale_sweep):
        return True
    return _unfinished_here(harness_name, root)


@dataclass(frozen=True)
class FidelityResult:
    """The drift verdict for one profile-derived anchor on disk."""

    target: str
    status: Literal["faithful", "drifted", "missing"]


def _profile_anchor_targets(
    harness_name: str,
    *,
    harness_root: Path | None,
    project_root: Path | None,
) -> list[Path]:
    """Return the on-disk anchors that carry the projected profile managed block.

    Every ``sentinel_merge`` manifest target (anchor adapters fold the projected
    body into these), plus the bolt-on profile anchors written outside the
    manifest (claude_code's ``CLAUDE.md``, the single-file-config adapters'
    ``apothem/rules/00-apothem-profile.md``): the ones the current install
    record lists, so a deleted bolt-on reads as missing. Without a record (an
    install from before the ledger) a bolt-on counts only when present, and
    ``CLAUDE.md`` only for claude_code: at a project root it is the project's
    own file, which no other tool's install writes. An adapter that projects
    no profile content (GLM) has no anchors.
    """
    rules = install_driver.load_rules(harness_name)
    root = _root_for(harness_root, project_root)
    targets: list[Path] = [
        resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        for entry in rules.install
        if entry.mode == "sentinel_merge"
    ]
    try:
        record = install_ledger.current_install_record(harness_name, root=root)
    except install_ledger.LedgerError:
        record = None
    if record is not None:
        listed = {_path_text(target) for target in targets}
        targets.extend(
            Path(recorded.path)
            for recorded in record.targets
            if recorded.mode == "sentinel_merge" and recorded.path not in listed
        )
        return targets
    for relative in BOLT_ON_ANCHORS:
        if relative == "CLAUDE.md" and harness_name != "claude_code":
            continue
        bolt_on = root / relative
        if bolt_on.is_file():
            targets.append(bolt_on)
    return targets


def check_fidelity(
    harness_name: str,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    profile: dict[str, Any],
) -> list[FidelityResult]:
    """Classify each profile-derived anchor as faithful / drifted / missing.

    Re-projects *profile* through the same seam ``run_install`` uses and requires
    the freshly-projected managed-block body to appear verbatim inside the
    on-disk anchor's managed block. An anchor whose projected content was edited
    on disk (so the freshly-projected body is no longer a substring) reads as
    ``drifted``; an absent anchor or one with no managed block reads as
    ``missing``; an exact carry reads as ``faithful``. Line endings do not count:
    an anchor saved with CRLF endings carries the body as well as one with LF
    endings, and an update leaves such a file as it is. This is what makes the CLI
    ``verify`` answer "is the profile faithfully installed?" rather than merely
    "does a file exist".
    """
    # The anchor carries the body with any embedded sentinel neutralized (see
    # ``defuse_sentinels``), so compare against that same form.
    expected = defuse_sentinels(
        (_projected_profile_body(harness_name, profile) or "").strip()
    )
    results: list[FidelityResult] = []
    for target in _profile_anchor_targets(
        harness_name, harness_root=harness_root, project_root=project_root
    ):
        if not target.is_file():
            results.append(FidelityResult(_path_text(target), "missing"))
            continue
        try:
            text = target.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            results.append(FidelityResult(_path_text(target), "missing"))
            continue
        block = extract_managed_block(text)
        if block is None:
            results.append(FidelityResult(_path_text(target), "missing"))
        elif (
            expected
            and expected in block.replace("\r\n", "\n")
            and not stray_begin_at(target)
        ):
            results.append(FidelityResult(_path_text(target), "faithful"))
        else:
            results.append(FidelityResult(_path_text(target), "drifted"))
    return results


def fidelity_is_faithful(results: list[FidelityResult]) -> bool:
    """Reduce per-anchor fidelity results to a single bool (all faithful).

    No results means the adapter projects no profile content (GLM, a model
    backend): there is nothing to drift, so it is faithful. A projecting
    adapter whose anchor is gone yields a ``missing`` result, not an empty
    list (see :func:`_profile_anchor_targets`).
    """
    return all(result.status == "faithful" for result in results)


def _rendered_template_text(
    entry: InstallEntry,
    *,
    harness_root: Path | None,
    project_root: Path | None,
) -> str:
    """Return the rendered Apothem template text for a ``write_text`` entry.

    Reads the manifest source and substitutes ``${HARNESS_ROOT}`` /
    ``${PROJECT_ROOT}`` tokens exactly as the install pass did, so the
    surgical uninstall can recognize Apothem's on-disk contribution
    byte-for-byte. Returns ``""`` when the source is absent (nothing for the
    structured stripper to match — operator content is then preserved).
    """
    src = resolve_source(entry.source)
    if not src.is_file():
        return ""
    try:
        raw = src.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - defensive
        return ""
    return render_content_tokens(
        raw, harness_root=harness_root, project_root=project_root
    )


@locked_for_harness
@backup_session()
def run_uninstall(
    harness_name: str,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    prior_results: tuple[MaterializationResult, ...] = (),
) -> list[MaterializationResult]:
    """Remove Apothem-generated targets declared for *harness_name*.

    ``write_text`` / ``sentinel_merge`` operator-owned targets are cleaned
    surgically: only Apothem's contribution is stripped (the sentinel-delimited
    managed block for Markdown anchors; Apothem's keys / hook handlers for JSON
    and YAML configs), operator prose and operator-authored keys survive, and a
    file reduced to Apothem-only content is deleted rather than left as a stub.
    The pre-mutation file is copied into the Apothem backup root first — no
    whole-file ``.bak`` sibling is left in the operator's directory. Directory
    discovery surfaces are cleaned child-by-child, and each child only as far
    as the install record shows Apothem wrote it (see :func:`remove_written`):
    a file goes only while it still has the recorded SHA-256, so a file the
    operator added or changed stays, with a warning. Removed entries are
    backed up first.

    The pass is ledger-driven: the latest install record for this harness+root
    is the source of truth for which single-file targets were actually written,
    so manifest drift after install cannot strand or over-remove them (a target
    added to the manifest later is untouched; a recorded target removed from the
    manifest is still cleaned). Tree/discovery surfaces are enumerated from the
    manifest and source, and a child the record does not list stays. A record
    written before file digests existed, or no record at all (a pre-ledger
    install), proves nothing about the files, so those children stay too (see
    :func:`remove_written` for when that leaves the uninstall unfinished). The
    shared data home (memory / contexts / learning) is backed up and removed
    only when last-referenced, at the home the latest install recorded (see
    :func:`_data_home_for`). The directories the installs since the last
    uninstall created are removed once empty.

    Returns every removal's :class:`MaterializationResult` so callers can
    surface path-escape, backup, and write failures instead of reporting an
    unconditional success. A ``kind="uninstall"`` record is appended only when
    no removal errored and nothing Apothem wrote stays behind a link;
    otherwise, and when the pass raises, an ``uninstall-incomplete`` record is
    appended instead (see :func:`record_uninstall`): the install stays
    active, so verify, status, rollback and a second uninstall keep operating
    against it. Either record references every backup the uninstall took,
    including those in *prior_results*: removals the caller made just before
    this pass, such as a native config stripped of Apothem's keys. An error in
    *prior_results* also makes the uninstall unfinished.
    """
    root = _root_for(harness_root, project_root)
    root_floor = _allowed_write_root(harness_root, project_root)
    active: list[LedgerRecord] = []
    record: LedgerRecord | None = None
    results: list[MaterializationResult] = []
    # The records this pass builds, each kept before it is appended, so the
    # fallback below never contradicts one that landed (see record_uninstall).
    own: list[LedgerRecord] = []
    record_pass = functools.partial(record_uninstall, harness_name, root, own=own)
    try:
        active = install_ledger.active_install_records(harness_name, root=root)
        record = active[-1] if active else None
        _remove_installed(
            harness_name,
            record,
            active,
            results,
            harness_root=harness_root,
            project_root=project_root,
            already=frozenset(result.path for result in prior_results),
        )
        # The warnings are built before the record, so a failure here leaves
        # the uninstall recorded as unfinished, as the CLI then reports it.
        kept = left_behind(results, active, floor=root_floor, prior=prior_results)
        finished = not left_unfinished([*prior_results, *results])
        kept += record_pass(record, [*prior_results, *results], finished=finished)
        if finished:
            # Housekeeping after the final record: any failure here leaves
            # older backup sets for the next pass or ``backups prune``, and the
            # finished uninstall stands, as its record says.
            with contextlib.suppress(Exception):
                apply_retention(harness_name)
    except BaseException as exc:
        results += record_pass(record, [*prior_results, *results], finished=False)
        if not isinstance(exc, Exception):
            raise
        # Hand the caller what this pass removed before it stopped, so the CLI
        # can report the uninstall as partial instead of a bare failure, with
        # each file it rewrote that still holds a BEGIN marker alone named.
        done = [*prior_results, *results]
        kept_now = [*kept_file_warnings(results), *stray_begin_warnings(done)]
        run = MaterializationRun(harness_name, False, (*results, *kept_now))
        raise MaterializationError(f"uninstall stopped: {exc}", run) from exc
    return [*results, *kept]


def _remove_installed(
    harness_name: str,
    record: LedgerRecord | None,
    active: list[LedgerRecord],
    results: list[MaterializationResult],
    *,
    harness_root: Path | None,
    project_root: Path | None,
    already: frozenset[str] = frozenset(),
) -> None:
    """Remove what *record* shows this install wrote, appending to *results*.

    *results* is the caller's list, so the removals made before an exception
    are still recorded. A path in *already* (one the caller removed or
    reported before this pass) is not handled again.
    """
    rules = install_driver.load_rules(harness_name)
    root = _root_for(harness_root, project_root)
    allowed_root = _allowed_write_root(harness_root, project_root)
    # Ledger-driven: the latest install record is the source of truth for what
    # this harness+root actually wrote. ``recorded_paths`` is None when no record
    # exists (legacy / pre-ledger install) — fall back to removing every manifest
    # target. With a record, a single-file manifest target is removed only if it
    # was recorded, so an entry added to the manifest after install is not touched.
    recorded_targets = (
        {target.path: target for target in record.targets} if record is not None else {}
    )
    recorded_paths: set[str] | None = (
        set(recorded_targets) if record is not None else None
    )
    handled: set[str] = set(already)
    remove = functools.partial(
        remove_written,
        recorded=recorded_targets if record is not None else None,
        installs_ended=record is None and last_uninstall_finished(harness_name, root),
        install_root=root,
        harness_name=harness_name,
        expected=expected_lookup(
            rules,
            harness_name=harness_name,
            harness_root=harness_root,
            project_root=project_root,
            strict=record is None,
        ),
    )
    gate = UserLevelGate.build(
        rules,
        harness_name=harness_name,
        root=root,
        harness_root=harness_root,
        project_root=project_root,
    )
    if record is not None:
        blocked = gate.ledger_blocked(target.path for target in record.targets)
        if blocked is not None:
            results.append(blocked)
            return

    for entry in rules.install:
        if entry.user_level:
            # Record-driven and shared: a target another install still lists is
            # kept; the rest is removed within the home (see UserLevelGate).
            gate.release(entry, record, remove, results=results)
            continue
        if entry.mode in {"write_text", "sentinel_merge", HOOK_FILE_MODE}:
            target = resolve_target(
                entry.target,
                harness_root=harness_root,
                project_root=project_root,
            )
            if recorded_paths is not None and _path_text(target) not in recorded_paths:
                continue
            if entry.mode == HOOK_FILE_MODE:
                removed = release_native_hooks(
                    entry,
                    harness_root=harness_root,
                    project_root=project_root,
                    harness_name=harness_name,
                )
                if removed is not None:
                    results.append(removed)
                handled.add(_path_text(target))
                continue
            template_text = _rendered_template_text(
                entry, harness_root=harness_root, project_root=project_root
            )
            removal = _surgical_remove_from_target(
                target,
                template_text,
                mode=entry.mode,
                install_root=root,
                harness_name=harness_name,
                allowed_root=allowed_root,
                recorded=recorded_targets.get(_path_text(target)),
                earlier_digests=entry.earlier_digests,
                project_scope=harness_root is None,
            )
            if removal is not None:
                results.append(removal)
            handled.add(_path_text(target))
            continue
        # Tree/discovery surfaces are reversed child-by-child against the apothem
        # source enumeration so operator-authored siblings survive — a path list
        # cannot express that, so these stay manifest+source-driven. A name the
        # install filters out of this folder (statuslines/__init__.py) was never
        # Apothem's to write, so a file of that name is the user's and stays.
        filtered = set(
            rules.per_directory_filters.get(Path(entry.source.rstrip("/")).name, [])
        )
        if entry.mode == "command_skills":
            # A command that shares its name with a skill is left out of the
            # install (the skill is the sole writer), so it is not this entry's.
            filtered |= skills_sharing_command_target(entry, rules)
        for target in _generated_targets_for_entry(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            exclude=rules.exclude,
        ):
            if target.name in filtered:
                continue
            removal = remove(target, allowed_root=allowed_root)
            if removal is not None:
                results.append(removal)
            handled.add(_path_text(target))

    results.extend(
        _remove_unlisted_anchors(
            record,
            handled,
            root=root,
            harness_name=harness_name,
            allowed_root=allowed_root,
        )
    )

    # Back up and remove the shared data home (memory / contexts / learning) only
    # when this is the last harness referencing it; plans/ is always retained.
    # The home is the one the latest install recorded, so the stores are reversed
    # where they were written.
    data_home_removal = _remove_data_home(
        harness_name,
        root=root,
        home=_data_home_for(record, root=root),
        allowed_root=allowed_root,
    )
    if data_home_removal is not None:
        results.append(data_home_removal)

    # Remove the directories the installs since the last uninstall created,
    # now that their contents are gone — only the empty ones, deepest first, so
    # a directory still holding operator content or another harness's data
    # stays.
    created = {Path(path) for install in active for path in install.created_dirs}
    results.extend(remove_created_dirs(created, allowed_root=allowed_root))
    results.extend(gate.tidy(created))


def build_plan(
    harness_name: str,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
) -> list[dict[str, str]]:
    """Return *harness_name*'s propagation plan without writing anything.

    Each entry carries ``source`` (resolved on-disk path), ``target``
    (resolved against the supplied root), and ``mode``. When the relevant
    root is ``None`` the corresponding placeholder stays literal in the
    target string so the operator sees the unresolved template form instead
    of a misleading absolute path.
    """
    rules = install_driver.load_rules(harness_name)
    return [
        {
            "source": str(resolve_source(entry.source)),
            "target": str(
                resolve_target(
                    entry.target,
                    harness_root=harness_root,
                    project_root=project_root,
                )
            ),
            "mode": entry.mode,
        }
        for entry in rules.install
    ]
