<!-- SPDX-License-Identifier: MIT -->

# schemas/ — provenance notice

The `.json`, `.yaml`, and `.txt` files in this directory are exempt from the canonical authorship-header per spec §4.6.4: JSON has no comment syntax, and the byte-exact `.yaml` / `.txt` fixtures consumed verbatim by matchers and installers cannot carry an in-band header without breaking those consumers. This `NOTICE.md` carries the canonical Markdown-variant SPDX license notice on behalf of the entire `schemas/` directory as a **directory-class provenance statement**: every header-exempt file alongside it is licensed under MIT through this notice. For a curated, purpose-and-consumer description of each file, see [`README.md`](README.md) — this notice does not duplicate that enumeration. The schemas validate frontmatter on `agents/`, `skills/`, `commands/`, and `output-styles/` artifacts inside this ecosystem, and on plan files authored in downstream projects. The Plan schema is consumed by `/plan-spec --quick` at plan-frontmatter authoring time so downstream-project plans can be validated without invoking the full prose-refinement pipeline.

## License coverage

This notice covers every header-exempt file in this directory — the `.json` schemas, the `.yaml` configuration and manifest files, and the `.txt` fixtures (including `__init__.py`'s sibling data files). The authoritative per-file purpose-and-consumer catalog lives in [`README.md`](README.md); when a new schema or fixture is added, it is described there rather than re-enumerated here.
