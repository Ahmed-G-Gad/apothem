# SPDX-License-Identifier: MIT

"""Unified conformance / security auditor — config scan, secret detection, conformance.

This module is the single auditor that subsumes the standalone conformity
validators and the machinable subset of the audit / review commands. It scans
a configuration file (or any text artifact), detects secret literals against a
closed, enumerated catalog, and applies rule-based conformance checks to the
parsed structure. Every result is a :class:`Finding`.

The auditor is **advisory by default**: :func:`audit` reports findings without
blocking, and the standalone CLI exits zero even with findings present unless
``--strict`` (or the ``APOTHEM_AUDITOR_STRICT`` environment opt-in) is set. Every
finding carries a definitive ``next_step`` — the determinant move the operator
can take. A malformed config yields a structured finding, never a crash; an
internal auditor failure is itself reported as a ``category = error`` finding,
never swallowed.

The serialized run (:meth:`Findings.to_dict`) validates against the bundled
``advisory-finding.schema.json`` contract, the same shape the changed-path
audit entry point (:func:`pr_audit`) emits.

Standalone invocation (no package installation required; the plugin tree is
self-contained)::

    python -m apothem.lib.auditor <path> [<path> ...] [--strict] [--json]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal, cast

from jsonschema import Draft202012Validator

from apothem.lib.schema_errors import format_schema_errors
from apothem.schemas import advisory_finding_schema_path

Category = Literal["config-scan", "secret", "conformance", "error"]
Severity = Literal["HIGH", "MEDIUM", "LOW"]

#: Opt-in environment variable that promotes the advisory default to strict.
STRICT_ENV: Final[str] = "APOTHEM_AUDITOR_STRICT"
_STRICT_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})

#: Config suffixes the structured scanner knows how to parse. Everything else is
#: still secret-scanned line-by-line as plain text.
_YAML_SUFFIXES: Final[frozenset[str]] = frozenset({".yaml", ".yml"})
_JSON_SUFFIXES: Final[frozenset[str]] = frozenset({".json"})
_TOML_SUFFIXES: Final[frozenset[str]] = frozenset({".toml"})

#: Substrings that mark a token as an obvious placeholder / example, not a
#: live secret, used to suppress the high-entropy heuristic's false positives.
_PLACEHOLDER_HINTS: Final[tuple[str, ...]] = (
    "example",
    "placeholder",
    "dummy",
    "redacted",
    "your-",
    "xxxx",
    "changeme",
    "<",
    "...",
)

#: Owner-identity strings that legitimately appear in the leading SPDX header
#: comment and maintainer-identity surfaces and must never be flagged as secrets.
_IDENTITY_ALLOWLIST: Final[tuple[str, ...]] = (
    "ahmedgad.com",
    "me@ahmedgad.com",
    "github.com/ahmed-g-gad",
    "ahmed-g-gad",
)

#: Universal-deny grant patterns: a conformance rule flags a config that grants
#: one of these in a permission / allow surface (the universal-deny floor).
_DENIED_GRANT_PATTERNS: Final[tuple[tuple[str, str], ...]] = (
    (r"rm\s+-rf", "destructive recursive removal"),
    (r"\bsudo\b", "privilege escalation"),
    (r"git\s+push\s+--force", "history-rewriting force push"),
    (r"\.env\b", "secret-file read access"),
    (r"~/\.ssh", "ssh-credential read access"),
    (r"\beval\b", "arbitrary code evaluation"),
)


class AuditorError(ValueError):
    """Raised when the auditor's own output fails its schema contract."""


@dataclass(frozen=True)
class Location:
    """Where a finding was found."""

    path: str
    line: int | None = None
    column: int | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the schema-shaped location mapping (omitting absent fields)."""
        out: dict[str, object] = {"path": self.path}
        if self.line is not None:
            out["line"] = self.line
        if self.column is not None:
            out["column"] = self.column
        return out


@dataclass(frozen=True)
class Finding:
    """A single advisory finding, shared by all three auditor capabilities."""

    id: str
    category: Category
    severity: Severity
    location: Location
    message: str
    next_step: str

    def to_dict(self) -> dict[str, object]:
        """Return the schema-shaped finding mapping."""
        return {
            "id": self.id,
            "category": self.category,
            "severity": self.severity,
            "location": self.location.to_dict(),
            "message": self.message,
            "next_step": self.next_step,
        }

    def _order_key(self) -> tuple[str, int, str, str]:
        """Deterministic sort key: path, line, category, id."""
        return (self.location.path, self.location.line or 0, self.category, self.id)


@dataclass(frozen=True)
class SecretPattern:
    """One entry in the closed secret-pattern catalog."""

    label: str
    match_rule: str
    severity: Severity = "HIGH"
    #: When ``True`` the rule is the Shannon-entropy heuristic, not a literal regex
    #: match; the detector applies the entropy gate and placeholder suppression.
    entropy: bool = False
    _compiled: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Compile ``match_rule`` once and cache it on the frozen instance.

        Compiling at construction rather than per :meth:`search` call keeps the
        cost off the hot scanning loop, where one pattern is applied across
        every file. ``object.__setattr__`` is required because the dataclass is
        frozen; the assignment is the documented escape hatch for a derived
        field.
        """
        object.__setattr__(self, "_compiled", re.compile(self.match_rule))

    def search(self, text: str) -> Iterable[re.Match[str]]:
        """Yield every non-overlapping match of this pattern in *text*."""
        return self._compiled.finditer(text)


#: The closed secret-pattern catalog. Each pattern carries a ``label`` and a
#: ``match_rule``; together they are the exhaustive set the auditor detects.
#: Excluded classes are attested in :data:`SECRET_PATTERNS_NA`.
SECRET_PATTERNS: Final[tuple[SecretPattern, ...]] = (
    SecretPattern("aws-access-key-id", r"\bAKIA[0-9A-Z]{16}\b"),
    SecretPattern("github-personal-token", r"\bghp_[A-Za-z0-9]{36}\b"),
    SecretPattern("github-oauth-token", r"\bgho_[A-Za-z0-9]{36}\b"),
    SecretPattern("github-app-token", r"\b(?:ghs|ghu|ghr)_[A-Za-z0-9]{36}\b"),
    SecretPattern("openai-style-api-key", r"\bsk-[A-Za-z0-9]{32,}\b"),
    SecretPattern("google-api-key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    SecretPattern("slack-token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    SecretPattern(
        "jwt",
        r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b",
    ),
    SecretPattern(
        "pem-private-key",
        r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----",
    ),
    SecretPattern(
        "high-entropy-token",
        r"[A-Za-z0-9_+/=\-]{40,}",
        severity="LOW",
        entropy=True,
    ),
)

#: Secret classes the catalog explicitly does NOT cover (the N/A attestation). A
#: downstream catalog-assembly step (the repo-wide sync) consumes this list when
#: deciding whether to widen coverage.
SECRET_PATTERNS_NA: Final[tuple[str, ...]] = (
    "oauth-client-secrets (no distinctive prefix)",
    "database-connection-strings (user:pass@host)",
    "azure / microsoft cloud credentials",
    "gcp-service-account-json keys",
    "stripe / twilio api keys",
    "ssh host keys / known_hosts entries",
    "pkcs#8 / sec1 private keys outside the PEM armor",
)

#: Minimum Shannon entropy (bits / char) for the high-entropy heuristic to fire.
_ENTROPY_THRESHOLD: Final[float] = 4.5


@dataclass(frozen=True)
class Findings:
    """The result of an audit run — the schema-shaped output contract."""

    findings: tuple[Finding, ...]
    strict: bool

    @property
    def summary(self) -> dict[str, int]:
        """Aggregate finding counts by severity."""
        high = sum(1 for f in self.findings if f.severity == "HIGH")
        medium = sum(1 for f in self.findings if f.severity == "MEDIUM")
        low = sum(1 for f in self.findings if f.severity == "LOW")
        return {"total": len(self.findings), "high": high, "medium": medium, "low": low}

    @property
    def present(self) -> bool:
        """True when at least one finding was produced."""
        return bool(self.findings)

    def to_dict(self) -> dict[str, object]:
        """Return the full schema-shaped run mapping (``advisory-finding`` schema)."""
        return {
            "findings": [f.to_dict() for f in self.findings],
            "strict": self.strict,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class PrAuditInput:
    """Input for a changed-path audit (a CI / pull-request audit caller).

    The caller hands the auditor the set of changed configuration paths plus
    repository context (branch, base ref, repo identity); the auditor returns
    the same :class:`Findings` shape the standalone CLI produces.
    """

    changed_paths: tuple[Path, ...]
    repo_context: Mapping[str, object] = field(default_factory=dict)
    strict: bool = False


def _schema() -> dict[str, object]:
    """Load and parse the advisory-finding output schema."""
    raw = advisory_finding_schema_path().read_text(encoding="utf-8")
    return cast("dict[str, object]", json.loads(raw))


def validate_findings(data: Mapping[str, object]) -> None:
    """Validate a serialized run against the advisory-finding schema.

    Args:
        data: A :meth:`Findings.to_dict` mapping.

    Raises:
        AuditorError: When *data* violates the schema; the message lists every
            validation error discovered.
    """
    validator = Draft202012Validator(_schema())
    details = format_schema_errors(validator, dict(data))
    if details:
        raise AuditorError(f"auditor output violates schema: {details}")


def resolve_strict(flag: bool) -> bool:
    """Resolve the effective strict mode from the CLI flag and the env opt-in.

    Strict is enabled when the ``--strict`` flag is passed OR the
    ``APOTHEM_AUDITOR_STRICT`` environment variable is truthy. The shipped default
    is advisory (``False``).
    """
    if flag:
        return True
    return os.environ.get(STRICT_ENV, "").strip().lower() in _STRICT_TRUTHY


def _shannon_entropy(token: str) -> float:
    """Return the Shannon entropy (bits / char) of *token*."""
    if not token:
        return 0.0
    counts: dict[str, int] = {}
    for char in token:
        counts[char] = counts.get(char, 0) + 1
    length = len(token)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def _is_allowlisted(text: str) -> bool:
    """True when *text* contains an owner-identity allowlist token."""
    return any(token in text for token in _IDENTITY_ALLOWLIST)


def _looks_like_placeholder(token: str) -> bool:
    """True when *token* is an obvious example / placeholder, not a live secret."""
    lowered = token.lower()
    return any(hint in lowered for hint in _PLACEHOLDER_HINTS)


# --- Capability 1: configuration-file scanning ------------------------------


def scan_config(path: Path) -> tuple[object | None, Finding | None]:
    """Parse a harness configuration file into an inspectable structure.

    Args:
        path: The configuration file to read.

    Returns:
        A ``(structure, finding)`` pair. On success ``structure`` is the parsed
        object and ``finding`` is ``None``. On a missing, unreadable, or malformed
        file ``structure`` is ``None`` and ``finding`` is a structured
        ``config-scan`` finding — never a raised exception.
    """
    if not path.is_file():
        return None, Finding(
            id="config-unreadable",
            category="config-scan",
            severity="MEDIUM",
            location=Location(path=str(path)),
            message=f"configuration path does not exist or is not a file: {path}",
            next_step=f"create the file at {path} or correct the path passed to the auditor.",
        )
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, Finding(
            id="config-unreadable",
            category="config-scan",
            severity="MEDIUM",
            location=Location(path=str(path)),
            message=f"configuration file is not readable as UTF-8 text: {exc}",
            next_step="verify the file is UTF-8 encoded and readable, then re-run the auditor.",
        )

    suffix = path.suffix.lower()
    try:
        structure = _parse_structure(text, suffix)
    except _ParseError as exc:
        return None, Finding(
            id="config-malformed",
            category="config-scan",
            severity="MEDIUM",
            location=Location(path=str(path), line=exc.line),
            message=f"configuration file is malformed ({suffix or 'text'}): {exc}",
            next_step="fix the reported syntax error; the auditor parses the file once it is well-formed.",
        )
    return structure, None


class _ParseError(Exception):
    """Internal: a configuration file failed to parse."""

    def __init__(self, message: str, line: int | None = None) -> None:
        """Record the parse failure and, where the parser reported one, its line.

        Pre-conditions: ``message`` is the underlying parser's error text.
        Post-conditions: ``line`` is the 1-based line the parser blamed, or
        ``None`` when the format gave no position — so a caller renders a
        located error where possible and a bare one otherwise, never a
        fabricated line number.
        """
        super().__init__(message)
        self.line = line


def _parse_structure(text: str, suffix: str) -> object:
    """Parse *text* by *suffix*; raise :class:`_ParseError` on malformed input."""
    if suffix in _JSON_SUFFIXES:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise _ParseError(str(exc), exc.lineno) from exc
    if suffix in _YAML_SUFFIXES:
        import yaml  # vendored; deferred so non-YAML scans never import it

        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise _ParseError(str(exc)) from exc
    if suffix in _TOML_SUFFIXES:
        try:
            # tomllib is stdlib only from 3.11; on 3.10 expose raw text.
            # The dual-code ignore keeps both type-check contexts clean:
            # import-not-found fires under --python-version=3.10 (typeshed
            # gates tomllib to 3.11+), unused-ignore self-suppresses where
            # the interpreter-version context resolves the stub.
            import tomllib  # type: ignore[import-not-found, unused-ignore]
        except ModuleNotFoundError:
            return {"_raw": text}

        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise _ParseError(str(exc)) from exc
    # Unknown / plain-text config: expose the raw text for line-level scanning.
    return {"_raw": text}


# --- Capability 2: secret-pattern detection ---------------------------------


def detect_secrets(path: Path, text: str) -> list[Finding]:
    """Detect secret literals in *text* against the closed catalog.

    Args:
        path: The artifact the text came from (for finding locations).
        text: The raw file content, scanned line by line.

    Returns:
        One finding per detected secret, deterministically ordered.
    """
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in SECRET_PATTERNS:
            for match in pattern.search(line):
                token = match.group(0)
                # Allowlist at match granularity, never line granularity: a
                # live token sharing a line with the owner identity must
                # still be scanned — only a matched token that itself embeds
                # an identity value is the owner's own data.
                if _is_allowlisted(token):
                    continue
                if pattern.entropy:
                    if _looks_like_placeholder(token):
                        continue
                    if _shannon_entropy(token) < _ENTROPY_THRESHOLD:
                        continue
                    # Skip tokens a named pattern already owns (dedupe).
                    if _matched_by_named_pattern(token):
                        continue
                findings.append(
                    Finding(
                        id=f"secret-{pattern.label}",
                        category="secret",
                        severity=pattern.severity,
                        location=Location(
                            path=str(path), line=lineno, column=match.start() + 1
                        ),
                        message=f"possible {pattern.label} literal detected in {path.name}.",
                        next_step=(
                            "remove the literal; load the value from an environment variable "
                            "or secret manager and rotate the exposed credential."
                        ),
                    )
                )
    return findings


def _matched_by_named_pattern(token: str) -> bool:
    """True when a non-entropy catalog pattern fully owns *token*."""
    return any(
        not p.entropy and p._compiled.fullmatch(token) is not None
        for p in SECRET_PATTERNS
    )


# --- Capability 3: rule-based conformance -----------------------------------


def run_conformance(path: Path, structure: object) -> list[Finding]:
    """Apply conformance rules to a parsed configuration structure.

    The rules walk the parsed structure shape-agnostically (no per-harness schema
    is assumed), so the same engine audits a JSON, YAML, or TOML config alike. The
    shipped rule is the universal-deny floor: a permission / allow surface must not
    grant a denied operation.

    Args:
        path: The configuration file (for finding locations).
        structure: The parsed structure from :func:`scan_config`.

    Returns:
        One finding per conformance violation, deterministically ordered.
    """
    findings: list[Finding] = []
    for grant in _iter_string_values(structure):
        for regex, label in _DENIED_GRANT_PATTERNS:
            if re.search(regex, grant):
                findings.append(
                    Finding(
                        id="denied-grant",
                        category="conformance",
                        severity="HIGH",
                        location=Location(path=str(path)),
                        message=f"configuration grants a denied operation ({label}): {grant!r}.",
                        next_step=(
                            f"remove the {label} grant; the universal-deny floor forbids it "
                            "regardless of the per-harness allow-list."
                        ),
                    )
                )
                break
    return findings


def _iter_string_values(structure: object) -> Iterable[str]:
    """Yield every string leaf in a nested mapping / sequence structure."""
    if isinstance(structure, str):
        yield structure
    elif isinstance(structure, Mapping):
        for value in structure.values():
            yield from _iter_string_values(value)
    elif isinstance(structure, (list, tuple)):
        for item in structure:
            yield from _iter_string_values(item)


# --- Top-level audit + integration contracts --------------------------------


def _audit_path(path: Path) -> list[Finding]:
    """Run all three capabilities over a single path; never raise."""
    findings: list[Finding] = []
    try:
        structure, scan_finding = scan_config(path)
        if scan_finding is not None:
            findings.append(scan_finding)
        # Secret detection runs on raw text even when parsing failed.
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                text = ""
            findings.extend(detect_secrets(path, text))
        if structure is not None:
            findings.extend(run_conformance(path, structure))
    except Exception as exc:
        findings.append(
            Finding(
                id="auditor-internal-error",
                category="error",
                severity="MEDIUM",
                location=Location(path=str(path)),
                message=f"the auditor failed while scanning {path}: {exc}",
                next_step="report this path to the auditor maintainer; the run continues for other paths.",
            )
        )
    return findings


def audit(paths: Sequence[Path], *, strict: bool = False) -> Findings:
    """Scan, detect, and conform over *paths*; return structured findings.

    Args:
        paths: Configuration files (or directories — every contained file is
            scanned) to audit.
        strict: When ``True`` the result's ``strict`` flag is set so a CLI caller
            exits non-zero on findings-present. Advisory (``False``) is the default.

    Returns:
        A :class:`Findings` whose serialization validates against the
        advisory-finding schema. The result is always returned — an internal error
        on any path becomes a ``category = error`` finding, never an exception.
    """
    collected: list[Finding] = []
    for path in _expand_paths(paths):
        collected.extend(_audit_path(path))
    ordered = tuple(sorted(collected, key=Finding._order_key))
    return Findings(findings=ordered, strict=strict)


def pr_audit(changed: PrAuditInput) -> Findings:
    """Audit the changed configuration paths of a change-set (integration contract).

    This is the stable integration point a CI / pull-request audit caller consumes:
    it receives the changed configuration paths plus repository context and returns
    the same :class:`Findings` shape the standalone :func:`audit` produces. The
    repository context is carried for the caller's reporting; the audit itself runs
    over the changed paths.

    Args:
        changed: The changed configuration paths and repository context.

    Returns:
        Findings over the changed paths, in the advisory-finding shape.
    """
    return audit(changed.changed_paths, strict=changed.strict)


def _expand_paths(paths: Sequence[Path]) -> list[Path]:
    """Expand directories to their contained files; keep files as-is, sorted."""
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            expanded.extend(sorted(p for p in path.rglob("*") if p.is_file()))
        else:
            expanded.append(path)
    return expanded


def _exit_code(findings_present: bool, *, strict: bool) -> int:
    """Map a verdict to an exit code: advisory exits 0; strict exits 1 on findings."""
    if findings_present and strict:
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the standalone CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m apothem.lib.auditor",
        description="Advisory conformance / security auditor: config scan, secret detection, conformance.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="configuration files or directories to audit",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when findings are present (default: advisory, always exit 0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the findings as JSON (default: human-readable advisory summary)",
    )
    return parser


def _render_human(result: Findings) -> str:
    """Render a human-readable advisory summary of the run."""
    lines: list[str] = []
    summary = result.summary
    if not result.present:
        return "auditor: 0 findings — configuration is clean."
    lines.append(
        f"auditor: {summary['total']} finding(s) "
        f"(HIGH {summary['high']} | MEDIUM {summary['medium']} | LOW {summary['low']}) -- advisory."
    )
    for finding in result.findings:
        loc = finding.location
        where = loc.path + (f":{loc.line}" if loc.line is not None else "")
        lines.append(
            f"  [{finding.severity}] {finding.category}/{finding.id} @ {where}"
        )
        lines.append(f"      {finding.message}")
        lines.append(f"      next step: {finding.next_step}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Standalone CLI entry point (``python -m apothem.lib.auditor``).

    Args:
        argv: The argument vector (defaults to ``sys.argv[1:]``).

    Returns:
        ``0`` in advisory mode (the shipped default), even with findings present;
        ``1`` when ``--strict`` (or the env opt-in) is set and findings are present.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    strict = resolve_strict(bool(args.strict))
    result = audit(cast("list[Path]", args.paths), strict=strict)
    serialized = result.to_dict()
    validate_findings(serialized)
    if args.json:
        sys.stdout.write(json.dumps(serialized, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(_render_human(result) + "\n")
    return _exit_code(result.present, strict=strict)


__all__ = [
    "SECRET_PATTERNS",
    "SECRET_PATTERNS_NA",
    "STRICT_ENV",
    "AuditorError",
    "Category",
    "Finding",
    "Findings",
    "Location",
    "PrAuditInput",
    "SecretPattern",
    "Severity",
    "audit",
    "detect_secrets",
    "main",
    "pr_audit",
    "resolve_strict",
    "run_conformance",
    "scan_config",
    "validate_findings",
]


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess in tests
    raise SystemExit(main(sys.argv[1:]))
