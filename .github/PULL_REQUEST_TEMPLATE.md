<!-- SPDX-License-Identifier: MIT -->

## Summary

Describe the change in one paragraph: what does this pull request do, and what is the user-visible effect?

## Motivation

Describe the why in one paragraph: what problem does this change solve, and why is this approach the right one?

## Mandate alignment

Name the M1-M15 mandates the change advances or touches. See `site/content/docs/governance/positioning.mdx` §3 for the registry walkthrough. If the change is orthogonal to the registry, say so explicitly. Cite the rule path + section anchor where the binding clause lives.

## Test plan

- [ ] Tests added or updated (describe the cases covered):
- [ ] `pytest tests/` passes locally
- [ ] Manual verification steps where automated tests cannot cover the surface:

## Conformity-gate verification

- [ ] `python scripts/dev/validate_ecosystem.py` passes
- [ ] `pre-commit run --all-files` passes
- [ ] Pre-emission gate attestation recorded for meaningful-scope changes

## CHANGELOG entry

- [ ] User-visible changes appended to `CHANGELOG.md` Unreleased section, OR
- [ ] N/A - change is internal only (rationale: ...)

## Foundational discipline checks

- [ ] No planning artifact added to this pull request (Plans-Locality — `CLAUDE.md` Plans Discipline).
- [ ] Every new file carries the canonical authorship header (`site/content/docs/reference/authorship-header.mdx`; `src/apothem/schemas/authorship-header.txt` is the byte-exact fixture).
- [ ] No contradiction between `CLAUDE.md` and `.github/copilot-instructions.md` (`CLAUDE.md` AI Surface Canon).

## Related issues

Link any issues this pull request closes, references, or depends on (for example `Closes #123`, `Refs #456`).

## Checklist

- [ ] I have read `CONTRIBUTING.md`.
- [ ] This pull request follows Conventional Commits (`type(scope): subject`).
- [ ] I have signed off my commits per the DCO (`git commit -s`).
- [ ] I have updated documentation if necessary.
