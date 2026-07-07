# SPDX-License-Identifier: MIT

"""Property tests for `install_driver_pathsafety` write-target validation.

Path-escape validation is the install driver's security primitive: every
resolved write target is run through `_validate_target_path` before any byte is
written, and a target that escapes the allowed materialization root — or crosses
a symlink — must be rejected. A single false-safe verdict would let a crafted
profile (or a `..`-laden cohort path) write outside the harness's own tree.

Invariants exercised over auto-generated path components (safe segments plus
``..`` traversal tokens), against a real temporary root so the case-fold and
symlink-chain probes run against an actual filesystem:

* **Acceptance.** A target built from only safe, non-traversing segments under
  the allowed root is accepted (`result is None`) — the validator never
  over-rejects a legitimate in-root write.
* **Escape rejection.** A target with enough leading ``..`` tokens to climb above
  the filesystem root genuinely escapes, and is always rejected
  (`result is not None`) — no escaping path is ever deemed safe.
* **Verdict ⇔ containment.** For any generated path (with or without traversal),
  the safe verdict tracks an *independent* containment oracle exactly: with no
  symlink present, `(_validate_target_path(...) is None)` equals
  `_is_relative_to(_normalized(target), _normalized(root))`. The validator adds
  no false-safe and no false-reject beyond containment-plus-symlink.

No symlinks are created, so the symlink-chain guard is a no-op here and the
verdict isolates the escape check; the symlink leg has its own unit coverage.
Segments are lowercase-only so the independent exact-containment oracle is not
perturbed by the case-fold path the validator takes on case-insensitive volumes.

`derandomize=True` pins the generated inputs so the same examples run every CI
invocation; `deadline=None` removes per-example filesystem-probe timing flakiness.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# ``install_driver_pathsafety`` sits inside the _shared install-driver import
# cycle (pathsafety -> types -> install_driver -> apply -> backup -> pathsafety);
# the cycle resolves only when entered via the ``install_driver`` top, so import
# that first for its module-init side effect before reaching the leaf module.
from apothem.harnesses._shared import install_driver as _install_driver  # noqa: F401
from apothem.harnesses._shared.install_driver_pathsafety import (
    _is_relative_to,
    _normalized,
    _validate_target_path,
    _within_allowed_root,
)

# A real, empty temporary root reused across examples. The validator only reads
# the filesystem (``.exists()`` / ``.is_symlink()``); no example mutates it, so a
# single module-scoped root is sound and the directory auto-cleans at exit.
_TMP = tempfile.TemporaryDirectory(prefix="apothem-pathsafety-prop-")
_ROOT = Path(_TMP.name).resolve()

# Conservative, deterministic property settings (mirrors the merge / frontmatter
# property-test templates, plus derandomize for byte-stable CI runs).
TEST_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)

# Lowercase path-segment alphabet — no separators, no dots, so a segment is never
# ``.`` / ``..`` / empty, and case-folding never perturbs the exact oracle.
_SAFE_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789-_"
_safe_segment = st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=8)
_safe_parts = st.lists(_safe_segment, min_size=1, max_size=5)
_traversal_parts = st.lists(
    st.one_of(_safe_segment, st.just("..")), min_size=1, max_size=6
)


@given(parts=_safe_parts)
@TEST_SETTINGS
def test_safe_in_root_target_is_accepted(parts: list[str]) -> None:
    """A non-traversing target under the allowed root is never rejected."""
    target = _ROOT.joinpath(*parts)
    result = _validate_target_path(target, allowed_root=_ROOT, operation="install")
    assert result is None, f"legitimate in-root target rejected: {target}"
    assert _within_allowed_root(target, _ROOT)


@given(tail=_safe_segment)
@TEST_SETTINGS
def test_escaping_target_is_always_rejected(tail: str) -> None:
    """A target that climbs above the filesystem root is always rejected."""
    # Enough ``..`` tokens to climb past the root's depth (``..`` clamps at the
    # filesystem root), so the final segment lands outside the allowed root.
    climb = [".."] * (len(_ROOT.parts) + 2)
    target = _ROOT.joinpath(*climb, tail)
    # Sanity: the target genuinely escapes by independent normalization.
    assert not _is_relative_to(_normalized(target), _normalized(_ROOT))
    result = _validate_target_path(target, allowed_root=_ROOT, operation="install")
    assert result is not None, f"escaping target deemed safe: {target}"


@given(parts=_traversal_parts)
@TEST_SETTINGS
def test_verdict_matches_independent_containment(parts: list[str]) -> None:
    """The safe verdict tracks independent path-containment exactly (no symlink)."""
    target = _ROOT.joinpath(*parts)
    contained = _is_relative_to(_normalized(target), _normalized(_ROOT))
    result = _validate_target_path(target, allowed_root=_ROOT, operation="install")
    assert (result is None) == contained, (
        f"verdict/containment mismatch for {target}: "
        f"safe={result is None} contained={contained}"
    )
