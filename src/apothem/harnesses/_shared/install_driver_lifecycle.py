# SPDX-License-Identifier: MIT

"""Uninstall, verify, fidelity, and the pure build_plan entrypoint."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from apothem.harnesses._shared import install_driver
from apothem.lib import install_ledger
from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.harness_materializer import (
    extract_managed_block,
)
from apothem.lib.harness_registry import SUPPORTED_PACKAGE_KEYS
from apothem.lib.install_ledger import LedgerRecord
from apothem.lib.propagation import (
    InstallEntry,
    resolve_target,
)

from .install_driver_backup import _replace_path, backup_existing
from .install_driver_merge import render_content_tokens
from .install_driver_pathsafety import (
    _allowed_write_root,
    _root_for,
    _validate_target_path,
)
from .install_driver_planvalidation import (
    _generated_targets_for_entry,
    _projected_profile_body,
)
from .install_driver_removal import _surgical_remove_from_target
from .install_driver_types import (
    MaterializationResult,
    _handle_rm_error,
    _path_text,
    _result,
    resolve_source,
)


def _native_config_parses(target: Path) -> bool:
    """Return True unless *target* is a structurally invalid JSON/YAML file.

    Only ``.json``/``.yaml``/``.yml`` targets are parsed; other suffixes (e.g.
    Markdown anchors) pass trivially. A present-but-corrupt config reads as
    not-installed.
    """
    suffix = target.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        return True
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        if suffix == ".json":
            json.loads(text)
        else:
            yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError):
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
    Returns False on the first unsatisfied target.
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
        if entry.mode in {"write_text", "sentinel_merge"}:
            if not target.is_file() or target.stat().st_size <= 0:
                return False
            if not _native_config_parses(target):
                return False
        elif entry.mode == "replace_tree":
            if not target.is_dir():
                return False
        elif not target.exists():
            return False
    return True


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
    body into these), plus the two bolt-on profile anchors written outside the
    manifest when present: claude_code's ``CLAUDE.md`` and the single-file-config
    adapters' ``apothem/rules/00-apothem-profile.md``.
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
    for relative in ("CLAUDE.md", "apothem/rules/00-apothem-profile.md"):
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
    ``missing``; an exact carry reads as ``faithful``. This is what makes the CLI
    ``verify`` answer "is the profile faithfully installed?" rather than merely
    "does a file exist".
    """
    expected = _projected_profile_body(harness_name, profile) or ""
    results: list[FidelityResult] = []
    for target in _profile_anchor_targets(
        harness_name, harness_root=harness_root, project_root=project_root
    ):
        if not target.is_file():
            results.append(FidelityResult(_path_text(target), "missing"))
            continue
        try:
            text = target.read_text(encoding="utf-8")
        except OSError:
            results.append(FidelityResult(_path_text(target), "missing"))
            continue
        block = extract_managed_block(text)
        if block is None:
            results.append(FidelityResult(_path_text(target), "missing"))
        elif expected and expected in block:
            results.append(FidelityResult(_path_text(target), "faithful"))
        else:
            results.append(FidelityResult(_path_text(target), "drifted"))
    return results


def fidelity_is_faithful(results: list[FidelityResult]) -> bool:
    """Reduce per-anchor fidelity results to a single bool (all faithful)."""
    return bool(results) and all(result.status == "faithful" for result in results)


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


def _shared_home_root_for(root: Path) -> Path:
    """Return the shared working-directory root anchored at *root*.

    Uninstall carries no profile, so the workspace scope defaults to
    project-local and the directory name to ``.apothem`` — the base is *root*
    and the shared root is ``<root>/.apothem``. This mirrors the resolution the
    install pass uses on the no-profile path, so an install and its later
    uninstall agree on the home's location.
    """
    return resolve_shared_data_home(base=root).root


def _other_harness_shares_home(*, current_harness: str, shared_root: Path) -> bool:
    """Report whether another installed harness still shares *shared_root*.

    The shared data home is collapsed across harnesses, so removing it on the
    first uninstall would destroy data the remaining harnesses depend on. This
    consults the install ledger across every package key (except
    *current_harness*) and returns ``True`` when any other harness's latest
    record at its install root resolves to the SAME ``shared_root`` AND that
    latest record is an ``install`` (not yet uninstalled or rolled back).

    A harness is "still installed at its root" when its most recent ledger
    record of any kind for that root is an ``install``. Because the current
    uninstall's own ``uninstall`` marker is appended only AFTER this guard runs
    (see :func:`run_uninstall`), *current_harness* is excluded explicitly so it
    never counts itself as a co-occupant.

    The check is fail-safe: any error reading the ledger raises out to the
    caller, which treats it as "cannot prove last-harness" and retains the
    shared home rather than risk a destructive removal on an uncertain count.
    """
    for package_key in SUPPORTED_PACKAGE_KEYS:
        if package_key == current_harness:
            continue
        # Find this harness's MOST RECENT record whose install root resolves to
        # the same shared home. Records are append-ordered, so the last match in
        # iteration order is the latest. Its kind tells the live state: an
        # `install` means still installed; an `uninstall`/`rollback` means gone.
        latest_kind: str | None = None
        for record in install_ledger.read_records(package_key):
            if _shared_home_root_for(Path(record.root)) == shared_root:
                latest_kind = record.kind
        if latest_kind == "install":
            return True
    return False


def _remove_data_home(
    harness_name: str, *, root: Path, allowed_root: Path
) -> MaterializationResult | None:
    """Back up and remove the shared data home only when it is last-referenced.

    The data home is the Apothem-owned ``<root>/.apothem/`` subtree shared
    across every harness rooted at *root*, holding the operator's memory
    records, context fragments, and learning signals (see
    :func:`apothem.lib.data_home.resolve_shared_data_home`). Because it is
    SHARED, removing it on the first harness uninstall would destroy data the
    other still-installed harnesses depend on. The removal is therefore
    conditional:

    * If another installed harness still shares this home, the home is RETAINED
      and an informational ``unchanged`` result is returned.
    * If this is the last harness referencing the home, only the data stores
      (``memory/``, ``contexts/``, ``learning/``) are backed up and removed.
      ``plans/`` is NEVER auto-removed — it is operator planning state, not
      Apothem-materialized config — and the ``.apothem`` root itself is left
      in place so any operator ``plans/`` survives. Each removed child is copied
      into the Apothem backup root first, so the data stays recoverable.

    Returns ``None`` when no data store exists (nothing to remove) or the home
    path falls outside the allowed write root.
    """
    home = _shared_home_root_for(root)
    if not home.exists():
        return None
    if (
        _validate_target_path(
            home, allowed_root=allowed_root, operation="remove_data_home"
        )
        is not None
    ):
        return None

    # Last-harness guard: retain the shared home while another harness still
    # references it. An uncertain ledger read raises and is caught here, falling
    # back to RETAIN — the safe default that never risks shared-data loss.
    try:
        retain = _other_harness_shares_home(
            current_harness=harness_name, shared_root=home
        )
    except Exception:  # pragma: no cover - defensive: ledger read is robust
        retain = True
    if retain:
        return _result(
            "unchanged",
            "remove_data_home",
            home,
            "shared data home retained — another harness is still installed",
        )

    spec = resolve_shared_data_home(base=root)
    backups: list[Path] = []
    removed_any = False
    # plans/ is intentionally excluded — operator planning state is never
    # auto-removed by uninstall.
    for child in (spec.memory, spec.contexts, spec.learning):
        if not child.exists():
            continue
        backup = backup_existing(
            child,
            install_root=root,
            harness_name=harness_name,
            allowed_root=allowed_root,
        )
        if backup is not None:
            backups.append(backup)
        shutil.rmtree(child, onerror=_handle_rm_error)
        removed_any = True
    if not removed_any:
        return None
    return _result(
        "updated",
        "remove_data_home",
        home,
        "removed shared data stores (memory, contexts, learning); plans retained",
        backup_path=backups[0] if backups else None,
    )


def run_uninstall(
    harness_name: str,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
) -> list[MaterializationResult]:
    """Remove Apothem-generated targets declared for *harness_name*.

    ``write_text`` / ``sentinel_merge`` operator-owned targets are cleaned
    surgically: only Apothem's contribution is stripped (the sentinel-delimited
    managed block for Markdown anchors; Apothem's keys / hook handlers for JSON
    and YAML configs), operator prose and operator-authored keys survive, and a
    file reduced to Apothem-only content is deleted rather than left as a stub.
    The pre-mutation file is copied into the Apothem backup root first — no
    whole-file ``.bak`` sibling is left in the operator's directory. Directory
    discovery surfaces are cleaned child-by-child so unrelated operator-authored
    commands, skills, agents, and rules remain in place; existing generated
    entries are backed up before removal.

    The pass is ledger-driven: the latest install record for this harness+root
    is the source of truth for which single-file targets were actually written,
    so manifest drift after install cannot strand or over-remove them (a target
    added to the manifest later is untouched; a recorded target removed from the
    manifest is still cleaned). Tree/discovery surfaces stay manifest+source
    driven. The shared data home (memory / contexts / learning) is backed up and
    removed only when last-referenced, and an uninstall marker is appended to the
    ledger. With no ledger
    record (a pre-ledger install), the pass falls back to the full manifest.

    Returns every removal's :class:`MaterializationResult` so callers can
    surface path-escape, backup, and write failures instead of reporting an
    unconditional success. The ``kind="uninstall"`` ledger marker is appended
    only when no removal errored — a failed uninstall leaves the install
    record as the latest ledger entry, matching the on-disk reality that
    targets remain.
    """
    rules = install_driver.load_rules(harness_name)
    root = _root_for(harness_root, project_root)
    allowed_root = _allowed_write_root(harness_root, project_root)

    # Ledger-driven: the latest install record is the source of truth for what
    # this harness+root actually wrote. ``recorded_paths`` is None when no record
    # exists (legacy / pre-ledger install) — fall back to removing every manifest
    # target. With a record, a single-file manifest target is removed only if it
    # was recorded, so an entry added to the manifest after install is not touched.
    record = install_ledger.latest_record(harness_name, root=root)
    recorded_paths: set[str] | None = (
        {target.path for target in record.targets} if record is not None else None
    )
    handled: set[str] = set()
    results: list[MaterializationResult] = []

    for entry in rules.install:
        if entry.mode in {"write_text", "sentinel_merge"}:
            target = resolve_target(
                entry.target,
                harness_root=harness_root,
                project_root=project_root,
            )
            if recorded_paths is not None and _path_text(target) not in recorded_paths:
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
            )
            if removal is not None:
                results.append(removal)
            handled.add(_path_text(target))
            continue
        # Tree/discovery surfaces are reversed child-by-child against the apothem
        # source enumeration so operator-authored siblings survive — a path list
        # cannot express that, so these stay manifest+source-driven.
        for target in _generated_targets_for_entry(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            exclude=rules.exclude,
        ):
            removal = _replace_path(
                target,
                install_root=root,
                harness_name=harness_name,
                allowed_root=allowed_root,
            )
            if removal is not None:
                results.append(removal)
            handled.add(_path_text(target))

    # Recorded sentinel anchors not covered by a current manifest entry: the
    # bolt-on profile anchors (claude-code ``CLAUDE.md``, the single-file adapters'
    # profile rule) and any sentinel entry removed from the manifest after install.
    # The managed block self-delimits, so it strips without the template.
    if record is not None:
        for recorded in record.targets:
            if recorded.path in handled or recorded.mode != "sentinel_merge":
                continue
            removal = _surgical_remove_from_target(
                Path(recorded.path),
                "",
                mode="sentinel_merge",
                install_root=root,
                harness_name=harness_name,
                allowed_root=allowed_root,
            )
            if removal is not None:
                results.append(removal)
            handled.add(recorded.path)

    # Back up and remove the shared data home (memory / contexts / learning) only
    # when this is the last harness referencing it; plans/ is always retained.
    data_home_removal = _remove_data_home(
        harness_name, root=root, allowed_root=allowed_root
    )
    if data_home_removal is not None:
        results.append(data_home_removal)

    # Append an uninstall marker referencing the install pass it reversed —
    # only when every removal succeeded. On any error the install record
    # stays latest, matching the on-disk state (targets remain) so verify,
    # status, and rollback keep operating against the truth.
    if not any(result.outcome == "error" for result in results):
        install_ledger.append_record(
            LedgerRecord.create(
                harness=harness_name,
                root=root,
                kind="uninstall",
                install_id=record.install_id if record is not None else None,
            )
        )
    return results


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
