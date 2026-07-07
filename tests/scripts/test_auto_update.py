# SPDX-License-Identifier: MIT

"""Unit tests for the ``auto_update`` checkout updater.

``scripts/dev/auto_update.py`` surfaces (and, with ``--apply``, fast-forwards
to) the latest signed release tag. It is release-critical and security-
relevant — it can move the operator's working tree — so the invariants under
test are: read-only by default (``_apply`` is reached only on ``behind`` +
``--apply``), verify-before-fast-forward (signature checked before the merge,
fail-closed unless ``APOTHEM_ALLOW_UNVERIFIED=1``), dirty-tree refusal, and the
``_check_state`` state machine. Every ``_git`` call is mocked, so the suite
touches neither the network nor a real repository.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import auto_update  # noqa: E402

GitResult = tuple[int, str, str]


def make_git(table: dict[tuple[str, ...], GitResult]) -> Callable[..., GitResult]:
    """Build a fake ``_git`` dispatching on the exact argument tuple."""

    def fake_git(*args: str, cwd: Path) -> GitResult:
        return table.get(tuple(args), (1, "", "not-mocked"))

    return fake_git


class TestReleaseTagRecognition:
    def test_is_release_tag_accepts_pure_semver_v_tag(self) -> None:
        assert auto_update._is_release_tag("v1.2.3") is True

    def test_is_release_tag_rejects_prerelease_and_non_tags(self) -> None:
        assert auto_update._is_release_tag("v1.2.3-rc1") is False
        assert auto_update._is_release_tag("v1.2") is False
        assert auto_update._is_release_tag("main") is False
        assert auto_update._is_release_tag("1.2.3") is False


class TestLatestReleaseTag:
    def test_returns_highest_by_numeric_components(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Lexical sort would pick v1.9.0 over v1.10.0; numeric sort must not.
        monkeypatch.setattr(
            auto_update,
            "_git",
            make_git(
                {
                    ("tag", "--list", "v*.*.*"): (
                        0,
                        "v1.9.0\nv1.10.0\nv1.2.3\nv0.1.0",
                        "",
                    )
                }
            ),
        )
        assert auto_update._latest_release_tag(tmp_path) == "v1.10.0"

    def test_excludes_prerelease_tags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auto_update,
            "_git",
            make_git({("tag", "--list", "v*.*.*"): (0, "v2.0.0-rc1\nv1.0.0", "")}),
        )
        # v2.0.0-rc1 is excluded -> the highest FINAL release is v1.0.0.
        assert auto_update._latest_release_tag(tmp_path) == "v1.0.0"

    def test_empty_when_no_tags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auto_update, "_git", make_git({("tag", "--list", "v*.*.*"): (0, "", "")})
        )
        assert auto_update._latest_release_tag(tmp_path) == ""


class TestResolveRef:
    def test_explicit_ref_wins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(auto_update, "DEFAULT_REF", "main")
        assert auto_update._resolve_ref(tmp_path) == "main"

    def test_defaults_to_latest_tag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(auto_update, "DEFAULT_REF", "")
        monkeypatch.setattr(auto_update, "_latest_release_tag", lambda _d: "v3.1.4")
        assert auto_update._resolve_ref(tmp_path) == "v3.1.4"

    def test_falls_back_to_main_when_no_tag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(auto_update, "DEFAULT_REF", "")
        monkeypatch.setattr(auto_update, "_latest_release_tag", lambda _d: "")
        assert auto_update._resolve_ref(tmp_path) == "main"


def _state_table(
    local: str, target: str, ab: str | None
) -> dict[tuple[str, ...], GitResult]:
    """Assemble a _check_state git table for the given HEAD/target SHAs."""
    table: dict[tuple[str, ...], GitResult] = {
        ("fetch", "--tags", "--prune", "origin"): (0, "", ""),
        ("tag", "--list", "v*.*.*"): (0, "v1.0.0", ""),
        ("rev-parse", "HEAD"): (0, local, ""),
        ("rev-parse", "v1.0.0"): (0, target, ""),
    }
    if ab is not None:
        table[("rev-list", "--left-right", "--count", f"HEAD...{target}")] = (0, ab, "")
    return table


class TestCheckState:
    def test_no_checkout_when_no_git_dir(self, tmp_path: Path) -> None:
        # tmp_path has no .git -> no-checkout, no git calls needed.
        state, *_ = auto_update._check_state(tmp_path)
        assert state == "no-checkout"

    def test_missing_remote_on_fetch_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.setattr(
            auto_update,
            "_git",
            make_git({("fetch", "--tags", "--prune", "origin"): (1, "", "no network")}),
        )
        state, _count, _l, err, _ref = auto_update._check_state(tmp_path)
        assert state == "missing-remote"
        assert err == "no network"

    def test_up_to_date_when_shas_match(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.setattr(auto_update, "DEFAULT_REF", "")
        monkeypatch.setattr(
            auto_update, "_git", make_git(_state_table("abc", "abc", None))
        )
        state, count, *_ = auto_update._check_state(tmp_path)
        assert state == "up-to-date"
        assert count == 0

    def test_behind_when_target_ahead(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.setattr(auto_update, "DEFAULT_REF", "")
        monkeypatch.setattr(
            auto_update, "_git", make_git(_state_table("abc", "def", "0\t3"))
        )
        state, count, _l, target, ref = auto_update._check_state(tmp_path)
        assert state == "behind"
        assert count == 3
        assert (target, ref) == ("def", "v1.0.0")

    def test_ahead_when_local_ahead(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.setattr(auto_update, "DEFAULT_REF", "")
        monkeypatch.setattr(
            auto_update, "_git", make_git(_state_table("abc", "def", "2\t0"))
        )
        state, count, *_ = auto_update._check_state(tmp_path)
        assert state == "ahead"
        assert count == 2

    def test_diverged_when_both(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.setattr(auto_update, "DEFAULT_REF", "")
        monkeypatch.setattr(
            auto_update, "_git", make_git(_state_table("abc", "def", "2\t5"))
        )
        state, *_ = auto_update._check_state(tmp_path)
        assert state == "diverged"


class TestVerifyRef:
    def test_release_tag_with_good_signature_verifies(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auto_update, "_git", make_git({("verify-tag", "v1.0.0"): (0, "", "")})
        )
        ok, reason = auto_update._verify_ref(tmp_path, "v1.0.0")
        assert ok is True
        assert reason == ""

    def test_release_tag_with_bad_signature_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auto_update,
            "_git",
            make_git({("verify-tag", "v1.0.0"): (1, "", "BAD signature")}),
        )
        ok, reason = auto_update._verify_ref(tmp_path, "v1.0.0")
        assert ok is False
        assert "BAD signature" in reason

    def test_non_release_ref_is_unverifiable(self, tmp_path: Path) -> None:
        ok, reason = auto_update._verify_ref(tmp_path, "main")
        assert ok is False
        assert "not a signed release tag" in reason


class TestApply:
    def test_dirty_tree_refuses_without_merging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_git(*args: str, cwd: Path) -> GitResult:
            calls.append(tuple(args))
            if args[:2] == ("status", "--porcelain"):
                return (0, " M file.py", "")
            return (0, "", "")

        monkeypatch.setattr(auto_update, "_git", fake_git)
        rc = auto_update._apply(tmp_path, "v1.0.0", "def")
        assert rc == 1
        # A dirty tree must short-circuit BEFORE any merge.
        assert not any(c[:1] == ("merge",) for c in calls)

    def test_unverified_refuses_when_not_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_git(*args: str, cwd: Path) -> GitResult:
            calls.append(tuple(args))
            if args[:2] == ("status", "--porcelain"):
                return (0, "", "")  # clean
            if args[:1] == ("verify-tag",):
                return (1, "", "no signature")  # verification fails
            return (0, "", "")

        monkeypatch.setattr(auto_update, "_git", fake_git)
        monkeypatch.setattr(auto_update, "ALLOW_UNVERIFIED", False)
        rc = auto_update._apply(tmp_path, "v1.0.0", "def")
        # Fail-closed: refuses, and crucially NEVER merges.
        assert rc == 1
        assert not any(c[:1] == ("merge",) for c in calls)

    def test_allow_unverified_downgrades_to_warning_and_merges(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_git(*args: str, cwd: Path) -> GitResult:
            calls.append(tuple(args))
            if args[:1] == ("verify-tag",):
                return (1, "", "no signature")
            return (0, "", "")

        monkeypatch.setattr(auto_update, "_git", fake_git)
        monkeypatch.setattr(auto_update, "ALLOW_UNVERIFIED", True)
        rc = auto_update._apply(tmp_path, "v1.0.0", "def")
        assert rc == 0
        assert ("merge", "--ff-only", "def") in calls

    def test_verified_tag_fast_forwards(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auto_update,
            "_git",
            make_git(
                {
                    ("status", "--porcelain"): (0, "", ""),
                    ("verify-tag", "v1.0.0"): (0, "", ""),
                    ("merge", "--ff-only", "def"): (0, "", ""),
                }
            ),
        )
        assert auto_update._apply(tmp_path, "v1.0.0", "def") == 0

    def test_fast_forward_failure_propagates_rc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auto_update,
            "_git",
            make_git(
                {
                    ("status", "--porcelain"): (0, "", ""),
                    ("verify-tag", "v1.0.0"): (0, "", ""),
                    ("merge", "--ff-only", "def"): (3, "", "not a ff"),
                }
            ),
        )
        assert auto_update._apply(tmp_path, "v1.0.0", "def") == 3


class TestMain:
    def test_read_only_by_default_does_not_apply_when_behind(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The core safety invariant: behind + NO --apply must never mutate.
        monkeypatch.setattr(
            auto_update,
            "_check_state",
            lambda _d: ("behind", 4, "abc", "def", "v1.0.0"),
        )
        applied: list[Any] = []
        monkeypatch.setattr(
            auto_update, "_apply", lambda *a, **k: applied.append(a) or 0
        )
        rc = auto_update.main(["--install-dir", str(tmp_path)])
        assert rc == 0
        assert applied == []  # _apply was never called

    def test_behind_with_apply_invokes_apply(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auto_update,
            "_check_state",
            lambda _d: ("behind", 4, "abc", "def", "v1.0.0"),
        )
        applied: list[tuple[Any, ...]] = []
        monkeypatch.setattr(
            auto_update, "_apply", lambda *a, **k: applied.append(a) or 0
        )
        rc = auto_update.main(["--install-dir", str(tmp_path), "--apply"])
        assert rc == 0
        assert len(applied) == 1
        # _apply receives (install_dir, ref, target_sha).
        assert applied[0][1:] == ("v1.0.0", "def")

    def test_check_only_behind_is_informational_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            auto_update,
            "_check_state",
            lambda _d: ("behind", 2, "abc", "def", "v1.0.0"),
        )
        rc = auto_update.main(["--install-dir", str(tmp_path), "--check-only"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "2 commit(s) behind v1.0.0" in out

    def test_up_to_date_returns_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auto_update,
            "_check_state",
            lambda _d: ("up-to-date", 0, "abc", "abc", "v1.0.0"),
        )
        assert auto_update.main(["--install-dir", str(tmp_path)]) == 0

    def test_no_checkout_returns_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auto_update, "_check_state", lambda _d: ("no-checkout", 0, "", "", "main")
        )
        assert auto_update.main(["--install-dir", str(tmp_path)]) == 1

    def test_diverged_returns_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            auto_update,
            "_check_state",
            lambda _d: ("diverged", 0, "abc", "def", "v1.0.0"),
        )
        assert auto_update.main(["--install-dir", str(tmp_path)]) == 1

    @pytest.mark.parametrize(
        ("state", "count", "expected_rc", "needle"),
        [
            ("up-to-date", 0, 0, "up-to-date (v1.0.0)"),
            ("ahead", 2, 0, "2 commit(s) ahead of v1.0.0"),
            ("diverged", 0, 1, "history diverged"),
            ("no-checkout", 0, 1, "no git checkout"),
            ("missing-remote", 0, 1, "cannot reach v1.0.0"),
        ],
    )
    def test_quiet_mode_one_line_banner_and_exit_code(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        state: str,
        count: int,
        expected_rc: int,
        needle: str,
    ) -> None:
        monkeypatch.setattr(
            auto_update,
            "_check_state",
            lambda _d: (state, count, "abc", "def", "v1.0.0"),
        )
        rc = auto_update.main(["--install-dir", str(tmp_path), "--quiet"])
        assert rc == expected_rc
        assert needle in capsys.readouterr().out
