#!/usr/bin/env python
# SPDX-License-Identifier: MIT

"""Regenerate the behavior-diff golden corpus from the deterministic oracles.

The behavior-diff regression wall (``tests/integration/test_install_driver_behavior_diff.py``
and ``test_cli_behavior_diff.py``) compares freshly-captured behavior against a
committed golden corpus under ``tests/fixtures/behavior-diff/``. The corpus is
produced by two deterministic, HOME-isolated oracles:

- ``_install_driver_oracle.capture_full`` — plan + dry-run + real-install across
  every adapter (self-clears + rewrites ``install_driver/``).
- ``_cli_oracle.capture`` — every CLI matrix invocation (self-clears + rewrites
  ``cli/``).

Both oracles emit platform-independent bytes. They tokenize machine-specific
paths (``_normalize_text`` / ``_path_variants``, including their JSON-escaped
spellings), rewrite Windows separators to forward slashes in tokenized paths and
in the relative adapter paths the CLI prints, pin Rich's rendering (no
legacy-Windows box substitution, no color, a fixed width, table cells measured
after tokenization), skip Click's probe of the host's bash, ignore the
operator's ``CODEX_HOME``, store ledger targets in code-point path order, and
write LF line-endings. A capture taken on Windows or Linux is therefore
byte-identical, and this script is safe to run from a Windows checkout. The
comparison layer (``_behavior_canon``) additionally collapses box-drawing,
padding, separators, and array order, so the tests also accept a corpus
captured before those pins existed.

Before it captures anything, the script stops when the result would depend on
the machine rather than the source: an interpreter started with ``-OO`` or
``-v``, a Click or Rich version outside the ``pyproject.toml`` requirement, or
ignored files and ignored-only directories under ``src/apothem`` (a Finder
``.DS_Store``, an editor backup, a directory left holding only ``__pycache__``
after a branch switch), which the installer would copy and the ledger would
record. It captures into a staging directory beside the destination and swaps
it in only after both oracles succeed, so a failed run leaves the committed
corpus as it was.

Workflow:

    python scripts/dev/regen-behavior-goldens.py          # regenerate in place
    python -m pytest tests/integration/test_install_driver_behavior_diff.py \\
                     tests/integration/test_cli_behavior_diff.py             # verify
    git diff --stat tests/fixtures/behavior-diff/          # review churn

A non-empty ``git diff`` after regeneration is a real change in captured
behavior, on any platform. Review it as part of the change-set that caused it.

The ``--dest DIR`` flag writes to an alternate directory instead of the
committed corpus, so a capture can be diffed without touching the working tree.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = REPO_ROOT / "tests" / "integration"
GOLDEN_ROOT = REPO_ROOT / "tests" / "fixtures" / "behavior-diff"
SOURCE_ROOT = PurePosixPath("src/apothem")

# The libraries whose output the CLI goldens embed: Click writes the help text
# and the completion scripts, Rich draws the tables and decides on color.
_RENDERING_LIBRARIES = ("click", "rich")

# What the installer already drops: the propagation manifest's exclude list
# (src/apothem/lib/propagation-manifest.yaml) less README.md and AGENTS.md,
# which are tracked. Their presence under src/apothem cannot change a capture.
_INSTALLER_SKIPPED_PARTS = frozenset({"__pycache__", ".mypy_cache", ".pytest_cache"})
_INSTALLER_SKIPPED_SUFFIX = ".pyc"


def _load_oracle(module_name: str) -> ModuleType:
    """Load an oracle module under a synthetic package so relative imports resolve.

    The oracles share helpers via ``from ._oracle_norm import ...``; a relative
    import needs a parent package. ``tests/integration`` carries no
    ``__init__.py`` — pytest supplies the package context itself — so a plain
    file-path load leaves ``__package__`` empty and the relative import raises
    ``ImportError``. Registering a synthetic package rooted at that directory and
    importing each oracle as a submodule of it reproduces the package context,
    so ``._oracle_norm`` resolves the same way it does under pytest.
    """
    package = "_behavior_diff_oracles"
    if package not in sys.modules:
        parent = ModuleType(package)
        parent.__path__ = [str(INTEGRATION)]
        sys.modules[package] = parent
    qualified = f"{package}.{module_name}"
    path = INTEGRATION / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(qualified, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise SystemExit(f"cannot load oracle module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


def interpreter_problems(*, optimize: int, verbose: int) -> list[str]:
    """Name each interpreter setting that would change the captured bytes.

    ``-OO`` (``PYTHONOPTIMIZE=2``) strips the docstrings Click builds every
    ``--help`` text from. ``-v`` (``PYTHONVERBOSE``) writes import traces, with
    memory addresses, into the captured CLI output. ``-O`` changes nothing.
    """
    problems: list[str] = []
    if optimize >= 2:
        problems.append(
            "the interpreter runs with -OO or PYTHONOPTIMIZE=2, which strips "
            "the docstrings Click builds --help text from"
        )
    if verbose:
        problems.append(
            "the interpreter runs with -v or PYTHONVERBOSE, which writes import "
            "traces into the CLI captures"
        )
    return problems


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:3])


def library_problems(
    pyproject_text: str, version_of: Callable[[str], str]
) -> list[str]:
    """Name each rendering library whose installed version misses pyproject.toml.

    Click's completion templates and Rich's table titles and color handling
    change between releases (Click 8.4.1 writes a different fish script, Rich
    before 14.3 pads table titles, Rich 13 ignores ``TTY_COMPATIBLE``), and a
    ``PYTHONPATH=src`` run uses whatever the host interpreter has installed.
    The requirement is read from the ``dependencies`` strings; ``==`` must match
    exactly and ``>=`` is compared on the numeric release parts.
    """
    problems: list[str] = []
    for name in _RENDERING_LIBRARIES:
        match = re.search(rf'"{name}\s*(==|>=)\s*([0-9][^"\s]*)"', pyproject_text)
        if match is None:
            continue
        operator, required = match.groups()
        wanted = f"{name}{operator}{required}"
        try:
            found = version_of(name)
        except importlib.metadata.PackageNotFoundError:
            problems.append(
                f"{name} is not installed; pyproject.toml requires {wanted}"
            )
            continue
        if operator == "==":
            satisfied = found == required
        else:
            satisfied = _version_key(found) >= _version_key(required)
        if not satisfied:
            problems.append(
                f"{name} {found} is installed; pyproject.toml requires {wanted}"
            )
    return problems


def _installer_skips(path: PurePosixPath) -> bool:
    return path.suffix == _INSTALLER_SKIPPED_SUFFIX or any(
        part in _INSTALLER_SKIPPED_PARTS for part in path.parts
    )


def stray_source_paths(repo_root: Path) -> list[str] | None:
    """Return the ignored entries under ``src/apothem`` that a capture would install.

    The installer copies every file a cohort directory holds, minus the
    manifest's exclude list, without consulting git. A file git ignores (a
    Finder ``.DS_Store``, an editor ``~`` or ``.swp`` file, a mergetool
    ``.orig``) and a directory holding no file git would keep (left with only
    ``__pycache__`` after a branch switch, or empty) therefore reach the
    ledger and envelope goldens although ``git status`` shows nothing. Returns
    the repository-relative POSIX paths, directories with a trailing ``/``,
    sorted; ``None`` when git is unavailable or *repo_root* is not a work tree.
    """
    git = shutil.which("git")
    if git is None:
        return None

    def ls_files(*options: str) -> list[str] | None:
        result = subprocess.run(  # noqa: S603 — trusted invocation: literal argv against a `shutil.which`-resolved git, no shell
            [git, "ls-files", "-z", *options, "--", str(SOURCE_ROOT)],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return [os.fsdecode(entry) for entry in result.stdout.split(b"\0") if entry]

    ignored = ls_files("--others", "--ignored", "--exclude-standard")
    kept = ls_files("--cached", "--others", "--exclude-standard")
    if ignored is None or kept is None:
        return None
    stray = {path for path in ignored if not _installer_skips(PurePosixPath(path))}
    kept_dirs = {
        parent.as_posix() for path in kept for parent in PurePosixPath(path).parents
    }
    for dirpath, dirnames, _filenames in os.walk(repo_root / SOURCE_ROOT):
        relative = Path(dirpath).relative_to(repo_root).as_posix()
        if relative != str(SOURCE_ROOT) and relative not in kept_dirs:
            stray.add(f"{relative}/")
            dirnames.clear()
            continue
        dirnames[:] = [
            name for name in dirnames if name not in _INSTALLER_SKIPPED_PARTS
        ]
    return sorted(stray)


def capture_staged(
    dest: Path, install_oracle: ModuleType, cli_oracle: ModuleType
) -> int:
    """Capture both corpora beside *dest* and swap them in only on success.

    Each oracle clears its output directory before it captures, so capturing
    straight into the committed corpus left it deleted whenever a capture
    raised. The staging directory sits beside *dest*, so the swap is a rename
    on the same file system, and it is removed whether or not the run
    succeeds. Returns the number of CLI captures.
    """
    dest.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{dest.name}.regen-", dir=dest.parent))
    try:
        install_oracle.capture_full(staging / "install_driver")
        cli_count = int(cli_oracle.capture(staging / "cli"))
        for subtree in ("install_driver", "cli"):
            target = dest / subtree
            if target.exists():
                shutil.rmtree(target)
            (staging / subtree).replace(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return cli_count


def main() -> int:
    """Recapture both golden corpora from the oracles; return the exit code.

    Pre-conditions: the ``apothem`` package must be importable — either the
    dedicated virtualenv install or a ``PYTHONPATH=src`` invocation satisfies
    this; the function inserts the checkout's ``src`` onto ``sys.path`` when it
    is absent. The interpreter, library, and source-tree checks above must
    pass; otherwise the function names each problem and returns ``1`` without
    touching the destination.

    Post-conditions: both subtrees are rewritten from the current source, so
    the corpus reflects it exactly rather than accumulating stale entries; a
    failed capture leaves the destination unchanged. ``--dest`` redirects the
    write to an alternate root, leaving the committed corpus untouched for a
    diff-only comparison. Returns ``0``.
    """
    parser = argparse.ArgumentParser(
        description="Regenerate the behavior-diff golden corpus (Windows-capable)."
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=GOLDEN_ROOT,
        help="Destination root for the corpus (default: the committed corpus).",
    )
    args = parser.parse_args()

    # The engine package must be importable; the dedicated .venv install or a
    # `PYTHONPATH=src` invocation both satisfy this.
    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))

    problems = interpreter_problems(
        optimize=sys.flags.optimize, verbose=sys.flags.verbose
    )
    problems += library_problems(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        importlib.metadata.version,
    )
    stray = stray_source_paths(REPO_ROOT)
    if stray is None:
        print(
            "[WARN] git is unavailable; skipped the check for ignored files "
            "under src/apothem",
            file=sys.stderr,
        )
    elif stray:
        listed = "\n".join(f"      {path}" for path in stray)
        problems.append(
            "these ignored entries under src/apothem would be installed into "
            f"the captures; delete or move them:\n{listed}"
        )
    if problems:
        print(
            "[FAIL] the capture would depend on this machine, not on the source:",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    install_oracle = _load_oracle("_install_driver_oracle")
    cli_oracle = _load_oracle("_cli_oracle")

    dest: Path = args.dest
    cli_count = capture_staged(dest, install_oracle, cli_oracle)
    print(
        f"[OK] install_driver corpus -> {dest / 'install_driver'} "
        f"({len(install_oracle.ALL_ADAPTERS)} adapters)"
    )
    print(f"[OK] cli corpus -> {dest / 'cli'} ({cli_count} captures)")

    print(
        "\nRegenerated. Verify with:\n"
        "  python -m pytest tests/integration/test_install_driver_behavior_diff.py "
        "tests/integration/test_cli_behavior_diff.py\n"
        "  git diff --stat tests/fixtures/behavior-diff/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
