# SPDX-License-Identifier: MIT

"""Auto-update check for the apothem checkout.

Purpose
-------
Surface the latest signed release the local checkout has not yet
incorporated. Default invocation (`python scripts/dev/auto_update.py`) is
read-only: it fetches `origin` with tags (network), resolves the latest
released ``vMAJOR.MINOR.PATCH`` tag, compares HEAD against that tag, and
prints a status banner naming the tag. With `--apply` it fast-forwards the
working tree to the resolved tag — after verifying the tag's signature.

Trust model (tag-pinned, verified-by-default)
---------------------------------------------
Updates target the latest signed release TAG, not a moving branch. Before
``--apply`` fast-forwards, the target tag is verified with ``git
verify-tag``; an unsigned / tampered tag REFUSES the update unless
``APOTHEM_ALLOW_UNVERIFIED=1`` downgrades the refusal to a loud warning.
An explicit ``APOTHEM_REF`` pins a specific tag (or the moving ``main``
branch); the empty default resolves the latest release tag. This mirrors
scripts/installer/install.{sh,ps1}.

Contract
--------
Exits 0 when the checkout is up-to-date OR when `--apply` succeeds.
Exits 0 with a banner when behind upstream and `--apply` was not given
(behind-state is informational, not an error). Exits non-zero only on
hard failure (no checkout, no network, dirty tree blocking fast-forward,
or a refused unverified update under `--apply`).

Used by
-------
- Operator-invoked: ``python scripts/dev/auto_update.py [--apply]``.
- Not yet wired to a hook: a SessionStart hook could invoke this with
  ``--check-only --quiet`` to surface a single-line behind-by-N banner
  to the operating context without touching the working tree, but no hook
  currently does so.

Compatible with Python >= 3.10. Pure stdlib; no external dependencies.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_INSTALL_DIR = Path(
    os.environ.get("APOTHEM_HOME", str(Path.home() / ".apothem"))
)
# Empty sentinel means "resolve the latest released tag" in _resolve_ref. An
# explicit APOTHEM_REF pins a tag (or the moving `main` branch). Both names
# mirror scripts/installer/install.{sh,ps1}.
DEFAULT_REF = os.environ.get("APOTHEM_REF", "")
# When "1", a tag-verification failure downgrades from a hard refusal to a loud
# warning (air-gapped / pre-signed-release interim use). Mirrors the installers.
ALLOW_UNVERIFIED = os.environ.get("APOTHEM_ALLOW_UNVERIFIED", "0") == "1"

# Final-release tag shape: pure-numeric semver with a leading "v". Pre-release
# / build-metadata tags (v1.2.3-rc1) are intentionally excluded so the default
# never resolves to a non-final release.
_RELEASE_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def _git(*args: str, cwd: Path) -> tuple[int, str, str]:
    """Run a git command at ``cwd`` and capture exit-code, stdout, stderr."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _latest_release_tag(install_dir: Path) -> str:
    """Return the highest vMAJOR.MINOR.PATCH tag known to the checkout, or "".

    Tags must already be present locally (the caller fetches `--tags` first).
    Pre-release / build-metadata tags are excluded by `_RELEASE_TAG_RE` so the
    resolution never lands on a non-final release. Sorting is by the three
    numeric components, mirroring resolve_latest_tag in install.{sh,ps1}.
    """
    rc, out, _ = _git("tag", "--list", "v*.*.*", cwd=install_dir)
    if rc != 0 or not out:
        return ""
    versioned: list[tuple[tuple[int, int, int], str]] = []
    for line in out.splitlines():
        tag = line.strip()
        m = _RELEASE_TAG_RE.match(tag)
        if m:
            versioned.append(((int(m[1]), int(m[2]), int(m[3])), tag))
    if not versioned:
        return ""
    versioned.sort(key=lambda item: item[0])
    return versioned[-1][1]


def _is_release_tag(ref: str) -> bool:
    """Return True when ref is a verifiable vMAJOR.MINOR.PATCH release tag."""
    return bool(_RELEASE_TAG_RE.match(ref))


def _resolve_ref(install_dir: Path) -> str:
    """Return the ref the updater targets.

    An explicit APOTHEM_REF pins a tag (or the moving `main` branch). Otherwise
    the latest released tag is resolved from the local tag set (the caller
    fetches `--tags` first); if no release tag exists, fall back to "main" so
    the banner still names a concrete ref rather than failing opaquely.
    """
    if DEFAULT_REF:
        return DEFAULT_REF
    latest = _latest_release_tag(install_dir)
    return latest if latest else "main"


def _check_state(install_dir: Path) -> tuple[str, int, str, str, str]:
    """Return (state, behind_or_ahead_count, local_sha, target_sha, ref).

    state is one of: 'up-to-date', 'behind', 'ahead', 'diverged',
    'missing-remote', 'no-checkout'. The comparison target is the resolved ref
    (the latest release tag by default), not a moving remote branch — so the
    behind-count and banner name the tag the updater would fast-forward to.
    """
    if not (install_dir / ".git").is_dir():
        return ("no-checkout", 0, "", "", DEFAULT_REF or "main")

    # Fetch first so the latest tags are local before resolving the target ref.
    rc_fetch, _, fetch_err = _git(
        "fetch", "--tags", "--prune", "origin", cwd=install_dir
    )
    if rc_fetch != 0:
        # network or auth failure — surface as 'missing-remote' so callers
        # can degrade gracefully rather than crash on intermittent network.
        return ("missing-remote", 0, "", fetch_err, DEFAULT_REF or "main")

    ref = _resolve_ref(install_dir)

    # Resolve the target SHA: a tag resolves directly; a branch ref resolves
    # through its origin/<branch> remote-tracking ref.
    rc_local, local_sha, _ = _git("rev-parse", "HEAD", cwd=install_dir)
    rc_target, target_sha, _ = _git("rev-parse", ref, cwd=install_dir)
    if rc_target != 0:
        rc_target, target_sha, _ = _git("rev-parse", f"origin/{ref}", cwd=install_dir)
    if rc_local != 0 or rc_target != 0:
        return ("missing-remote", 0, local_sha, target_sha, ref)

    if local_sha == target_sha:
        return ("up-to-date", 0, local_sha, target_sha, ref)

    rc_ab, ab_out, _ = _git(
        "rev-list", "--left-right", "--count", f"HEAD...{target_sha}", cwd=install_dir
    )
    if rc_ab != 0:
        return ("diverged", 0, local_sha, target_sha, ref)

    parts = ab_out.split()
    ahead = int(parts[0]) if len(parts) >= 1 else 0
    behind = int(parts[1]) if len(parts) >= 2 else 0
    if ahead == 0 and behind > 0:
        return ("behind", behind, local_sha, target_sha, ref)
    if ahead > 0 and behind == 0:
        return ("ahead", ahead, local_sha, target_sha, ref)
    if ahead > 0 and behind > 0:
        return ("diverged", behind, local_sha, target_sha, ref)
    return ("up-to-date", 0, local_sha, target_sha, ref)


def _verify_ref(install_dir: Path, ref: str) -> tuple[bool, str]:
    """Verify the target ref's signature. Return (ok, reason).

    A release tag (vN.N.N) is checked with `git verify-tag`. A non-release ref
    (main, a SHA, a pre-release tag) is not a verifiable tag object and is
    reported as unverifiable. The caller applies the fail-closed gate (refuse
    unless APOTHEM_ALLOW_UNVERIFIED=1).
    """
    if not _is_release_tag(ref):
        return (False, f"ref {ref} is not a signed release tag")
    rc, _, err = _git("verify-tag", ref, cwd=install_dir)
    if rc == 0:
        return (True, "")
    return (False, err or f"tag {ref} signature did not verify")


def _apply(install_dir: Path, ref: str, target_sha: str) -> int:
    """Verify then fast-forward the local checkout to the target tag.

    Refuses on a dirty tree, on a failed signature verification (unless
    APOTHEM_ALLOW_UNVERIFIED=1), or on a non-fast-forward. Returns an exit code.
    """
    rc_dirty, dirty_out, _ = _git("status", "--porcelain", cwd=install_dir)
    if rc_dirty == 0 and dirty_out:
        sys.stderr.write(
            "auto_update: working tree has uncommitted changes — refusing to fast-forward.\n"
            "Commit or stash them, then re-run with --apply.\n"
        )
        return 1

    # Fail-closed verification BEFORE the working tree is moved. Status glyphs
    # are safe here because main() reconfigures the output streams to
    # backslashreplace on legacy consoles before any write.
    verified, reason = _verify_ref(install_dir, ref)
    if verified:
        sys.stdout.write(f"  ✓ verified signature on {ref}\n")
    elif ALLOW_UNVERIFIED:
        sys.stdout.write(
            f"  ! {reason} — proceeding because APOTHEM_ALLOW_UNVERIFIED=1\n"
        )
    else:
        sys.stderr.write(
            f"auto_update: {reason} — refusing to apply.\n"
            "Pin a signed release tag, or set APOTHEM_ALLOW_UNVERIFIED=1 to "
            "proceed without verification.\n"
        )
        return 1

    # Fast-forward to the resolved target SHA (the verified tag's commit).
    rc, _, err = _git("merge", "--ff-only", target_sha, cwd=install_dir)
    if rc != 0:
        sys.stderr.write(f"auto_update: fast-forward failed — {err}\n")
        return rc
    return 0


def _make_output_encoding_safe() -> None:
    """Make stdout/stderr tolerant of non-UTF-8 consoles.

    The banners carry status glyphs (✓ · ✗ etc.); a legacy Windows code page
    (cp1256, cp1252, …) cannot encode them and would raise mid-run rather than
    print a clean line. Switch the streams to ``backslashreplace`` so a
    non-encodable glyph degrades to an escape sequence instead of crashing. A
    no-op on UTF-8 consoles and on streams that do not expose ``reconfigure``.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):
                reconfigure(errors="backslashreplace")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. See module docstring for the contract."""
    _make_output_encoding_safe()
    parser = argparse.ArgumentParser(
        prog="auto_update",
        description="Check (and optionally apply) upstream updates for the apothem checkout.",
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=DEFAULT_INSTALL_DIR,
        help="Path to the apothem checkout (default: $APOTHEM_HOME or ~/.apothem).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Fast-forward the checkout to the resolved signed release tag when behind (verified before applying).",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Print one-line status and exit. Implies read-only.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress informational banners; emit one-line status only.",
    )
    args = parser.parse_args(argv)

    install_dir: Path = args.install_dir
    state, count, _local, target_sha, ref = _check_state(install_dir)

    if args.quiet or args.check_only:
        # Single-line summary suitable for hook-context inclusion. The behind
        # banner names the resolved tag, not a moving branch.
        if state == "up-to-date":
            print(f"apothem: up-to-date ({ref})")
        elif state == "behind":
            print(
                f"apothem: {count} commit(s) behind {ref} — run `python scripts/dev/auto_update.py --apply`"
            )
        elif state == "ahead":
            print(f"apothem: {count} commit(s) ahead of {ref} (local-only)")
        elif state == "diverged":
            print(
                f"apothem: history diverged from {ref} — manual reconciliation required"
            )
        elif state == "no-checkout":
            print(f"apothem: no git checkout at {install_dir}")
        elif state == "missing-remote":
            print(f"apothem: cannot reach {ref} (network or auth failure)")
        return 0 if state in ("up-to-date", "behind", "ahead") else 1

    # Verbose banner mode --------------------------------------------------------
    print(f"apothem updater (target: {install_dir}, ref: {ref})")
    print()

    if state == "no-checkout":
        sys.stderr.write(
            f"  ✗ {install_dir} is not a git checkout — run scripts/installer/install.sh / scripts/installer/install.ps1 first.\n"
        )
        return 1
    if state == "missing-remote":
        sys.stderr.write(f"  ✗ cannot reach {ref} (network or auth failure)\n")
        return 1
    if state == "ahead":
        print(f"  ✓ {count} local commit(s) ahead of {ref}; nothing to fetch.")
        return 0
    if state == "diverged":
        sys.stderr.write(
            f"  ✗ history diverged from {ref} — manual reconciliation required\n"
            f"    Inspect with: git -C {install_dir} log --oneline --left-right HEAD...{ref}\n"
        )
        return 1
    if state == "up-to-date":
        print(f"  ✓ already up-to-date with {ref}")
        return 0

    # state == "behind" — name the resolved release tag in the banner.
    print(f"  · {count} commit(s) available on {ref}")
    if not args.apply:
        print(f"  · run `python {Path(__file__).name} --apply` to fast-forward")
        return 0

    rc = _apply(install_dir, ref, target_sha)
    if rc == 0:
        print(f"  ✓ fast-forwarded to {ref}")
    return rc


if __name__ == "__main__":  # pragma: no cover — CLI entry
    raise SystemExit(main())
