# SPDX-License-Identifier: MIT

"""Flag mechanistic / harness-internal vocabulary in user-facing prose.

Why this enforcement exists. The plain-language rule requires user-facing
surfaces (READMEs, documentation pages, landing pages, install guides)
to read as natural product prose — never as a leak of harness identity,
plan-internal taxonomy, or implementation mechanism. Tokens like ``AI``,
``agent``, ``LLM``, ``attestation``, the process-tooling markers
``ratified`` and ``cutover-rehearsal``, the registered harness brand names
(``claude_code``, ``cursor``, ``gemini``, ``copilot``, ``windsurf``,
``codex``, ``hermes``), and plan-stage tokens (numeric stage labels, stream
labels, and zero-padded nested-stage labels) are mechanistic. They belong to
internal rules / commands / agents / plans surfaces; on the user-facing
surface they break the plain-language floor.

The product noun ``harness`` / ``harnesses`` is NOT forbidden — it is
apothem's central product domain ("host-agnostic AI-harness configuration
manager"), a domain carve-out per the plain-language rule's §2.

Scope. Corpus-level standalone validator. Walks the working tree under
the supplied root and inspects ONLY in-scope surfaces:

- ``README.md`` at the repository root.
- ``site/content/docs/**/*.{md,mdx}`` — the documentation tree.

OUT of scope (skipped wholesale): technical documentation routes
(``blog/``, ``comparison/``, ``reference/``, the agent-architecture
concept page, and the instruction-surface convention references),
generated reference inventory blocks, ``rules/**``,
``commands/**``, ``agents/**``, ``skills/**``, ``.plans/**``, ``tests/**``,
``scripts/**``, every ``*.py`` / ``*.sh`` / ``*.ps1`` source file,
``CLAUDE.md``, ``.github/copilot-instructions.md``. The dev-facing surface
is permissive by design — only the general operator-facing prose is held
to the plain-language bar.

Detection. Each forbidden token is a word-boundary case-insensitive
match. Matches inside fenced code blocks (triple-backtick) are excluded:
docs legitimately quote command names, sample config, and tool output
inside fences. Inline-code (single-backtick) spans are NOT excluded —
inline code in user-facing prose is the typical leak surface and the
matcher catches it intentionally.

Exit semantics. Exits 0 when zero findings across every in-scope file;
exits 2 on any finding. The exit-2 convention matches the conformity-
gate orchestrator's EXIT_FAIL constant.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "plain-language-grep"
RULE_ANCHOR: Final[str] = "rules/plain-language.md — user-facing prose"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Forbidden vocabulary on user-facing prose surfaces. Tokens are matched
# case-insensitively at word boundaries. Multi-word tokens (e.g.,
# ``claude code``) are matched as literal phrases.
_FORBIDDEN_TOKENS: Final[tuple[str, ...]] = (
    # Mechanistic generics.
    "AI",
    "agent",
    "agents",
    "LLM",
    "LLMs",
    "attestation",
    "attestations",
    # Process-tooling vocabulary (plan / governance markers that leak the
    # internal process onto the user-facing surface). ``cutover-rehearsal``
    # carries a hyphen; it is ``re.escape``d into the alternation, so the
    # hyphen is matched literally.
    "ratified",
    "cutover-rehearsal",
    # Registered harness identifiers (both snake_case slug and brand form).
    "claude_code",
    "claude-code",
    "cursor",
    "gemini",
    "copilot",
    "windsurf",
    "codex",
    "hermes",
)

# Plan-stage taxonomy tokens. These are regex patterns (not literal
# words), so they live separately and are joined into the master regex
# verbatim rather than via ``re.escape``.
_PLAN_PHASE_PATTERNS: Final[tuple[str, ...]] = (
    r"phase\s+\d+",  # numbered stage labels
    r"stream\s+[A-Z]\b",  # "stream A", "Stream B"
    r"\b\d{2}[A-Z]\b",  # zero-padded nested-stage tokens
)

_LITERAL_GROUP: Final[str] = "|".join(re.escape(t) for t in _FORBIDDEN_TOKENS)
_PATTERN_GROUP: Final[str] = "|".join(_PLAN_PHASE_PATTERNS)

# Combined regex: word-boundary anchored case-insensitive scan.
_FORBIDDEN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:" + _LITERAL_GROUP + r"|" + _PATTERN_GROUP + r")\b"
)

# Fenced code block delimiter — matches a line whose first non-whitespace
# content is ```, so fences indented under list items (valid CommonMark) are
# recognized too, not only column-0 fences. Opening and closing fences both
# match; the matcher toggles in_fence state on each occurrence.
_CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^[ \t]*```")

# In-scope path predicates. The matcher walks the corpus and applies
# these predicates to every Markdown / MDX file to decide whether to scan it.
_DOCS_PATH_PARTS: Final[tuple[str, ...]] = ("site", "content", "docs")
_README_FILENAME: Final[str] = "README.md"
_MARKDOWN_SUFFIXES: Final[frozenset[str]] = frozenset({".md", ".mdx"})
_TECHNICAL_DOC_PREFIXES: Final[tuple[str, ...]] = (
    "site/content/docs/blog/",
    "site/content/docs/comparison/",
    "site/content/docs/reference/",
)
_TECHNICAL_DOC_FILES: Final[frozenset[str]] = frozenset(
    {
        "site/content/docs/reference/ai-conventions.mdx",
        "site/content/docs/architecture/agents.mdx",
        "site/content/docs/architecture/cohort-packaging-contract.mdx",
        "site/content/docs/architecture/harness-adapter-abstraction.mdx",
        "site/content/docs/architecture/shared-profile-schema.mdx",
        "site/content/docs/concepts/agent-architecture.mdx",
        "site/content/docs/how-to/installer-environment-variables.mdx",
        "site/content/docs/reference/plans-discipline.mdx",
    }
)
_PRODUCT_INDEX_PATH: Final[str] = "site/content/docs/index.mdx"
# Cohort-locale segments mirrored under ``site/content/docs/<locale>/``. A
# locale subtree is a translation of the English source, so every EN-path
# exclusion predicate (technical-doc prefixes / files, harness-page allowlist,
# product index) applies identically to its locale mirror. The matcher strips
# the locale segment before exclusion matching so a translated comparison /
# reference page is not false-flagged for the harness brand names its English
# source legitimately carries.
_COHORT_LOCALE_SEGMENTS: Final[frozenset[str]] = frozenset(
    {"zh-cn", "es", "pt-br", "fr", "de", "ja", "ko", "ru", "id", "ar", "hi"}
)
# Documentation pages carry these region markers in the comment syntax of the
# host docs framework: the HTML-comment form (``<!-- ... -->``) for Markdown
# pages and the JSX-comment form (``{/* ... */}``) for MDX pages. Both forms are
# recognized so the exclusion regions fire regardless of the page's extension.
_GENERATED_REFERENCE_START: Final[frozenset[str]] = frozenset(
    {
        "<!-- apothem:generated-reference:start -->",
        "{/* apothem:generated-reference:start */}",
    }
)
_GENERATED_REFERENCE_END: Final[frozenset[str]] = frozenset(
    {
        "<!-- apothem:generated-reference:end -->",
        "{/* apothem:generated-reference:end */}",
    }
)
# The changelog page injects the root ``CHANGELOG.md`` body between these
# markers at build time. The release history records the harness brand names
# and product vocabulary as factual release-note content (the same content the
# root ``CHANGELOG.md`` carries), not user-facing landing prose, so it is
# skipped exactly as the generated-reference block is.
_CHANGELOG_START: Final[frozenset[str]] = frozenset(
    {
        "<!-- apothem:changelog:start -->",
        "{/* apothem:changelog:start */}",
    }
)
_CHANGELOG_END: Final[frozenset[str]] = frozenset(
    {
        "<!-- apothem:changelog:end -->",
        "{/* apothem:changelog:end */}",
    }
)

# Per-harness-page brand allowlist. A page at
# ``site/content/docs/harnesses/<stem>.mdx``
# is the canonical product description for that harness; brand-token
# references to that harness are load-bearing (page title, frontmatter
# ``description``, prose product identification, inline-code CLI paths,
# table cells) and cannot relocate inside fenced code blocks without
# breaking the rendered surface. The matcher exempts the brand tokens
# in the stem's allowlist when the finding's path resolves to the
# corresponding harness page. Tokens are lower-cased and matched
# case-insensitively against the finding's ``match`` field.
_HARNESS_PAGE_ALLOWED_BRANDS: Final[dict[str, frozenset[str]]] = {
    "antigravity": frozenset({"gemini"}),  # Google Antigravity bundles Gemini.
    # claude-code's install propagation lists the canonical sibling
    # directories ``agents/`` ``commands/`` ``rules/`` ``skills/`` etc.;
    # the noun ``agents`` here names the Claude Code harness directory,
    # not the mechanistic ``AI agent`` vocabulary.
    "claude-code": frozenset({"claude-code", "claude_code", "agents"}),
    # CodeBuddy's page enumerates the apothem cohort surface (skills,
    # commands, agents, hooks); the noun ``agents`` names the cohort class,
    # not the mechanistic ``AI agent`` vocabulary.
    "codebuddy": frozenset({"agents"}),
    # OpenAI Codex's canonical config filename is ``AGENTS.md``; the
    # noun on this page describes the file, not the mechanistic agent.
    "codex": frozenset({"codex", "agents"}),
    "cursor": frozenset({"cursor"}),
    "gemini-cli": frozenset({"gemini"}),
    "github-copilot": frozenset({"copilot"}),
    # GLM's vendor is Z.ai; the ``ai`` token in the ``Z.ai`` brand name and
    # the ``api.z.ai`` backend URLs names the vendor, not the mechanistic
    # ``AI`` vocabulary the plain-language rule prohibits.
    "glm": frozenset({"ai"}),
    # ``Hermes Agent`` is the canonical product name (proper noun).
    "hermes": frozenset({"hermes", "agent"}),
    # Kiro's ``Agent Hooks`` is a documented product feature (proper noun).
    "kiro": frozenset({"agent"}),
    "windsurf": frozenset({"windsurf"}),
    # Zed's canonical instruction filename is ``AGENTS.md`` and its product
    # surface is the agent panel; the nouns name the file/feature, not the
    # mechanistic vocabulary.
    "zed": frozenset({"agent", "agents"}),
}
_HARNESS_PAGE_PARENT: Final[str] = "site/content/docs/harnesses"

# Generic mechanistic nouns that the per-harness-page allowlist legitimately
# carries on a brand's OWN product page (``Hermes Agent`` proper noun, the
# ``AGENTS.md`` filename on the Codex / Zed pages, the cohort-directory noun on
# the Claude Code / CodeBuddy pages) but that MUST NOT be blanket-exempted on
# the README / product-index surface. On the README a bare ``agent`` / ``agents``
# in prose is the mechanistic leak the plain-language rule prohibits; only the
# directory / cohort-enumeration uses of ``agents`` clear, and those clear via
# the line-scoped ``_is_directory_or_cohort_reference`` carve-out below — never
# via a blanket token exemption.
_GENERIC_MECHANISTIC_NOUNS: Final[frozenset[str]] = frozenset({"agent", "agents"})

# README brand allowlist. The repository ``README.md`` is the apothem
# product index: its CLI-usage section MUST enumerate the supported
# ``--harness <name>`` flag values for the documentation to be useful,
# and those flag values are the canonical adapter-package identifiers
# under ``src/apothem/harnesses/``. References to those identifiers
# at the README surface are load-bearing product domain — not the
# narrative-vocabulary class the plain-language rule prohibits. The set is
# the union of every harness-page allowlist (minus the generic mechanistic
# nouns, which are page-scoped, never README-blanket) plus the kebab-case CLI
# variants (e.g. ``claude-code``) so adapter identifiers spelled either
# in their snake_case Python form or their kebab-case CLI form clear the
# matcher. ``agent`` / ``agents`` are deliberately excluded — the generic
# noun on the README is held to the line-scoped directory / cohort carve-out,
# not a blanket pass.
_README_ALLOWED_BRANDS: Final[frozenset[str]] = (
    frozenset(
        {token for tokens in _HARNESS_PAGE_ALLOWED_BRANDS.values() for token in tokens}
        | {
            "claude-code",
            "claude_code",
            "cursor",
            "codex",
            "gemini-cli",
            "github-copilot",
            "hermes",
            "opencode",
            "qwen-code",
            "qwen_code",
            "windsurf",
            "antigravity",
        }
    )
    - _GENERIC_MECHANISTIC_NOUNS
)


@dataclass(frozen=True)
class Finding:
    """One forbidden token in a user-facing prose surface."""

    path: str
    line: int
    match: str
    context: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for a single corpus sweep."""

    grep: str
    root: str
    scanned_count: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, scanned_count,
        passed, findings}``; each finding is flattened through
        ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "scanned_count": self.scanned_count,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _is_user_facing(path: Path, root: Path) -> bool:
    """Return True iff ``path`` is an in-scope user-facing Markdown surface.

    In scope:
        - ``<root>/README.md``
        - any ``*.md`` / ``*.mdx`` under ``<root>/site/content/docs/``

    Out of scope: every other path. The matcher is deliberately permissive
    on dev-facing surfaces.
    """
    if path.suffix not in _MARKDOWN_SUFFIXES:
        return False
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    parts = rel.parts
    if len(parts) == 1 and parts[0] == _README_FILENAME:
        return True
    normalised = _delocalise_docs_path(rel.as_posix())
    if normalised in _TECHNICAL_DOC_FILES:
        return False
    if any(normalised.startswith(prefix) for prefix in _TECHNICAL_DOC_PREFIXES):
        return False
    return parts[: len(_DOCS_PATH_PARTS)] == _DOCS_PATH_PARTS


def _delocalise_docs_path(norm: str) -> str:
    """Strip a cohort-locale segment from a docs path for exclusion matching.

    ``site/content/docs/<locale>/comparison/index.mdx`` normalises to
    ``site/content/docs/comparison/index.mdx`` so the EN-path exclusion
    predicates apply identically to every locale mirror. Non-docs paths and
    English-root docs paths pass through unchanged.
    """
    prefix = "site/content/docs/"
    if not norm.startswith(prefix):
        return norm
    head, slash, tail = norm[len(prefix) :].partition("/")
    if slash and head in _COHORT_LOCALE_SEGMENTS:
        return prefix + tail
    return norm


def _harness_page_allowlist(rel_path: str) -> frozenset[str]:
    """Return the allowed-brand token set for a harness-page surface.

    A page at ``site/content/docs/harnesses/<stem>.mdx`` may freely reference its own
    canonical brand identifier - the page IS the product description.
    Returns the lower-cased token set from
    ``_HARNESS_PAGE_ALLOWED_BRANDS[stem]`` when the path matches the
    harness-page parent; ``frozenset()`` otherwise (no exemption).
    """
    norm = _delocalise_docs_path(rel_path.replace("\\", "/"))
    if norm == _README_FILENAME:
        return _README_ALLOWED_BRANDS
    if norm == _PRODUCT_INDEX_PATH:
        return _README_ALLOWED_BRANDS
    if not norm.startswith(_HARNESS_PAGE_PARENT + "/"):
        return frozenset()
    stem = Path(norm).stem
    return _HARNESS_PAGE_ALLOWED_BRANDS.get(stem, frozenset())


# Markdown link URL ranges — carve-out class. Canonical filename slugs
# referenced inside a link URL (``[text](url)``, ``![alt](url)``) or a
# link-reference definition (``[id]: url``) are addressing the on-disk
# artifact, not asserting the vocabulary in prose. Matches whose offset
# falls inside one of these URL spans are excluded from the finding set
# alongside fenced code blocks. The link text itself remains in scope.
_LINK_URL_RE: Final[re.Pattern[str]] = re.compile(
    r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)"
)
_LINK_REF_RE: Final[re.Pattern[str]] = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)")


def _link_url_spans(line: str) -> list[tuple[int, int]]:
    """Return (start, end) spans of every markdown link / reference URL.

    Matches:
    - Inline link / image URL: ``[text](url)`` / ``![alt](url)``; the
      URL span is the capture group (excludes the parens themselves).
    - Reference definition: ``[id]: url`` at line start (optionally
      indented). The URL span is the capture group.
    """
    spans: list[tuple[int, int]] = []
    for m in _LINK_URL_RE.finditer(line):
        spans.append(m.span(1))
    ref = _LINK_REF_RE.match(line)
    if ref is not None:
        spans.append(ref.span(1))
    return spans


# Sibling cohort-directory names. When the generic noun ``agents`` is
# enumerated alongside two or more of these on the same line, it names the
# cohort directory class (``skills, commands, agents, hooks``), not the
# mechanistic ``AI agent`` vocabulary. Two siblings is the threshold so a
# single co-occurrence of a common word does not trigger a false carve-out.
_COHORT_DIRECTORY_SIBLINGS: Final[tuple[str, ...]] = (
    "commands",
    "rules",
    "skills",
    "hooks",
    "templates",
)
_COHORT_SIBLING_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:" + "|".join(_COHORT_DIRECTORY_SIBLINGS) + r")\b"
)

# Path-separator characters that, when adjacent to the matched token, mark it
# as a directory reference (``agents/``, ``~/.agents``, ``.agents``,
# ``\agents``) rather than a prose noun.
_PATH_SEPARATORS: Final[frozenset[str]] = frozenset({"/", "\\", "."})


def _is_directory_or_cohort_reference(line: str, match: re.Match[str]) -> bool:
    """Return True iff the matched generic noun is a directory / cohort use.

    The line-scoped carve-out for ``agent`` / ``agents`` on the README and
    product-index surface. Two recognised forms clear:

    - **Directory reference.** The token is immediately adjacent to a path
      separator on either side — ``agents/``, ``/agents``, ``.agents``,
      ``\\agents`` — including the backticked ```agents/``` form
      (the backtick is not the separator; the trailing ``/`` is). This names
      an on-disk directory, not the mechanistic vocabulary.
    - **Cohort-directory enumeration.** The token co-occurs on the same line
      with two or more sibling cohort-directory names
      (``commands`` / ``rules`` / ``skills`` / ``hooks`` / ``templates``),
      e.g. ``skills, commands, agents, hooks``. This names the cohort
      directory class, not the mechanistic vocabulary.

    Applies only to the generic nouns in ``_GENERIC_MECHANISTIC_NOUNS``; every
    other forbidden token (harness identifiers, ``AI`` / ``LLM`` / process
    markers) is unaffected and never clears via this carve-out.
    """
    if match.group().lower() not in _GENERIC_MECHANISTIC_NOUNS:
        return False
    start, end = match.start(), match.end()
    before = line[start - 1] if start > 0 else ""
    after = line[end] if end < len(line) else ""
    if before in _PATH_SEPARATORS or after in _PATH_SEPARATORS:
        return True
    siblings = sum(1 for _ in _COHORT_SIBLING_RE.finditer(line))
    return siblings >= 2


def _scan_file(path: Path, root: Path) -> list[Finding]:
    """Scan one Markdown file; return findings outside fenced code blocks.

    Applies the per-harness-page brand allowlist: when ``path`` resolves
    to ``site/content/docs/harnesses/<stem>.mdx`` and the matched token is in the
    stem's allowed-brand set, the match is skipped. Matches whose offset
    falls inside a markdown link URL (``[text](url)``) or link-reference
    definition (``[id]: url``) are also excluded — the URL addresses an
    on-disk artifact, not the vocabulary in prose.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        rel_path = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        rel_path = str(path)
    allowlist = _harness_page_allowlist(rel_path)
    findings: list[Finding] = []
    inside_fence = False
    inside_generated_reference = False
    inside_changelog = False
    for line_index, line in enumerate(content.splitlines(), start=1):
        if _CODE_FENCE_RE.match(line):
            inside_fence = not inside_fence
            continue
        if line.strip() in _GENERATED_REFERENCE_START:
            inside_generated_reference = True
            continue
        if line.strip() in _GENERATED_REFERENCE_END:
            inside_generated_reference = False
            continue
        if line.strip() in _CHANGELOG_START:
            inside_changelog = True
            continue
        if line.strip() in _CHANGELOG_END:
            inside_changelog = False
            continue
        if inside_fence:
            continue
        if inside_generated_reference or inside_changelog:
            continue
        url_spans = _link_url_spans(line)
        for match in _FORBIDDEN_RE.finditer(line):
            if match.group().lower() in allowlist:
                continue
            if _is_directory_or_cohort_reference(line, match):
                continue
            start = match.start()
            if any(s <= start < e for s, e in url_spans):
                continue
            findings.append(
                Finding(
                    path=rel_path,
                    line=line_index,
                    match=match.group(),
                    context=line.strip(),
                )
            )
    return findings


def check(root: Path) -> GrepResult:
    """Walk the corpus under ``root``; flag forbidden tokens in user prose.

    Pre-conditions: ``root`` is the repository root (or an arbitrary
    subtree to scan).
    Post-conditions: ``result.passed`` is True iff every in-scope file
    contained zero forbidden tokens outside fenced code blocks.
    """
    findings: list[Finding] = []
    scanned = 0
    candidates = sorted(
        p for suffix in _MARKDOWN_SUFFIXES for p in root.rglob(f"*{suffix}")
    )
    for path in candidates:
        if not path.is_file():
            continue
        if not _is_user_facing(path, root):
            continue
        scanned += 1
        findings.extend(_scan_file(path, root))
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        scanned_count=scanned,
        passed=not findings,
        findings=findings,
    )


def _read_input(argv: list[str]) -> Path:
    if len(argv) >= 2:
        return Path(argv[1])
    return Path.cwd()


def _main(argv: list[str]) -> int:
    root = _read_input(argv)
    result = check(root)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
