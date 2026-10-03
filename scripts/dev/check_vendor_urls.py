#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Check the vendor URLs cited by harness pins and templates.

Every ``STANDARD-CONVENTION-PIN.md`` and every file under a harness
``templates/`` directory cites vendor documentation by absolute URL. Vendors
move and retire pages, so this script fetches each unique URL and classifies
it:

- ``ok``: the URL answers 2xx at the same address.
- ``moved``: the URL answers 2xx only after redirecting to a different page.
  Pins and templates should cite the final address. A site root that
  redirects to a landing page on the same host is not a move, and neither is
  a documented alias listed in ``_ACCEPTED_REDIRECTS``.
- ``dead``: the URL answers 404, 410, or another non-blocking error status, or
  the host cannot be reached after retries.
- ``blocked``: the URL answers 401, 403, or 429. Bot protection returns these
  for live pages, so they are reported but do not fail the check.

The report is JSON. The exit code is 2 when any URL is ``moved`` or ``dead``,
0 otherwise. The harness-convention monitor runs this weekly.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit, urlunsplit

_URL: Final[re.Pattern[str]] = re.compile(r"https?://[^\s<>()\[\]`\"'|]+")
_TRAILING_PUNCTUATION: Final[str] = ".,;:!?*"

# Addresses that are configuration values, not documents: API base URLs the
# templates write into a native config. Fetching them is meaningless.
_NOT_DOCUMENTS: Final[tuple[str, ...]] = ("https://api.z.ai/",)

# Redirects a vendor documents as the address to use. Claude Code's settings
# docs publish json.schemastore.org for the ``$schema`` line, which the
# SchemaStore host redirects to www.schemastore.org.
_ACCEPTED_REDIRECTS: Final[frozenset[tuple[str, str]]] = frozenset(
    {("json.schemastore.org", "www.schemastore.org")}
)

_BLOCKED_STATUSES: Final[frozenset[int]] = frozenset({401, 403, 429})
_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (compatible; apothem-vendor-url-check/1.0; "
    "+https://github.com/ahmed-g-gad/apothem)"
)


@dataclass(frozen=True)
class FetchResult:
    """What one request for a URL returned."""

    status: int | None
    final_url: str | None
    error: str | None = None


@dataclass(frozen=True)
class UrlReport:
    """The classification of one cited URL and the files that cite it."""

    url: str
    outcome: str
    status: int | None
    final_url: str | None
    cited_in: list[str] = field(default_factory=list)
    error: str | None = None


Fetcher = Callable[[str], FetchResult]


def _clean(url: str) -> str:
    return url.rstrip(_TRAILING_PUNCTUATION)


def _is_placeholder(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return (
        any(token in url for token in ("${", "{", "<", "..."))
        or host in {"localhost", "127.0.0.1", "example.com"}
        or host.endswith(".example.com")
        or url.startswith(_NOT_DOCUMENTS)
    )


def cited_files(harnesses_root: Path) -> list[Path]:
    """Return the pin and template files under *harnesses_root*."""
    files: list[Path] = []
    for harness in sorted(harnesses_root.iterdir()):
        if not harness.is_dir() or harness.name.startswith(("_", ".")):
            continue
        pin = harness / "STANDARD-CONVENTION-PIN.md"
        if pin.is_file():
            files.append(pin)
        templates = harness / "templates"
        if templates.is_dir():
            files.extend(
                path
                for path in sorted(templates.rglob("*"))
                if path.is_file() and "__pycache__" not in path.parts
            )
    return files


def collect_urls(files: Iterable[Path], root: Path) -> dict[str, list[str]]:
    """Map each cited document URL to the files that cite it."""
    cited: dict[str, list[str]] = {}
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            label = path.relative_to(root).as_posix()
        except ValueError:
            label = path.as_posix()
        for match in _URL.finditer(text):
            url = _clean(match.group(0))
            if _is_placeholder(url):
                continue
            sources = cited.setdefault(url, [])
            if label not in sources:
                sources.append(label)
    return dict(sorted(cited.items()))


def _normalized(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", (parts.hostname or "").lower(), path, "", ""))


def _benign_redirect(url: str, final_url: str) -> bool:
    start, end = urlsplit(url), urlsplit(final_url)
    start_host, end_host = start.hostname or "", end.hostname or ""
    if start_host == end_host and start.path.strip("/") == "":
        return True
    same_path = start.path.rstrip("/") == end.path.rstrip("/")
    return same_path and (start_host, end_host) in _ACCEPTED_REDIRECTS


def classify(url: str, result: FetchResult) -> str:
    """Return ``ok``, ``moved``, ``dead`` or ``blocked`` for one fetch."""
    if result.status is None:
        return "dead"
    if result.status in _BLOCKED_STATUSES:
        return "blocked"
    if result.status >= 400:
        return "dead"
    final = result.final_url
    if final and _normalized(final) != _normalized(url):
        return "ok" if _benign_redirect(url, final) else "moved"
    return "ok"


def fetch(url: str, *, attempts: int = 3, timeout: float = 30.0) -> FetchResult:
    """GET *url*, following redirects, with retries on network errors."""
    if urlsplit(url).scheme not in {"http", "https"}:
        return FetchResult(None, None, "not an http(s) URL")
    error = "no attempt made"
    for attempt in range(attempts):
        # The scheme is checked above, so only http(s) URLs are opened.
        request = urllib.request.Request(  # noqa: S310
            url, headers={"User-Agent": _USER_AGENT}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                response.read(1024)
                return FetchResult(response.status, response.geturl())
        except urllib.error.HTTPError as exc:
            if exc.code not in {500, 502, 503, 504} or attempt == attempts - 1:
                return FetchResult(exc.code, exc.geturl() or url)
            error = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = str(getattr(exc, "reason", exc))
        time.sleep(2**attempt)
    return FetchResult(None, None, error)


def check(cited: dict[str, list[str]], fetcher: Fetcher) -> list[UrlReport]:
    """Fetch and classify every cited URL."""
    reports: list[UrlReport] = []
    for url, sources in cited.items():
        result = fetcher(url)
        reports.append(
            UrlReport(
                url=url,
                outcome=classify(url, result),
                status=result.status,
                final_url=result.final_url,
                cited_in=sources,
                error=result.error,
            )
        )
    return reports


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--harnesses-root",
        type=Path,
        default=Path("src/apothem/harnesses"),
        help="Root directory containing harness adapter packages.",
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Optional JSON report path."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the cited URLs without fetching them.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, fetcher: Fetcher = fetch) -> int:
    """CLI entry point."""
    args = _parse_args(argv)
    root: Path = args.harnesses_root
    if not root.is_dir():
        sys.stderr.write(f"harnesses root not found: {root}\n")
        return 1
    cited = collect_urls(cited_files(root), root)
    if args.list:
        for url, sources in cited.items():
            sys.stdout.write(f"{url}\t{', '.join(sources)}\n")
        return 0
    reports = check(cited, fetcher)
    failing = [r for r in reports if r.outcome in {"moved", "dead"}]
    payload = {
        "validator": "check_vendor_urls",
        "passed": not failing,
        "url_count": len(reports),
        "counts": {
            outcome: sum(1 for r in reports if r.outcome == outcome)
            for outcome in ("ok", "moved", "dead", "blocked")
        },
        "urls": [asdict(report) for report in reports],
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 2 if failing else 0


if __name__ == "__main__":
    raise SystemExit(main())
