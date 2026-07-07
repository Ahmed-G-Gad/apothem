# SPDX-License-Identifier: MIT

"""Validate Markdown internal links against the on-disk reference graph.

Why this enforcement exists. Spec section 2.4 ratifies that every
emitted Markdown link is resolvable at the artifact's emission time.
Stale internal links (pointing at moved or removed paths) are findings
per the visual-leverage rule's section 4 staleness clause and per the
ten-dimension check's dimension 5 (orphanism / staleness). The pre-
emission gate's mechanical row catches dead internal-path references
before they leave the operator's hands.

Detection strategy. The validator parses Markdown link syntax
``[text](path)`` and ``[text](path#anchor)`` from the input body and
checks each resolvable internal reference:

- **Relative links** (``../foo.md``, ``foo/bar.md``) resolve against the
  source file's directory; a destination with no on-disk artifact is a
  finding.
- **Site-route links** of the form ``/docs/<path>`` (English, served at
  the site root) and ``/<locale>/docs/<path>`` (a non-default cohort
  locale) resolve against the Fumadocs page set under
  ``site/content/docs/``. ``/docs/a/b`` maps to
  ``site/content/docs/a/b.mdx`` or the folder-index page
  ``site/content/docs/a/b/index.mdx``; the locale form maps under the
  ``site/content/docs/<locale>/`` subtree. A route backed by neither file
  is a dead route — a user-facing 404 — and a finding, caught here rather
  than only by the site build. The page root is discovered by walking the
  source file's ancestors; when no ``site/content/docs`` ancestor exists
  (a Markdown body outside the site repo) ``/docs/`` routes stay out of
  scope.
- **Other root-absolute routes** (``/``, asset paths, well-known files)
  and **external references** (HTTP / HTTPS, ``mailto:``) are counted but
  not retrieved — their validity is the site build's or remote host's
  concern, not this matcher's.

The Fumadocs routing contract this mapping mirrors is declared at
``site/lib/source.ts`` (``baseUrl: '/docs'``, ``parser: 'dir'``,
``hideLocale: 'default-locale'``) and the locale cohort at
``site/lib/i18n.ts`` (``ROUTED_NON_DEFAULT_LOCALES``).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

# Markdown inline link shape: [text](destination "optional title"). Two
# destination forms per CommonMark:
#   * angle-bracketed ``<dest>`` — may contain spaces and ``)`` characters;
#   * bare ``dest`` — runs to the first whitespace or closing ``)``.
# The optional title may be double-quoted, single-quoted, or parenthesised.
# Capturing both dest forms into the same ``dest`` group (via two named
# sub-groups reconciled by ``_dest_of``) closes three silent-skip gaps in
# the prior bare-only pattern: a ``)`` inside an angle-bracketed dest, a
# space inside one, and a single-quoted or parenthesised title. Reference-
# style links (``[text][label]``) stay out of scope for the baseline pass.
LINK_RE: Final[re.Pattern[str]] = re.compile(
    r"\[(?P<text>[^\]]*)\]\("
    r"(?:<(?P<adest>[^>\n]*)>|(?P<dest>[^)\s]*))"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?"
    r"\s*\)"
)


def _dest_of(match: re.Match[str]) -> str:
    """Return the destination text from either the angle-bracket or bare form."""
    angle = match.group("adest")
    return angle if angle is not None else match.group("dest")


EXTERNAL_PREFIXES: Final[tuple[str, ...]] = (
    "http://",
    "https://",
    "mailto:",
    "ftp://",
    "ftps://",
)
GREP_NAME: Final[str] = "link-check"
RULE_ANCHOR: Final[str] = "rules/code-craft-markdown.md §6 Link Discipline"
EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2
STDIN_FLAG: Final[str] = "--stdin"

# --- Fumadocs site-route resolution -----------------------------------------
#
# Root-absolute links of the form ``/docs/<path>`` (English, served at the
# site root) and ``/<locale>/docs/<path>`` (a non-default cohort locale) are
# real published routes whose validity the conformity gate can check without a
# site build: the Fumadocs ``loader`` (``site/lib/source.ts``) maps each route
# to an on-disk page under ``site/content/docs/``. Every OTHER root-absolute
# route (``/``, ``/img/...``, ``/.well-known/...``) carries no such mapping and
# stays out of scope.

# Repo-root-relative path components of the Fumadocs page content root.
DOCS_CONTENT_ROOT_SEGMENTS: Final[tuple[str, ...]] = ("site", "content", "docs")
# The route segment that mounts the docs tree (``baseUrl: '/docs'``).
DOCS_ROUTE_PREFIX: Final[str] = "docs"
# Page-source suffixes Fumadocs loads (``.mdx`` primary, ``.md`` accepted). A
# route resolves when any leaf-page or folder-index candidate, in any of these
# suffixes, exists on disk.
PAGE_SUFFIXES: Final[tuple[str, ...]] = (".mdx", ".md")
# Non-default routed-locale URL segments — the ``/<locale>/docs/...`` prefixes.
# Mirrors ``ROUTED_NON_DEFAULT_LOCALES`` at ``site/lib/i18n.ts`` (the single
# source of truth for the locale cohort); ``en`` is omitted because
# ``hideLocale: 'default-locale'`` serves English at the unprefixed root.
# Cohort amendments route through structured inquiry there, then mirror here.
LOCALE_ROUTE_SEGMENTS: Final[frozenset[str]] = frozenset(
    {"es", "zh-cn", "pt-br", "fr", "de", "ja", "ko", "ru", "id", "hi", "ar"}
)


@dataclass(frozen=True)
class Finding:
    line: int
    destination: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    grep: str
    path: str | None
    passed: bool
    internal_count: int
    external_count: int
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        # snake_case payload keys, matching the dataclass attribute names and
        # the sibling matchers' convention (e.g. reference_token's
        # ``files_inspected``); no consumer parses the prior kebab-case keys.
        payload = {
            "grep": self.grep,
            "path": self.path,
            "passed": self.passed,
            "internal_count": self.internal_count,
            "external_count": self.external_count,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _is_external(destination: str) -> bool:
    return destination.startswith(EXTERNAL_PREFIXES)


def _strip_fragment(destination: str) -> str:
    return destination.split("#", 1)[0]


def _resolve_target(
    source: Path | None,
    destination: str,
) -> Path | None:
    """Resolve a relative destination to an on-disk path."""
    target = _strip_fragment(destination)
    if not target:
        # Anchor-only links (e.g., [foo](#section)) point inside the
        # source file; treat as resolved by construction.
        return source
    if source is None:
        return None
    return (source.parent / target).resolve()


def _find_docs_content_root(source: Path | None) -> Path | None:
    """Locate the ``site/content/docs`` page root above *source*, if any.

    Walks *source*'s resolved ancestors and returns the first that contains
    a ``site/content/docs`` directory. Returns None when *source* is None or
    no such ancestor exists (e.g. a Markdown body checked outside the site
    repo) — in which case ``/docs/`` routes stay out of scope, exactly as
    before this resolution was added.
    """
    if source is None:
        return None
    try:
        resolved = source.expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    for ancestor in resolved.parents:
        candidate = ancestor.joinpath(*DOCS_CONTENT_ROOT_SEGMENTS)
        if candidate.is_dir():
            return candidate
    return None


def _docs_route_targets(docs_root: Path, route: str) -> list[Path] | None:
    """Map a root-absolute ``/docs/...`` route to its on-disk page candidates.

    *route* is the destination with its fragment already stripped and a
    leading ``/``. Returns the candidate on-disk paths — the leaf page and
    the folder-index page, across the accepted page suffixes — when *route*
    is a ``/docs/<path>`` or ``/<locale>/docs/<path>`` site route; returns
    None for any other root-absolute path (out of scope). The caller treats
    a non-None list whose members all fail ``exists()`` as a dead route.
    """
    # Drop a query string and any trailing slash; the live corpus carries
    # neither, but tolerating them keeps a future ``/docs/a/`` or
    # ``/docs/a?x=1`` from being mis-flagged.
    path_part = route.split("?", 1)[0].rstrip("/")
    segments = [segment for segment in path_part.split("/") if segment]
    if segments and segments[0] == DOCS_ROUTE_PREFIX:
        locale: str | None = None
        rest = segments[1:]
    elif (
        len(segments) >= 2
        and segments[0] in LOCALE_ROUTE_SEGMENTS
        and segments[1] == DOCS_ROUTE_PREFIX
    ):
        locale = segments[0]
        rest = segments[2:]
    else:
        return None
    base = docs_root if locale is None else docs_root / locale
    if not rest:
        # Bare ``/docs`` (or ``/<locale>/docs``): the section landing page.
        return [base / f"index{suffix}" for suffix in PAGE_SUFFIXES]
    leaf = base.joinpath(*rest)
    candidates: list[Path] = []
    for suffix in PAGE_SUFFIXES:
        # The route as a page file: /docs/a/b -> site/content/docs/a/b.mdx.
        candidates.append(leaf.parent / f"{leaf.name}{suffix}")
        # The route as a section folder: -> site/content/docs/a/b/index.mdx.
        candidates.append(leaf / f"index{suffix}")
    return candidates


def _render_targets(docs_root: Path, targets: list[Path]) -> str:
    """Render candidate paths relative to the repo root for a finding message."""
    # docs_root == <repo>/site/content/docs; parents[2] is the repo root.
    try:
        repo_root = docs_root.parents[len(DOCS_CONTENT_ROOT_SEGMENTS) - 1]
    except IndexError:
        repo_root = docs_root
    rendered: list[str] = []
    for target in targets:
        try:
            rendered.append(str(target.relative_to(repo_root)).replace("\\", "/"))
        except ValueError:
            rendered.append(str(target))
    return " | ".join(rendered)


def check(
    content: str,
    path: Path | None = None,
) -> GrepResult:
    """Scan a Markdown body for internal-link reachability."""
    findings: list[Finding] = []
    internal = 0
    external = 0
    # The Fumadocs page root, discovered lazily on the first root-absolute
    # link so the common path (no ``/docs/`` links) pays no filesystem cost.
    docs_root: Path | None = None
    docs_root_computed = False

    for index, line in enumerate(content.splitlines(), start=1):
        for match in LINK_RE.finditer(line):
            destination = _dest_of(match)
            if not destination:
                # An empty destination (``[text]()`` or ``[text](<>)``) has
                # nothing to resolve; skip it rather than mis-count it.
                continue
            if _is_external(destination):
                external += 1
                continue
            stripped = _strip_fragment(destination)
            if stripped.startswith("/"):
                if not docs_root_computed:
                    docs_root = _find_docs_content_root(path)
                    docs_root_computed = True
                if docs_root is None:
                    # A Markdown body checked outside the site repo: the page
                    # set cannot be located, so ``/docs/`` routes are not
                    # checkable here. Counted like an external reference.
                    external += 1
                    continue
                targets = _docs_route_targets(docs_root, stripped)
                if targets is None:
                    # A non-``/docs/`` root-absolute route (site root, asset
                    # path, well-known file): route validity is the site
                    # build's concern, out of scope here.
                    external += 1
                    continue
                internal += 1
                if not any(target.exists() for target in targets):
                    findings.append(
                        Finding(
                            line=index,
                            destination=destination,
                            detail=(
                                "docs site route resolves to no page on disk "
                                f"(tried {_render_targets(docs_root, targets)})"
                            ),
                        )
                    )
                continue
            internal += 1
            resolved = _resolve_target(path, destination)
            if resolved is None:
                findings.append(
                    Finding(
                        line=index,
                        destination=destination,
                        detail="cannot resolve relative destination without source path",
                    )
                )
                continue
            if not resolved.exists():
                findings.append(
                    Finding(
                        line=index,
                        destination=destination,
                        detail=f"target does not exist on disk at {resolved}",
                    )
                )

    return GrepResult(
        grep=GREP_NAME,
        path=str(path) if path is not None else None,
        passed=not findings,
        internal_count=internal,
        external_count=external,
        findings=findings,
    )


def _read_input(argv: list[str]) -> tuple[str, Path | None]:
    if len(argv) >= 2 and argv[1] != STDIN_FLAG:
        path = Path(argv[1])
        return path.read_text(encoding="utf-8"), path
    return sys.stdin.read(), None


def _main(argv: list[str]) -> int:
    content, path = _read_input(argv)
    result = check(content, path)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
