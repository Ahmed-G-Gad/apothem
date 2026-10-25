<!-- SPDX-License-Identifier: MIT -->

# Related-work section from supplied sources

Detail for `related` mode. The section is built from the papers the user supplied and nothing else. The skill does not search and does not add a paper from memory, even a famous one.

## Inputs

- **Position:** one to three sentences from the user saying what the draft contributes and to what problem. Without it, ask.
- **Sources:** the supplied files or a supplied `.bib` with the files it points to. Each source is opened and given a basis (`read in full`, `excerpt`, `abstract only`, `unread`) before it is used.
- **Citation keys:** keys from a supplied bibliography are used as given. Otherwise write first-author surname plus year and flag each one `provisional key`.

## Shape of the draft

Two to five themes, each a paragraph or two, in this order: background that every reader needs, the lines of work closest to the draft, then the gap the position fills. Inside a theme, say what the line of work established, how the supplied papers differ from one another, and where the draft's contribution sits against them. A last paragraph names the closest work in the set and states the difference. When the set holds no work that close, the paragraph carries a marker instead of a guess.

## Sentence rules

1. Every sentence that reports what a paper did or found carries that paper's key.
2. A sentence that gives a method detail, a number, or a comparison between papers needs a source whose basis covers it. A source with basis `abstract only` supports a sentence only at the level the abstract states, and the coverage report lists it as such.
3. Write what the supplied papers show, not what the literature contains. Do not write "first", "novel", "no prior work", or "to our knowledge" on the strength of the set; a supplied set cannot establish them. Where the user wants a novelty statement, leave `[novelty statement: needs a recorded search]` and explain in the report why the set cannot carry it (see `rules/authoritative-referencing-provenance.md` §3).
4. Paraphrase, and quote only when the wording itself is the point, with the quote copied from the text read.
5. When two supplied papers disagree, say so in the text and give each side's key.

## Citation-needed markers

Where the argument needs support the supplied set lacks, write a marker in the prose, in this exact form:

```
[citation needed: <what the support must show>]
```

One marker per gap. The marker names the claim to be supported, not a suggested paper. A marker is never replaced by a reference the skill remembers. Every marker is repeated in the coverage report so none can be missed on a skim.

## Coverage report

Place it after the draft.

| Theme | Sources used (keys) | Basis mix | Markers left |
|-------|--------------------|-----------|--------------|

Then four short lists:

- **Supplied but unused:** each source with the reason (off-topic for the position, duplicate of another source, unread).
- **Abstract only:** sources that support abstract-level statements only.
- **Unread:** sources that failed to open, and why.
- **Markers:** every `[citation needed: ...]` and `[novelty statement: ...]` with its theme.

End with one plain line: *This report covers the supplied set. It does not describe the literature.*

## Hand-offs

- A related-work section inside a suite's manuscript is `commands/research-paper.md`, which draws on the suite's ledger.
- To check that the references in the finished section exist and say what the text attributes to them, use `agents/citation-auditor.md`.
- To find sources for the markers, use `skills/multi-source-research/SKILL.md` or `agents/research-scout.md`, then run `related` mode again with the enlarged set.
