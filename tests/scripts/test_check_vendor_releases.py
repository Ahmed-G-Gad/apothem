# SPDX-License-Identifier: MIT

"""Tests for the vendor release-channel checker. No test touches the network."""

from __future__ import annotations

import http.client
import io
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import urllib.response
from collections.abc import Collection, Mapping
from email.message import Message
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import check_vendor_releases as cvr  # noqa: E402

_HARNESSES = _REPO_ROOT / "src" / "apothem" / "harnesses"
_MONITOR = _REPO_ROOT / ".github" / "workflows" / "harness-convention-monitor.yml"
_NPM_URL = "https://registry.npmjs.org/-/package/tool-cli/dist-tags"
_LATEST_URL = "https://api.github.com/repos/acme/tool/releases/latest"
_LIST_URL = "https://api.github.com/repos/acme/tool/releases?per_page=100"
_PYPI_URL = "https://pypi.org/pypi/tool-cli/json"
_INSTALLER_URL = "https://get.acme.dev/install"
_TARGET = "raw.example.org/acme/tool/v1/install"
_PIN = (
    "# Pin\n\n"
    "- Vendor source: the `tool-cli` npm package, reviewed at 1.4.2.\n"
    "- Source: <https://github.com/acme/tool/tree/v0.26.0> and the PyPI project\n"
    "  `tool-cli`.\n"
    f"- Installer: `get.acme.dev/install` redirects to `{_TARGET}`.\n"
)


def _channel(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "registry": "npm",
        "name": "tool-cli",
        "tag": "latest",
        "reviewed": "1.4.2",
        "reviewed_on": "2026-11-01",
        "reviewed_from": "pin",
        "evidence": "the `tool-cli` npm package",
    }
    entry.update(overrides)
    return {key: value for key, value in entry.items() if value is not None}


def _github(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "registry": "github",
        "name": "acme/tool",
        "tag": None,
        "reviewed": "0.26.0",
        "evidence": "github.com/acme/tool",
    }
    entry.update(overrides)
    return _channel(**entry)


def _redirect(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "registry": "redirect",
        "name": "get.acme.dev/install",
        "tag": None,
        "reviewed": _TARGET,
        "evidence": f"`get.acme.dev/install` redirects to `{_TARGET}`",
        "trigger": {"action": "Read the new installer."},
    }
    entry.update(overrides)
    return _channel(**entry)


def _npm(**tags: str) -> cvr.Response:
    return cvr.Response(200, json.dumps(tags).encode("utf-8"))


def _json(payload: object) -> cvr.Response:
    return cvr.Response(200, json.dumps(payload).encode("utf-8"))


def _release(tag: str, *, prerelease: bool = False) -> dict[str, object]:
    return {"tag_name": tag, "draft": False, "prerelease": prerelease}


def _answering(
    answers: Mapping[str, cvr.Response], keep_redirects: Collection[str] = ()
) -> cvr.Fetcher:
    """Answer each known URL; *keep_redirects* must not follow their redirect."""

    def fetcher(
        url: str, _headers: Mapping[str, str], *, follow_redirects: bool = True
    ) -> cvr.Response:
        assert url in answers, f"unexpected request: {url}"
        assert follow_redirects is (url not in keep_redirects), url
        return answers[url]

    return fetcher


def _send_no_request(
    url: str, _headers: Mapping[str, str], **_kwargs: object
) -> cvr.Response:
    raise AssertionError(f"the check sent a request: {url}")


def _setup(
    tmp_path: Path, harnesses: Mapping[str, object], pin_text: str = _PIN
) -> tuple[Path, Path]:
    root = tmp_path / "harnesses"
    for name in harnesses:
        folder = root / name
        folder.mkdir(parents=True)
        folder.joinpath("capabilities.yml").write_text(
            'standard_convention_pin: "STANDARD-CONVENTION-PIN.md"\n', encoding="utf-8"
        )
        folder.joinpath("STANDARD-CONVENTION-PIN.md").write_text(
            pin_text, encoding="utf-8"
        )
    channels = tmp_path / "channels.json"
    channels.write_text(json.dumps({"harnesses": harnesses}), encoding="utf-8")
    return root, channels


def _run(
    tmp_path: Path,
    harnesses: Mapping[str, object],
    fetcher: cvr.Fetcher,
    pin_text: str = _PIN,
) -> tuple[int, dict[str, object]]:
    root, channels = _setup(tmp_path, harnesses, pin_text)
    output = tmp_path / "report.json"
    rc = cvr.main(
        [
            "--channels",
            str(channels),
            "--harnesses-root",
            str(root),
            "--output",
            str(output),
        ],
        fetcher=fetcher,
    )
    if not output.exists():
        return rc, {}
    return rc, json.loads(output.read_text(encoding="utf-8"))


def _one(payload: Mapping[str, object]) -> dict[str, object]:
    reports = payload["channels"]
    assert isinstance(reports, list)
    assert len(reports) == 1
    return reports[0]


def _refused(payload: Mapping[str, object]) -> list[str]:
    """Return the problems of a report written by a run that exited 1."""
    problems = payload["problems"]
    assert payload["passed"] is False
    assert payload["channels"] == []
    assert payload["channel_count"] == 0
    assert isinstance(problems, list)
    assert problems
    return problems


def test_a_new_major_is_drift(tmp_path: Path) -> None:
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [_channel()]}},
        _answering({_NPM_URL: _npm(latest="2.0.0", next="2.1.0-rc.1")}),
    )

    report = _one(payload)
    assert rc == 2
    assert payload["passed"] is False
    assert report["outcome"] == "drift"
    assert report["current"] == "2.0.0"
    assert report["detail"] == "serves 2.0.0, a new major after the reviewed 1.4.2"
    assert report["trigger"] is None


def test_the_reviewed_version_is_clean(tmp_path: Path) -> None:
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [_channel()]}},
        _answering({_NPM_URL: _npm(latest="1.4.2")}),
    )

    assert rc == 0
    assert payload["passed"] is True
    assert payload["counts"] == {
        "clean": 1,
        "info": 0,
        "drift": 0,
        "missing": 0,
        "unreachable": 0,
    }
    assert _one(payload)["outcome"] == "clean"


@pytest.mark.parametrize(
    ("latest", "detail"),
    [
        ("1.5.0", "serves 1.5.0, a newer minor than the reviewed 1.4.2"),
        ("1.4.3", "serves 1.4.3, a newer patch than the reviewed 1.4.2"),
        ("1.4.1", "serves 1.4.1, older than the reviewed 1.4.2"),
    ],
)
def test_a_newer_minor_or_patch_is_information(
    tmp_path: Path, latest: str, detail: str
) -> None:
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [_channel()]}},
        _answering({_NPM_URL: _npm(latest=latest)}),
    )

    report = _one(payload)
    assert rc == 0
    assert payload["passed"] is True
    assert report["outcome"] == "info"
    assert report["detail"] == detail


@pytest.mark.parametrize(
    ("response", "detail"),
    [
        pytest.param(cvr.Response(None, error="timed out"), "timed out", id="timeout"),
        pytest.param(cvr.Response(503, error="HTTP 503"), "HTTP 503", id="outage"),
        pytest.param(cvr.Response(403, error="HTTP 403"), "HTTP 403", id="rate-limit"),
        pytest.param(cvr.Response(429, error="HTTP 429"), "HTTP 429", id="too-many"),
        pytest.param(
            cvr.Response(200, b"<html>busy</html>"),
            "the answer is not JSON",
            id="not-json",
        ),
        pytest.param(
            _json(["1.4.2"]), "the dist-tags answer is not an object", id="wrong-shape"
        ),
        pytest.param(
            cvr.Response(200, error="the answer is larger than 16 MiB"),
            "the answer is larger than 16 MiB",
            id="too-large",
        ),
        pytest.param(
            cvr.Response(200, b"[" * 100_000 + b"]" * 100_000),
            "the answer nests deeper than the check reads",
            id="nested-too-deep",
        ),
        pytest.param(
            _npm(latest="1" + "0" * 5000),
            "the answer names a version in a form the check does not read",
            id="version-thousands-of-digits-long",
        ),
        pytest.param(
            _npm(latest="v9.0.0-@octocat<img/src=//evil.example/x.png>`x`"),
            "the answer names a version in a form the check does not read",
            id="version-with-markup",
        ),
    ],
)
def test_an_unreachable_channel_is_unreachable_not_drift(
    tmp_path: Path, response: cvr.Response, detail: str
) -> None:
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [_channel()]}},
        _answering({_NPM_URL: response}),
    )

    report = _one(payload)
    assert rc == 0
    assert payload["passed"] is True
    assert report["outcome"] == "unreachable"
    assert report["current"] is None
    assert report["detail"] == detail
    # Nothing the registry sent beyond the version form reaches the report.
    assert "octocat" not in json.dumps(payload)


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(cvr.Response(404, error="HTTP 404"), id="no-package"),
        pytest.param(cvr.Response(410, error="HTTP 410"), id="gone"),
        pytest.param(_npm(next="2.0.0"), id="no-dist-tag"),
    ],
)
def test_a_package_or_tag_that_is_gone_is_missing(
    tmp_path: Path, response: cvr.Response
) -> None:
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [_channel()]}},
        _answering({_NPM_URL: response}),
    )

    assert rc == 2
    assert _one(payload)["outcome"] == "missing"
    assert _one(payload)["trigger"] is None


def test_a_missing_channel_names_its_trigger_action(tmp_path: Path) -> None:
    # The trigger's signal can no longer be seen, so its action is reported.
    entry = _channel(trigger={"major_above": 1, "action": "Read the package."})
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [entry]}},
        _answering({_NPM_URL: cvr.Response(404, error="HTTP 404")}),
    )

    report = _one(payload)
    assert rc == 2
    assert report["outcome"] == "missing"
    assert report["trigger"] == "Read the package."


@pytest.mark.parametrize(
    ("response", "outcome", "current", "detail"),
    [
        pytest.param(
            cvr.Response(307, location=f"https://{_TARGET}"),
            "clean",
            _TARGET,
            f"redirects to {_TARGET}, the reviewed target",
            id="same-target",
        ),
        pytest.param(
            cvr.Response(302, location="https://raw.example.org/acme/tool/v2/install"),
            "drift",
            "raw.example.org/acme/tool/v2/install",
            f"redirects to raw.example.org/acme/tool/v2/install, not the reviewed {_TARGET}",
            id="new-target",
        ),
        pytest.param(
            cvr.Response(301, location="/v2/install"),
            "drift",
            "get.acme.dev/v2/install",
            f"redirects to get.acme.dev/v2/install, not the reviewed {_TARGET}",
            id="relative-target",
        ),
        pytest.param(
            cvr.Response(307, location=f"http://{_TARGET}"),
            "drift",
            f"http://{_TARGET}",
            f"redirects to http://{_TARGET}, not the reviewed {_TARGET}",
            id="plain-http-target",
        ),
        pytest.param(
            cvr.Response(200, b"#!/bin/sh\n"),
            "drift",
            None,
            f"answers 200 without redirecting; it redirected to {_TARGET} when reviewed",
            id="no-redirect",
        ),
        pytest.param(
            cvr.Response(307, location="https://[bad/install"),
            "drift",
            None,
            f"redirects to an address the check does not read, not the reviewed {_TARGET}",
            id="target-that-does-not-parse",
        ),
        pytest.param(
            cvr.Response(
                302,
                location=(
                    "https://evil.example/install [Fix now](https://phish.example/)"
                    " @octocat <b>bold</b>"
                ),
            ),
            "drift",
            None,
            f"redirects to an address the check does not read, not the reviewed {_TARGET}",
            id="target-with-markup",
        ),
    ],
)
def test_an_installer_address_is_judged_by_its_redirect_target(
    tmp_path: Path,
    response: cvr.Response,
    outcome: str,
    current: str | None,
    detail: str,
) -> None:
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [_redirect()]}},
        _answering({_INSTALLER_URL: response}, keep_redirects={_INSTALLER_URL}),
    )

    report = _one(payload)
    assert report["channel"] == "redirect get.acme.dev/install"
    assert report["outcome"] == outcome
    assert report["current"] == current
    assert report["detail"] == detail
    assert report["trigger"] == (
        None if outcome == "clean" else "Read the new installer."
    )
    assert rc == (0 if outcome == "clean" else 2)
    assert "octocat" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("response", "outcome", "detail"),
    [
        pytest.param(
            cvr.Response(404, error="HTTP 404"),
            "missing",
            "the address answers 404: no such page",
            id="gone",
        ),
        pytest.param(
            cvr.Response(410, error="HTTP 410"),
            "missing",
            "the address answers 410: no such page",
            id="removed",
        ),
        pytest.param(
            cvr.Response(307, error="HTTP 307"),
            "unreachable",
            "answers 307 with no target",
            id="no-location",
        ),
        pytest.param(
            cvr.Response(None, error="timed out"),
            "unreachable",
            "timed out",
            id="timeout",
        ),
        pytest.param(
            cvr.Response(503, error="HTTP 503"), "unreachable", "HTTP 503", id="outage"
        ),
        pytest.param(
            cvr.Response(403, error="HTTP 403"), "unreachable", "HTTP 403", id="blocked"
        ),
    ],
)
def test_an_installer_address_that_is_gone_or_silent_names_no_target(
    tmp_path: Path, response: cvr.Response, outcome: str, detail: str
) -> None:
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [_redirect()]}},
        _answering({_INSTALLER_URL: response}, keep_redirects={_INSTALLER_URL}),
    )

    report = _one(payload)
    assert report["outcome"] == outcome
    assert report["current"] is None
    assert report["detail"] == detail
    # An address that is gone no longer redirects to the reviewed target, so
    # it names the trigger's action; one that does not answer names none.
    assert report["trigger"] == (
        "Read the new installer." if outcome == "missing" else None
    )
    assert rc == (2 if outcome == "missing" else 0)


def test_an_installer_address_is_asked_without_the_token_or_its_redirect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_example_only")
    seen: dict[str, tuple[dict[str, str], bool]] = {}

    def fetcher(
        url: str, headers: Mapping[str, str], *, follow_redirects: bool = True
    ) -> cvr.Response:
        seen[url] = (dict(headers), follow_redirects)
        return cvr.Response(307, location=f"https://{_TARGET}")

    rc, payload = _run(tmp_path, {"alpha": {"channels": [_redirect()]}}, fetcher)

    headers, follow = seen[_INSTALLER_URL]
    assert rc == 0
    assert _one(payload)["outcome"] == "clean"
    assert follow is False
    assert "Authorization" not in headers


def _real_answers(overrides: Mapping[str, str]) -> cvr.Fetcher:
    """Answer every real channel with what was reviewed, bar *overrides*."""
    channels, _unwatched = cvr.load_channels(cvr.CHANNELS_FILE)
    answers: dict[str, cvr.Response] = {}
    keep_redirects: set[str] = set()
    for channel in channels:
        url, _headers = cvr.request_for(channel)
        value = overrides.get(channel.name, channel.reviewed)
        if channel.registry == "redirect":
            answers[url] = cvr.Response(307, location=f"https://{value}")
            keep_redirects.add(url)
        elif channel.registry == "npm":
            answers[url] = _npm(**{channel.tag: value})
        elif channel.registry == "pypi":
            answers[url] = _json({"info": {"version": value}})
        elif channel.tag_pattern:
            answers[url] = _json([_release(f"v{value}")])
        else:
            answers[url] = _json(_release(f"v{value}"))
    return _answering(answers, keep_redirects)


def _run_repository(
    tmp_path: Path, overrides: Mapping[str, str]
) -> tuple[int, dict[str, dict[str, object]]]:
    output = tmp_path / "report.json"
    rc = cvr.main(["--output", str(output)], fetcher=_real_answers(overrides))
    payload = json.loads(output.read_text(encoding="utf-8"))
    return rc, {f"{r['harness']} {r['channel']}": r for r in payload["channels"]}


def test_the_opencode_trigger_fires_when_opencode_ai_moves_to_2(
    tmp_path: Path,
) -> None:
    rc, reports = _run_repository(tmp_path, {"opencode-ai": "2.0.0"})

    one = reports["opencode npm opencode-ai@latest"]
    two = reports["opencode npm @opencode/cli@latest"]
    assert rc == 2
    assert one["outcome"] == "drift"
    assert one["detail"] == "serves 2.0.0, past major 1, this channel's trigger"
    assert isinstance(one["trigger"], str)
    assert "version-aware output" in one["trigger"]
    assert two["outcome"] == "clean"
    others = [
        r for key, r in reports.items() if key != "opencode npm opencode-ai@latest"
    ]
    assert {r["outcome"] for r in others} == {"clean"}


def test_the_opencode_trigger_stays_quiet_on_the_opencode_1_line(
    tmp_path: Path,
) -> None:
    rc, reports = _run_repository(tmp_path, {"opencode-ai": "1.20.0"})

    one = reports["opencode npm opencode-ai@latest"]
    assert rc == 0
    assert one["outcome"] == "info"
    assert one["trigger"] is None


def test_the_opencode_trigger_fires_when_the_installer_redirects_elsewhere(
    tmp_path: Path,
) -> None:
    target = "raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/install"
    rc, reports = _run_repository(tmp_path, {"opencode.ai/install": target})

    installer = reports["opencode redirect opencode.ai/install"]
    assert rc == 2
    assert installer["outcome"] == "drift"
    assert installer["current"] == target
    assert isinstance(installer["trigger"], str)
    assert "version-aware output" in installer["trigger"]
    others = [
        r
        for key, r in reports.items()
        if key != "opencode redirect opencode.ai/install"
    ]
    assert {r["outcome"] for r in others} == {"clean"}


def test_a_new_opencode_major_line_shows_in_its_github_releases(
    tmp_path: Path,
) -> None:
    rc, reports = _run_repository(tmp_path, {"anomalyco/opencode": "3.0.0"})

    releases = reports["opencode github anomalyco/opencode releases"]
    assert rc == 2
    assert releases["outcome"] == "drift"
    assert releases["detail"] == "serves v3.0.0, a new major after the reviewed 2.2.5"


def test_every_recorded_channel_cites_evidence_present_in_its_pin() -> None:
    channels, unwatched = cvr.load_channels(cvr.CHANNELS_FILE)
    pins = cvr.harness_pins(_HARNESSES)

    assert cvr.evidence_problems(channels, unwatched, _HARNESSES) == []
    # Every harness folder has exactly one entry: its channels, or the reason
    # it is not watched.
    watched = {channel.harness for channel in channels}
    assert watched.isdisjoint(item.harness for item in unwatched)
    assert watched | {item.harness for item in unwatched} == set(pins)
    for channel in channels:
        text = " ".join(pins[channel.harness].read_text(encoding="utf-8").split())
        assert " ".join(channel.evidence.split()) in text, channel.label
        assert channel.name in channel.evidence, channel.label
        if channel.reviewed_from == "pin":
            assert channel.reviewed in text, channel.label
    assert all(item.reason.strip() for item in unwatched)


def test_the_opencode_record_watches_both_lines_and_both_switch_signals() -> None:
    channels, _unwatched = cvr.load_channels(cvr.CHANNELS_FILE)
    opencode = {c.name: c for c in channels if c.harness == "opencode"}

    assert set(opencode) == {
        "opencode-ai",
        "@opencode/cli",
        "anomalyco/opencode",
        "opencode.ai/install",
    }
    one, two = opencode["opencode-ai"], opencode["@opencode/cli"]
    assert one.trigger is not None
    assert one.trigger.major_above == 1
    assert one.reviewed.startswith("1.")
    assert two.trigger is None
    assert two.reviewed.startswith("2.")
    releases = opencode["anomalyco/opencode"]
    assert releases.registry == "github"
    assert releases.tag_pattern is not None
    installer = opencode["opencode.ai/install"]
    assert installer.registry == "redirect"
    assert installer.reviewed.endswith("/refs/heads/v1/install")
    assert installer.trigger is not None
    assert installer.trigger.major_above is None


@pytest.mark.parametrize(
    ("pin_text", "entry", "problem"),
    [
        pytest.param(
            "# Pin\n",
            _channel(reviewed_from="registry"),
            "evidence is not in STANDARD-CONVENTION-PIN.md",
            id="evidence-absent",
        ),
        pytest.param(
            _PIN,
            _channel(evidence="Vendor source"),
            "evidence does not name tool-cli",
            id="evidence-names-another-thing",
        ),
        pytest.param(
            _PIN,
            _channel(reviewed="1.4.20"),
            "reviewed 1.4.20 is not in STANDARD-CONVENTION-PIN.md",
            id="reviewed-version-absent",
        ),
        pytest.param(
            _PIN,
            _redirect(
                reviewed="raw.example.org/acme/tool/v1/inst",
                evidence="`get.acme.dev/install`",
            ),
            "reviewed raw.example.org/acme/tool/v1/inst is not in "
            "STANDARD-CONVENTION-PIN.md",
            id="reviewed-target-only-a-prefix",
        ),
        pytest.param(
            "- the `tool-cli` npm package, release 1.4.2.1.\n",
            _channel(),
            "reviewed 1.4.2 is not in STANDARD-CONVENTION-PIN.md",
            id="reviewed-only-inside-a-longer-version",
        ),
        pytest.param(
            "- the `tool-cli` npm package, release 1.4.2-rc.1.\n",
            _channel(),
            "reviewed 1.4.2 is not in STANDARD-CONVENTION-PIN.md",
            id="reviewed-only-as-a-prerelease",
        ),
    ],
)
def test_evidence_that_the_pin_does_not_hold_is_refused(
    tmp_path: Path, pin_text: str, entry: dict[str, object], problem: str
) -> None:
    root, channels = _setup(tmp_path, {"alpha": {"channels": [entry]}}, pin_text)
    loaded, unwatched = cvr.load_channels(channels)

    problems = cvr.evidence_problems(loaded, unwatched, root)

    assert len(problems) == 1
    assert problem in problems[0]
    # The run stops before any request, and its report says why.
    rc, payload = _run(
        tmp_path / "run", {"alpha": {"channels": [entry]}}, _send_no_request, pin_text
    )
    assert rc == 1
    assert _refused(payload) == [f"channels.json: {problems[0]}"]


def test_a_harness_folder_without_an_entry_is_refused(tmp_path: Path) -> None:
    root, channels = _setup(tmp_path, {"alpha": {"channels": [_channel()]}})
    extra = root / "beta"
    extra.mkdir()
    extra.joinpath("capabilities.yml").write_text("", encoding="utf-8")
    extra.joinpath("STANDARD-CONVENTION-PIN.md").write_text(_PIN, encoding="utf-8")
    loaded, unwatched = cvr.load_channels(channels)

    assert cvr.evidence_problems(loaded, unwatched, root) == [
        "beta: no entry for this harness folder"
    ]


@pytest.mark.parametrize(
    ("latest", "outcome"),
    [("1.5.0", "drift"), ("1.4.3", "info"), ("2.0.0", "drift")],
)
def test_a_watch_level_turns_a_newer_minor_into_drift(
    tmp_path: Path, latest: str, outcome: str
) -> None:
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [_channel(watch="minor")]}},
        _answering({_NPM_URL: _npm(latest=latest)}),
    )

    assert _one(payload)["outcome"] == outcome
    assert rc == (2 if outcome == "drift" else 0)


@pytest.mark.parametrize(
    ("latest", "outcome", "detail"),
    [
        ("1.9.4", "clean", "serves 1.9.4, in the reviewed major 1"),
        ("2.0.0", "drift", "serves 2.0.0, a new major after the reviewed 1"),
    ],
)
def test_a_record_of_a_major_alone_matches_every_version_of_it(
    tmp_path: Path, latest: str, outcome: str, detail: str
) -> None:
    entry = _channel(reviewed="1", reviewed_from="registry")
    _rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [entry]}},
        _answering({_NPM_URL: _npm(latest=latest)}),
    )

    report = _one(payload)
    assert report["outcome"] == outcome
    assert report["detail"] == detail


@pytest.mark.parametrize("latest", ["2027.1.2", "2026.11.1"])
def test_a_calendar_version_reports_a_new_year_as_information(
    tmp_path: Path, latest: str
) -> None:
    entry = _channel(
        reviewed="2026.10.10", reviewed_from="registry", versioning="calendar"
    )
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [entry]}},
        _answering({_NPM_URL: _npm(latest=latest)}),
    )

    assert rc == 0
    assert _one(payload)["outcome"] == "info"


def test_a_github_channel_reads_the_latest_release_tag(tmp_path: Path) -> None:
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [_github()]}},
        _answering({_LATEST_URL: _json(_release("rust-v0.27.1"))}),
    )

    report = _one(payload)
    assert rc == 0
    assert report["current"] == "rust-v0.27.1"
    assert report["outcome"] == "info"
    assert (
        report["detail"]
        == "serves rust-v0.27.1, a newer minor than the reviewed 0.26.0"
    )


def test_a_latest_release_tag_that_holds_no_version_is_unreachable(
    tmp_path: Path,
) -> None:
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [_github()]}},
        _answering({_LATEST_URL: _json(_release("nightly"))}),
    )

    report = _one(payload)
    assert rc == 0
    assert report["outcome"] == "unreachable"
    assert report["current"] == "nightly"
    assert report["detail"] == "the registry names nightly, which holds no version"


def test_a_tag_pattern_picks_the_newest_stable_matching_release(
    tmp_path: Path,
) -> None:
    releases = [
        _release("sdk-typescript-v1.1.27"),
        _release("v0.27.0-nightly.20261102", prerelease=True),
        # Matches the pattern and is newer, but is a prerelease.
        _release("v0.26.9", prerelease=True),
        _release("desktop-v0.26.9"),
        _release("v0.26.5"),
        _release("v0.26.6"),
        {"tag_name": "v0.30.0", "draft": True, "prerelease": False},
    ]
    entry = _github(tag_pattern="v[0-9]+[.][0-9]+[.][0-9]+")
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [entry]}},
        _answering({_LIST_URL: _json(releases)}),
    )

    report = _one(payload)
    assert rc == 0
    assert report["current"] == "v0.26.6"
    assert report["outcome"] == "info"


@pytest.mark.parametrize(
    ("releases", "detail"),
    [
        pytest.param(
            [_release("sdk-typescript-v0.1.27")],
            "no stable release among the newest 1 has a tag that matches "
            "v[0-9]+[.][0-9]+[.][0-9]+",
            id="no-tag-matches",
        ),
        pytest.param(
            [
                _release("v0.27.0", prerelease=True),
                {"tag_name": "v0.28.0", "draft": True, "prerelease": False},
            ],
            "no stable release among the newest 2 has a tag that matches "
            "v[0-9]+[.][0-9]+[.][0-9]+",
            id="only-prereleases-and-drafts-match",
        ),
        pytest.param([], "the repository lists no releases", id="no-releases"),
    ],
)
def test_a_tag_pattern_with_no_stable_match_is_missing(
    tmp_path: Path, releases: list[dict[str, object]], detail: str
) -> None:
    entry = _github(
        tag_pattern="v[0-9]+[.][0-9]+[.][0-9]+",
        trigger={"major_above": 0, "action": "Find the CLI releases."},
    )
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [entry]}},
        _answering({_LIST_URL: _json(releases)}),
    )

    report = _one(payload)
    assert rc == 2
    assert report["outcome"] == "missing"
    assert report["current"] is None
    assert report["detail"] == detail
    assert report["trigger"] == "Find the CLI releases."


def test_a_pypi_project_reads_its_version(tmp_path: Path) -> None:
    entry = _channel(
        registry="pypi", tag=None, reviewed="2.1.0", reviewed_from="registry"
    )
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [entry]}},
        _answering({_PYPI_URL: _json({"info": {"version": "3.0.0"}})}),
    )

    assert rc == 2
    assert _one(payload)["outcome"] == "drift"


def test_the_token_goes_to_the_github_api_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_example_only")
    seen: dict[str, Mapping[str, str]] = {}

    def fetcher(
        url: str, headers: Mapping[str, str], **_kwargs: object
    ) -> cvr.Response:
        seen[url] = dict(headers)
        if url == _NPM_URL:
            return _npm(latest="1.4.2")
        return _json(_release("v0.26.0"))

    rc, payload = _run(
        tmp_path, {"alpha": {"channels": [_channel(), _github()]}}, fetcher
    )

    assert rc == 0
    assert seen[_LATEST_URL]["Authorization"] == "Bearer ghs_example_only"
    assert "Authorization" not in seen[_NPM_URL]
    assert "ghs_example_only" not in json.dumps(payload)


class _Answer:
    """A 200 answer whose body comes in *chunks*, one per read."""

    status = 200

    def __init__(self, *chunks: bytes) -> None:
        self._chunks = list(chunks or (b"{}",))

    def __enter__(self) -> _Answer:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self, _size: int) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""


def test_fetch_keeps_the_token_off_other_hosts_and_off_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[urllib.request.Request] = []

    def urlopen(request: urllib.request.Request, **_kwargs: object) -> _Answer:
        sent.append(request)
        return _Answer()

    monkeypatch.setattr(cvr.urllib.request, "urlopen", urlopen)
    token = {"Authorization": "Bearer ghs_example_only", "Accept": "application/json"}

    cvr.fetch("https://registry.npmjs.org/-/package/tool-cli/dist-tags", token)
    cvr.fetch(_LATEST_URL, token)

    npm, github = sent
    assert not npm.has_header("Authorization")
    assert github.unredirected_hdrs == {"Authorization": "Bearer ghs_example_only"}
    assert "Authorization" not in github.headers


class _ServeOneRedirect(urllib.request.HTTPSHandler):
    """Answer every https request with one redirect, without a network."""

    def __init__(self, status: int, location: str | None) -> None:
        super().__init__()
        self.status = status
        self.location = location
        self.seen: list[str] = []

    def https_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
        self.seen.append(req.full_url)
        headers = Message()
        if self.location is not None:
            headers["Location"] = self.location
        answer = urllib.response.addinfourl(
            io.BytesIO(b""), headers, req.full_url, self.status
        )
        answer.msg = "Temporary Redirect"
        return answer


@pytest.mark.parametrize("location", [f"https://{_TARGET}", None])
def test_fetch_hands_back_a_redirect_it_was_told_not_to_follow(
    monkeypatch: pytest.MonkeyPatch, location: str | None
) -> None:
    served = _ServeOneRedirect(307, location)
    build_opener = urllib.request.build_opener
    handlers: list[object] = []

    def build(*given: object) -> urllib.request.OpenerDirector:
        handlers.extend(given)
        return build_opener(*given, served)

    def no_urlopen(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a redirect that is kept never goes through urlopen")

    monkeypatch.setattr(cvr.urllib.request, "build_opener", build)
    monkeypatch.setattr(cvr.urllib.request, "urlopen", no_urlopen)

    response = cvr.fetch(_INSTALLER_URL, {}, follow_redirects=False)

    assert handlers == [cvr._KeepRedirect]
    assert served.seen == [_INSTALLER_URL]
    assert response.status == 307
    assert response.location == location


def test_fetch_hands_back_a_kept_redirect_whose_target_does_not_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    served = _ServeOneRedirect(307, "https://[bad/install")
    build_opener = urllib.request.build_opener
    monkeypatch.setattr(
        cvr.urllib.request, "build_opener", lambda *given: build_opener(*given, served)
    )

    response = cvr.fetch(_INSTALLER_URL, {}, follow_redirects=False)

    assert response.status == 307
    assert response.location == "https://[bad/install"


def test_fetch_reports_a_followed_redirect_that_does_not_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    served = _ServeOneRedirect(307, "https://[bad/install")
    opener = urllib.request.build_opener(served)
    calls: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> object:
        calls.append(request.full_url)
        return opener.open(request, timeout=timeout)

    monkeypatch.setattr(cvr.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(cvr.time, "sleep", lambda _seconds: None)

    response = cvr.fetch(_NPM_URL, {}, attempts=3)

    # urllib raises ValueError on the Location; another attempt gets the same.
    assert calls == [_NPM_URL]
    assert response.status is None
    assert response.error == "the answer could not be used (ValueError)"


def test_fetch_abandons_an_attempt_that_outlasts_its_time_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A name lookup, or a connection to one silent address after another,
    # that never ends.
    release = threading.Event()
    calls: list[int] = []

    def stall(*_args: object, **_kwargs: object) -> object:
        calls.append(1)
        release.wait(30)
        raise TimeoutError("timed out")

    monkeypatch.setattr(cvr.urllib.request, "urlopen", stall)
    monkeypatch.setattr(cvr.time, "sleep", lambda _seconds: None)
    started = time.monotonic()
    try:
        response = cvr.fetch(_NPM_URL, {}, attempts=2, timeout=0.2)
    finally:
        release.set()

    assert time.monotonic() - started < 10
    assert len(calls) == 2
    assert response.status is None
    assert response.error == "no complete answer within 0.2 seconds"


class _Drip(_Answer):
    """An answer that sends one byte at a time, each well inside a read timeout."""

    def read1(self, _size: int) -> bytes:
        time.sleep(0.02)
        return b" "


def test_fetch_stops_reading_an_answer_that_arrives_too_slowly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cvr.urllib.request, "urlopen", lambda *_a, **_k: _Drip())
    started = time.monotonic()

    response = cvr.fetch(_NPM_URL, {}, attempts=1, timeout=0.3)

    assert time.monotonic() - started < 10
    assert response.status is None
    assert response.error == "no complete answer within 0.3 seconds"


def test_fetch_refuses_an_answer_larger_than_its_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk = b"x" * (64 * 1024)
    calls: list[int] = []

    def urlopen(*_args: object, **_kwargs: object) -> _Answer:
        calls.append(1)
        return _Answer(*[chunk] * 40)

    monkeypatch.setattr(cvr, "_MAX_BODY", 2 * 1024 * 1024)
    monkeypatch.setattr(cvr.urllib.request, "urlopen", urlopen)

    response = cvr.fetch(_NPM_URL, {}, attempts=3)

    # Not cut short and parsed as broken JSON, and not asked for again.
    assert calls == [1]
    assert response.status == 200
    assert response.body == b""
    assert response.error == "the answer is larger than 2 MiB"


def _short_answer() -> http.client.HTTPResponse:
    """A 200 answer that gives its length, then closes after part of the body."""
    body = b'{"tag_name": "v0.26.0", "draft": false}'
    raw = (
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        + body[:14]
    )
    answer = http.client.HTTPResponse(_Socket(raw))  # type: ignore[arg-type]
    answer.begin()
    return answer


def test_fetch_retries_an_answer_shorter_than_its_stated_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def urlopen(*_args: object, **_kwargs: object) -> http.client.HTTPResponse:
        calls.append(1)
        return _short_answer()

    monkeypatch.setattr(cvr.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(cvr.time, "sleep", lambda _seconds: None)

    response = cvr.fetch(_LATEST_URL, {}, attempts=3)

    assert len(calls) == 3
    assert response.status is None
    assert response.error == "the answer broke off after 14 of 39 bytes"


@pytest.mark.parametrize(("code", "calls"), [(503, 3), (502, 3), (404, 1), (403, 1)])
def test_fetch_retries_only_the_server_errors_an_outage_produces(
    monkeypatch: pytest.MonkeyPatch, code: int, calls: int
) -> None:
    seen: list[int] = []

    def fail(*_args: object, **_kwargs: object) -> object:
        seen.append(code)
        raise urllib.error.HTTPError(_NPM_URL, code, "error", Message(), None)

    monkeypatch.setattr(cvr.urllib.request, "urlopen", fail)
    monkeypatch.setattr(cvr.time, "sleep", lambda _seconds: None)

    response = cvr.fetch(_NPM_URL, {}, attempts=3)

    assert len(seen) == calls
    assert response.status == code


def test_fetch_reports_a_network_failure_without_a_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.URLError(ConnectionRefusedError("refused"))

    monkeypatch.setattr(cvr.urllib.request, "urlopen", fail)
    monkeypatch.setattr(cvr.time, "sleep", lambda _seconds: None)

    response = cvr.fetch(_NPM_URL, {}, attempts=2)

    assert response.status is None
    assert response.error == "refused"


class _Socket:
    """Hand http.client a recorded answer, as a socket's file would."""

    def __init__(self, data: bytes) -> None:
        self._file = io.BytesIO(data)

    def makefile(self, *_args: object, **_kwargs: object) -> io.BytesIO:
        return self._file


def _cut_off_answer() -> http.client.HTTPResponse:
    """A chunked 200 answer whose connection drops partway through the body."""
    body = b'{"tag_name": "v0.26.0", "draft": false}'
    raw = (
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        b"Transfer-Encoding: chunked\r\n\r\n"
        + f"{len(body):x}\r\n".encode("ascii")
        + body[:14]
    )
    answer = http.client.HTTPResponse(_Socket(raw))  # type: ignore[arg-type]
    answer.begin()
    return answer


def test_fetch_retries_an_answer_cut_off_partway_then_reports_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def urlopen(*_args: object, **_kwargs: object) -> http.client.HTTPResponse:
        calls.append(1)
        return _cut_off_answer()

    monkeypatch.setattr(cvr.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(cvr.time, "sleep", lambda _seconds: None)

    response = cvr.fetch(_LATEST_URL, {}, attempts=3)

    assert len(calls) == 3
    assert response.status is None
    assert response.error is not None
    assert response.error.startswith("IncompleteRead(")


def test_an_answer_cut_off_partway_is_unreachable_and_the_report_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cvr.urllib.request, "urlopen", lambda *_a, **_k: _cut_off_answer()
    )
    monkeypatch.setattr(cvr.time, "sleep", lambda _seconds: None)

    rc, payload = _run(tmp_path, {"alpha": {"channels": [_github()]}}, cvr.fetch)

    report = _one(payload)
    assert rc == 0
    assert report["outcome"] == "unreachable"
    assert str(report["detail"]).startswith("IncompleteRead(")


def test_fetch_reports_an_answer_that_is_not_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def urlopen(*_args: object, **_kwargs: object) -> object:
        calls.append(1)
        raise http.client.BadStatusLine("garbage")

    monkeypatch.setattr(cvr.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(cvr.time, "sleep", lambda _seconds: None)

    response = cvr.fetch(_NPM_URL, {}, attempts=2)

    assert len(calls) == 2
    assert response.status is None
    assert response.error == "BadStatusLine('garbage')"


def test_the_check_job_outlasts_a_run_where_every_request_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each attempt takes its whole time limit, the most fetch() lets it take
    # however many addresses a host resolves to and however slowly it answers.
    clock = [0.0]

    def time_out(_request: object, timeout: float = 0.0) -> object:
        clock[0] += timeout
        raise TimeoutError("timed out")

    class _Opener:
        def open(self, request: object, timeout: float = 0.0) -> object:
            return time_out(request, timeout)

    def sleep(seconds: float) -> None:
        clock[0] += seconds

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(cvr.urllib.request, "urlopen", time_out)
    monkeypatch.setattr(cvr.urllib.request, "build_opener", lambda *_h: _Opener())
    monkeypatch.setattr(cvr.time, "sleep", sleep)
    output = tmp_path / "report.json"

    rc = cvr.main(["--output", str(output)], clock=lambda: clock[0])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 0
    assert report["counts"]["unreachable"] == report["channel_count"]
    backoff = sum(2**attempt for attempt in range(cvr.ATTEMPTS - 1))
    per_channel = cvr.ATTEMPTS * cvr.ATTEMPT_SECONDS + backoff
    # The run asks no channel once its budget has passed, so it ends within
    # the budget and one more channel's worst case.
    bound = cvr.RUN_BUDGET_SECONDS + per_channel
    assert clock[0] <= bound, (clock[0], bound)
    workflow = yaml.safe_load(_MONITOR.read_text(encoding="utf-8"))
    minutes = workflow["jobs"]["vendor-release-check"]["timeout-minutes"]
    # Leave five minutes for the job's other steps.
    assert bound + 5 * 60 <= minutes * 60, (bound, minutes)


def test_the_run_asks_no_channel_once_its_time_budget_runs_out(
    tmp_path: Path,
) -> None:
    clock = [0.0]
    asked: list[str] = []

    def slow(url: str, _headers: Mapping[str, str], **_kwargs: object) -> cvr.Response:
        asked.append(url)
        clock[0] += 500.0
        return _npm(latest="1.4.2")

    _root, channels_file = _setup(
        tmp_path, {name: {"channels": [_channel()]} for name in "abcde"}
    )
    channels, _unwatched = cvr.load_channels(channels_file)

    reports = cvr.check(channels, slow, budget=1200.0, clock=lambda: clock[0])

    # Asked at 0, 500 and 1000 seconds; at 1500 the budget has run out.
    assert len(asked) == 3
    assert [r.outcome for r in reports] == ["clean"] * 3 + ["unreachable"] * 2
    assert {r.detail for r in reports[3:]} == {
        "not asked: the run's time budget of 20 minutes ran out"
    }
    assert all(r.status is None and r.current is None for r in reports[3:])


def test_one_answer_the_check_cannot_read_stops_no_other_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_channel: cvr.Channel, _payload: object) -> cvr.Reading:
        raise KeyError("an answer shape no branch expects")

    monkeypatch.setattr(cvr, "_npm_version", boom)
    rc, payload = _run(
        tmp_path,
        {"alpha": {"channels": [_channel()]}, "beta": {"channels": [_github()]}},
        _answering(
            {
                _NPM_URL: _npm(latest="2.0.0"),
                _LATEST_URL: _json(_release("v0.26.0")),
            }
        ),
    )

    reports = {r["harness"]: r for r in payload["channels"]}
    assert rc == 0
    assert reports["alpha"]["outcome"] == "unreachable"
    assert reports["alpha"]["detail"] == "the answer could not be read (KeyError)"
    assert reports["alpha"]["current"] is None
    assert reports["beta"]["outcome"] == "clean"


def test_a_run_that_stops_on_an_error_still_writes_its_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def crash(*_args: object, **_kwargs: object) -> list[cvr.ChannelReport]:
        raise RuntimeError("boom")

    monkeypatch.setattr(cvr, "check", crash)
    rc, payload = _run(
        tmp_path, {"alpha": {"channels": [_channel()]}}, _send_no_request
    )

    assert rc == 1
    assert _refused(payload) == ["the check stopped: RuntimeError: boom"]


def test_fetch_refuses_a_url_that_is_not_https() -> None:
    response = cvr.fetch("http://registry.npmjs.org/-/package/x/dist-tags", {})

    assert response.status is None
    assert response.error == "not an https URL"


@pytest.mark.parametrize(
    "harnesses",
    [
        pytest.param({"alpha": {"channels": [_channel(extra=1)]}}, id="unknown-key"),
        pytest.param(
            {"alpha": {"channels": [_channel()], "not_watched": "no"}},
            id="both-kinds",
        ),
        pytest.param({"alpha": {"channels": []}}, id="no-channels"),
        pytest.param(
            {"alpha": {"channels": [_channel(reviewed="1.x")]}}, id="reviewed"
        ),
        pytest.param(
            {"alpha": {"channels": [_channel(reviewed_on="2026-13-01")]}}, id="date"
        ),
        pytest.param({"alpha": {"channels": [_channel(name="Tool CLI")]}}, id="name"),
        pytest.param(
            {"alpha": {"channels": [_github(tag="latest")]}}, id="tag-on-github"
        ),
        pytest.param(
            {"alpha": {"channels": [_channel(tag_pattern="v.*")]}}, id="pattern-on-npm"
        ),
        pytest.param(
            {"alpha": {"channels": [_github(tag_pattern="v[")]}}, id="bad-pattern"
        ),
        pytest.param(
            {"alpha": {"channels": [_channel(trigger={"major_above": 1})]}},
            id="trigger-without-action",
        ),
        pytest.param(
            {"alpha": {"channels": [_channel(trigger={"action": "Look."})]}},
            id="trigger-without-major",
        ),
        pytest.param(
            {"alpha": {"channels": [_channel(watch="build")]}}, id="watch-level"
        ),
        pytest.param(
            {
                "alpha": {
                    "channels": [
                        _channel(
                            reviewed="2026.10.10",
                            reviewed_from="registry",
                            versioning="calendar",
                            watch="minor",
                        )
                    ]
                }
            },
            id="watch-on-calendar",
        ),
        pytest.param(
            {"alpha": {"channels": [_channel(reviewed="1.4.1234567890")]}},
            id="reviewed-number-too-long",
        ),
        pytest.param({"alpha": {"not_watched": " "}}, id="empty-reason"),
        pytest.param(
            {"alpha": {"channels": [_redirect(name=_INSTALLER_URL)]}},
            id="address-with-scheme",
        ),
        pytest.param(
            {"alpha": {"channels": [_redirect(reviewed="the v1 script")]}},
            id="target-not-an-address",
        ),
        pytest.param(
            {"alpha": {"channels": [_redirect(watch="patch")]}},
            id="watch-on-address",
        ),
        pytest.param(
            {"alpha": {"channels": [_redirect(versioning="calendar")]}},
            id="versioning-on-address",
        ),
        pytest.param(
            {
                "alpha": {
                    "channels": [
                        _redirect(trigger={"major_above": 1, "action": "Look."})
                    ]
                }
            },
            id="major-on-address",
        ),
    ],
)
def test_the_channel_file_format_is_enforced(
    tmp_path: Path, harnesses: Mapping[str, object]
) -> None:
    rc, payload = _run(tmp_path, harnesses, _send_no_request)

    assert rc == 1
    [problem] = _refused(payload)
    assert problem.startswith("channels.json: ")


def test_list_prints_the_channels_without_fetching(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, channels = _setup(
        tmp_path,
        {
            "alpha": {"channels": [_channel()]},
            "beta": {"not_watched": "Desktop only."},
            "gamma": {"channels": [_redirect()]},
        },
    )

    rc = cvr.main(
        ["--channels", str(channels), "--harnesses-root", str(root), "--list"],
        fetcher=_send_no_request,
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "alpha\tnpm tool-cli@latest\treviewed 1.4.2 on 2026-11-01\n" in out
    assert "beta\tnot watched\tDesktop only.\n" in out
    assert (
        f"gamma\tredirect get.acme.dev/install\treviewed {_TARGET} on 2026-11-01\n"
        in out
    )


def test_missing_root_returns_error(tmp_path: Path) -> None:
    rc = cvr.main(
        ["--harnesses-root", str(tmp_path / "absent")], fetcher=_send_no_request
    )

    assert rc == 1
