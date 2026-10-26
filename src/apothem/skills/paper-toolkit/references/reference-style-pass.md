<!-- SPDX-License-Identifier: MIT -->

# Reference style pass

Detail for `style` mode. The pass finds duplicates, preprint and published pairs, missing fields, and inconsistent form in a reference list. It does not decide whether a reference exists or supports a statement; `agents/citation-auditor.md` does that.

## Inputs

A `.bib` file, several `.bib` files, or a bibliography section in a draft. A draft, if given, enables check S6. Parse entries with Grep and Read; when a file is too irregular to parse, report the unreadable lines instead of guessing at them, and let check S8 carry the defect.

## Checks

| ID | Check | How it runs |
|----|-------|-------------|
| S1 | Duplicate entries | Two entries share a DOI or an arXiv identifier, or share a normalised title (lower-case, punctuation removed, whitespace collapsed) together with first-author surname and year. List the keys in each group. |
| S2 | Preprint and published pairs | An entry is a preprint when its venue or note names an archive such as arXiv, SSRN, bioRxiv, or medRxiv, or when it has an `eprint` field and no journal or booktitle. Report a pair when another entry in the list, or a lookup, shows a published version of the same work. |
| S3 | Missing fields | Compare each entry with the required fields for its type (table below). Report each blank field with its state: `missing`, `inapplicable`, or `unassigned` (definitions in `bibliography-entries.md`). With no record to consult, a blank field is `missing` unless the entry itself shows otherwise: an article number in place of pages makes pages `inapplicable`, and a note reading in press or online first makes volume, issue, and pages `unassigned`. |
| S4 | Inconsistent form | Mixed full and abbreviated venue names, mixed author-name forms, title-case against sentence-case, hyphen against en dash in page ranges, a DOI written as a URL in some entries and bare in others, accented letters written as characters in some entries and as commands in others, key styles that differ across the list. The target form is the file's own consistent convention, else the normalised form in `bibliography-entries.md`. |
| S5 | Key collisions across files | With several `.bib` files: one key naming different works, or one work under several keys. |
| S6 | Cited against listed | With a draft: keys cited in the text that have no entry, and entries never cited. |
| S7 | Truncated author lists | An `author` or `editor` field that ends in `and others` or `et al`. Report the entry; with a lookup, say whether the record lists more names. The fix is the full list from the record; shortening to "et al." is the citation style's job at render time. |
| S8 | BibTeX well-formedness | Per entry: unbalanced braces or quotation marks, a missing comma between fields, a missing closing brace, an entry type outside the toolchain's set, an entry with no key, a key used twice in one file, a field repeated within one entry (tools differ on which value wins), a reserved character (`&`, `%`, `$`, `#`, `_`) left unescaped in a text field such as title, journal, or note (`doi` and `url` are exempt, and so is a character inside math between `$` signs). Report the line and the defect. Grep and Read count the braces per entry; a bibliography parser the host provides MAY be used and is named in the report. |

Add one pattern-only check to S3: an identifier that is malformed by pattern (a DOI not starting `10.`, an arXiv identifier with the wrong shape, a year in the future, a reversed page range). Report it as `malformed by pattern`; whether the work exists is for the auditor.

## Required fields by entry type

| Entry type | Required | Expected when available |
|------------|----------|-------------------------|
| article | author, title, journal, year | volume, issue or article number, pages, DOI, biomedical-index identifier (PMID or PMCID) when the work is indexed |
| inproceedings | author, title, booktitle, year | pages or paper number, conference location, publisher or organisation, DOI |
| incollection (chapter in an edited volume) | author, title, booktitle, editor, publisher, year | pages or chapter number, edition, DOI, ISBN |
| book | author or editor, title, publisher, year | edition, ISBN |
| thesis | author, title, school, year | type, URL |
| techreport | author, title, institution, year | report number |
| preprint (misc) | author, title, year, archive and identifier or URL | version |
| dataset (misc) | author or organisation, title, year, repository or publisher, persistent identifier or URL | version, release date |
| software (misc) | author or organisation, title, year, repository or publisher, persistent identifier or URL, version or commit hash | release date |
| unpublished | author, title, note giving the status | year, address of the holding copy |
| web page | author or organisation, title, URL, access date | publication date |

A required field in state `missing` is a finding. An expected field in state `missing` is a note. `inapplicable` and `unassigned` are recorded and are never findings; an `unassigned` field is re-checked on the next pass.

## Looking things up

- Lookups serve S2 (does a published version exist), S7 (does the record list more names), and, only when the user asks, filling a missing field.
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
