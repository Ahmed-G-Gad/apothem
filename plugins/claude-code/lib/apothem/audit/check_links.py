# SPDX-License-Identifier: MIT

"""Walk every Markdown file and verify each link target is reachable.

Why this scan exists. Cross-references decay silently as the corpus
evolves: files move, sections get renamed, external sources rot, badge
URLs shift. A broken internal link wastes the reader's attention; a
broken external link erodes the author's credibility. The scan
enumerates every Markdown link, classifies it, and verifies the target
where verification is mechanical (internal paths, in-file anchors).

What this scan covers. Three link forms:

- ``[text](path/to/file.md)`` — Markdown inline link. Internal targets
  resolve relative to the source file's directory.
- ``[text](path/to/file.md#anchor)`` — anchor link. Verifies both that
  the file exists and that a heading slugged to ``anchor`` is present.
- ``<https://example.com/page>`` and ``[text](https://...)`` — external
  link. By default these are enumerated but NOT HTTP-checked; pass
  ``--check-external`` to issue HEAD requests with timeout.

What this scan reports per finding. ``file:line``, the link target as
written, the resolution outcome (``broken-internal-path`` /
``broken-internal-anchor`` / ``broken-external``), and a remediation
hint pointing at the most likely fix (move the target back, update the
link, or remove the dead reference).

What this scan excludes. Links inside fenced code blocks (which
document, rather than reference, link syntax). The ``link-allowlist.md``
file at the repository root, when present, lists URL substrings that
should be treated as known-flaky and skipped on the external-check pass.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scan_lib import (
    CONTENT_ROOT,
    NARRATIVE_CLASSES,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    Hit,
    load_inventory,
    read_text_safely,
)

# Markdown inline link: `[text](target)` with optional title.
_INLINE_LINK_RE = re.compile(
    r"\[(?P<text>[^\]\n]*?)\]\((?P<target>[^()\s]+(?:\([^)]*\))?)"
    r"(?:\s+\"[^\"]*\")?\)"
)

# Markdown autolink: `<https://example.com>` or `<email@example.com>`.
_AUTOLINK_RE = re.compile(r"<((?:https?|ftp)://[^>\s]+)>")

# Heading line: `## Heading text` capturing the depth and the text.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

# Markdown anchor slug: lowercase letters / digits / hyphens; punctuation
# is stripped; whitespace becomes a hyphen. The implementation follows
# the GitHub-Flavored-Markdown convention used by the docs site, the
# repository renderer, and most static-site generators in the corpus.
_SLUG_STRIP_RE = re.compile(r"[^\w\s-]")
_SLUG_SPACE_RE = re.compile(r"\s+")

EXTERNAL_TIMEOUT_SECONDS: Final[float] = 8.0

MARKDOWN_SUFFIXES: Final[frozenset[str]] = frozenset({".md", ".markdown"})


def _slug_for_heading(text: str) -> str:
    """Return the GitHub-Flavored-Markdown slug for a heading."""
    cleaned = _SLUG_STRIP_RE.sub("", text.strip().lower())
    return _SLUG_SPACE_RE.sub("-", cleaned).strip("-")


def _collect_anchors(content: str) -> set[str]:
    """Walk a Markdown document and return every available anchor slug."""
    anchors: set[str] = set()
    in_fence = False
    for line in content.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            anchors.add(_slug_for_heading(match.group(2)))
    return anchors


def _load_allowlist(path: Path) -> list[str]:
    """Parse the optional URL-substring allowlist."""
    if not path.exists():
        return []
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def _is_external(target: str) -> bool:
    """Return True for absolute http(s) targets and mailto links."""
    return (
        target.startswith("http://")
        or target.startswith("https://")
        or target.startswith("mailto:")
    )


def _resolve_internal(
    source: Path, target: str, root: Path
) -> tuple[Path | None, str | None]:
    """Split ``target`` into ``(resolved-path, anchor)``.

    Returns ``(None, anchor)`` when the path part is empty (anchor-only
    link, e.g. ``[#section](#section)``); the caller resolves the anchor
    against ``source``.
    """
    if "#" in target:
        path_part, anchor = target.split("#", 1)
    else:
        path_part, anchor = target, None
    if not path_part:
        return None, anchor
    base = source.parent
    if path_part.startswith("/"):
        resolved = root / path_part.lstrip("/")
    else:
        resolved = base / path_part
    return resolved.resolve(), anchor


def _check_external(url: str, timeout: float) -> int | None:
    """Issue a HEAD request and return the response status code, or
    ``None`` on connection / timeout error."""
    # The audit context only ever issues HEAD against http(s) URLs the
    # Markdown corpus already cites; no scheme expansion happens here.
    request = urllib.request.Request(  # noqa: S310 (audit context)
        url, method="HEAD"
    )
    request.add_header("User-Agent", "apothem-link-checker/0.1")
    try:
        with urllib.request.urlopen(  # noqa: S310 (audit context)  # nosec B310
            request, timeout=timeout
        ) as resp:
            return resp.status
    except URLError:
        return None
    except (OSError, ValueError, http.client.HTTPException) as exc:
        # Concrete network/transport failure (SSL, socket timeout, malformed
        # URL, protocol error) — report the link as unreachable. Surface the
        # exception class to stderr so a genuine defect in the checker itself
        # is distinguishable from a true unreachable link; programming errors
        # (NameError/AttributeError/TypeError) deliberately propagate.
        print(f"link-check: {type(exc).__name__} probing {url}", file=sys.stderr)
        return None


def _walk_links(content: str) -> list[tuple[int, str]]:
    """Return ``(lineno, target)`` for every link in the document."""
    out: list[tuple[int, str]] = []
    in_fence = False
    for lineno, line in enumerate(content.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in _INLINE_LINK_RE.finditer(line):
            out.append((lineno, match.group("target")))
        for match in _AUTOLINK_RE.finditer(line):
            out.append((lineno, match.group(1)))
    return out


def _check_internal(
    rel: str,
    source_path: Path,
    target: str,
    lineno: int,
    root: Path,
    anchor_cache: dict[Path, set[str]],
    self_anchors: set[str],
) -> Hit | None:
    """Verify an internal link; return a Hit on failure."""
    resolved, anchor = _resolve_internal(source_path, target, root)
    if resolved is None:
        if anchor and anchor not in self_anchors:
            return Hit(
                file=rel,
                line=lineno,
                signal=f"broken-internal-anchor: {target}",
                severity=SEVERITY_HIGH,
                remediation=(
                    "Update the in-file anchor; the heading text it"
                    " refers to was renamed or removed."
                ),
            )
        return None
    if not resolved.exists():
        return Hit(
            file=rel,
            line=lineno,
            signal=f"broken-internal-path: {target}",
            severity=SEVERITY_HIGH,
            remediation=(
                "Update the link target to a path that exists; the"
                " referenced file was moved or removed."
            ),
        )
    if anchor and resolved.suffix.lower() in MARKDOWN_SUFFIXES:
        if resolved not in anchor_cache:
            anchor_cache[resolved] = _collect_anchors(read_text_safely(resolved))
        if anchor not in anchor_cache[resolved]:
            return Hit(
                file=rel,
                line=lineno,
                signal=f"broken-internal-anchor: {target}",
                severity=SEVERITY_HIGH,
                remediation=(
                    "Update the cross-file anchor; the heading text it"
                    " refers to was renamed or removed."
                ),
            )
    return None


def _scan_record(
    record: dict[str, Any],
    root: Path,
    anchor_cache: dict[Path, set[str]],
    allowlist: list[str],
    check_external: bool,
) -> tuple[list[Hit], int]:
    """Walk a single Markdown record and return its hits + ext-checks."""
    rel = record["path"]
    if Path(rel).suffix.lower() not in MARKDOWN_SUFFIXES:
        return [], 0
    source_path = root / rel
    content = read_text_safely(source_path)
    if not content:
        return [], 0
    self_anchors = _collect_anchors(content)
    hits: list[Hit] = []
    external_checked = 0
    for lineno, target in _walk_links(content):
        if _is_external(target):
            if not check_external or target.startswith("mailto:"):
                continue
            if any(skip in target for skip in allowlist):
                continue
            external_checked += 1
            status = _check_external(target, EXTERNAL_TIMEOUT_SECONDS)
            if status is None or status >= 400:
                hits.append(
                    Hit(
                        file=rel,
                        line=lineno,
                        signal=(
                            f"broken-external: {target}"
                            f" (status={status if status else 'no-response'})"
                        ),
                        severity=SEVERITY_LOW,
                        remediation=(
                            "Verify the URL is still live; if rotated,"
                            " update the link or move the resource to a"
                            " permalinked alternative."
                        ),
                    )
                )
        else:
            hit = _check_internal(
                rel,
                source_path,
                target,
                lineno,
                root,
                anchor_cache,
                self_anchors,
            )
            if hit:
                hits.append(hit)
    return hits, external_checked


def main(argv: list[str] | None = None) -> int:
    """Walk every Markdown record, verify its links, and write ``drift-broken-links.json``.

    Loads the inventory, checks each narrative Markdown file's internal paths
    and anchors (and external URLs when ``--check-external`` is set), writes
    the hit envelope, and prints a per-signal summary.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(".audit/inventory.json"),
    )
    parser.add_argument("--root", type=Path, default=CONTENT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".audit/drift-broken-links.json"),
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=Path("link-allowlist.md"),
        help="Optional URL-substring allowlist for external checks",
    )
    parser.add_argument(
        "--check-external",
        action="store_true",
        help=(
            "Issue HTTP HEAD against external URLs (slow; off by default"
            " to keep the scan deterministic and offline)"
        ),
    )
    args = parser.parse_args(argv)

    if not args.inventory.exists():
        print(
            f"error: inventory not found at {args.inventory}",
            file=sys.stderr,
        )
        return 1

    records, sha = load_inventory(args.inventory)
    allowlist = _load_allowlist(args.allowlist)
    anchor_cache: dict[Path, set[str]] = {}
    hits: list[Hit] = []
    external_total = 0
    md_total = 0
    for record in records:
        if record.get("class") not in NARRATIVE_CLASSES:
            continue
        if Path(record["path"]).suffix.lower() not in MARKDOWN_SUFFIXES:
            continue
        md_total += 1
        record_hits, ext = _scan_record(
            record,
            args.root,
            anchor_cache,
            allowlist,
            args.check_external,
        )
        hits.extend(record_hits)
        external_total += ext

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "scanner": "check_links",
        "inventory-source-sha256": sha,
        "external-checked": external_total,
        "external-check-enabled": args.check_external,
        "markdown-files-scanned": md_total,
        "hit-count": len(hits),
        "hits": [asdict(h) for h in hits],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    by_signal: dict[str, int] = {}
    for h in hits:
        kind = h.signal.split(":", 1)[0]
        by_signal[kind] = by_signal.get(kind, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_signal.items()))
    print(
        f"check_links: {len(hits)} hit(s) across {md_total} Markdown files"
        f" [{summary or 'none'}]; external-checked={external_total}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
