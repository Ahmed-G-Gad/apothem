<!-- SPDX-License-Identifier: MIT -->

# Output Styles

Output-style definitions — flat `.md` files, each defining a tone and output-shape the operator selects via `/output-style`. An output style governs *how* the agent presents work: prose density, formatting conventions, citation posture, and finding-shape — without weakening any behavioral mandate.

## Index

| Style | `name` | What it sets |
|-------|--------|--------------|
| [`default.md`](default.md) | Default | Ecosystem-default output style — the baseline tone every session inherits. Encodes unified output conventions, planning-content routing, and the file-authoring contract. |
| [`default-architect.md`](default-architect.md) | Default Architect | Senior Software Architect tone — analytical, brutally honest, concrete-driver citations, seven-axs-of-breadth attestation. |
| [`concise-engineer.md`](concise-engineer.md) | Concise Engineer | Engineering-focused short-form output — minimum prose, maximum signal, code-first. |
| [`forensic-auditor.md`](forensic-auditor.md) | Forensic Auditor | Forensic-audit posture for review-class work — finding-by-finding, scorecard-shaped output, a falsifier per finding. |

## The baseline-plus-supplement relationship

`default.md` is the **baseline** — every session inherits it unless the operator selects a different style. It defines the ecosystem floor: the output conventions, definitiveness posture, and authoring contract that always hold.

The three sibling styles are **supplements**, not replacements. Each layers a posture on top of the `default.md` floor without weakening it — `default-architect` adds the architect's analytical register, `concise-engineer` tightens prose density, `forensic-auditor` reshapes output into the scorecard form review work needs. Selecting a sibling style supplements the baseline; the baseline's conventions still apply.

## Frontmatter contract

Output-style frontmatter carries two required fields, the floor the conformity grep enforces on every cohort file:

- `name` — the human-readable style name shown in `/output-style`.
- `description` — one-line statement of the style's posture.

Every shipped style also sets `keep-coding-instructions: true`. A style changes how work is presented, not how engineering work is done, so the host's built-in software-engineering instructions (scoping changes, writing comments, verifying work) stay on. A host that honours this key drops those instructions when the key is absent, because its default is `false`.

[`../schemas/output-style.schema.json`](../schemas/output-style.schema.json) requires the same `name` + `description` floor, types `keep-coding-instructions` as a boolean, and admits `id`, `applies-to`, `version`, and `last-reviewed` as optional extensions. The body after the frontmatter specifies the style's conventions.

## Conventions

- One flat `.md` file per style; kebab-case filenames.
- Every file carries the canonical single-line SPDX license header.
- A style supplements the `default.md` floor; it never weakens a behavioral mandate. Disclosure-ledger markers and other mandate-required surfaces are preserved under every style.

## Operating in this folder

- **Harness- and model-agnostic, no exceptions.** This folder is swept by the agnosticism matcher: a style file MUST NOT name or privilege any harness, model, or vendor, and MUST NOT pre-set an effort or model preference. A posture describes presentation register only.
- **Adding or changing a style:** author the frontmatter against the schema (including `keep-coding-instructions: true`), write the posture body as a supplement to the baseline (never a replacement that weakens a mandate), confirm it introduces no harness/model/effort bias, and register the new style in the index above in the same change-set.
- Validate with `python -m ruff check` and `python -m ruff format`, the conformity gate `python -m apothem.conformity.gate --all .` (which runs the agnosticism sweep over this folder), and `python -m pytest`.
