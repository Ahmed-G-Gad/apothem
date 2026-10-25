<!-- SPDX-License-Identifier: MIT -->

# Knowledge-Wiki Drift and Hub Procedures

Reference for the [`knowledge-wiki`](../SKILL.md) skill, `drift` and `hubs` modes. Both are computed from the files with Glob, Grep, and Read; neither depends on a script. Page shapes and log syntax are in [`page-templates.md`](page-templates.md).

## Drift

Drift answers one question: did the base change since the last time anyone looked? It stays silent when the answer is no.

### Fingerprint

A fingerprint has two parts:

- `pages=<N>`: the number of `.md` files directly inside `sources/`, `entities/`, and `syntheses/`, redirect and retired stubs included. A missing directory counts as zero.
- `last=<date>|<operation>|<id>`: the newest log line whose operation is neither `lint` nor `baseline`. Position in the file decides which line is newest, since the log is append-only. A log with no such line gives `last=none`.

The stored fingerprint is the detail of the most recent baseline line in `log.md`:

```text
- 2026-10-27 | baseline | all | pages=41; last=2026-10-26|retire|some-id
```

### Procedure

1. Grep `\| baseline \| all \| ` with `-n` in `log.md`. Take the last match as the stored baseline.
2. Compute the current fingerprint: Glob the three page directories for `N`; Grep `^- ` with `-n` in `log.md`, drop lines whose operation is `lint` or `baseline`, and take the last remaining line for `last`.
3. **No stored baseline.** Append a baseline line with the current fingerprint and print `Baseline recorded: <fingerprint>`. Print nothing else: the first run has nothing to compare against.
4. **Fingerprints equal.** Print `No change since baseline <date>: <fingerprint>` and stop. Write nothing.
5. **Stored `last` is missing from the log.** A line that the baseline relied on is gone, so the log was edited after the fact. Report it, do not append a baseline, and ask how to proceed through the structured-inquiry channel.
6. **Fingerprints differ.** Produce the report below, then append a new baseline line with the current fingerprint.

### Session-start check

The SessionStart hook runs a read-only, bounded version of the comparison above, so a base that moved between sessions is flagged without anyone asking. It and this mode share one definition of the fingerprint, so a change to the fingerprint above is made in both.

- It looks only at `knowledge-base/`, `wiki/`, `docs/knowledge-base/`, and `docs/wiki/` under the project root, and only at a directory that holds both `index.md` and `log.md`. It never searches the tree.
- The stored fingerprint is the newest `baseline ... | all |` line in `log.md`, read from the last 256 KiB of the file. The current one is the page count (a listing of the three page directories) and the newest non-`lint`, non-`baseline` log line.
- A differing fingerprint produces one line that names the base and recommends `--mode drift --kb <path>`. The line holds a date and two numbers taken from the base, never its text.
- No baseline, a malformed newest baseline, a baseline further back than the window, an unreadable file, or an unchanged fingerprint produces nothing. The hook writes nothing, and records no baseline: this mode does.

### Drift report

```text
Knowledge base: <kb path>    Baseline: <date>    Now: <date>
Pages: <old N> -> <new N>

Added:     <ids from create lines after the baseline>
Ingested:  <id> F<n> (<basis>, focus: <question>) ...
Updated:   <ids from update lines after the baseline>
Renamed:   <old id> -> <new id> ...
Retired:   <ids>
Log lines since baseline: <count>
```

Then two cross-checks:

- If the page-count change differs from the number of `create` lines after the baseline, print `Pages changed outside the log` with the count difference, and point to lint check L9 for the pages involved.
- If the count is unchanged and `last` differs, the change is new focus blocks or edits to existing pages; the `Ingested` and `Updated` lines carry them.

A report lists changes; it does not judge them. The recommended follow-up is `lint` when any line appears under `Pages changed outside the log` or when `Ingested` or `Updated` is non-empty.

### Limits to state when relevant

The fingerprint sees additions, removals, and logged operations. A page edited in place with no log line is invisible to it. That is a log-discipline failure, and L9 is the check that surfaces it.

## Hubs

Hub analysis shows what the base hinges on: the pages many others lean on, and the pages that alone connect two parts of the base.

### Procedure

1. **Extract links.** Grep `\[\[([a-z0-9]+(-[a-z0-9]+)*)(#F[0-9]+)?\]\]` with `-o -n` over the three page directories. Leave out `index.md` and `log.md`: the index links to everything and would flatten the ranking.
2. **Normalise.** Drop the `#F<n>` anchors. Replace each redirect ID with its target. Drop self-links. Keep one edge per ordered pair of pages, however many times the link appears.
3. **Count inbound.** For each page, the number of distinct pages linking to it. Rank descending; ties break by ID. Report the top 10, or all pages when the base has fewer. Show each page's kind, inbound count, and outbound count.
4. **Find components.** Treat every edge as undirected and flood-fill. Report the number of components and list every page with no edges, since an isolated page is reachable only through the index.
5. **Test bridges.** A candidate is a page with at least two distinct neighbours. For each candidate, remove it and flood-fill the rest of its component. If the component splits into more than one piece, the page is a bridge. Record the piece sizes and up to three sample IDs from each piece.
6. **Limit the work on large bases.** Above 150 pages, test only the candidates with at least three neighbours plus the top 20 by inbound count, and say so in the report.
7. **Flag unopened hubs.** A hub or bridge whose page has `status: "unread"` is a part of the base that rests on nothing anyone has read. List these first.

### Hub report

```text
Knowledge base: <kb path>    Date: <date>    Pages: <N>    Components: <n>

Most linked
  1. <id> (<kind>)  inbound <n>  outbound <n>
  ...

Bridges (ranked by size of the smaller piece)
  <id> joins {<sample ids>} (<size>) and {<sample ids>} (<size>)
  <id> strands only <id>

Isolated pages: <ids or none>
Unopened hubs: <ids or none>
Restrictions: <what was limited, or none>
```

A bridge that strands a single page is listed after the bridges that split the base into larger pieces, since a lone leaf is a weaker dependency than a split between clusters.

### Reading the result

A high inbound count on an entity page means many sources were filed against it, so its definition deserves the most careful verification. A bridge page is the only route between two clusters: adding a direct relation between the clusters, or a second page that links both, removes the single point of dependence. The report states these readings only when the data shows them, and leaves the choice of restructuring to the user.
