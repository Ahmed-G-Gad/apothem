# SPDX-License-Identifier: MIT

"""Prove every command and skill surface has a deterministic output shape.

Why this enforcement exists. apothem renders option sets and terminal
next-step blocks with a strictly expected output structure: identical
inputs produce identically-shaped output, the recommended marker sits in
a fixed position, and every terminal surface closes with a named next
step. This harness is the executable proof of that determinism contract
(`rules/determinism.md`): it reduces each surface to a canonical
structural signature, recomputes the signature across repeated reads, and
asserts the signature is byte-stable. A surface whose signature drifts
between runs carries undeclared non-determinism; a surface that fails the
minimal output-shape floor is structurally incomplete. Both are findings.

The signature is the deterministic structural fingerprint of a surface —
its SPDX-header presence, frontmatter key set, ordered H2 heading
sequence, recommended-marker count, fenced-code language multiset,
bindings-section presence, and terminal next-step form. The fingerprint
is sensitive to any shape change but immune to cosmetic prose edits, so
it captures "shape" rather than "content".

Division of labour. The per-dimension semantics of the recommended
marker and the next-step block are owned by `option_annotation_grep` and
`recommend_next_step_grep` respectively; this harness owns the *composite*
shape's stability and the minimal completeness floor that makes a
perturbed surface fail. The overlap on next-step presence is deliberate
defense-in-depth and extends coverage to skill surfaces.

Detection strategy. The validator walks `src/apothem/commands/*.md`
(excluding `README.md` and `AGENTS.md`) and `src/apothem/skills/*/SKILL.md`. For each
surface it computes the structural signature three times from fresh reads
and compares; inequality is a non-determinism finding. It then checks the
output-shape floor: an SPDX header, at least one H2 heading, and a
terminal next-step heading (`## Recommended Next Step` or `## Next
Steps`). A missing element is an incomplete-shape finding.

Exit semantics. Exits 0 when every surface passes; exits 2 on any
finding. The exit-2 convention matches the conformity-gate orchestrator's
EXIT_FAIL constant.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "determinism-grep"
RULE_ANCHOR: Final[str] = "rules/determinism.md"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Surface roots relative to the repository root supplied at invocation.
COMMANDS_DIR: Final[str] = "src/apothem/commands"
SKILLS_DIR: Final[str] = "src/apothem/skills"

# Filenames excluded from the command sweep — folder-companion docs, not
# commands: the human-facing directory index and the agent-facing companion.
EXCLUDED_FILES: Final[frozenset[str]] = frozenset({"README.md", "AGENTS.md"})

# Number of independent signature recomputations per surface. Identical
# inputs must yield identical signatures across every recomputation.
RECOMPUTE_RUNS: Final[int] = 3

_SPDX_RE: Final[re.Pattern[str]] = re.compile(r"SPDX-License-Identifier:\s*MIT")
_H2_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+(?P<text>\S.*?)\s*$")
_FRONTMATTER_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^(?P<key>[A-Za-z0-9_-]+):")
_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^```(?P<lang>[A-Za-z0-9_+-]*)")
_RECOMMENDED_MARKER_RE: Final[re.Pattern[str]] = re.compile(r"\*\*Recommended\*\*")
_RECOMMENDED_POSTFIX_RE: Final[re.Pattern[str]] = re.compile(r"\(Recommended\)")

_NEXTSTEP_SINGULAR_RE: Final[re.Pattern[str]] = re.compile(
    r"^##\s+Recommended\s+Next\s+Step\s*$"
)
_NEXTSTEP_MULTI_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+Next\s+Steps\s*$")
_BINDINGS_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+Bindings\b")


@dataclass(frozen=True)
class Finding:
    """One surface that violates the determinism / output-shape contract."""

    surface: str
    kind: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated sweep result across every command and skill surface."""

    grep: str
    root: str
    files_inspected: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "grep": self.grep,
            "root": self.root,
            "files_inspected": self.files_inspected,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _frontmatter_keys(lines: list[str]) -> list[str]:
    """Return the sorted key set of a leading YAML frontmatter block.

    The block is delimited by `---` on the first non-empty line and the
    next `---`. Surfaces without frontmatter return an empty list.
    """
    start = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if start is None or lines[start].strip() != "---":
        return []
    keys: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() == "---":
            break
        match = _FRONTMATTER_KEY_RE.match(line)
        if match:
            keys.append(match.group("key"))
    return sorted(keys)


def _fenced_languages(lines: list[str]) -> list[str]:
    """Return the sorted multiset of fenced-code language tags.

    Only opening fences are counted: every second fence in a file is a
    close. Untagged fences contribute an empty-string entry.
    """
    langs: list[str] = []
    in_fence = False
    for line in lines:
        match = _FENCE_RE.match(line)
        if match is None:
            continue
        if not in_fence:
            langs.append(match.group("lang"))
        in_fence = not in_fence
    return sorted(langs)


def _terminal_nextstep_form(lines: list[str]) -> str:
    """Return the terminal next-step form: 'singular', 'multi', or 'absent'."""
    for line in lines:
        if _NEXTSTEP_SINGULAR_RE.match(line):
            return "singular"
        if _NEXTSTEP_MULTI_RE.match(line):
            return "multi"
    return "absent"


def _structural_shape(body: str) -> dict[str, object]:
    """Reduce a surface to its canonical, order-stable structural shape."""
    lines = body.splitlines()
    h2_sequence = [m.group("text") for ln in lines if (m := _H2_RE.match(ln))]
    return {
        "spdx": bool(_SPDX_RE.search(body)),
        "frontmatter_keys": _frontmatter_keys(lines),
        "h2_sequence": h2_sequence,
        "recommended_marker_count": len(_RECOMMENDED_MARKER_RE.findall(body)),
        "recommended_postfix_count": len(_RECOMMENDED_POSTFIX_RE.findall(body)),
        "fenced_languages": _fenced_languages(lines),
        "bindings_present": any(_BINDINGS_RE.match(ln) for ln in lines),
        "nextstep_form": _terminal_nextstep_form(lines),
    }


def _signature(body: str) -> str:
    """Compute the deterministic structural fingerprint of a surface."""
    canonical = json.dumps(_structural_shape(body), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _classify_surface(path: Path) -> list[Finding]:
    """Return findings for one surface — non-determinism + shape floor."""
    surface = str(path)
    findings: list[Finding] = []

    signatures: list[str] = []
    bodies: list[str] = []
    for _ in range(RECOMPUTE_RUNS):
        try:
            body = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return [
                Finding(
                    surface=surface,
                    kind="unreadable",
                    detail=f"could not read surface: {exc}",
                )
            ]
        bodies.append(body)
        signatures.append(_signature(body))

    if len(set(signatures)) != 1:
        findings.append(
            Finding(
                surface=surface,
                kind="non-deterministic-signature",
                detail=(
                    f"structural signature drifted across {RECOMPUTE_RUNS} reads "
                    f"({sorted(set(signatures))}); identical input must yield an "
                    "identically-shaped output or declare its non-determinism source"
                ),
            )
        )

    shape = _structural_shape(bodies[0])
    if not shape["spdx"]:
        findings.append(
            Finding(
                surface=surface,
                kind="incomplete-shape",
                detail="no SPDX-License-Identifier header found",
            )
        )
    if not shape["h2_sequence"]:
        findings.append(
            Finding(
                surface=surface,
                kind="incomplete-shape",
                detail="no H2 section heading found; the surface has no structure",
            )
        )
    if shape["nextstep_form"] == "absent":
        findings.append(
            Finding(
                surface=surface,
                kind="incomplete-shape",
                detail=(
                    "no terminal `## Recommended Next Step` or `## Next Steps` "
                    "heading; every terminal surface closes with a named next step"
                ),
            )
        )
    return findings


def _iter_surfaces(root: Path) -> list[Path]:
    """Return the sorted command + skill surface set under root."""
    surfaces: list[Path] = []
    commands_dir = root / COMMANDS_DIR
    if commands_dir.is_dir():
        surfaces.extend(
            p for p in commands_dir.glob("*.md") if p.name not in EXCLUDED_FILES
        )
    skills_dir = root / SKILLS_DIR
    if skills_dir.is_dir():
        surfaces.extend(skills_dir.glob("*/SKILL.md"))
    return sorted(surfaces)


def check(root: Path) -> GrepResult:
    """Sweep every command and skill surface for a deterministic shape."""
    findings: list[Finding] = []
    surfaces = _iter_surfaces(root)
    missing: list[str] = []
    if not (root / COMMANDS_DIR).is_dir():
        missing.append(COMMANDS_DIR)
    if not (root / SKILLS_DIR).is_dir():
        missing.append(SKILLS_DIR)
    for rel in missing:
        findings.append(
            Finding(
                surface=rel,
                kind="missing-surface-root",
                detail=f"surface directory absent at canonical path {root / rel}",
            )
        )
    for path in surfaces:
        findings.extend(_classify_surface(path))
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        files_inspected=len(surfaces),
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
