# SPDX-License-Identifier: MIT

"""Parity tests pinning the four MUST-NOT-DIVERGE hook couplings.

``askuserquestion_validator.py`` documents (near its ``STRICT_ENV`` declaration)
four comment-only couplings that MUST stay aligned with a source elsewhere, with
no shared source or enforcing test until now:

1. ``STRICT_ENV`` / truthy-set mirror ``conformity/gate.py``'s strict opt-in.
2. The recommended-marker matchers mirror ``conformity/option_annotation_grep``.
3. ``_BASH_GIT_TRIGGERS`` mirror the trigger list in
   ``hooks/messages/pretooluse-bash.md``.
4. The session-start plans-root resolver mirrors the statusline resolver.

These tests pin each pairing so a future edit to one side that silently diverges
from the other fails in CI rather than at an operator's live hook.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import ClassVar

_HOOKS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import askuserquestion_validator as aqv  # noqa: E402
import emit_hook_context as ehc  # noqa: E402

from apothem.conformity import gate, option_annotation_grep  # noqa: E402


class TestStrictOptInCoupling:
    """Coupling 1: the AskUserQuestion strict opt-in mirrors gate.py's."""

    def test_strict_env_name_matches_gate(self) -> None:
        assert aqv.STRICT_ENV == gate.STRICT_ENV

    def test_strict_truthy_set_matches_gate(self) -> None:
        assert aqv._STRICT_TRUTHY == gate._STRICT_TRUTHY


class TestRecommendedMarkerCoupling:
    """Coupling 2: the marker matchers agree with option_annotation_grep.

    The two families operate on different input shapes (a structured label
    string here; a Markdown line there), so the regex *sources* differ by
    design — but the CONTRACT they encode (capital ``(Recommended)`` at the
    label tail is canonical; the lowercase variant is banned) MUST agree on
    every shared example. This pins that agreement.
    """

    _CANONICAL: ClassVar[list[str]] = [
        "Proceed anyway (Recommended)",
        "pin-to-exact (Recommended)",
    ]
    _LOWERCASE: ClassVar[list[str]] = [
        "Proceed anyway (recommended)",
        "keep as-is (recommended)",
    ]
    _UNMARKED: ClassVar[list[str]] = [
        "Proceed anyway",
        "cancel the edit",
    ]

    def test_canonical_labels_agree(self) -> None:
        for label in self._CANONICAL:
            assert aqv._CANONICAL_POSTFIX_RE.search(label) is not None
            assert (
                option_annotation_grep._CANONICAL_POSTFIX_RE.search(label) is not None
            )

    def test_lowercase_labels_agree_as_banned(self) -> None:
        for label in self._LOWERCASE:
            # Neither family accepts the lowercase form as canonical...
            assert aqv._CANONICAL_POSTFIX_RE.search(label) is None
            assert option_annotation_grep._CANONICAL_POSTFIX_RE.search(label) is None
            # ...and both recognize it as the banned lowercase variant.
            assert aqv._LOWERCASE_POSTFIX_RE.search(label) is not None
            assert (
                option_annotation_grep._LOWERCASE_POSTFIX_RE.search(label) is not None
            )

    def test_unmarked_labels_agree(self) -> None:
        for label in self._UNMARKED:
            assert aqv._CANONICAL_POSTFIX_RE.search(label) is None
            assert option_annotation_grep._CANONICAL_POSTFIX_RE.search(label) is None
            assert aqv._LOWERCASE_POSTFIX_RE.search(label) is None
            assert option_annotation_grep._LOWERCASE_POSTFIX_RE.search(label) is None


class TestBashGitTriggerCoupling:
    """Coupling 3: ``_BASH_GIT_TRIGGERS`` mirror the message's trigger list."""

    def _triggers_from_message(self) -> set[str]:
        message = (_HOOKS_DIR / "messages" / "pretooluse-bash.md").read_text(
            encoding="utf-8"
        )
        # The Trigger line enumerates each git-mutation phrase in backticks.
        trigger_line = next(
            line for line in message.splitlines() if line.startswith("Trigger.")
        )
        return set(re.findall(r"`(git [^`]+)`", trigger_line))

    def test_code_triggers_match_message_triggers(self) -> None:
        assert set(ehc._BASH_GIT_TRIGGERS) == self._triggers_from_message()


class TestPlansRootResolverCoupling:
    """Coupling 4: the session-start resolver mirrors the statusline resolver.

    Both resolve to the canonical ``<base>/.apothem/plans`` tree when it exists
    on disk — the shared contract this pins. The session-start resolver
    additionally honors a legacy ``.plans`` tree as a documented dual-read
    fallback when the canonical tree is absent (see its docstring); that
    fallback is intentional and out of scope for this shared-target parity.
    """

    def test_both_resolve_canonical_apothem_plans_when_present(
        self, tmp_path: Path
    ) -> None:
        import session_start_bootstrap as ssb

        from apothem.statuslines import render

        # Canonical tree present on disk → both resolvers point at it.
        (tmp_path / ".apothem" / "plans").mkdir(parents=True)
        ssb_resolved = ssb._resolve_plan_suites_root(tmp_path)
        render_resolved = render._resolve_plans_dir(
            {"workspace": {"project_dir": str(tmp_path)}}
        )
        assert ssb_resolved == tmp_path / ".apothem" / "plans"
        assert render_resolved == tmp_path / ".apothem" / "plans"
        assert ssb_resolved == render_resolved
