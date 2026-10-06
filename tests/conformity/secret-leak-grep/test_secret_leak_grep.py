# SPDX-License-Identifier: MIT

"""Behavioral pass+fail coverage for the secret-leak matcher.

Clean prose with no credential literal passes; content carrying a planted
fake vendor-prefixed secret (AWS access key, GitHub token, RSA private-key
header) fails with a redacted finding. The planted values are synthetic
and match only the matcher's distinctive prefixes — they are not real
credentials.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "secret_leak_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("secret_leak_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["secret_leak_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()
_PATH: Final[Path] = Path("src/apothem/config.py")


def test_clean_content_passes() -> None:
    body = "\n".join(
        [
            "import os",
            "",
            "API_KEY = os.environ['APOTHEM_TOKEN']",
            "TIMEOUT = 30  # seconds",
        ]
    )
    result = _MOD.check(body, _PATH)
    assert result.passed, [f.label for f in result.findings]
    assert result.findings == []


def test_planted_aws_key_fails() -> None:
    body = 'aws_key = "AKIA' + "ABCDEFGHIJKLMNOP" + '"'
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("AWS access key" in f.label for f in result.findings)


def test_planted_github_token_fails() -> None:
    body = 'token = "ghp_' + ("a" * 36) + '"'
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("GitHub" in f.label for f in result.findings)


def test_planted_rsa_private_key_header_fails() -> None:
    body = "-----BEGIN RSA PRIVATE KEY-----"
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert result.findings


def test_finding_value_is_redacted() -> None:
    body = 'aws_key = "AKIA' + "ABCDEFGHIJKLMNOP" + '"'
    result = _MOD.check(body, _PATH)
    assert not result.passed
    # The raw 20-char key must not appear verbatim in any finding report.
    assert all("AKIAABCDEFGHIJKLMNOP" not in f.redacted_match for f in result.findings)


def test_planted_github_oauth_token_fails() -> None:
    body = 'token = "gho_' + ("a" * 36) + '"'
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("GitHub" in f.label for f in result.findings)


def test_planted_github_server_token_fails() -> None:
    body = 'token = "ghs_' + ("a" * 36) + '"'
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("GitHub" in f.label for f in result.findings)


def test_planted_github_user_token_fails() -> None:
    body = 'token = "ghu_' + ("a" * 36) + '"'
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("GitHub" in f.label for f in result.findings)


def test_planted_github_refresh_token_fails() -> None:
    body = 'token = "ghr_' + ("a" * 36) + '"'
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("GitHub" in f.label for f in result.findings)


def test_planted_openai_key_fails() -> None:
    body = 'key = "sk-' + ("0123456789abcdef" * 2) + '"'
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("OpenAI" in f.label for f in result.findings)


def test_planted_slack_token_fails() -> None:
    body = 'token = "xoxb-' + ("0" * 12) + '"'
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("Slack" in f.label for f in result.findings)


def test_planted_google_api_key_fails() -> None:
    body = 'key = "AIza' + ("a" * 35) + '"'
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("Google" in f.label for f in result.findings)


def test_planted_jwt_fails() -> None:
    body = "token = eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcDEF123"
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("JWT" in f.label for f in result.findings)


def test_planted_high_entropy_token_fails() -> None:
    # A 40-char token whose Shannon entropy exceeds 4.5 bits/char and which
    # matches no named vendor prefix exercises the entropy heuristic.
    body = "secret = " + "aB3xQ9zK7mP2wV5tR8nL4cY6hD1gF0sJ7uE2oI9"
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("high-entropy token" in f.label for f in result.findings)


def test_banner_line_exempted() -> None:
    body = "#  Email:     mailto:me@ahmedgad.com              #"
    result = _MOD.check(body, _PATH)
    assert result.passed, [f.label for f in result.findings]
    assert result.findings == []


def test_every_banner_token_exempted() -> None:
    for token in _MOD.BANNER_ALLOW_LIST:
        body = f"# banner line containing {token} here"
        result = _MOD.check(body, _PATH)
        assert result.passed, (token, [f.label for f in result.findings])


def test_banner_allow_list_does_not_mask_real_secret_elsewhere() -> None:
    body = (
        "#  Email:     mailto:me@ahmedgad.com              #\n"
        'AWS_ACCESS_KEY_ID = "AKIA' + "QWERTYUIOPASDFGH" + '"\n'
    )
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert all(f.line == 2 for f in result.findings)


# AWS publishes these two values in its documentation as placeholders; they
# are not credentials, so a docs page or a code sample quoting them passes.
_AWS_DOC_KEY_ID: Final[str] = "AKIA" + "IOSFODNN7EXAMPLE"
_AWS_DOC_SECRET: Final[str] = "wJalrXUtnFEMI/K7MDENG/" + "bPxRfiCYEXAMPLEKEY"


def test_aws_documentation_example_key_id_passes() -> None:
    body = f'aws_access_key_id = "{_AWS_DOC_KEY_ID}"'
    result = _MOD.check(body, _PATH)
    assert result.passed, [f.label for f in result.findings]


def test_aws_documentation_example_secret_passes() -> None:
    body = f'aws_secret_access_key = "{_AWS_DOC_SECRET}"'
    result = _MOD.check(body, _PATH)
    assert result.passed, [f.label for f in result.findings]


def test_example_allow_list_does_not_mask_real_key_on_same_line() -> None:
    """Only the exact published placeholder is exempt, not its whole line."""
    body = f"{_AWS_DOC_KEY_ID} rotated to AKIA" + "QWERTYUIOPASDFGH"
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert len(result.findings) == 1
    assert result.findings[0].label == "AWS access key"


def test_near_miss_of_example_key_is_still_flagged() -> None:
    """A key that only resembles the placeholder is detected."""
    body = 'aws_key = "AKIA' + "IOSFODNN7EXAMPLF" + '"'
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any("AWS access key" in f.label for f in result.findings)
