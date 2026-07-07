# SPDX-License-Identifier: MIT

"""Flag artifacts emitted to non-canonical locations or without provenance.

Why this enforcement exists. The canonical-layout rule M12 + the
systemicity rule M14 require every emitted artifact to land at a
ratified output directory and to declare its producer (provenance
frontmatter, header comment, or registry entry). Orphan outputs —
artifacts the host's reference graph does not consume — fragment the
project surface and resist maintenance. The pre-emission gate's
mechanical bar 12 (M12 canonical layout) catches two failure modes: location drift (artifact
not under any ratified output directory) and provenance absence (no
frontmatter / header / registry entry naming the producer).

Detection strategy. The grep accepts a content body and an artifact
path. It checks the path against the ratified output-directory list
discovered from the host's existing layout (`src/`, `lib/`, `tests/`,
`site/`, `.github/`, plus the host-discovery default harness-config
subtree — for example `~/.claude/` for the Claude Code harness).
When the path is outside every ratified directory, that is one finding. When the content body lacks a provenance marker
(YAML frontmatter `provenance:` field, comment-line `provenance:`
marker, or a `Bindings` section binding the artifact to its producer),
that is another finding.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

# Ratified output-directory prefixes. The set is conservative — it covers
# the canonical surfaces the host project emits to. New artifact classes
# either land at one of these prefixes or surface an inquiry to the
# operator before silent installation.
RATIFIED_OUTPUT_PREFIXES: Final[tuple[str, ...]] = (
    "src/",
    "lib/",
    "tests/",
    "site/",
    ".github/",
    "rules/",
    "skills/",
    "commands/",
    "agents/",
    "hooks/",
    "tools/",
    "scripts/",
    "assets/",
    "schemas/",
    "templates/",
    "memory/",
    ".plans/",
    "output-styles/",
    "statuslines/",
)

# Root-level singletons that are canonical by filename, not by directory
# prefix. README, LICENSE, CHANGELOG, CONTRIBUTING etc. land at the repo
# root by universal convention. Harness-config singleton settings.json
# lives at the harness config root for every integrated harness —
# `~/.claude/settings.json` for Claude Code, `.vscode/settings.json` for
# VS Code, `~/.cursor/settings.json` for Cursor, etc. — and is canonical
# by basename per the module docstring's harness-config-subtree clause.
RATIFIED_ROOT_FILENAMES = frozenset(
    {
        "README.md",
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "SUPPORT.md",
        "CODE_OF_CONDUCT.md",
        "GOVERNANCE.md",
        "AUTHORS.md",
        "NOTICE",
        "NOTICE.md",
        "NOTICE.txt",
        "CODEOWNERS",
        "FUNDING.yml",
        "CITATION.cff",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "Makefile",
        "CLAUDE.md",
        "settings.json",
    }
)

# Provenance markers — any one of these in the content body satisfies
# the M14 producer-attribution requirement. Source-language artifacts
# satisfy provenance via the canonical SPDX authorship-header banner
# enforced by `file-header-grep`; the SPDX-License-Identifier line is
# the machine-readable producer-attribution marker per the REUSE
# specification, mirroring how Markdown artifacts satisfy it via the
# `## Bindings` section or frontmatter `description:` field.
PROVENANCE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:provenance:|## Bindings\b|^---\s*$.*?\bdescription:|SPDX-License-Identifier:)",
    re.MULTILINE | re.DOTALL,
)

# Trivial-by-extension carve-out: data files (`.json`, `.yml`, `.yaml`,
# `.toml`) and lockfiles can satisfy provenance via their parent
# package-manifest contract; per-file frontmatter is not required for
# these classes.
TRIVIAL_PROVENANCE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".json", ".yaml", ".yml", ".toml", ".lock", ".cfg", ".ini"}
)

# Trivial-by-basename carve-out: files whose format convention does not admit
# a per-file provenance banner and whose provenance is satisfied structurally.
# `.SRCINFO` is a machine-parseable manifest generated from `PKGBUILD` — a
# banner would corrupt the parser's input. `py.typed` is the PEP 561 inline-
# type marker: conventionally zero-byte (a banner would defeat the marker), and
# its provenance is the package contract that ships it — the `apothem`
# `[tool.setuptools.package-data]` entry in `pyproject.toml`.
TRIVIAL_PROVENANCE_BASENAMES: Final[frozenset[str]] = frozenset(
    {".SRCINFO", "py.typed"}
)

# Memory-index carve-out: the auto-memory convention defines `MEMORY.md` as a
# frontmatter-free index — one index line per memory, no per-file frontmatter.
# Its producer attribution is structural: it is the index every memory topic
# file points back to, and the topic files it indexes carry their own
# frontmatter. Requiring a provenance marker from the index itself is a
# category error; a memory-index write would otherwise fail-close the harness's
# per-project memory tree (the `MEMORY.md` write the operator makes at session
# end has no frontmatter to satisfy `PROVENANCE_RE`).
MEMORY_INDEX_BASENAMES: Final[frozenset[str]] = frozenset({"MEMORY.md"})

GREP_NAME: Final[str] = "orphan-output-grep"
RULE_ANCHOR: Final[str] = "M12 canonical-layout + M14 systemicity"


@dataclass(frozen=True)
class Finding:
    issue: str
    detail: str
    rule: str = RULE_ANCHOR


def _is_under_ratified_prefix(path: Path) -> bool:
    """Return True iff the path is under a ratified prefix or is a root-level singleton."""
    posix = path.as_posix()
    if any(prefix in posix for prefix in RATIFIED_OUTPUT_PREFIXES):
        return True
    # Root-level canonical files (README, LICENSE, etc.) match by name.
    return path.name in RATIFIED_ROOT_FILENAMES


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content + path; return a structured result."""
    findings: list[Finding] = []
    if path is not None and not _is_under_ratified_prefix(path):
        findings.append(
            Finding(
                issue="non-canonical location",
                detail=(
                    f"path {path.as_posix()!r} is not under any ratified output "
                    f"prefix; surface as an inquiry before emission"
                ),
            )
        )
    requires_provenance = path is None or (
        path.suffix.lower() not in TRIVIAL_PROVENANCE_EXTENSIONS
        and path.name not in TRIVIAL_PROVENANCE_BASENAMES
        and path.name not in MEMORY_INDEX_BASENAMES
    )
    if requires_provenance and PROVENANCE_RE.search(content) is None:
        findings.append(
            Finding(
                issue="provenance absent",
                detail=(
                    "content lacks a provenance marker (YAML `provenance:` field, "
                    "header `## Bindings` section, or frontmatter description); "
                    "the producer of this artifact is unrecorded"
                ),
            )
        )
    return GrepResult(
        grep=GREP_NAME,
        path=str(path) if path is not None else None,
        passed=not findings,
        findings=findings,
    )


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
