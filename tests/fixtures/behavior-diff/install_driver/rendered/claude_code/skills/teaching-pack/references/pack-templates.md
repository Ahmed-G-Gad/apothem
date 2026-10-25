<!-- SPDX-License-Identifier: MIT -->

# Pack templates

The shapes the six parts take. Placeholders sit in angle brackets. A line that
teaches, a walk-through step, an example step, a key line, and a glossary entry
each end with one marker; headings, question stems, and the pack header need none.

## Marker legend

| Marker | Meaning | Where it may appear |
|--------|---------|---------------------|
| `[§3.2]` | The source states this at section 3.2 (a heading text for an unnumbered document, a page only when seen) | Anywhere |
| `[built from §3.2]` | The pack constructed this (toy numbers, an analogy, a reordering) from what the source states at 3.2 | Anywhere |
| `[not in source]` | Outside knowledge | Glossary glosses and prerequisite lines only |

A line that fits none of the three is not written.

## Pack header

```markdown
# <Document title as seen> - teaching pack

Source: <path>. Authors, venue, year as seen: <text, or "not seen">.
Basis: <read in full | read in part: sections ... | abstract only>.
Audience: <level>. Assumed prior knowledge: <list>. Both <user-set | default>.
Parts: goals, curriculum, walk-throughs, examples, quiz, glossary<, slide outline>.
Markers: [§x] stated by the source - [built from §x] constructed here - [not in source] outside knowledge.
```

## Goal

```markdown
**G1.** The learner can <observable verb> <object> under <condition>. [§2, §3.1]
```

Verbs that can be tested: derive, compute, choose between, explain why, predict,
identify the assumption in, reproduce the steps of.

## Curriculum module

```markdown
### M1. <Section title or the one idea it carries>

Sections: §<x> (a group only when the sections share one idea). Comes after: <M... or "none">.
After this module the learner can: <outcome>. Serves: G1.

<Three to six sentences, each ending in a marker.>

Check question: <question>. Key: K1.
Order note: <only if this module sits elsewhere than in the source: where and why>.
```

The last module is `Assumptions and limits`. Each assumption or limit the source
states is listed with its locator; when it states none, the module holds the single
line `The source states no limits.` and nothing else.

## Formula or algorithm walk-through

```markdown
### W1. <Name> [§<x>]

Computes: <one plain sentence>.

| Symbol | Meaning | Type or range | Defined at |
|--------|---------|---------------|------------|
| <s> | <meaning> | <type> | §<x> |

Steps:
1. <Plain-word step.> Maps to: <term or line>. [§<x>]
2. ...

Why this form: <reason [§x]> or "The source gives no reason."
Boundary case: <input at the edge and what happens> [§<x> | built from §<x>]
Worked example: E1.
```

For an algorithm, number the steps by the source's own line numbers when it has
them. A symbol the source uses without defining is listed with
`Defined at: not defined in source`.

## Worked example

```markdown
### E1. <Name> - for W1

Inputs: <values> [§<x> | built from §<x>]
1. <operation>: <intermediate value>.
2. ...
Result: <value>.
Arithmetic: <machine-checked, with the calculation run | hand-computed>.
Sanity check: <what the result should look like, and why> [built from §<x>]
Slip to watch: <optional; one step where a wrong move is easy> [built from §<x>]
```

A hand-computed example is recomputed by a second route (a different order of
operations, or substituting the result back) before delivery; see the checks.

## Quiz item and key

```markdown
**Q1.** (tests G1; kind: recall | apply | explain | spot-the-error | predict; level: easy | medium | hard)
<Question stem.>
A) <option> B) <option> C) <option> D) <option>      (choice items only)
```

```markdown
**K1.** <Answer.> [§<x>]
Why: <one or two sentences.>
Why the tempting option fails: <the near-miss it echoes> [§<x>]
```

Spread the kinds so that no more than half the items are recall. A free-response
item states in its key the points an answer must contain.

## Glossary entry

```markdown
**<term>**: <plain definition in at most two sentences>. [§<x>]
First used: §<x>. Basis: defined in source | used but not defined in source | background [not in source].
See also: <terms>.
```

The marker after the definition is `[not in source]` whenever the basis is not
`defined in source`. Order entries alphabetically. A term the source uses in two
senses gets one entry with both senses and the locator of each.

## Thin notice

```markdown
Thin source: <part> not written. Needs: <requirement from source-requirements>. Found: <what the source offers>.
```

A thin notice replaces the part; it is never followed by a shortened version of
the part built from outside knowledge.
