# SPDX-License-Identifier: MIT

"""Guard: no tracked text file holds a hidden bidirectional control.

The embedding and override controls (U+202A to U+202E) and the isolate
controls (U+2066 to U+2069) are invisible and reorder the text around them, so
a diff or a review cannot show what a reader will see (the "Trojan Source"
class, CVE-2021-42574). No other gate looks for them. A page that needs an
isolate uses a visible form instead: ``<bdi>`` in a Markdown or MDX body, and a
YAML escape in frontmatter (see the Arabic conventions in ``site/README.md``).

The marks LRM (U+200E), RLM (U+200F) and ALM (U+061C) stay allowed: they are
directional characters, not controls that open a run, and the Arabic pages use
them on purpose.

The guard lists tracked files with ``git ls-files``, skips binary files by
extension or by a NUL byte in the first 8000 bytes (Git's own test), and names
each control it finds as ``path:line:column U+XXXX NAME``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

# LRE, RLE, PDF, LRO, RLO, then LRI, RLI, FSI, PDI.
_FORBIDDEN: Final[tuple[int, ...]] = (*range(0x202A, 0x202F), *range(0x2066, 0x206A))
_FORBIDDEN_RE: Final[re.Pattern[bytes]] = re.compile(
    b"|".join(re.escape(chr(cp).encode("utf-8")) for cp in _FORBIDDEN)
)
_ALLOWED_MARKS: Final[tuple[int, ...]] = (0x200E, 0x200F, 0x061C)
_BINARY_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".7z", ".avif", ".bmp", ".bz2", ".dll", ".dylib", ".eot", ".exe", ".gif",
        ".gz", ".ico", ".jar", ".jpeg", ".jpg", ".mp3", ".mp4", ".otf", ".pdf",
        ".png", ".pyc", ".so", ".tar", ".tgz", ".ttf", ".wav", ".webm", ".webp",
        ".whl", ".woff", ".woff2", ".xz", ".zip",
    }
)  # fmt: skip
_SNIFF_BYTES: Final[int] = 8000

# Tracked files that genuinely need one of these controls, each with the
# reason. No file needs one today. An entry must name a tracked file that still
# holds a control, so the list cannot go stale.
_ALLOWLIST: Final[dict[str, str]] = {}


@lru_cache(maxsize=1)
def _tracked() -> tuple[str, ...]:
    """Return every tracked path, repo-relative with forward slashes."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is required to list tracked files")
    result = subprocess.run(
        [git, "-C", str(_REPO_ROOT), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        pytest.skip("not a git checkout, so there are no tracked files to list")
    return tuple(name for name in result.stdout.decode("utf-8").split("\0") if name)


def _find_controls(data: bytes) -> list[tuple[int, int, int]]:
    """Return ``(line, column, code point)``, 1-based, for each control in *data*."""
    hits: list[tuple[int, int, int]] = []
    for match in _FORBIDDEN_RE.finditer(data):
        start = match.start()
        line_start = data.rfind(b"\n", 0, start) + 1
        column = len(data[line_start:start].decode("utf-8", errors="replace")) + 1
        line = data.count(b"\n", 0, start) + 1
        hits.append((line, column, ord(match.group().decode("utf-8"))))
    return hits


def _describe(name: str, hit: tuple[int, int, int]) -> str:
    line, column, cp = hit
    return f"{name}:{line}:{column} U+{cp:04X} {unicodedata.name(chr(cp))}"


@lru_cache(maxsize=1)
def _scan_tracked() -> dict[str, tuple[tuple[int, int, int], ...]]:
    """Map each tracked text file that holds a control to its hits."""
    found: dict[str, tuple[tuple[int, int, int], ...]] = {}
    for name in _tracked():
        if Path(name).suffix.lower() in _BINARY_SUFFIXES:
            continue
        try:
            data = (_REPO_ROOT / name).read_bytes()
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            continue  # deleted in the working tree, or a submodule entry
        if b"\0" in data[:_SNIFF_BYTES]:
            continue
        hits = _find_controls(data)
        if hits:
            found[name] = tuple(hits)
    return found


def test_detector_names_each_control_by_line_and_column() -> None:
    sample = (
        "first line\n"
        + "ab"
        + chr(0x2066)
        + "/plan"
        + chr(0x2069)
        + "\n"
        + chr(0x202E)
        + "x"
        + "".join(chr(cp) for cp in _ALLOWED_MARKS)
        + "\n"
    )
    hits = _find_controls(sample.encode("utf-8"))
    assert hits == [(2, 3, 0x2066), (2, 9, 0x2069), (3, 1, 0x202E)]
    assert _describe("f.md", hits[0]) == "f.md:2:3 U+2066 LEFT-TO-RIGHT ISOLATE"


def test_detector_covers_every_control_and_spares_the_marks() -> None:
    for cp in _FORBIDDEN:
        assert _find_controls(("a" + chr(cp)).encode("utf-8")) == [(1, 2, cp)]
    for cp in _ALLOWED_MARKS:
        assert _find_controls(("a" + chr(cp)).encode("utf-8")) == []


def test_no_tracked_text_file_holds_a_hidden_bidi_control() -> None:
    offenders = [
        _describe(name, hit)
        for name, hits in sorted(_scan_tracked().items())
        if name not in _ALLOWLIST
        for hit in hits
    ]
    assert not offenders, (
        "hidden bidirectional controls in tracked files (write a visible "
        "<bdi> or YAML escape instead, or allowlist the file with a reason):\n"
        + "\n".join(offenders)
    )


def test_allowlist_names_only_files_that_still_need_it() -> None:
    # Scan only when there is an entry to check: under xdist this test usually
    # runs in another worker than the test above, so an empty allowlist would
    # otherwise pay for a second full scan. ``found`` holds tracked files only,
    # so an entry that is no longer tracked is reported as stale too.
    found = _scan_tracked() if _ALLOWLIST else {}
    stale = [name for name in _ALLOWLIST if name not in found]
    assert not stale, f"allowlist entries with no control left: {stale}"
