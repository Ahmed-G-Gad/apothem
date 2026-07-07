# SPDX-License-Identifier: MIT

"""Property tests for `install_driver._merge_json_values`.

The JSON-settings merge is the operator-safety primitive: when Apothem
re-materializes a harness config that the operator has hand-edited, the merge
must never silently drop an operator-authored key. Two collision policies share
one recursion:

* `prefer_existing=True` (the operator-preserving merge, `_merge_json_settings`)
  keeps the existing value on every key collision; keys only in the incoming
  object are added.
* `prefer_existing=False` (the managed-overlay merge, `_overlay_json_settings`)
  takes the incoming value on a key collision; keys only in the existing object
  are still retained.

Invariants exercised over auto-generated safe JSON-like maps:

* prefer_existing=True keeps every existing key with its existing value, at
  every nesting depth, while adding incoming-only keys (no operator key dropped).
* prefer_existing=False takes the incoming value on a collision while retaining
  existing-only keys (the merge stays additive; only collision-resolution flips).
* The merge is idempotent: re-merging the same incoming object is a no-op
  (`merge(merge(a, b), b) == merge(a, b)` for a fixed prefer flag).

Semantics are grounded on the real `_merge_json_values` body: dicts merge
recursively; on a non-dict collision the prefer flag picks the winner; lists
under `prefer_existing=True` are deduped-union, and under `prefer_existing=False`
the incoming list replaces the existing list; scalars are replaced, not merged.
The generated inputs avoid the special-cased `hooks` key so the assertions
reflect the generic dict/list/scalar paths only.

These property runs land in CI on every PR. `derandomize=True` pins the
generated inputs so the same examples run every CI invocation (deterministic
under a fixed seed), and `deadline=None` removes per-example timing flakiness.
"""

from __future__ import annotations

from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apothem.harnesses._shared.install_driver import _merge_json_values

# Conservative, deterministic property settings (mirrors the frontmatter
# property-test template, plus derandomize for byte-stable CI runs).
TEST_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)

# Safe object keys: short ASCII identifiers. "hooks" is excluded so the generic
# dict/list/scalar merge paths are exercised, not the Claude-Code hook-merge
# special case the real function branches into for that exact key.
json_keys = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), max_codepoint=127),
    min_size=1,
    max_size=6,
).filter(lambda s: s != "hooks")

# Leaf JSON scalars and short scalar lists (no nested dicts at the leaf level;
# the recursion is supplied by st.recursive below).
json_scalars = st.one_of(
    st.text(max_size=8),
    st.integers(min_value=-1000, max_value=1000),
    st.booleans(),
    st.none(),
)
json_leaves = st.one_of(
    json_scalars,
    st.lists(json_scalars, max_size=4),
)

# Recursive JSON-like maps: dicts of keys to leaves-or-nested-dicts, bounded so
# property runs stay fast.
json_maps = st.recursive(
    st.dictionaries(json_keys, json_leaves, max_size=4),
    lambda children: st.dictionaries(json_keys, children, max_size=3),
    max_leaves=8,
)


def _assert_existing_keys_preserved(existing: object, merged: object) -> None:
    """Recursively assert every operator key in `existing` survives in `merged`.

    Under prefer_existing=True: a scalar collision keeps the existing scalar
    exactly; a dict collision recurses; a LIST collision is a dedupe-UNION
    (`_dedupe_json_list`) that keeps every operator list item but may also carry
    incoming items, so the operator items are preserved as a subset (not
    value-identical); an existing-only key is carried verbatim. A dropped key, a
    dropped operator list item, a changed scalar on collision, or a type change
    is a counterexample.
    """
    assert isinstance(merged, dict), "merge of two dicts must be a dict"
    for key, existing_value in existing.items():
        assert key in merged, f"existing key {key!r} dropped from merge result"
        merged_value = merged[key]
        if isinstance(existing_value, dict) and isinstance(merged_value, dict):
            _assert_existing_keys_preserved(existing_value, merged_value)
        elif isinstance(existing_value, list):
            # prefer_existing list handling is dedupe-union: every operator item
            # survives (membership), but the merged list may also carry incoming
            # items, so assert preservation-as-subset rather than equality.
            assert isinstance(merged_value, list), (
                f"existing list for {key!r} became {type(merged_value).__name__}"
            )
            for item in existing_value:
                assert item in merged_value, (
                    f"operator list item {item!r} for {key!r} dropped: "
                    f"{existing_value!r} -> {merged_value!r}"
                )
        else:
            # Scalar (or None) existing value: prefer_existing keeps it exactly,
            # whether or not the incoming object collided on this key.
            assert merged_value == existing_value, (
                f"existing value for {key!r} changed: "
                f"{existing_value!r} -> {merged_value!r}"
            )


@given(existing=json_maps, incoming=json_maps)
@TEST_SETTINGS
def test_prefer_existing_preserves_all_operator_keys(
    existing: dict[str, Any], incoming: dict[str, Any]
) -> None:
    """prefer_existing=True drops no existing key and keeps existing values."""
    merged = _merge_json_values(existing, incoming, prefer_existing=True)
    _assert_existing_keys_preserved(existing, merged)


@given(existing=json_maps, incoming=json_maps)
@TEST_SETTINGS
def test_prefer_existing_adds_incoming_only_keys(
    existing: dict[str, Any], incoming: dict[str, Any]
) -> None:
    """prefer_existing=True adds keys present only in the incoming object."""
    merged = _merge_json_values(existing, incoming, prefer_existing=True)
    for key, incoming_value in incoming.items():
        assert key in merged, f"incoming-only key {key!r} not added"
        if key not in existing:
            # A key only in incoming carries the incoming value verbatim.
            assert merged[key] == incoming_value


@given(existing=json_maps, incoming=json_maps)
@TEST_SETTINGS
def test_overlay_incoming_wins_on_collision_and_retains_existing_only(
    existing: dict[str, Any], incoming: dict[str, Any]
) -> None:
    """prefer_existing=False takes incoming on collision, retains existing-only.

    The merge stays additive: only the collision winner flips relative to the
    prefer_existing=True policy. Existing-only keys remain; on a top-level
    non-dict collision the incoming value wins.
    """
    merged = _merge_json_values(existing, incoming, prefer_existing=False)
    # Existing-only keys are retained (additive merge).
    for key, existing_value in existing.items():
        if key not in incoming:
            assert key in merged, f"existing-only key {key!r} dropped"
            assert merged[key] == existing_value
    # Top-level non-dict / non-dict collisions resolve to the incoming value.
    for key, incoming_value in incoming.items():
        assert key in merged
        existing_value = existing.get(key)
        existing_is_dict = isinstance(existing_value, dict)
        incoming_is_dict = isinstance(incoming_value, dict)
        if not (existing_is_dict and incoming_is_dict):
            assert merged[key] == incoming_value, (
                f"incoming value for {key!r} did not win on collision"
            )


@given(existing=json_maps, incoming=json_maps, prefer=st.booleans())
@TEST_SETTINGS
def test_merge_is_idempotent_under_repeated_incoming(
    existing: dict[str, Any], incoming: dict[str, Any], prefer: bool
) -> None:
    """Re-merging the same incoming object changes nothing.

    merge(merge(a, b), b) == merge(a, b) for a fixed prefer flag. The list-union
    dedupe under prefer_existing=True and the scalar/dict collision rules are all
    fixed points under a repeated identical incoming object.
    """
    once = _merge_json_values(existing, incoming, prefer_existing=prefer)
    twice = _merge_json_values(once, incoming, prefer_existing=prefer)
    assert twice == once
