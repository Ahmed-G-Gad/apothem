<!-- SPDX-License-Identifier: MIT -->

# Knowledge-Wiki Page Templates

Reference for the [`knowledge-wiki`](../SKILL.md) skill. Every file the skill writes into a base follows one of the shapes below. Placeholders in angle brackets are filled per page; everything else is literal, because the lint checks match on it.

## Layout

```text
<kb-root>/
  index.md          one line per page
  log.md            append-only change record
  sources/<id>.md   one page per source
  entities/<id>.md  one page per concept, method, tool, person, or dataset
  syntheses/<id>.md one page per question answered across sources
```

## IDs and links

- An ID is lowercase kebab-case: `[a-z0-9]+(-[a-z0-9]+)*`. The file stem equals the `id` front-matter value.
- An ID is unique across all three page directories, so `[[id]]` resolves to exactly one file.
- An ID is never reused. Pages are not deleted. A page that is replaced becomes a redirect stub; a page that is withdrawn becomes a retired stub. Either way the file stays and its ID stays taken.
- Source IDs follow the cite key when one exists (`lastname-year-keyword`); entity and synthesis IDs name the subject in two to four words.
- A link is `[[id]]`. A link to a focus block is `[[source-id#F2]]`. Links use IDs only, never titles or paths.

## index.md

```markdown
# Index

- [[source-id]] | source | One-line description of what the source is and its newest focus.
- [[entity-id]] | entity | One-line definition.
- [[synthesis-id]] | synthesis | The question it answers.
```

One line per page, redirect and retired stubs included (their description starts with `redirect to [[new-id]]` or `retired`). The index carries no other content, so a reader can scan the whole base in one screen of lines.

## log.md

```markdown
# Log

- 2026-10-24 | create | vaswani-2017-attention | source page, status active
- 2026-10-24 | ingest | vaswani-2017-attention | F1, basis full-text, focus: does attention replace recurrence
- 2026-10-25 | rename | old-id | now new-id, redirect stub left
- 2026-10-25 | update | some-entity | relation added from vaswani-2017-attention#F1
- 2026-10-26 | retire | some-id | withdrawn, reason in page
- 2026-10-27 | lint | all | 2 blocking, 5 warning
- 2026-10-27 | baseline | all | pages=41; last=2026-10-26|retire|some-id
```

Each line is `- <date> | <operation> | <id or all> | <detail>`. Operations are `create` (a new page), `ingest` (a new focus block on a source page), `update` (an edit to an entity or synthesis page), `rename`, `retire`, `lint`, `baseline`. Lines are only ever appended; an earlier line is never edited or removed. A correction is a new line.

## Source page

```markdown
---
id: "<id>"
kind: "source"
title: "<title of the source>"
status: "active"
cite-key: "<bibliography key, or none>"
origin: "<path, URL, or DOI where the source was opened>"
created: "<date>"
---

# <title of the source>

## F1: <focus question>

- Basis: full-text
- Read: <date>
- Claims:
  - <claim in one sentence> | locator: p. 4
  - <claim in one sentence> | locator: none seen
- Relations:
  - supports [[entity-id]] | confidence: high | block: <id>#F1

## F2: <second focus question>

- Basis: excerpt (section 3 only)
- Read: <date>
- Claims:
  - ...
```

Rules for the blocks:

- Blocks are numbered `F1`, `F2`, ... in the order written. A number is never reused or renumbered, and a block is never edited after it is written. New reading adds a new block.
- `Basis` is exactly one of `full-text`, `abstract-only`, or `excerpt (<portion>)`. The portion is mandatory for an excerpt: a section, a page range, or a named figure.
- A locator is copied from what was seen: a page number, section number, or line range visible in the text read. When none was visible, write `none seen`. A locator is never inferred from a table of contents, the position in a file, or memory of the source.
- A claim is a statement the source makes under this focus. The reader's own inference goes to the synthesis page, not here. A claim starts with its subject, never with a relation word, so relation lines stay separable by pattern.
- A relation in a block has its subject in this source and its target elsewhere; see the relation grammar below.

## Unread stub (source not opened)

```markdown
---
id: "<id>"
kind: "source"
title: "<title as cited>"
status: "unread"
cite-key: "<key or none>"
origin: "<where the reference was found>"
created: "<date>"
---

# <title as cited>

Not opened. Known from: [[<page that cites it>]]. Reason it could not be opened: <paywall, dead link, file unreadable, not yet requested>.
```

An unread stub has no focus block and no claims. When the source is later opened, `status` changes to `active` and `F1` is written; the log gets an `ingest` line.

## Entity page

```markdown
---
id: "<id>"
kind: "entity"
title: "<name>"
status: "active"
created: "<date>"
---

# <name>

<One to three sentences defining the entity. Each factual sentence ends with a block citation such as [[source-id#F1]].>

## Relations

- extends [[other-entity-id]] | confidence: medium | block: <source-id>#F2
- part-of [[parent-entity-id]] | confidence: high | block: <source-id>#F1

## Open points

- [unverified: <reason>] <statement made about the entity that no opened source backs yet>
```

## Synthesis page

```markdown
---
id: "<id>"
kind: "synthesis"
title: "<the question, as a short title>"
status: "active"
created: "<date>"
---

# <the question>

## Answer so far

<Two to five sentences. Every claim ends with one or more block citations. A claim that rests on a single source says so.>

## Evidence

- <claim> [[source-id#F1]] [[other-source-id#F3]]
- <claim> [unverified: attributed to [[unread-source-id]], not opened]

## Disagreements

- [[source-id#F1]] says X; [[other-source-id#F2]] says Y. Not resolved.
```

## Relation line grammar

```text
- <relation> [[<target-id>]] | confidence: <level> | block: <source-id>#F<n>
```

- `<relation>` is one of `supports`, `contradicts`, `extends`, `uses`, `part-of`. The subject is the page holding the line.
- `<level>` is `high` (stated directly in the block), `medium` (follows from the block's claims with one inference step), or `low` (suggested by the block, not stated).
- `block` names the source page and focus block the relation was read from. The block must exist and must have a basis.
- Relations whose evidence is not in an opened block are not written as relation lines. They go under "Open points" or "Evidence" as unverified statements.

## Redirect stub (renamed page)

```markdown
---
id: "<old-id>"
kind: "<source|entity|synthesis>"
status: "redirect"
redirect: "<new-id>"
---

Moved to [[<new-id>]].
```

Create the stub in the same directory as the original, update the index line for the old ID to say `redirect to [[new-id]]`, add the new page to the index, and log a `rename` line. Links to the old ID keep resolving; lint reports them as informational so they can be updated later.

## Retired stub

Same shape as the redirect stub with `status: "retired"` and no `redirect` key; the body states why the page was withdrawn.
