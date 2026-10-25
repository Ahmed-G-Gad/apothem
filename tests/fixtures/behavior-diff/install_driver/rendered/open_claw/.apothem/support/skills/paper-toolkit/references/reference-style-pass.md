<!-- SPDX-License-Identifier: MIT -->

# Reference style pass

Detail for `style` mode. The pass finds duplicates, preprint and published pairs, missing fields, and inconsistent form in a reference list. It does not decide whether a reference exists or supports a statement; `agents/citation-auditor.md` does that.

## Inputs

A `.bib` file, several `.bib` files, or a bibliography section in a draft. A draft, if given, enables check S6. Parse entries with Grep and Read; when a file is too irregular to parse, report the unreadable lines instead of guessing at them.

## Checks

| ID | Check | How it runs |
|----|-------|-------------|
| S1 | Duplicate entries | Two entries share a DOI or an arXiv identifier, or share a normalised title (lower-case, punctuation removed, whitespace collapsed) together with first-author surname and year. List the keys in each group. |
| S2 | Preprint and published pairs | An entry is a preprint when its venue or note names an archive such as arXiv, SSRN, bioRxiv, or medRxiv, or when it has an `eprint` field and no journal or booktitle. Report a pair when another entry in the list, or a lookup, shows a published version of the same work. |
| S3 | Missing fields | Compare each entry with the required fields for its type (table below). |
| S4 | Inconsistent form | Mixed full and abbreviated venue names, mixed author-name forms, title-case against sentence-case, hyphen against en dash in page ranges, a DOI written as a URL in some entries and bare in others, key styles that differ across the list. |
| S5 | Key collisions across files | With several `.bib` files: one key naming different works, or one work under several keys. |
| S6 | Cited against listed | With a draft: keys cited in the text that have no entry, and entries never cited. |

Add one pattern-only check to S3: an identifier that is malformed by pattern (a DOI not starting `10.`, an arXiv identifier with the wrong shape, a year in the future, a reversed page range). Report it as `malformed by pattern`; whether the work exists is for the auditor.

## Required fields by entry type

| Entry type | Required | Expected when available |
|------------|----------|-------------------------|
| article | author, title, journal, year | volume, issue or article number, pages, DOI |
| inproceedings | author, title, booktitle, year | pages or paper number, publisher or organisation, DOI |
| book | author or editor, title, publisher, year | edition, ISBN |
| thesis | author, title, school, year | type, URL |
| techreport | author, title, institution, year | report number |
| preprint (misc) | author, title, year, archive and identifier or URL | version |
| web page | author or organisation, title, URL, access date | publication date |

A missing required field is a finding. A missing expected field is a note.

## Looking things up

- Lookups serve S2 (does a published version exist) and, only when the user asks, filling a missing field.
- A lookup sends an identifier, or a title with the first author, and nothing else. No sentence from the draft, and no text from an unpublished manuscript, goes into a query or a fetched page.
- Use a scholarly index tool when the host provides one, chosen by what it does (identifier lookup, title search) and not by its name; otherwise a web search on title and first author. Cite the record opened for each value.
- A value is never filled from memory. When no record is found, the field stays missing and the note reads `TODO: value not found`.
- With no lookup capability, an entry that needs one is `unchecked`. That is not the same as "no published version exists".

## Handling pairs and duplicates

- For a preprint with a published version, recommend citing the version whose text the author read. If only the preprint was read, say that the published text may differ and leave the swap to the author. Never swap an entry or change a key without being asked.
- For duplicates, name the entry to keep (the more complete one), list the keys to retire, and list each place in the draft where a retired key is cited so the citations can be updated.

## Report

| ID | Entries (keys) | Finding | Suggested fix | Evidence or lookup |
|----|----------------|---------|---------------|--------------------|

After the table: counts per check, checks skipped with the reason, every lookup made with what was sent, and entries left `unchecked`. The pass edits no file. On request it produces a corrected file as a diff, one finding class at a time, so each change can be accepted or refused on its own.
