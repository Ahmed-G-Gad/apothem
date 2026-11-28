# SPDX-License-Identifier: MIT

"""Report files a folder ships that its own README never names.

Why this check exists. The per-folder README is the folder's operating
contract — `AGENTS.md` makes it the surface that serves both the human and the
agent reader. Its file table is therefore load-bearing: a reader who cannot
find a module in the table concludes it does not exist, or that it is
incidental. Nothing enforced that table against the folder's actual contents,
and the drift is invisible from either side. You do not notice a missing row
while reading the README, and you do not think about the README while adding
a file.

The gap is real and recurring. A repo-wide audit found the skills and
conformity tables each missing entries; a thirteen-module refactor of the
audit package added every one of them without touching that package's README.
Three independent occurrences of one defect class is the point at which the
check should be mechanical rather than remembered.

A folder with no README of its own is indexed by the README above it:
``scripts/README.md`` names the files of ``scripts/release/``. Its source
modules are therefore checked against the nearest README above it; checking
only the folder a README sits in let a new release script and two test helpers
go unnamed. When two files that one README indexes share a name (the four
``page.tsx`` routes under ``site/app/``), the bare name no longer tells them
apart, so each such file must be named by its path from the README's folder.
Whether a folder has a README is read from the git-tracked set, like the files
themselves, so an untracked local README cannot change the result.

What it does NOT check. Whether a described row is *accurate* — only whether a
shipped file is named at all. Presence is what drifts silently; a wrong
description tends to be noticed when read. `agents_md_coverage_grep.py` in the
conformity package covers the neighbouring question of whether a folder has a
README at all.

Advisory by default: findings print and the command exits 0. Pass ``--strict``
to exit non-zero on any finding, which is how a CI or pre-commit step should
invoke it.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Trees whose contents are not the folder's own authored surface: vendored
# third-party code, generated state, and fixture corpora whose files are test
# material rather than modules a reader navigates.
EXCLUDED_PARTS = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "_vendor",
        "node_modules",
        "dist",
        "build",
        "out",
        ".next",
        ".audit",
        ".apothem",
        ".plans",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        "fixtures",
        "completions",
        "templates",
    }
)

# File classes a README is not expected to enumerate row by row: package
# markers, license and metadata boilerplate, and the tool-config files whose
# presence is a convention rather than a thing a reader navigates to.
IGNORED_NAMES = frozenset(
    {
        "README.md",
        "__init__.py",
        "py.typed",
        "LICENSE",
        ".keep",
        ".gitkeep",
        "package.json",
        "package-lock.json",
        "tsconfig.json",
        "components.json",
        "next.config.mjs",
        "postcss.config.mjs",
        "source.config.ts",
        "REUSE.toml",
        "CITATION.cff",
        "Makefile",
        "PSScriptAnalyzerSettings.psd1",
    }
)
IGNORED_SUFFIXES = frozenset({".pyc", ".pyo", ".png", ".ico", ".svg", ".woff2"})

# In a folder with no README of its own, only source modules are held to the
# nearest README above it. Such folders are mostly corpora a README describes
# as a whole rather than file by file: the documentation pages under
# site/content/docs/, eval cases, fuzz seeds. A module there is code another
# file runs or imports, which a reader needs to find by name.
SOURCE_SUFFIXES = frozenset(
    {
        ".py",
        ".sh",
        ".ps1",
        ".psm1",
        ".bat",
        ".cmd",
        ".js",
        ".mjs",
        ".cjs",
        ".jsx",
        ".ts",
        ".tsx",
    }
)

# Test modules are named by their test area's row, not one by one: a README
# that listed every test file would restate the folder and drift on the next
# test. Helper modules beside them (``_shared/``, an oracle module) are not
# tests, so they still need a name.
TEST_MODULE = re.compile(
    r"^(test_.*\.py|.*_test\.py|conftest\.py|.*\.(test|spec)\.[cm]?[jt]sx?)$"
)

# Some READMEs are published product front pages, not file indexes: they
# introduce the project to a newcomer or a marketplace visitor. Holding one to
# the per-folder contract would demand an implementation-file table in copy
# written for end users — noise in the report and a worse page for its actual
# audience. The repository root is the project's front page; the VS Code
# extension's README is its Visual Studio Marketplace listing.
FRONT_PAGE_READMES = frozenset(
    {
        Path("README.md"),
        Path("vscode-extension/README.md"),
    }
)


# Generated distribution trees, matched by path prefix rather than by a bare
# path part: every file is machine-emitted from a source elsewhere in the repo,
# so a README row per file would index a copy, not an authored surface. These
# carry their own drift gate — the generator is the contract, not a file table.
# Prefix matching keeps the exclusion narrow: the bare part "claude-code" would
# also silence unrelated folders that happen to share the name.
GENERATED_TREES = frozenset({Path("plugins/claude-code")})


def is_excluded(path: Path) -> bool:
    """Return True when the path sits in a tree the contract does not govern.

    Three classes: the excluded trees named above, the generated distribution
    trees (matched by path prefix), and the conformity fixture corpora: the
    ``tests/conformity/*/pass|fail/`` folders, whose READMEs describe what the
    corpus proves rather than indexing each fixture file, and the single-file
    ``pass.py`` / ``fail.py`` fixtures a validator's test folder carries.
    """
    parts = path.parts
    if any(part in EXCLUDED_PARTS for part in parts):
        return True
    if any(path.is_relative_to(tree) for tree in GENERATED_TREES):
        return True
    return "conformity" in parts and any(
        Path(part).stem in ("pass", "fail") for part in parts
    )


def tracked_files(root: Path) -> set[Path]:
    """Return every git-tracked file, as paths relative to the root.

    Walking the working tree instead would pick up build output and anything
    else the repo deliberately ignores — an earlier draft of this check
    reported a gitignored ``tsconfig.tsbuildinfo`` as an undocumented file.
    The tracked set is the honest definition of what the repo ships.
    """
    git = shutil.which("git")
    if git is None:
        raise SystemExit("check-readme-file-coverage: git not found on PATH")
    result = subprocess.run(  # noqa: S603 — trusted invocation: literal argv against a `shutil.which`-resolved git, no shell
        [git, "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit("check-readme-file-coverage: git ls-files failed")
    return {Path(line) for line in result.stdout.splitlines() if line}


def is_indexable(name: str) -> bool:
    """Return True for a file name a README is expected to name."""
    return (
        name not in IGNORED_NAMES
        and Path(name).suffix not in IGNORED_SUFFIXES
        and not name.startswith(".")
    )


def shipped_files(folder: Path, root: Path, tracked: set[Path]) -> list[Path]:
    """Return the tracked files a reader would expect the README to name."""
    return sorted(
        entry
        for entry in folder.iterdir()
        if entry.is_file()
        and entry.relative_to(root) in tracked
        and is_indexable(entry.name)
    )


def nearest_ancestor_readme(folder: Path, tracked: set[Path]) -> Path | None:
    """Return the tracked README of the nearest folder above ``folder``.

    ``folder`` and the result are relative to the repository root; the walk
    stops at the root, and the result is ``None`` when no folder on the way
    carries a tracked README. Presence is read from the tracked set rather than
    the disk, so an untracked local README cannot make the check skip a folder
    that CI still checks.
    """
    for ancestor in folder.parents:
        candidate = ancestor / "README.md"
        if candidate in tracked:
            return candidate
    return None


def is_subfolder_module(name: str) -> bool:
    """Return True for a file a README-less folder's governing README must name."""
    return (
        is_indexable(name)
        and Path(name).suffix in SOURCE_SUFFIXES
        and not TEST_MODULE.match(name)
    )


def subfolder_findings(root: Path, tracked: set[Path]) -> dict[Path, list[str]]:
    """Return the modules of README-less folders that the governing README never names.

    A folder with no README of its own is indexed by the nearest README above
    it: ``scripts/README.md`` names the files of ``scripts/release/``, and
    ``tests/README.md`` those of ``tests/_shared/``. Checking only the folder a
    README sits in let such a subfolder's new module go unnamed. Only source
    modules count here (see ``SOURCE_SUFFIXES`` and ``TEST_MODULE``). The
    result maps each governing README's folder to the unnamed files, written
    relative to that folder. A front-page README, or one in an excluded tree,
    governs nothing, so its README-less subfolders are not checked.

    A file whose name another file indexed by the same README also carries
    must be named by its path from the README's folder (see ``path_named_in``):
    otherwise ``app/page.tsx`` in the README would vouch for every other
    ``page.tsx`` below it.
    """
    governed: dict[Path, list[Path]] = {}
    for rel in sorted(tracked):
        folder = rel.parent
        if folder == Path() or folder / "README.md" in tracked:
            continue
        if (
            is_excluded(rel)
            or not is_subfolder_module(rel.name)
            or not (root / rel).is_file()
        ):
            continue
        readme = nearest_ancestor_readme(folder, tracked)
        if readme is None or readme in FRONT_PAGE_READMES or is_excluded(readme):
            continue
        governed.setdefault(readme, []).append(rel)

    findings: dict[Path, list[str]] = {}
    for readme, modules in governed.items():
        text = (root / readme).read_text(encoding="utf-8", errors="replace")
        own_names = [
            p.name
            for p in tracked
            if p.parent == readme.parent and is_indexable(p.name)
        ]
        names = own_names + [rel.name for rel in modules]
        for rel in modules:
            relative = rel.relative_to(readme.parent).as_posix()
            if names.count(rel.name) > 1:
                named = path_named_in(text, relative)
            else:
                named = named_in(text, rel.name)
            if not named:
                findings.setdefault(readme.parent, []).append(relative)
    return findings


def named_in(readme_text: str, filename: str) -> bool:
    """Return True when the README names the file.

    Matches the bare filename anywhere in the prose, not only inside a table
    row: some folders describe a file in a paragraph rather than a table, and
    that is still a reader finding it. The stem is accepted too, because a
    table sometimes writes ``install`` for ``install.sh`` where the folder
    ships several extensions of one recipe.
    """
    if filename in readme_text:
        return True
    stem = Path(filename).stem
    return bool(re.search(rf"`{re.escape(stem)}`", readme_text))


# A folder segment a README may write as a placeholder, so one entry such as
# ``<adapter>/install.py`` or ``*/install.py`` names the same module in every
# sibling folder that carries it.
_PLACEHOLDER_SEGMENT = r"(?:<[^<>`/\s]+>|\*)"


def path_named_in(readme_text: str, relative: str) -> bool:
    """Return True when the README names the file by its relative path.

    ``relative`` is the file's path from the README's folder, such as
    ``app/[lang]/page.tsx``. The path must not continue a longer path to its
    left, so ``docs/page.tsx`` is not named by ``app/docs/page.tsx``. Any folder
    segment may be written as a placeholder (``<adapter>`` or ``*``); the file
    name itself must be literal.
    """
    *folders, filename = relative.split("/")
    segments = [rf"(?:{re.escape(part)}|{_PLACEHOLDER_SEGMENT})" for part in folders]
    pattern = "/".join([*segments, re.escape(filename)])
    bounded = rf"(?<![\w./\-\]])(?:\./)?{pattern}(?![\w/-]|\.\w)"
    return bool(re.search(bounded, readme_text))


def main(argv: list[str] | None = None) -> int:
    """Walk every folder with a README and report the files it never names.

    Post-conditions: prints one line per unnamed file, grouped by folder, and
    a total. Exits 0 unless ``--strict`` was passed and findings exist.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any shipped file is unnamed by its README.",
    )
    args = parser.parse_args(argv)

    findings: list[tuple[Path, str]] = []
    folders_checked = 0
    tracked = tracked_files(args.root)

    for relative in sorted(p for p in tracked if p.name == "README.md"):
        readme = args.root / relative
        if is_excluded(relative) or not readme.is_file():
            continue
        if relative in FRONT_PAGE_READMES:
            continue
        folder = readme.parent
        files = shipped_files(folder, args.root, tracked)
        if not files:
            continue
        folders_checked += 1
        text = readme.read_text(encoding="utf-8", errors="replace")
        for entry in files:
            if not named_in(text, entry.name):
                findings.append((folder.relative_to(args.root), entry.name))

    for folder, names in subfolder_findings(args.root, tracked).items():
        findings.extend((folder, name) for name in names)
    findings.sort(key=lambda finding: (finding[0].as_posix(), finding[1]))

    if findings:
        current: Path | None = None
        for folder, name in findings:
            if folder != current:
                print(f"\n{folder.as_posix()}/README.md does not name:")
                current = folder
            print(f"  {name}")
        print(
            f"\ncheck-readme-file-coverage: {len(findings)} unnamed file(s) "
            f"across {folders_checked} folder(s) with a README"
        )
        return 1 if args.strict else 0

    print(
        f"check-readme-file-coverage: OK — every shipped file is named "
        f"({folders_checked} folders checked)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
