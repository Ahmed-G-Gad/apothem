<!-- SPDX-License-Identifier: MIT -->

<!-- REUSE-IgnoreStart -->
# MCP — Authorship Notice

> **Role.** Records the authorship and license provenance for the JSON
> template files in this directory. JSON admits no comment construct
> (RFC 8259), so the canonical `SPDX-License-Identifier: MIT` header line
> cannot live inline at the head of `mcp/*.json` files; JSON files are
> categorically header-exempt, and this `NOTICE.md` carries the provenance
> for the directory class.

## JSON Header-Exemption Rationale

The canonical file header is the single `SPDX-License-Identifier: MIT` line,
written in the comment family matching each filetype (the byte-exact fixture
is `src/apothem/schemas/authorship-header.txt`). JSON has no comment syntax,
so `mcp/*.json` template files are **header-exempt** per the categorical
exemption at `src/apothem/schemas/header-exceptions.txt`. The `*.json`
siblings carry only their structural payload; this `NOTICE.md` carries the
provenance the directory class requires.

## Authorship Provenance for the JSON Templates

- **Author.** Ahmed G. Gad.
- **License.** MIT, per the repository `LICENSE` at the top of the working
  tree (which carries the full copyright instrument).
- **Provenance trail.** Every `mcp/*.json` template was authored under the
  same authorship as this NOTICE; commits touching the templates carry the
  author's identity in the git authorship surface per
  `src/apothem/rules/production-ready-prs.md` §6 (commit-message discipline —
  human-only authorship).

<!-- REUSE-IgnoreEnd -->

## Bindings

- **Drives →** Every operator's authorship-trail audit of the `mcp/*.json`
  templates; the categorical-exemption check at the file-header validator
  (`src/apothem/conformity/file_header_grep.py`), which honors
  `src/apothem/schemas/header-exceptions.txt` for JSON files in this directory.
- **Established by ↑** `src/apothem/schemas/header-exceptions.txt` (the
  categorical JSON exemption).
- **Cross-bound with ↔** `mcp/README.md` (operator instructions for
  populating local MCP configs); `src/apothem/conformity/file_header_grep.py`
  (the validator that honors the exemption).
