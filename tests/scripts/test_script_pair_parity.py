# SPDX-License-Identifier: MIT

"""Cross-OS executable parity for shell scripts.

The project ships paired install / update / uninstall and dev / release
tooling so an operator on either a POSIX shell or PowerShell can run the
same workflow. The cross-platform discipline (mirrored by
``src/apothem/conformity/cross_platform_matrix_grep.py`` for CI) extends
to the executable surface: every POSIX ``.sh`` script that is meant to
run on any host has a PowerShell ``.ps1`` sibling at the same path stem.

A small set of scripts legitimately ship POSIX-only. Each such script is
recorded here as an explicit exception with a concrete reason; an
unlisted ``.sh`` without a ``.ps1`` sibling is a real parity finding.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[2]

# Roots searched for POSIX shell scripts. Each is a surface where an
# operator or the harness invokes a script directly.
SHELL_SCRIPT_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "scripts",
    REPO_ROOT / "src" / "apothem" / "hooks" / "lib",
)

# POSIX-only scripts with no PowerShell sibling, each with a concrete
# reason the parity requirement does not apply. Keyed by repo-relative
# POSIX path so the assertion message names the precise script.
NO_PARITY_EXCEPTIONS: dict[str, str] = {
    "scripts/inject-header.sh": (
        "Reflex convenience wrapper that locates a Python interpreter and "
        "delegates to scripts/inject-header.py; the substantive work is the "
        "already-cross-platform Python script, which Windows operators invoke "
        "directly. The wrapper's own docstring states it exists for shell-"
        "reflex parity, not as the canonical entrypoint."
    ),
}


def _iter_shell_scripts() -> list[Path]:
    scripts: list[Path] = []
    for root in SHELL_SCRIPT_ROOTS:
        if root.is_dir():
            scripts.extend(sorted(root.rglob("*.sh")))
    return scripts


def _relpath(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def test_shell_scripts_exist() -> None:
    """The repo actually ships POSIX shell scripts to check parity against."""
    assert _iter_shell_scripts(), "no .sh scripts discovered under the search roots"


def test_every_shell_script_has_powershell_sibling_or_exception() -> None:
    """Each ``.sh`` has a ``.ps1`` sibling, or a recorded no-parity reason."""
    findings: list[str] = []
    for sh in _iter_shell_scripts():
        rel = _relpath(sh)
        ps1 = sh.with_suffix(".ps1")
        if ps1.exists():
            continue
        if rel in NO_PARITY_EXCEPTIONS:
            continue
        findings.append(
            f"{rel} has no {ps1.with_suffix('.ps1').name} sibling and no "
            f"recorded NO_PARITY_EXCEPTIONS entry"
        )
    assert not findings, "shell scripts lacking PowerShell parity:\n" + "\n".join(
        findings
    )


def test_no_parity_exceptions_are_real_and_unpaired() -> None:
    """Every recorded exception names an existing, genuinely unpaired ``.sh``."""
    stale: list[str] = []
    for rel, reason in NO_PARITY_EXCEPTIONS.items():
        sh = REPO_ROOT / rel
        if not sh.exists():
            stale.append(f"{rel}: exception recorded but the .sh does not exist")
            continue
        if sh.with_suffix(".ps1").exists():
            stale.append(
                f"{rel}: exception recorded but a .ps1 sibling exists — drop the exception"
            )
        assert reason.strip(), f"{rel}: exception reason must be non-empty"
    assert not stale, "stale NO_PARITY_EXCEPTIONS entries:\n" + "\n".join(stale)


def test_paired_scripts_have_matching_stems() -> None:
    """Where a ``.ps1`` sibling exists, it shares the ``.sh`` path stem."""
    for sh in _iter_shell_scripts():
        ps1 = sh.with_suffix(".ps1")
        if ps1.exists():
            assert ps1.stem == sh.stem
            assert ps1.parent == sh.parent


def _iter_windows_cmd_wrappers() -> list[Path]:
    """All Windows CMD wrappers (``.bat`` / ``.cmd``) under the search roots."""
    wrappers: list[Path] = []
    for root in SHELL_SCRIPT_ROOTS:
        if root.is_dir():
            for suffix in ("*.bat", "*.cmd"):
                wrappers.extend(sorted(root.rglob(suffix)))
    return wrappers


def test_no_duplicate_windows_cmd_wrapper() -> None:
    """No script stem ships both a ``.bat`` and a ``.cmd`` wrapper.

    A stem carrying both is a duplicate-wrapper orphan: one is canonical
    (bundled into releases, created by the installer, exercised by tests)
    and the other drifts unmaintained. The repo settled on ``.cmd`` for the
    CLI launcher and ``.bat`` for the installer shims; either is fine for a
    given stem, but never both — that asymmetry is how a stale duplicate
    hides. This guard closes the ``.sh``/``.ps1``-only blind spot of the
    parity checks above, which never inspect the CMD-wrapper layer.
    """
    by_stem: dict[tuple[Path, str], set[str]] = {}
    for wrapper in _iter_windows_cmd_wrappers():
        by_stem.setdefault((wrapper.parent, wrapper.stem), set()).add(
            wrapper.suffix.lower()
        )
    duplicates = [
        f"{(parent / stem).relative_to(REPO_ROOT).as_posix()} ships both .bat and .cmd"
        for (parent, stem), suffixes in sorted(by_stem.items())
        if {".bat", ".cmd"} <= suffixes
    ]
    assert not duplicates, "duplicate Windows CMD wrappers:\n" + "\n".join(duplicates)
