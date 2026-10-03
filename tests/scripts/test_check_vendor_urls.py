# SPDX-License-Identifier: MIT

"""Tests for the vendor URL checker over harness pins and templates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import check_vendor_urls as cvu  # noqa: E402


def _harness(root: Path, name: str, pin: str, template: str | None = None) -> None:
    folder = root / name
    folder.mkdir()
    (folder / "STANDARD-CONVENTION-PIN.md").write_text(pin, encoding="utf-8")
    if template is not None:
        (folder / "templates").mkdir()
        (folder / "templates" / "rules.md").write_text(template, encoding="utf-8")


def test_collects_urls_from_pins_and_templates(tmp_path: Path) -> None:
    _harness(
        tmp_path,
        "alpha",
        "- vendor-doc-url: <https://docs.example.org/rules>.\n"
        "- base: `https://api.z.ai/api/anthropic`\n"
        "- placeholder: https://<your-server-url>/mcp\n",
        "See https://docs.example.org/rules, and (https://docs.example.org/mcp).\n",
    )
    _harness(tmp_path, "_shared", "https://docs.example.org/ignored\n")

    cited = cvu.collect_urls(cvu.cited_files(tmp_path), tmp_path)

    assert cited == {
        "https://docs.example.org/mcp": ["alpha/templates/rules.md"],
        "https://docs.example.org/rules": [
            "alpha/STANDARD-CONVENTION-PIN.md",
            "alpha/templates/rules.md",
        ],
    }


@pytest.mark.parametrize(
    ("url", "result", "outcome"),
    [
        ("https://a.dev/x", cvu.FetchResult(200, "https://a.dev/x/"), "ok"),
        ("https://a.dev/x", cvu.FetchResult(200, "https://a.dev/y"), "moved"),
        ("https://a.dev/", cvu.FetchResult(200, "https://a.dev/start"), "ok"),
        ("https://a.dev/x", cvu.FetchResult(404, "https://a.dev/x"), "dead"),
        ("https://a.dev/x", cvu.FetchResult(None, None, "reset"), "dead"),
        ("https://a.dev/x", cvu.FetchResult(403, "https://a.dev/x"), "blocked"),
        ("https://a.dev/x", cvu.FetchResult(429, "https://a.dev/x"), "blocked"),
        (
            "https://json.schemastore.org/claude-code-settings.json",
            cvu.FetchResult(
                200, "https://www.schemastore.org/claude-code-settings.json"
            ),
            "ok",
        ),
        (
            "https://json.schemastore.org/a.json",
            cvu.FetchResult(200, "https://www.schemastore.org/b.json"),
            "moved",
        ),
    ],
)
def test_classify(url: str, result: cvu.FetchResult, outcome: str) -> None:
    assert cvu.classify(url, result) == outcome


def test_fetch_refuses_non_http_schemes() -> None:
    result = cvu.fetch("file:///etc/passwd", attempts=1)
    assert result.status is None
    assert result.error == "not an http(s) URL"


def test_main_fails_on_moved_and_dead_but_not_blocked(tmp_path: Path) -> None:
    root = tmp_path / "harnesses"
    root.mkdir()
    _harness(
        root,
        "alpha",
        "https://a.dev/ok https://a.dev/old https://a.dev/gone https://a.dev/bot\n",
    )
    answers = {
        "https://a.dev/ok": cvu.FetchResult(200, "https://a.dev/ok"),
        "https://a.dev/old": cvu.FetchResult(200, "https://a.dev/new"),
        "https://a.dev/gone": cvu.FetchResult(404, "https://a.dev/gone"),
        "https://a.dev/bot": cvu.FetchResult(403, "https://a.dev/bot"),
    }
    output = tmp_path / "report.json"

    rc = cvu.main(
        ["--harnesses-root", str(root), "--output", str(output)],
        fetcher=answers.__getitem__,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 2
    assert payload["passed"] is False
    assert payload["counts"] == {"ok": 1, "moved": 1, "dead": 1, "blocked": 1}
    moved = next(u for u in payload["urls"] if u["outcome"] == "moved")
    assert moved["final_url"] == "https://a.dev/new"
    assert moved["cited_in"] == ["alpha/STANDARD-CONVENTION-PIN.md"]


def test_main_passes_when_every_url_resolves(tmp_path: Path) -> None:
    _harness(tmp_path, "alpha", "https://a.dev/ok\n")
    rc = cvu.main(
        ["--harnesses-root", str(tmp_path), "--output", str(tmp_path / "r.json")],
        fetcher=lambda url: cvu.FetchResult(200, url),
    )
    assert rc == 0


def test_missing_root_returns_error(tmp_path: Path) -> None:
    assert cvu.main(["--harnesses-root", str(tmp_path / "absent")]) == 1
