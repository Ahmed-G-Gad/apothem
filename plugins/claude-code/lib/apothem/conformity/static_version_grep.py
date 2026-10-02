# SPDX-License-Identifier: MIT

"""Verify version-bearing sites resolve dynamically, not as static literals.

Why this enforcement exists. Companion to ``dynamism_grep.py``. The
dynamism rule mandates that every version-bearing site in the project
derive its value from a single source of truth (package metadata via
``importlib.metadata``, the shields.io dynamic badge endpoints that
resolve against the npm registry and GitHub Releases, or the site
build's version-injection mechanism) rather than carry the version
as a hard-coded literal. Static literals drift the moment a release
ships: badge URLs lie about the current version, docs pages display
the version that was true at last edit, and the runtime ``__version__``
attribute returns a value that disagrees with the installed package.
This standalone validator walks three classes of site (README badges,
docs site config, runtime ``__version__``) and reports every static
resolution so the operator can convert it to a dynamic form.

Scope. Standalone corpus-level validator. Walks the project root from a
single ``main(root)`` entry point and exits 0 (PASS) or 2 (FAIL) with a
structured JSON report listing every static-version site. Invoked via
``python -m apothem.conformity.gate --all .`` or
``python -m apothem.conformity.gate --check static-version-grep <root>``.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "static-version-grep"
RULE_ANCHOR: Final[str] = "rules/dynamism.md §static-version-resolution"
EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# README sites inspected for badge URLs. Shields.io dynamic badge paths
# include the project / package coordinate after a `/github/v/release/`,
# `/github/v/tag/`, `/npm/v/`, or `/npm/dm/` segment; static badges instead
# embed a literal version number in the URL or use the `/badge/` static
# generator with a hard-coded value.
README_CANDIDATES: Final[tuple[str, ...]] = ("README.md", "README.rst", "README")

# Site config candidates. Each is inspected for a `version:` key bearing a
# string-literal value rather than a templated / dynamic reference.
SITE_CONFIG_CANDIDATES: Final[tuple[str, ...]] = (
    "site/next.config.mjs",
    "site/package.json",
)

# Runtime version-bearing module. The canonical pattern is
# ``__version__ = importlib.metadata.version(__package__)`` (or an
# equivalent ``metadata.version("apothem")`` form). A literal string
# assignment is the failure mode this validator catches.
RUNTIME_VERSION_MODULE: Final[str] = "src/apothem/__init__.py"

# A semver-shaped literal version embedded in a badge URL or a config
# value. Captures forms like `v1.2.3`, `1.2.3`, `1.2.3-alpha.1`,
# `2.0.0+build.7`. Word boundaries prevent partial matches inside
# longer identifiers.
LITERAL_VERSION_RE: Final[re.Pattern[str]] = re.compile(
    r"\bv?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\b"
)

# Shields.io dynamic badge markers — any of these path fragments in a
# badge URL indicates the badge resolves dynamically against an upstream
# registry rather than carrying a literal version.
SHIELDS_DYNAMIC_MARKERS: Final[tuple[str, ...]] = (
    "img.shields.io/github/v/release/",
    "img.shields.io/github/v/tag/",
    "img.shields.io/npm/v/",
    "img.shields.io/npm/dm/",
    "img.shields.io/crates/v/",
    "img.shields.io/gem/v/",
)

# Markdown badge / image syntax. Captures the URL inside the
# `![alt](url)` form so each URL can be classified independently.
MARKDOWN_IMAGE_RE: Final[re.Pattern[str]] = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

# Git-ref query parameters (`?branch=`, `?tag=`, `?ref=`) on a badge URL carry a
# git ref that may itself be a version tag — e.g. a build-status badge pinned to
# `?branch=v1.2.3`. That ref is not the badge's *displayed* version, so a semver
# token appearing only inside one of these parameters must not be read as a
# static-version literal. The parameter values are stripped before the
# literal-version scan; a version embedded in the URL *path* (the static
# `/badge/<label>-<version>-<color>` generator) is untouched and still flagged.
REF_PARAM_RE: Final[re.Pattern[str]] = re.compile(r"[?&](?:branch|tag|ref)=[^&]*")

# A literal ``version:`` key in a YAML/Python config carrying a quoted
# string value (site-generator config style). Templated references — e.g.
# ``version: !ENV [VERSION]`` or ``version = metadata.version(...)`` —
# do not match.
YAML_LITERAL_VERSION_RE: Final[re.Pattern[str]] = re.compile(
    r"""^\s*version\s*[:=]\s*["']([^"']+)["']""",
    re.MULTILINE,
)

# A literal ``__version__ = "x.y.z"`` assignment. Captures the assigned
# string when it is a literal; the dynamic form
# ``__version__ = importlib.metadata.version(...)`` is not matched.
LITERAL_DUNDER_VERSION_RE: Final[re.Pattern[str]] = re.compile(
    r"""^\s*__version__\s*=\s*["']([^"']+)["']""",
    re.MULTILINE,
)

# Dynamic ``__version__`` resolution markers. Presence of any of these
# fragments indicates the runtime version derives from package metadata
# rather than a literal.
DYNAMIC_VERSION_MARKERS: Final[tuple[str, ...]] = (
    "importlib.metadata.version",
    "importlib_metadata.version",
    "metadata.version(",
    "version(__package__",
    'version("apothem"',
    "version('apothem'",
)


@dataclass(frozen=True)
class Finding:
    """One static-version site discovered in the project."""

    site_class: str
    path: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Matcher report for a single sweep of this validator.

    Pre-conditions: ``findings`` holds this module's frozen ``Finding``
    dataclasses. Post-conditions: ``passed`` is ``True`` exactly when
    ``findings`` is empty; :meth:`to_json` emits the serialised payload.
    """

    grep: str
    path: str | None
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    # Version-bearing sites read (README, site config, runtime module); the
    # command-line entry stamps it on the report as ``inspected``.
    inspected: int = 0

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, path, passed,
        findings}``; each finding is flattened through ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "path": self.path,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _strip_ref_params(url: str) -> str:
    """Remove git-ref query-parameter values from a badge URL.

    ``?branch=v1.2.3`` / ``?tag=v1.2.3`` / ``?ref=v1.2.3`` carry a git ref, not
    a displayed version; their values are dropped so the literal-version scan
    does not misread a dynamic build-status badge pinned to a release branch.
    A version embedded in the URL path is untouched.
    """
    return REF_PARAM_RE.sub("", url)


def _check_readme(root: Path, findings: list[Finding]) -> int:
    """Flag badge URLs in README that carry literal versions; return files read."""
    read = 0
    for candidate in README_CANDIDATES:
        readme = root / candidate
        if not readme.is_file():
            continue
        try:
            text = readme.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        read += 1
        for match in MARKDOWN_IMAGE_RE.finditer(text):
            url = match.group(1).strip()
            if "shields.io" not in url and "badge" not in url.lower():
                continue
            is_dynamic = any(marker in url for marker in SHIELDS_DYNAMIC_MARKERS)
            if is_dynamic:
                continue
            if LITERAL_VERSION_RE.search(_strip_ref_params(url)):
                findings.append(
                    Finding(
                        site_class="readme-badge",
                        path=str(readme.relative_to(root)),
                        detail=(
                            f"badge URL carries a literal version: {url!r}; "
                            "convert to a shields.io dynamic endpoint "
                            "(e.g., img.shields.io/npm/v/%40ahmed-g-gad%2Fapothem "
                            "or img.shields.io/github/v/release/ahmed-g-gad/apothem)"
                        ),
                    )
                )
    return read


def _check_site_config(root: Path, findings: list[Finding]) -> int:
    """Flag site config files declaring a literal ``version:``; return files read."""
    read = 0
    for candidate in SITE_CONFIG_CANDIDATES:
        config = root / candidate
        if not config.is_file():
            continue
        try:
            text = config.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        read += 1
        if any(marker in text for marker in DYNAMIC_VERSION_MARKERS):
            # The config imports a dynamic version-resolution helper; a
            # nearby literal `version:` key is almost certainly a fallback
            # default rather than the canonical source, so do not flag.
            continue
        for match in YAML_LITERAL_VERSION_RE.finditer(text):
            literal = match.group(1)
            if not LITERAL_VERSION_RE.search(literal):
                continue
            findings.append(
                Finding(
                    site_class="site-config",
                    path=str(config.relative_to(root)),
                    detail=(
                        f"site config declares a literal version: {literal!r}; "
                        'derive from importlib.metadata.version("apothem") '
                        "or an equivalent dynamic source"
                    ),
                )
            )
    return read


def _check_runtime_version(root: Path, findings: list[Finding]) -> int:
    """Flag a literal ``__version__`` in the runtime module; return files read."""
    module = root / RUNTIME_VERSION_MODULE
    if not module.is_file():
        return 0
    try:
        text = module.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    if any(marker in text for marker in DYNAMIC_VERSION_MARKERS):
        return 1
    match = LITERAL_DUNDER_VERSION_RE.search(text)
    if match is None:
        return 1
    findings.append(
        Finding(
            site_class="runtime-version",
            path=str(module.relative_to(root)),
            detail=(
                f"__version__ is a literal string {match.group(1)!r}; "
                "derive from importlib.metadata.version(__package__) so "
                "the runtime value tracks the installed package metadata"
            ),
        )
    )
    return 1


def check(root: Path) -> GrepResult:
    """Walk the three version-bearing site classes; return a structured result.

    Pre-conditions: ``root`` is the project root (the directory holding
    ``pyproject.toml`` or its closest ancestor).
    Post-conditions: ``result.passed`` is True iff every inspected site
    resolves dynamically (README badges hit shields.io dynamic endpoints,
    docs config derives version from package metadata, runtime
    ``__version__`` calls ``importlib.metadata.version`` or equivalent).
    """
    findings: list[Finding] = []
    inspected = _check_readme(root, findings)
    inspected += _check_site_config(root, findings)
    inspected += _check_runtime_version(root, findings)
    return GrepResult(
        grep=GREP_NAME,
        path=str(root),
        passed=not findings,
        findings=findings,
        inspected=inspected,
    )


def main(root: Path) -> int:
    """Run the check over *root*, print the report, return the exit code.

    Pre-conditions: ``root`` is the repository root to inspect.
    Post-conditions: the JSON report, stamped with ``inspected``, is written
    to stdout; the return is :data:`EXIT_PASS` when the sweep passed and
    :data:`EXIT_FAIL` otherwise (including a sweep that read no site).
    """
    # Imported here, not at module top: ``check()`` stays stdlib-only.
    from apothem.conformity._grep_base import finish_root_report

    result = check(root)
    return finish_root_report(
        result.to_json(), passed=result.passed, inspected=result.inspected
    )


def _main(argv: list[str]) -> int:
    from apothem.conformity._grep_base import parse_root_args

    return main(parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root)


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
