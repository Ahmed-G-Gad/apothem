<!-- SPDX-License-Identifier: MIT -->

# Knowledge-Wiki Lint Catalog

Reference for the [`knowledge-wiki`](../SKILL.md) skill, `lint` mode. Each check is a Glob or Grep procedure with a fixed pattern, so two runs over the same base give the same findings. No check edits a page. Patterns are ripgrep syntax; `<kb>` is the resolved base directory and `<pages>` means `<kb>/sources`, `<kb>/entities`, and `<kb>/syntheses`.

## Checks at a glance

| ID | Check | Severity | Skipped when |
|----|-------|----------|--------------|
| L1 | Dangling links | blocking | never |
| L2 | Orphan pages and index defects | blocking | never |
| L3 | Duplicate or mismatched IDs | blocking | never |
| L4 | Relations without a valid source block | blocking | no relation lines exist |
| L5 | Citation keys with no bibliography entry | blocking | no bibliography file found |
| L6 | Focus blocks with no valid basis | blocking | no focus blocks exist |
| L7 | Unresolved citation placeholders in drafts | blocking | no drafts location known |
| L8 | Estimated or malformed locators | blocking for estimates, warning for malformed | no locator lines exist |
| L9 | Log integrity and unlogged pages | warning | never |

Blocking means the base cannot be navigated or attributed reliably until the finding is fixed. A warning lowers the reliability of drift reports or readability and does not stop ingest.

## Procedures

### L1. Dangling links

1. Grep `\[\[([a-z0-9]+(-[a-z0-9]+)*)(#F[0-9]+)?\]\]` with `-o -n` over every `.md` file under `<kb>`, `index.md` included.
2. Glob `<pages>/*.md` once and build the set of page stems.
3. A link whose ID is not in the set is a finding (`no page`).
4. For a link with `#F<n>`, Grep `^## F<n>: ` in the target page. No match is a finding (`no such block`).
5. A link whose target page has `status: "redirect"` is reported as informational (`old ID, redirects to <new-id>`), not as a finding.

### L2. Orphan pages and index defects

1. Grep `^- \[\[([a-z0-9-]+)\]\] \| (source|entity|synthesis) \| ` with `-o` in `index.md`.
2. A page stem missing from those lines is an orphan.
3. An ID listed twice in the index is a finding.
4. An index line whose kind word disagrees with the directory holding the page is a finding.
5. Index lines not matching the grammar at all (Grep `^- ` lines minus the matches of step 1) are findings.

### L3. Duplicate or mismatched IDs

1. Two files with the same stem in different page directories are a duplicate.
2. Grep `^id: ` with `-n` in each page; a value different from the file stem is a mismatch.
3. Grep `\| create \| ([a-z0-9-]+) \|` with `-o` in `log.md`; an ID created twice means a reused ID.
4. A page with `status: "redirect"` whose `redirect:` target does not exist is a finding.

### L4. Relations without a valid source block

1. Count relation lines per file: Grep `^\s*- (supports|contradicts|extends|uses|part-of) ` with output mode `count`.
2. Count well-formed lines per file with the full grammar: `^\s*- (supports|contradicts|extends|uses|part-of) \[\[[a-z0-9-]+\]\] \| confidence: (high|medium|low) \| block: [a-z0-9-]+#F[0-9]+\s*$`.
3. A file where the first count exceeds the second holds malformed lines. Grep the first pattern with `-n` on that file and drop the line numbers that matched the second; the rest are findings (`missing confidence`, `missing block`, or `bad relation word`).
4. For each well-formed line, take its `block:` value. The source page must exist, and Grep `^## F<n>: ` must match in it. A block pointing at an `unread` source or at a missing block is a finding.

### L5. Citation keys with no bibliography entry

1. Glob `**/*.bib` under the project root, skipping vendored and build directories. None found means the check is skipped, with the reason `no bibliography file`. A bibliography in another format is also skipped, with its format named.
2. Collect keys in use: Grep `^cite-key: "([^"]+)"` in source pages (ignore the value `none`), and Grep `\[@[^\]]+\]` with `-o` in all pages, splitting each match on `;` and stripping the leading `@`.
3. Collect defined keys: Grep `^@[A-Za-z]+\{([^,\s]+),` with `-o` in every bibliography file.
4. A key in use and not defined is a finding.

### L6. Focus blocks with no valid basis

1. Per source page, count headings: Grep `^## F[0-9]+: ` with output mode `count`.
2. Count valid basis lines: Grep `^- Basis: (full-text|abstract-only|excerpt \(.+\))\s*$` with output mode `count`.
3. A page where the counts differ has a block without a valid basis. Read the page and name the block. The basis line must be the first bullet under its heading.
4. A page with `status: "unread"` and any `## F` heading is a finding. A page with `status: "active"` and no `## F` heading is a finding.
5. Block numbers must ascend without repeats: list the headings with `-n` and compare.

### L7. Unresolved citation placeholders in drafts

1. Drafts location: any directory the user names, else Glob `**/drafts/**` and `**/build/**/*.{html,tex,txt}` under the project root. None found means the check is skipped, with the reason `no drafts location`.
2. Grep, case-insensitive, over the draft files for these placeholder shapes: `\[\?+\]`, `\(\?+\)`, `\?\?`, `\([A-Za-z0-9_:.-]+\?\)`, `\[(CITE|CITATION|REF|SOURCE|TODO)[^\]]*\]`, `\[citation needed\]`, `\\cite\{\s*\}`.
3. In files that are not Markdown or Quarto source, also report any raw `\[@[^\]]+\]`: it means the citation processor did not run.
4. Each hit is a finding with `path:line` and the matched text.

### L8. Estimated or malformed locators

1. Estimates: Grep, case-insensitive, `locator: *(~|approx|about|around|circa|ca\.|c\.|\?)` with `-n`. Every hit is blocking, since a locator that was guessed breaks the rule that locators are only recorded when seen.
2. Empty: Grep `locator: *$` with `-n`. Blocking.
3. Malformed: count all `\| locator: ` lines per file, then count those matching `\| locator: (none seen|(pp?\.|sec\.|section|§|fig\.|figure|table|eq\.|ll?\.|ch\.) ?[0-9A-Za-z.,–-]+)\s*$`. A shortfall is a warning; list the lines.

### L9. Log integrity and unlogged pages

1. Every line after the `# Log` heading must match `^- [0-9]{4}-[0-9]{2}-[0-9]{2} \| (create|ingest|update|rename|retire|lint|baseline) \| [a-z0-9-]+ \| `, with `all` allowed in place of an ID for `lint` and `baseline`. Other lines are findings.
2. Dates must not decrease from one line to the next. Read the file to check.
3. Each page stem needs a `create` line: Grep `\| create \| <stem> \|`. A missing line means an unlogged page.
4. Each focus block `F<n>` needs an `ingest` line: Grep `\| ingest \| <id> \| F<n>`. A missing line means an unlogged block.
5. Unlogged pages and blocks make the drift fingerprint miss changes, which is why this check exists.

## Inventory (reported with every lint run, not counted as findings)

- **Unverified claims.** Grep `\[unverified` with output mode `count`, per page, then the total. List each marker with `path:line` and its reason.
- **Resolvable markers.** An unverified marker that names `[[source-id]]` where that source page is now `active` can be re-checked against the opened source. List these first, since they are the cheapest to clear.
- **Stubs.** List every page with `status: "unread"`.
- **Redirects still in use.** The informational L1 hits.

## Report layout

```text
Knowledge base: <kb path>    Date: <date>
Blocking: <n>    Warnings: <n>    Skipped: <ids with reasons>

L1 Dangling links (n)
  <path>:<line>  [[target]]  <reason>
...
Inventory
  Unverified claims: <n> across <m> pages
  Resolvable markers: <list>
  Stubs: <list>
```

A check with no findings prints `L<n> clean`. A skipped check prints `L<n> skipped: <reason>`. The run ends by appending a `lint` line to `log.md` only when the user asked for the log to be updated; the default run changes nothing.
