#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Check each harness's release channels against the version last reviewed.

``vendor-release-channels.json``, beside this script, has one entry for every
harness folder under ``src/apothem/harnesses/``. A watched harness lists its
release channels: an npm package and one of its dist-tags, a GitHub
repository's latest release (or, for a channel with a ``tag_pattern``, the
newest stable release among its newest 100 whose tag matches), a PyPI
project, or an installer address whose redirect is watched. Each channel
records what was last reviewed, with the date and the phrase of the pin that
cites the channel: a version (a full version, or a major alone) or, for an
installer address, the target it redirected to. That is the version or target
the pin names or, where the pin names none, the one the registry served when
the channel was recorded. A harness with no channel a script can query, such
as a desktop editor, gives the reason it is not watched instead.

The script asks each registry for the channel's current version, and each
installer address where it redirects, and classifies the answer:

- ``clean``: the channel serves the reviewed version, or, when the record
  holds a major alone, a version of that major; or the installer address
  redirects to the reviewed target.
- ``info``: the channel serves a newer minor or patch release, any newer
  release of a channel with calendar versions, or an older release than the
  one reviewed. Reported; does not fail the check.
- ``drift``: the channel serves a new major release, a newer minor or patch
  release on a channel whose ``watch`` level asks for it, or a release past
  the major the channel's trigger names; or the installer address redirects
  somewhere else, or answers without redirecting. Fails the check.
- ``missing``: the registry answers that the package, its dist-tag, the
  repository's releases or the installer address do not exist (404 or 410,
  or a dist-tag that is gone), or no stable release among the repository's
  newest 100 has a tag that matches the channel's ``tag_pattern``. Fails the
  check: the record names a channel that is not there.
- ``unreachable``: no usable answer after retries: a timeout, a refused or
  reset connection, a DNS failure, an answer cut off partway or not in HTTP
  form, 401, 403 or 429 (GitHub answers a rate limit with 403 or 429), a 5xx
  or another 4xx, an answer larger than 16 MiB or one the check cannot read,
  an answer that names no version or names it in a form the check does not
  read, or a redirect that names no target. A channel the run did not ask,
  because its time budget ran out, is unreachable too. Reported; does not
  fail the check.

A channel's ``trigger`` names an action, which a failing channel reports. On
a version channel it comes with a release past the trigger's major, and with
a channel that is missing, whose signal the check can no longer see; it keeps
failing the check until the trigger is removed or changed. On an installer
address it comes with any target other than the reviewed one, an answer
without a redirect, or an address that is gone; recording the new target as
reviewed stops it.

The first number of a version is its major, a 0 included, so a move from
0.26 to 0.27 is a newer minor. GitHub requests carry the ``GITHUB_TOKEN``
environment variable when it is set, and only to api.github.com.

Each attempt at a request has 30 seconds in all, from the name lookup to the
last byte of the answer, however many addresses the host resolves to, and a
request makes up to three attempts. Once 20 minutes have passed, the run asks
no further channel, so it writes its report inside the monitor's time limit.

Before it asks any registry, the script checks the file against the pins:
every harness folder has an entry, each channel's ``evidence`` phrase appears
in its pin and names the channel, and a version or target reviewed from the
pin appears in it. The report is JSON. The exit code is 2 when a channel
drifted or is missing; 1 when the file or its evidence is wrong, or when the
check stops on an error, and the report then lists each problem; and 0
otherwise. The harness-convention monitor runs this weekly.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from functools import partial
from pathlib import Path
from typing import IO, Final, Protocol, TypeVar
from urllib.parse import quote, urljoin, urlsplit

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
CHANNELS_FILE: Final[Path] = Path(__file__).with_name("vendor-release-channels.json")

# ``redirect`` is an installer address: the check reads where it redirects.
REGISTRIES: Final[tuple[str, ...]] = ("npm", "github", "pypi", "redirect")
LEVELS: Final[tuple[str, ...]] = ("major", "minor", "patch")
VERSIONINGS: Final[tuple[str, ...]] = ("semver", "calendar")
SOURCES: Final[tuple[str, ...]] = ("pin", "registry")
OUTCOMES: Final[tuple[str, ...]] = ("clean", "info", "drift", "missing", "unreachable")
FAILING: Final[frozenset[str]] = frozenset({"drift", "missing"})

#: Each attempt at a request, from the name lookup to the last byte of the
#: answer, however many addresses the host resolves to.
ATTEMPT_SECONDS: Final[float] = 30.0
#: Attempts per request. A network error, a broken answer and a 5xx outage are
#: retried, after 1 and then 2 seconds.
ATTEMPTS: Final[int] = 3
#: After this long the run asks no further channel, so it writes its report
#: before the monitor job's time limit.
RUN_BUDGET_SECONDS: Final[float] = 20 * 60.0

_CHANNEL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "registry",
        "name",
        "tag",
        "tag_pattern",
        "versioning",
        "watch",
        "reviewed",
        "reviewed_on",
        "reviewed_from",
        "evidence",
        "trigger",
        "note",
    }
)
# An address as the pins write it: a host name and a path, without the
# https:// that the check always uses.
_ADDRESS: Final[re.Pattern[str]] = re.compile(
    r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+"
    r"(?:/[A-Za-z0-9._~%/+=?&-]*)?"
)
# A redirect target as the report shows it: an address, with any scheme other
# than https:// kept in front. A target in another form is reported without
# being repeated.
_SHOWN_TARGET: Final[re.Pattern[str]] = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://)?" + _ADDRESS.pattern
)
# A version or release tag as the report shows it. A registry answer in
# another form is reported without being repeated.
_SHOWN_VERSION: Final[re.Pattern[str]] = re.compile(r"[0-9A-Za-z._+@/-]{1,100}")
# Package and repository names as each registry spells them; anything else
# would change the request path.
_NAMES: Final[Mapping[str, re.Pattern[str]]] = {
    "npm": re.compile(r"(?:@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*"),
    "github": re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+"),
    "pypi": re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*"),
    "redirect": _ADDRESS,
}
# Each number has at most nine digits, so int() never meets one thousands of
# digits long. A longer run of digits, or a fourth number, holds no version.
_REVIEWED: Final[re.Pattern[str]] = re.compile(r"\d{1,9}(?:\.\d{1,9}){0,2}")
_VERSION: Final[re.Pattern[str]] = re.compile(
    r"(?<![\d.])(\d{1,9})(?:\.(\d{1,9}))?(?:\.(\d{1,9}))?(?!\d|\.\d)"
)
_PIN_LINE: Final[re.Pattern[str]] = re.compile(
    r"""^\s*standard_convention_pin\s*:\s*["']?(?P<path>[^"'\s#]+)["']?""",
    re.MULTILINE,
)
_CONTENT_LENGTH: Final[re.Pattern[str]] = re.compile(r"[0-9]{1,15}")
_GITHUB_API: Final[str] = "api.github.com"
_GONE_STATUSES: Final[frozenset[int]] = frozenset({404, 410})
# Server errors an outage produces; fetch() retries these.
_RETRIED_STATUSES: Final[frozenset[int]] = frozenset({500, 502, 503, 504})
_MAX_BODY: Final[int] = 16 * 1024 * 1024
# The answer is read a chunk at a time, so the attempt's time limit is checked
# between chunks.
_CHUNK: Final[int] = 64 * 1024
# The longest error text a report keeps; an exception's text can quote the
# answer.
_ERROR_LIMIT: Final[int] = 200
_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (compatible; apothem-vendor-release-check/1.0; "
    "+https://github.com/ahmed-g-gad/apothem)"
)

_T = TypeVar("_T")


class ChannelFileError(ValueError):
    """The channel file cannot be read, or an entry breaks its format."""


@dataclass(frozen=True)
class Trigger:
    """An action the report names when a channel fails.

    On a version channel, a release past ``major_above`` is drift whatever was
    reviewed, and a missing channel names the action too. An installer address
    has no versions, so ``major_above`` is None and the action comes with any
    target other than the reviewed one, an answer without a redirect, or an
    address that is gone.
    """

    major_above: int | None
    action: str


@dataclass(frozen=True)
class Channel:
    """One release channel of one harness, as the channel file records it."""

    harness: str
    registry: str
    name: str
    reviewed: str
    reviewed_on: str
    reviewed_from: str
    evidence: str
    tag: str = "latest"
    tag_pattern: str | None = None
    versioning: str = "semver"
    watch: str = "major"
    trigger: Trigger | None = None
    note: str = ""

    @property
    def label(self) -> str:
        """Return the channel as the report names it."""
        if self.registry == "npm":
            return f"npm {self.name}@{self.tag}"
        if self.registry == "github":
            return f"github {self.name} releases"
        if self.registry == "redirect":
            return f"redirect {self.name}"
        return f"pypi {self.name}"


@dataclass(frozen=True)
class NotWatched:
    """A harness with no channel a script can query, and why."""

    harness: str
    reason: str


@dataclass(frozen=True)
class Response:
    """What one request to a registry or an installer address returned."""

    status: int | None
    body: bytes = b""
    error: str | None = None
    #: The Location header of a redirect that was not followed.
    location: str | None = None


@dataclass(frozen=True)
class Reading:
    """The version a registry answer names, or why it names none."""

    version: str | None = None
    outcome: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class ChannelReport:
    """The classification of one channel."""

    harness: str
    channel: str
    outcome: str
    reviewed: str
    reviewed_on: str
    current: str | None
    detail: str
    url: str
    status: int | None
    trigger: str | None = None


class _Answer(Protocol):
    """The part of an HTTP answer the check reads its body from."""

    def read(self, amt: int, /) -> bytes:
        """Return up to *amt* bytes of the body; empty at its end."""
        ...


class Fetcher(Protocol):
    """Send one GET; follow redirects unless *follow_redirects* is False."""

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        *,
        follow_redirects: bool = True,
    ) -> Response:
        """Return what the request got back."""
        ...


def _text(entry: Mapping[str, object], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ChannelFileError(f"{where}: {key} must be a non-empty string")
    return value


def _choice(
    entry: Mapping[str, object],
    key: str,
    choices: tuple[str, ...],
    where: str,
    default: str | None = None,
) -> str:
    value = entry.get(key, default)
    if not isinstance(value, str) or value not in choices:
        raise ChannelFileError(f"{where}: {key} must be one of {', '.join(choices)}")
    return value


def _trigger(value: object, where: str, *, redirect: bool) -> Trigger | None:
    if value is None:
        return None
    # An installer address has no versions, so its trigger names no major.
    keys = {"action"} if redirect else {"major_above", "action"}
    if not isinstance(value, dict) or set(value) != keys:
        takes = "action alone" if redirect else "major_above and action"
        raise ChannelFileError(f"{where}: trigger takes {takes}")
    action = _text(value, "action", f"{where} trigger")
    if redirect:
        return Trigger(None, action)
    major = value["major_above"]
    if isinstance(major, bool) or not isinstance(major, int) or major < 0:
        raise ChannelFileError(f"{where}: trigger major_above must be a whole number")
    return Trigger(major, action)


def _tag_pattern(value: object, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ChannelFileError(f"{where}: tag_pattern must be a regular expression")
    try:
        re.compile(value)
    except re.error as exc:
        raise ChannelFileError(f"{where}: tag_pattern does not compile: {exc}") from exc
    return value


def _channel(harness: str, index: int, entry: object) -> Channel:
    where = f"{harness} channel {index + 1}"
    if not isinstance(entry, dict):
        raise ChannelFileError(f"{where}: must be an object")
    unknown = sorted(set(entry) - _CHANNEL_KEYS)
    if unknown:
        raise ChannelFileError(f"{where}: unknown keys {', '.join(unknown)}")
    registry = _choice(entry, "registry", REGISTRIES, where)
    redirect = registry == "redirect"
    name = _text(entry, "name", where)
    if not _NAMES[registry].fullmatch(name):
        kind = (
            "an address written without https://" if redirect else f"a {registry} name"
        )
        raise ChannelFileError(f"{where}: {name} is not {kind}")
    if "tag" in entry and registry != "npm":
        raise ChannelFileError(f"{where}: tag applies to an npm channel only")
    if "tag_pattern" in entry and registry != "github":
        raise ChannelFileError(f"{where}: tag_pattern applies to a GitHub channel only")
    if redirect and {"versioning", "watch"} & set(entry):
        raise ChannelFileError(
            f"{where}: versioning and watch apply to a version channel only"
        )
    versioning = _choice(entry, "versioning", VERSIONINGS, where, "semver")
    if versioning == "calendar" and "watch" in entry:
        # The first number of a calendar version is a year, so every newer
        # release is information and no level could turn it into drift.
        raise ChannelFileError(f"{where}: watch applies to a semver channel only")
    reviewed = _text(entry, "reviewed", where)
    if redirect and not _ADDRESS.fullmatch(reviewed):
        raise ChannelFileError(
            f"{where}: reviewed must be the redirect target, written without https://"
        )
    if not redirect and not _REVIEWED.fullmatch(reviewed):
        raise ChannelFileError(
            f"{where}: reviewed must be one to three numbers of at most nine digits"
        )
    reviewed_on = _text(entry, "reviewed_on", where)
    try:
        date.fromisoformat(reviewed_on)
    except ValueError as exc:
        raise ChannelFileError(f"{where}: reviewed_on must be YYYY-MM-DD") from exc
    note = entry.get("note", "")
    if not isinstance(note, str):
        raise ChannelFileError(f"{where}: note must be a string")
    return Channel(
        harness=harness,
        registry=registry,
        name=name,
        reviewed=reviewed,
        reviewed_on=reviewed_on,
        reviewed_from=_choice(entry, "reviewed_from", SOURCES, where),
        evidence=_text(entry, "evidence", where),
        tag=_text(entry, "tag", where) if "tag" in entry else "latest",
        tag_pattern=_tag_pattern(entry.get("tag_pattern"), where),
        versioning=versioning,
        watch=_choice(entry, "watch", LEVELS, where, "major"),
        trigger=_trigger(entry.get("trigger"), where, redirect=redirect),
        note=note,
    )


def load_channels(path: Path) -> tuple[list[Channel], list[NotWatched]]:
    """Read the channel file; raise ChannelFileError when it breaks the format."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ChannelFileError(f"cannot read the file: {exc}") from exc
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise ChannelFileError(f"not valid JSON: {exc}") from exc
    harnesses = document.get("harnesses") if isinstance(document, dict) else None
    if not isinstance(harnesses, dict) or not harnesses:
        raise ChannelFileError("harnesses must map each harness folder to an entry")
    watched: list[Channel] = []
    unwatched: list[NotWatched] = []
    for harness, entry in sorted(harnesses.items()):
        if not isinstance(entry, dict) or set(entry) not in (
            {"channels"},
            {"not_watched"},
        ):
            raise ChannelFileError(
                f"{harness}: needs exactly one of channels or not_watched"
            )
        if "not_watched" in entry:
            unwatched.append(NotWatched(harness, _text(entry, "not_watched", harness)))
            continue
        channels = entry["channels"]
        if not isinstance(channels, list) or not channels:
            raise ChannelFileError(f"{harness}: channels must be a non-empty list")
        watched.extend(_channel(harness, i, item) for i, item in enumerate(channels))
    return watched, unwatched


def _squashed(text: str) -> str:
    return " ".join(text.split())


def _reviewed_in(channel: Channel) -> re.Pattern[str]:
    """Match the reviewed version, or the whole reviewed address, in a pin."""
    value = re.escape(channel.reviewed)
    if channel.registry == "redirect":
        return re.compile(rf"(?<![\w./-]){value}(?![\w/-]|\.\w)")
    # Not part of a longer version: no fourth number (2.3.3.1), prerelease
    # (2.3.3-rc) or build (2.3.3+1) follows it.
    return re.compile(rf"(?<![\d.]){value}(?!\d|\.\d|[-+][0-9A-Za-z])")


def _pin_path(harness_dir: Path) -> Path:
    capabilities = harness_dir / "capabilities.yml"
    match = _PIN_LINE.search(capabilities.read_text(encoding="utf-8"))
    return harness_dir / (
        match.group("path") if match else "STANDARD-CONVENTION-PIN.md"
    )


def harness_pins(harnesses_root: Path) -> dict[str, Path]:
    """Map each harness folder that declares a capabilities manifest to its pin."""
    return {
        child.name: _pin_path(child)
        for child in sorted(harnesses_root.iterdir())
        if child.is_dir()
        and not child.name.startswith((".", "_"))
        and (child / "capabilities.yml").is_file()
    }


def evidence_problems(
    channels: Iterable[Channel],
    unwatched: Iterable[NotWatched],
    harnesses_root: Path,
) -> list[str]:
    """Return every way the channel file disagrees with the harness pins."""
    channels = list(channels)
    pins = harness_pins(harnesses_root)
    recorded = {c.harness for c in channels} | {n.harness for n in unwatched}
    problems = [
        f"{h}: no entry for this harness folder" for h in sorted(set(pins) - recorded)
    ]
    problems += [
        f"{h}: no harness folder with this name" for h in sorted(recorded - set(pins))
    ]
    texts: dict[str, str] = {}
    for channel in channels:
        pin = pins.get(channel.harness)
        if pin is None:
            continue
        if channel.harness not in texts:
            texts[channel.harness] = _squashed(pin.read_text(encoding="utf-8"))
        text = texts[channel.harness]
        where = f"{channel.harness} {channel.label}"
        if _squashed(channel.evidence) not in text:
            problems.append(
                f"{where}: evidence is not in {pin.name}: {channel.evidence}"
            )
        if channel.name not in channel.evidence:
            problems.append(f"{where}: evidence does not name {channel.name}")
        if channel.reviewed_from == "pin" and not _reviewed_in(channel).search(text):
            problems.append(
                f"{where}: reviewed {channel.reviewed} is not in {pin.name}"
            )
    return problems


def request_for(
    channel: Channel, token: str | None = None
) -> tuple[str, dict[str, str]]:
    """Return the URL and headers that ask a registry for *channel*'s version."""
    if channel.registry == "redirect":
        # An installer address answers with a script, not JSON, and gets no
        # token.
        return f"https://{channel.name}", {"User-Agent": _USER_AGENT, "Accept": "*/*"}
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    if channel.registry == "npm":
        package = quote(channel.name, safe="@")
        return f"https://registry.npmjs.org/-/package/{package}/dist-tags", headers
    if channel.registry == "pypi":
        return f"https://pypi.org/pypi/{channel.name}/json", headers
    headers["Accept"] = "application/vnd.github+json"
    headers["X-GitHub-Api-Version"] = "2022-11-28"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # A repository that also publishes other products' releases is read from
    # its release list and filtered by tag; any other from its latest release.
    path = "releases?per_page=100" if channel.tag_pattern else "releases/latest"
    return f"https://{_GITHUB_API}/repos/{channel.name}/{path}", headers


class _KeepRedirect(urllib.request.HTTPRedirectHandler):
    """Hand every redirect back as an HTTPError, without reading its Location.

    The caller reads the status and the Location header itself, so a Location
    that does not parse never raises inside urllib.
    """

    def http_error_302(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
    ) -> None:
        """Follow no redirect; urllib then raises it as an HTTPError."""

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def _clip(text: str, limit: int = _ERROR_LIMIT) -> str:
    """Return *text* cut to *limit* characters."""
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _too_slow(timeout: float) -> str:
    return f"no complete answer within {timeout:g} seconds"


def _within(seconds: float, work: Callable[[], _T]) -> _T | None:
    """Return what *work* returns, or None when it runs past *seconds*.

    The work runs in a daemon thread, so an attempt stuck in a name lookup, a
    connection to one address after another, or a slow answer is abandoned at
    the deadline. The thread ends on its own socket timeout, or with the
    process.
    """
    results: list[_T] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            results.append(work())
        except BaseException as exc:  # handed to the caller below
            errors.append(exc)

    worker = threading.Thread(target=run, name="vendor-release-request", daemon=True)
    worker.start()
    worker.join(seconds)
    if errors:
        raise errors[0]
    return results[0] if results else None


def _content_length(answer: object) -> int | None:
    """Return the answer's Content-Length when it declares a plain one."""
    headers = getattr(answer, "headers", None)
    value = headers.get("Content-Length") if headers is not None else None
    if isinstance(value, str) and _CONTENT_LENGTH.fullmatch(value.strip()):
        return int(value)
    return None


def _read_answer(
    answer: _Answer, status: int, deadline: float, timeout: float
) -> tuple[Response, bool]:
    """Read an answer's body a chunk at a time, raising TimeoutError at *deadline*.

    Return the response and whether another attempt could get a better one.
    """
    # read1 returns after one read from the connection, so a slow answer
    # reaches the deadline check between chunks.
    read: Callable[[int], bytes] = getattr(answer, "read1", None) or answer.read
    chunks: list[bytes] = []
    size = 0
    while chunk := read(_CHUNK):
        size += len(chunk)
        if size > _MAX_BODY:
            limit = f"{_MAX_BODY // (1024 * 1024)} MiB"
            return Response(status, error=f"the answer is larger than {limit}"), False
        if time.monotonic() > deadline:
            raise TimeoutError(_too_slow(timeout))
        chunks.append(chunk)
    expected = _content_length(answer)
    if expected is not None and size < expected:
        # http.client returns a body cut short without an error when the
        # answer gave its length.
        error = f"the answer broke off after {size} of {expected} bytes"
        return Response(None, error=error), True
    return Response(status, b"".join(chunks)), False


def _attempt(
    request: urllib.request.Request,
    opener: urllib.request.OpenerDirector | None,
    timeout: float,
) -> tuple[Response, bool]:
    """Send one request; return the response and whether a retry could help."""
    deadline = time.monotonic() + timeout
    try:
        if opener is None:
            answer = urllib.request.urlopen(request, timeout=timeout)  # noqa: S310  # nosec B310
        else:
            answer = opener.open(request, timeout=timeout)
        with answer as response:
            return _read_answer(response, response.status, deadline, timeout)
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location") if exc.headers is not None else None
        response = Response(exc.code, error=f"HTTP {exc.code}", location=location)
        return response, exc.code in _RETRIED_STATUSES
    except http.client.HTTPException as exc:
        # The answer broke off partway (IncompleteRead) or was not HTTP
        # (BadStatusLine). Retried, then reported as unreachable.
        return Response(None, error=_clip(repr(exc))), True
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return Response(None, error=_clip(str(getattr(exc, "reason", exc)))), True
    except ValueError as exc:
        # urllib could not use the answer, such as a redirect whose Location
        # does not parse. Another attempt gets the same answer.
        error = f"the answer could not be used ({type(exc).__name__})"
        return Response(None, error=error), False


def fetch(
    url: str,
    headers: Mapping[str, str],
    *,
    follow_redirects: bool = True,
    attempts: int = ATTEMPTS,
    timeout: float = ATTEMPT_SECONDS,
) -> Response:
    """GET *url*, retrying a network error, a broken answer, and a 5xx outage.

    Each attempt has *timeout* seconds in all: the name lookup, a connection to
    every address the host resolves to, and the whole answer. An attempt still
    running then is abandoned and counts as a timeout. The retried statuses
    are 500, 502, 503 and 504. With *follow_redirects* False, a redirect comes
    back as it was answered, with its status and its Location header.
    """
    parts = urlsplit(url)
    if parts.scheme != "https":
        return Response(None, error="not an https URL")
    opener = None if follow_redirects else urllib.request.build_opener(_KeepRedirect)
    response = Response(None, error="no attempt made")
    for attempt in range(attempts):
        # The scheme is checked above, so only https URLs are opened.
        request = urllib.request.Request(url)  # noqa: S310
        for key, value in headers.items():
            if key.lower() != "authorization":
                request.add_header(key, value)
            elif parts.hostname == _GITHUB_API:
                # Never copied onto a redirect, so the token reaches
                # api.github.com and no other host.
                request.add_unredirected_header(key, value)
        result = _within(timeout, partial(_attempt, request, opener, timeout))
        if result is None:
            response, retry = Response(None, error=_too_slow(timeout)), True
        else:
            response, retry = result
        if not retry:
            return response
        if attempt < attempts - 1:
            time.sleep(2**attempt)
    return response


def version_numbers(text: str) -> tuple[int, ...] | None:
    """Return the major, minor and patch numbers of the first version in *text*."""
    match = _VERSION.search(text)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups() if part is not None)


def _version(value: object, absent: str) -> Reading:
    """Return a reading of *value*, a version or tag a registry answered with."""
    if not isinstance(value, str) or not value:
        return Reading(outcome="unreachable", detail=absent)
    if not _SHOWN_VERSION.fullmatch(value):
        return Reading(
            outcome="unreachable",
            detail="the answer names a version in a form the check does not read",
        )
    return Reading(version=value)


def _npm_version(channel: Channel, payload: object) -> Reading:
    if not isinstance(payload, dict):
        return Reading(
            outcome="unreachable", detail="the dist-tags answer is not an object"
        )
    version = payload.get(channel.tag)
    if version is None:
        return Reading(
            outcome="missing", detail=f"the package has no {channel.tag} dist-tag"
        )
    return _version(version, f"the {channel.tag} dist-tag names no version")


def _pypi_version(payload: object) -> Reading:
    info = payload.get("info") if isinstance(payload, dict) else None
    version = info.get("version") if isinstance(info, dict) else None
    return _version(version, "the project answer names no version")


def _github_version(channel: Channel, payload: object) -> Reading:
    if channel.tag_pattern is None:
        tag = payload.get("tag_name") if isinstance(payload, dict) else None
        return _version(tag, "the latest release names no tag")
    if not isinstance(payload, list):
        return Reading(outcome="unreachable", detail="the release list is not a list")
    pattern = re.compile(channel.tag_pattern)
    best: tuple[tuple[int, ...], str] | None = None
    for release in payload:
        if (
            not isinstance(release, dict)
            or release.get("draft")
            or release.get("prerelease")
        ):
            continue
        tag = release.get("tag_name")
        if (
            not isinstance(tag, str)
            or not pattern.fullmatch(tag)
            or not _SHOWN_VERSION.fullmatch(tag)
        ):
            continue
        numbers = version_numbers(tag)
        if numbers is not None and (best is None or numbers > best[0]):
            best = (numbers, tag)
    if best is None:
        # The channel's releases are not where the record says: renamed tags,
        # or other products' releases have pushed them out of the newest 100.
        detail = (
            f"no stable release among the newest {len(payload)} has a tag that "
            f"matches {channel.tag_pattern}"
            if payload
            else "the repository lists no releases"
        )
        return Reading(outcome="missing", detail=detail)
    return Reading(version=best[1])


# No registry answer the check reads nests more than a few levels. Python 3.14
# parses JSON nested far deeper than earlier versions, which raise
# RecursionError, so the limit is checked here and holds on every version.
_MAX_NESTING = 64


def _nests_deeper_than(body: bytes, limit: int) -> bool:
    """Return True when *body* opens more than *limit* nested arrays or objects."""
    depth = 0
    in_string = False
    escaped = False
    for byte in body:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 0x5C:  # backslash
                escaped = True
            elif byte == 0x22:  # double quote
                in_string = False
        elif byte == 0x22:
            in_string = True
        elif byte in (0x5B, 0x7B):  # [ {
            depth += 1
            if depth > limit:
                return True
        elif byte in (0x5D, 0x7D):  # ] }
            depth -= 1
    return False


def read(channel: Channel, response: Response) -> Reading:
    """Return the version a registry *response* names for *channel*."""
    if response.status in _GONE_STATUSES:
        return Reading(
            outcome="missing",
            detail=f"the registry answers {response.status}: no such package or release",
        )
    if (
        response.error is not None
        or response.status is None
        or not 200 <= response.status < 300
    ):
        return Reading(
            outcome="unreachable", detail=response.error or f"HTTP {response.status}"
        )
    if _nests_deeper_than(response.body, _MAX_NESTING):
        return Reading(
            outcome="unreachable",
            detail="the answer nests deeper than the check reads",
        )
    try:
        payload = json.loads(response.body)
    except RecursionError:
        return Reading(
            outcome="unreachable",
            detail="the answer nests deeper than the check reads",
        )
    except ValueError:
        return Reading(outcome="unreachable", detail="the answer is not JSON")
    if channel.registry == "npm":
        return _npm_version(channel, payload)
    if channel.registry == "pypi":
        return _pypi_version(payload)
    return _github_version(channel, payload)


def _first_difference(
    reviewed: tuple[int, ...], current: tuple[int, ...]
) -> tuple[str | None, bool]:
    """Return the first level at which *current* differs, and whether it is newer.

    Only the levels the reviewed version records are compared, so a record
    that holds a major alone matches every version of that major.
    """
    for index, expected in enumerate(reviewed):
        actual = current[index] if index < len(current) else 0
        if actual != expected:
            return LEVELS[index], actual > expected
    return None, False


def classify(channel: Channel, current: str) -> tuple[str, str, str | None]:
    """Return the outcome, a one-line detail, and any trigger action for *current*."""
    numbers = version_numbers(current)
    if numbers is None:
        return (
            "unreachable",
            f"the registry names {current}, which holds no version",
            None,
        )
    trigger = channel.trigger
    major_above = trigger.major_above if trigger is not None else None
    if trigger is not None and major_above is not None and numbers[0] > major_above:
        return (
            "drift",
            f"serves {current}, past major {major_above}, this channel's trigger",
            trigger.action,
        )
    reviewed = version_numbers(channel.reviewed) or ()
    level, newer = _first_difference(reviewed, numbers)
    if level is None:
        if len(reviewed) == 1:
            return (
                "clean",
                f"serves {current}, in the reviewed major {channel.reviewed}",
                None,
            )
        return "clean", f"serves {current}, the reviewed version", None
    if not newer:
        return (
            "info",
            f"serves {current}, older than the reviewed {channel.reviewed}",
            None,
        )
    if channel.versioning == "calendar":
        return (
            "info",
            f"serves {current}, newer than the reviewed {channel.reviewed}",
            None,
        )
    if LEVELS.index(level) <= LEVELS.index(channel.watch):
        return (
            "drift",
            f"serves {current}, a new {level} after the reviewed {channel.reviewed}",
            None,
        )
    return (
        "info",
        f"serves {current}, a newer {level} than the reviewed {channel.reviewed}",
        None,
    )


def _target(url: str, location: str) -> str | None:
    """Return the address a Location header points at, as the file writes it.

    Return None when the header is not an address the check reads.
    """
    try:
        target = urljoin(url, location.strip())
    except ValueError:
        return None
    https = "https://"
    # Any other scheme stays in place, so it never equals a reviewed target.
    shown = target[len(https) :] if target.startswith(https) else target
    return shown if _SHOWN_TARGET.fullmatch(shown) else None


def classify_redirect(
    channel: Channel, url: str, response: Response
) -> tuple[str, str | None, str, str | None]:
    """Return the outcome, target, detail and any trigger action of an address."""
    action = channel.trigger.action if channel.trigger is not None else None
    status = response.status
    if status in _GONE_STATUSES:
        return "missing", None, f"the address answers {status}: no such page", action
    if status is not None and 300 <= status < 400:
        if not response.location:
            return "unreachable", None, f"answers {status} with no target", None
        current = _target(url, response.location)
        if current is None:
            detail = (
                f"redirects to an address the check does not read, not the "
                f"reviewed {channel.reviewed}"
            )
            return "drift", None, detail, action
        if current == channel.reviewed:
            return (
                "clean",
                current,
                f"redirects to {current}, the reviewed target",
                None,
            )
        detail = f"redirects to {current}, not the reviewed {channel.reviewed}"
        return "drift", current, detail, action
    if status is not None and 200 <= status < 300:
        detail = (
            f"answers {status} without redirecting; it redirected to "
            f"{channel.reviewed} when reviewed"
        )
        return "drift", None, detail, action
    return "unreachable", None, response.error or f"HTTP {status}", None


def _classify_reading(
    channel: Channel, reading: Reading
) -> tuple[str, str | None, str, str | None]:
    """Return the outcome, version, detail and any trigger action of a reading."""
    if reading.version is None:
        outcome = reading.outcome or "unreachable"
        detail = reading.detail or "the registry names no version"
        # A channel that is gone can no longer show its trigger's signal.
        action = (
            channel.trigger.action
            if outcome == "missing" and channel.trigger is not None
            else None
        )
        return outcome, None, detail, action
    outcome, detail, action = classify(channel, reading.version)
    return outcome, reading.version, detail, action


def _check_channel(
    channel: Channel, url: str, headers: Mapping[str, str], fetcher: Fetcher
) -> ChannelReport:
    """Ask one channel's registry or address and classify the answer."""
    redirect = channel.registry == "redirect"
    if redirect:
        response = fetcher(url, headers, follow_redirects=False)
    else:
        response = fetcher(url, headers)
    try:
        if redirect:
            outcome, current, detail, action = classify_redirect(channel, url, response)
        else:
            outcome, current, detail, action = _classify_reading(
                channel, read(channel, response)
            )
    except Exception as exc:  # one answer the check cannot read stops no other
        outcome, current, action = "unreachable", None, None
        detail = f"the answer could not be read ({type(exc).__name__})"
    return ChannelReport(
        harness=channel.harness,
        channel=channel.label,
        outcome=outcome,
        reviewed=channel.reviewed,
        reviewed_on=channel.reviewed_on,
        current=current,
        detail=detail,
        url=url,
        status=response.status,
        trigger=action,
    )


def check(
    channels: Iterable[Channel],
    fetcher: Fetcher,
    *,
    token: str | None = None,
    budget: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> list[ChannelReport]:
    """Ask each channel's registry or address and classify the answer.

    Once *budget* seconds have passed, each channel left is reported as
    unreachable without a request.
    """
    started = clock()
    reports: list[ChannelReport] = []
    for channel in channels:
        url, headers = request_for(channel, token)
        if budget is not None and clock() - started >= budget:
            reports.append(
                ChannelReport(
                    harness=channel.harness,
                    channel=channel.label,
                    outcome="unreachable",
                    reviewed=channel.reviewed,
                    reviewed_on=channel.reviewed_on,
                    current=None,
                    detail=(
                        f"not asked: the run's time budget of {budget / 60:g} "
                        "minutes ran out"
                    ),
                    url=url,
                    status=None,
                )
            )
            continue
        reports.append(_check_channel(channel, url, headers, fetcher))
    return reports


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--channels",
        type=Path,
        default=CHANNELS_FILE,
        help="The channel file (default: vendor-release-channels.json beside this script).",
    )
    parser.add_argument(
        "--harnesses-root",
        type=Path,
        default=REPO_ROOT / "src" / "apothem" / "harnesses",
        help="Root directory containing harness adapter packages and their pins.",
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Optional JSON report path."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the channels and the harnesses not watched, without fetching.",
    )
    return parser.parse_args(argv)


def _print_list(channels: list[Channel], unwatched: list[NotWatched]) -> None:
    for channel in channels:
        sys.stdout.write(
            f"{channel.harness}\t{channel.label}\t"
            f"reviewed {channel.reviewed} on {channel.reviewed_on}\n"
        )
    for item in unwatched:
        sys.stdout.write(f"{item.harness}\tnot watched\t{item.reason}\n")


def _payload(
    reports: list[ChannelReport], unwatched: list[NotWatched], problems: list[str]
) -> dict[str, object]:
    failing = [r for r in reports if r.outcome in FAILING]
    return {
        "validator": "check_vendor_releases",
        "passed": not failing and not problems,
        "problems": problems,
        "channel_count": len(reports),
        "counts": {
            outcome: sum(1 for r in reports if r.outcome == outcome)
            for outcome in OUTCOMES
        },
        "channels": [asdict(report) for report in reports],
        "not_watched": [asdict(item) for item in unwatched],
    }


def _write_report(payload: Mapping[str, object], output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(rendered)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")


def _problems(
    args: argparse.Namespace,
) -> tuple[list[str], list[Channel], list[NotWatched]]:
    """Return what is wrong with the channel file or its evidence, and the file."""
    root: Path = args.harnesses_root
    if not root.is_dir():
        return [f"harnesses root not found: {root}"], [], []
    name = args.channels.name
    try:
        channels, unwatched = load_channels(args.channels)
    except ChannelFileError as exc:
        return [f"{name}: {exc}"], [], []
    problems = evidence_problems(channels, unwatched, root)
    return [f"{name}: {problem}" for problem in problems], channels, unwatched


def _run(args: argparse.Namespace, fetcher: Fetcher, clock: Callable[[], float]) -> int:
    problems, channels, unwatched = _problems(args)
    if problems:
        sys.stderr.write("".join(f"{problem}\n" for problem in problems))
        if not args.list:
            _write_report(_payload([], unwatched, problems), args.output)
        return 1
    if args.list:
        _print_list(channels, unwatched)
        return 0
    reports = check(
        channels,
        fetcher,
        token=os.environ.get("GITHUB_TOKEN") or None,
        budget=RUN_BUDGET_SECONDS,
        clock=clock,
    )
    payload = _payload(reports, unwatched, [])
    _write_report(payload, args.output)
    return 0 if payload["passed"] else 2


def main(
    argv: list[str] | None = None,
    *,
    fetcher: Fetcher = fetch,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """CLI entry point."""
    args = _parse_args(argv)
    try:
        return _run(args, fetcher, clock)
    except Exception as exc:  # the report still says why the run stopped
        traceback.print_exc()
        problem = _clip(f"the check stopped: {type(exc).__name__}: {exc}", 300)
        if not args.list:
            _write_report(_payload([], [], [problem]), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
