<!-- SPDX-License-Identifier: MIT -->

# Reading note template

Detail for `note` mode, and for the per-paper notes inside `compare` mode. A note runs to one page. In `compare` mode a note shrinks to the header, the claim, the method line, and the evidence lines.

## Header

```
Reading note: <short title>
Citation:     <authors, year, title, venue or archive, identifier, as printed on the paper>
Version read: <preprint vN | accepted manuscript | published version | unknown>
Basis:        <read in full | excerpt (portion named) | abstract only>
Focus:        <the question put to this paper, or "general">
Read on:      <date>
```

The basis line is not optional. An `abstract only` note opens with the line `Full text not read` and keeps to what the abstract states.

## Fields

**Claim.** One or two sentences in the paper's own scope, qualifiers included ("on this benchmark", "for models under a given size", "in this population"). A claim stripped of its scope is a misquote; when the abstract and the body state the claim differently, give both and say which one the note follows.

**Method.** What was done to what: the data or participants, the systems or interventions, the comparators, and the measure. Give enough that a reader can tell whether a later comparison with another paper is fair. Name any step the text leaves unclear instead of filling it in.

**Evidence.** The results that carry the claim. Each line holds the number as printed, its unit, the setting it was measured in, and how variation was reported (repeated runs, intervals, a test, or nothing). Add a page, table, or figure locator only when it was seen while reading; otherwise write `locator: none seen`. Do not recompute or round a figure the paper prints.

**Limits.** Two lists, kept apart.

- *Stated by the authors:* the limitations the paper itself gives.
- *Visible on reading:* limits the reader can see that the paper does not state, such as a single dataset, no comparison to the strongest alternative, results without variation, or a design that supports association but not cause. Each one says where in the paper it shows.

**Citable for.** One to four statements, each worded as a citing sentence would be worded, and each tied to the result under Evidence that supports it. A statement with no supporting result is not listed. The paper's venue, a journal-level measure, or its citation count is not a reason to list a statement (`rules/authoritative-referencing-provenance.md` §8).

**Not citable for.** Statements that citations tend to attach to a paper and that it does not support: a result carried beyond the range tested, a cause drawn from a correlational design, a claim that appears only in the introduction's motivation, a figure quoted from another paper's work. This list is what keeps a later citation honest.

**Unread or unclear.** Sections skipped, appendices not opened, unreadable figures, terms left undefined. Say what would settle each.

## Rules that hold for every note

- A numerical value, a quotation, and a year are copied from the text read, never from memory.
- A claim the paper attributes to another work is recorded as that paper's report of it, not as a finding of this paper.
- A paper known only through another paper's description gets no note; it is listed as `unread` with the paper that described it.
- When the user wants the note filed into a project wiki, hand over to `skills/knowledge-wiki/SKILL.md`; this template is for notes that live in a file or in the conversation.
