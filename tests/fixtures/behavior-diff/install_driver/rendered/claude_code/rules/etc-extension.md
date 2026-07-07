---
name: "etc-extension"
description: "Enumerations are seeds, not ceilings — every 'etc.', 'e.g.', 'such as', 'like', 'including', and '…' is a directive to extend the set comprehensively from intent; only an enumeration explicitly marked closed is exhaustive."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Etc.-Extension — Enumerations Are Seeds, Not Ceilings

## Purpose

Govern how the ecosystem reads every open-ended enumeration in a directive, specification, or request. An enumeration trailing an open-set marker names examples, not the whole — acting on only the listed members under-delivers against the author's intent. This rule makes the extension obligation standing: the listed members are a seed the agent grows to the full intent-implied set before acting.

## Obligations

### 1. Open-set markers are extension directives

Every `etc.`, `e.g.`, `such as`, `like`, `including`, and the ellipsis `…` (or `...`) MUST be read as a directive to extend the enumeration comprehensively from the author's evident intent — never as a stopping point. The agent enumerates the full set the marker implies (the listed members PLUS every sibling the same intent reaches) and acts on that full set.

### 2. Extend from intent, not surface resemblance

The extension derives from the *purpose* the enumeration serves, not from superficial likeness to the listed members. Infer the classifying intent, then include every member that intent covers — including members the author did not think to name.

### 3. Closed-set carve-out

An enumeration explicitly marked closed is exhaustive and MUST NOT be extended. Closure is declared by an explicit boundary — "exactly", "only these", "the following N", "no others", "closed set" — or by a fixed-arity contract (a schema `enum`, a function signature, a protocol's method set). When closure is declared, adding a member is the failure; honor the stated boundary.

### 4. Disclose the extension

Every applied extension beyond the literally-listed members MUST be disclosed as an `[Extension]` marker in the change ledger per `rules/disclosure-ledger.md`, citing the intent it was derived from as its rationale. Silent extension and silent non-extension are both non-conformant.

## Seriousness Scaling

| Level | Extension obligation |
| ----- | -------------------- |
| EXPLORING | Extend where the fuller set is obvious; disclosure optional. |
| PERSONAL_USE | Extend from intent; disclose material extensions. |
| SHARED | Extend comprehensively; every extension disclosed with cited intent. |
| PUBLIC_LAUNCH | Extend exhaustively-from-intent; each extension disclosed and each closed-set boundary verified before emission. |

## Enforcement

Always-on at every seriousness level, scaling per the table above. Reading an open-set enumeration is a discrete pre-emission behavior: extend-or-honor-closure before the artifact leaves the agent's hands.

## Failure tells

An open-set enumeration acted on as the complete set (the listed three handled, the implied fourth and fifth dropped). An extension applied silently with no `[Extension]` ledger marker. A closed-set enumeration widened past its declared boundary. "Did exactly the listed items" offered as conformance where the marker directed extension.

## Bindings (§0.j five-direction)

- **Drives →** Every reading of an open-ended enumeration across every rule, command, skill, and request the ecosystem acts on; the comprehensiveness the artifact's coverage must reach before emission.
- **Satisfies →** The standing-mandate end-state that no open-set enumeration is silently treated as a ceiling.
- **Established by ↑** The operator's standing-mandate set (the "etc." extension mandate — enumerations are seeds, not ceilings).
- **Gated by ←** The closed-set carve-out (an explicitly-declared closed boundary suspends the extension obligation for that enumeration).
- **Cross-bound with ↔** `rules/ten-dimension-check.md` (dimension 6 Comprehensiveness — the extension obligation is the input behavior that dimension verifies at emission); `rules/disclosure-ledger.md` (M2 — every applied extension is recorded as an `[Extension]` marker).
