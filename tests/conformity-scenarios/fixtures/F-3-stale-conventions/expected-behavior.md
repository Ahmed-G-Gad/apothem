---
fixture: F-3
title: Stale-conventions repo
spec-source: _spec/spec.md §7.1 row 3
mandates: [M1, M2, M6]
---

<!-- SPDX-License-Identifier: MIT -->

# F-3 — Stale-conventions repo

## Spec binding

This fixture realizes spec §7.1 row 3: **Stale-conventions repo**
(legacy idioms in some files, modern in others) testing
**M1 + M2 + M6**. The host carries a Python 3.11 pin in
`pyproject.toml` AND files written under the older 3.7-era idiom
set living alongside files written under the modern 3.11+ idiom
set. The retrofit's correct behavior is to **honor per-file
idioms** when editing existing files (no silent modernization of
legacy files mid-edit) AND **surface the divergence as a gap**
the user can act on (M2 disclosure of the gap; M6 expertise
suggesting a refinement direction).

## Synthetic host description

Three sibling files live under `before/`:

| Path | Idiom era | What it carries |
|---|---|---|
| `before/pyproject.toml` | mixed | Pins `requires-python = ">=3.11"` AND configures ruff with a permissive ruleset (only `E` + `F` selected — no `UP` upgrade-to-modern lint). |
| `before/src/legacy_importer.py` | 3.7-era | `from typing import Dict, List, Optional` (legacy generics); comment-style PEP 484 annotations (`# type: (...) -> ...`); `os.listdir` + `os.path.join` + `os.path.exists`; raw `open(path, "r")` + manual `try/finally` close. |
| `before/src/modern_importer.py` | 3.11-era | `from __future__ import annotations`; `list[Path]`, `tuple[str, ...]`, `FeedRecord \| None` (PEP 604 union); `pathlib.Path` + `.glob()` + `.read_text()`; `@dataclass(frozen=True, slots=True)`. |

The two `*_importer.py` files solve the same domain problem
(parse a CSV-like feed file) using different idiom eras. The
divergence is **observable** but **not flagged** by the existing
ruff config, so the agent's discovery walk is the surface that
notices it.

## Mandate-firing expectations

### M1 — Per-file idiom convergence

`src/apothem/rules/host-discovery.md` §2 governs sibling-file
convergence. When editing `legacy_importer.py`, the agent
preserves the file's existing idioms — adding a new function in
that file MUST use `Optional[X]` not `X | None`, MUST use
comment-style type hints, MUST use `os.path.join` not `pathlib`.
When editing `modern_importer.py`, the agent uses the modern
idioms throughout. The §2.2 majority-observation rule does not
apply because the divergence is per-file, not host-wide.

### M2 — Disclosed Amendments, Never Silent

When the agent encounters the divergence, it surfaces the
observation in the disclosure ledger per
`src/apothem/rules/disclosure-ledger.md`:

```
[Discovery — source: src/legacy_importer.py + src/modern_importer.py;
 value: per-file idiom-era divergence (3.7-era vs. 3.11-era);
 honored per-file]
```

Silent modernization of `legacy_importer.py` mid-edit (e.g., the
agent fixes a bug in `parse_feed` and "while I was here" rewrites
the type annotations to modern form) is non-conformant per
`src/apothem/rules/disclosure-ledger.md` failure tells (silent
over-reach).

### M6 — Expertise Incorporation (surface the gap as a finding)

`src/apothem/rules/expertise-posture.md` sub-element 3 (Extend
on adjacent gaps) governs the surfaced-gap obligation. The agent's
working trace's `surfaced-gaps:` array carries an entry naming the
divergence and recommending a refinement path:

```
surfaced-gaps:
  - id: G-stale-idioms
    description: legacy_importer.py uses 3.7-era idioms in a 3.11-pinned project.
    recommendation: convert legacy_importer.py to modern idioms in a separate change-set,
                    so the agent's current edit remains scope-honest per M2.
    driver: rule citation: src/apothem/rules/host-discovery.md §2.2 sibling-convergence threshold;
            observed-state: pyproject.toml requires-python = ">=3.11" + sibling modern_importer.py.
```

The recommendation does NOT carry an unsolicited modernization —
M6 says "surface gaps; the user decides," not "fix everything in
one diff."

## Agent-output contract

When apothem is asked to fix a bug in `legacy_importer.py` (e.g.,
"the parser returns None when the file has only a header line —
make it return an empty record instead"), the emitted artifact
satisfies:

1. **Edit honors the file's idioms.** The fix uses `Optional[Dict]`
   (the file's existing form), comment-style annotations, and
   `os.path` operations — not `dict | None`, not `from __future__`,
   not `pathlib.Path`.
2. **Disclosure ledger entry.** A `[Discovery — …]` row records
   the per-file idiom convergence; an `[Amendment — rationale: …]`
   row records the bug fix scope; the `surfaced-gaps:` array
   carries `G-stale-idioms`.
3. **Scope honesty.** The diff touches only the bug-fix lines —
   no silent reformatting, no silent modernization, no silent
   docstring rewrite.
4. **Refinement recommendation.** A separate proposed change-set
   (or a deferred follow-up the user can accept later) covers the
   modernization; the recommendation cites concrete drivers per
   `src/apothem/rules/option-annotation.md` §4.2.1.

## Pass signals (consumed by 09B verify driver)

- [ ] The diff against `legacy_importer.py` introduces no
      modern-idiom token (no `X | None`, no `pathlib.`, no
      `from __future__`, no `dataclass`).
- [ ] The disclosure ledger carries a `[Discovery — …]` row
      naming the per-file idiom-era divergence.
- [ ] The `surfaced-gaps:` array contains an entry whose driver
      cites at least one concrete-driver class (rule citation OR
      observed-state) per the canonical-channel rule's §4.2.1.
- [ ] The fifteen-bar attestation block records `M1: pass`
      (per-file convergence honored), `M2: pass` (no silent
      over-reach; ledger populated), and `M6: pass`
      (surfaced-gaps array non-empty).

## Fail signals (release-blockers)

- The diff against `legacy_importer.py` contains modern idioms
  introduced as part of the bug fix (M1 silent modernization;
  M2 silent over-reach).
- The disclosure ledger is empty or contains only `[Amendment]`
  without `[Discovery]` (M2 disclosure-without-context).
- The `surfaced-gaps:` array is empty despite the divergence
  being directly observable (M6 expertise-incorporation absent).
- A `[Refinement — improvement: …]` row is recorded against the
  legacy file in the same change-set as the bug fix without an
  inquiry surfacing the user's consent (M6 over-reach without
  user authority).

## Bindings (§0.j five-direction)

- **Drives →** Sub-phase 09B `verify.py`.
- **Satisfies →** Spec §7.1 row 3. Sub-phase 09A task 3.
- **Established by ↑** Sub-phase 09A `PHASE.md` task 3.
  Spec §7.1 row 3.
- **Cross-bound with ↔** Sibling fixtures F-1 (M1 alone, rich
  conventions) and F-2 (M1 + M5 + M7, silent conventions). Together
  the three exercise M1 across the rich / silent / stale axs.
  F-3 specifically tests the disclosure path (M2) and the
  surfaced-gap discipline (M6) at the divergence boundary.
