# SPDX-License-Identifier: MIT

"""Unit tests for the solo-maintainer self-merge ceremony.

``scripts/dev/admin_merge.py`` runs a temp-toggle ceremony: capture the
branch's ``required_approving_review_count``, relax it to 0, squash-merge with
admin override, then restore the original count. The load-bearing invariant is
the ``try``/``finally`` ROLLBACK SAFETY -- the protection must be restored even
when the merge fails, or ``main`` is left unprotected. Every ``gh`` call is
mocked through ``_run``; the network and the real repo are never touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import admin_merge as am  # noqa: E402


class _FakeProc:
    """Stand-in for a completed subprocess.

    Carries only the fields the ceremony reads — return code and captured
    output — so the double cannot imply a dependency the code does not have.
    """

    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _install_fake_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    current_count: int = 1,
    merge_fails: bool = False,
    restore_fails: bool = False,
) -> tuple[list[list[str]], list[int]]:
    """Patch am._run with a gh-aware stub. Returns (all_calls, set_values)."""
    calls: list[list[str]] = []
    set_values: list[int] = []

    def fake_run(cmd: list[str], *, capture: bool = False) -> str:
        calls.append(list(cmd))
        if cmd[:3] == ["gh", "repo", "view"]:
            return "owner/repo"
        if ".required_approving_review_count" in cmd:  # the capture jq call
            return str(current_count)
        if "-F" in cmd:  # PATCH set-count call
            value = int(cmd[cmd.index("-F") + 1].split("=")[1])
            set_values.append(value)
            if restore_fails and value == current_count:
                raise am.AdminMergeError("restore boom")
            return ""
        if cmd[:3] == ["gh", "pr", "merge"]:
            if merge_fails:
                raise am.AdminMergeError("merge boom")
            return ""
        return ""

    monkeypatch.setattr(am, "_run", fake_run)
    return calls, set_values


class TestRunHelper:
    """The subprocess helper.

    Covers stdout returned on success and the raise on a non-zero exit, so a
    failed step cannot be mistaken for an empty result.
    """

    def test_returns_stdout_on_capture_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            am.subprocess, "run", lambda *a, **k: _FakeProc(0, stdout="owner/repo\n")
        )
        assert am._run(["gh", "x"], capture=True) == "owner/repo\n"

    def test_raises_on_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            am.subprocess, "run", lambda *a, **k: _FakeProc(1, stderr="boom")
        )
        with pytest.raises(am.AdminMergeError, match="exit 1"):
            am._run(["gh", "x"])


class TestCaptureApproverCount:
    """Parsing the approver count from the forge response."""

    def test_parses_int(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(am, "_run", lambda *a, **k: " 2 \n")
        assert am._capture_approver_count("o/r") == 2


class TestAdminMergeCeremony:
    """The relax-merge-restore ceremony.

    Covers the happy path relaxing then restoring protection, and — the property
    that matters most — that protection is restored even when the merge fails.
    Also covers a restore failure being surfaced rather than swallowed, and the
    repository defaulting to the current checkout.
    """

    def test_happy_path_relaxes_then_restores(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _calls, set_values = _install_fake_run(monkeypatch, current_count=1)

        am.admin_merge(7, "owner/repo")

        # Relaxed to 0, then restored to the captured original (1).
        assert set_values == [0, 1]

    def test_rollback_restores_protection_even_when_merge_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # THE invariant: a failed merge must NOT leave main relaxed.
        calls, set_values = _install_fake_run(
            monkeypatch, current_count=1, merge_fails=True
        )

        with pytest.raises(am.AdminMergeError, match="merge boom"):
            am.admin_merge(7, "owner/repo")

        # Despite the merge failure, the finally clause restored the count to 1.
        assert set_values == [0, 1]
        assert any(c[:3] == ["gh", "pr", "merge"] for c in calls)

    def test_restore_failure_is_surfaced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # If the restore itself fails, the operator must be told (it re-raises).
        _install_fake_run(monkeypatch, current_count=1, restore_fails=True)
        with pytest.raises(am.AdminMergeError, match="restore boom"):
            am.admin_merge(7, "owner/repo")

    def test_repo_defaults_to_gh_repo_view(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls, _ = _install_fake_run(monkeypatch, current_count=1)
        am.admin_merge(7, None)  # no repo -> resolve via gh repo view
        assert any(c[:3] == ["gh", "repo", "view"] for c in calls)


class TestParseArgs:
    """Command-line argument parsing.

    Covers the pull-request number parsed as an integer with the repository
    optional.
    """

    def test_pr_number_is_int_repo_optional(self) -> None:
        args = am._parse_args(["42"])
        assert args.pr_number == 42
        assert args.repo is None
        args2 = am._parse_args(["42", "owner/name"])
        assert args2.repo == "owner/name"


class TestMain:
    """Process-level entry point behaviour.

    Covers zero on success and one on a ceremony failure.
    """

    def test_returns_zero_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(am, "admin_merge", lambda *a, **k: None)
        assert am.main(["7", "owner/repo"]) == 0

    def test_returns_one_on_ceremony_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*_a: object, **_k: object) -> None:
            raise am.AdminMergeError("nope")

        monkeypatch.setattr(am, "admin_merge", boom)
        assert am.main(["7"]) == 1
