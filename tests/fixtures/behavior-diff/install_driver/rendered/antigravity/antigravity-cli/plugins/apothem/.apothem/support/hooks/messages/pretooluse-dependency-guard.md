<!-- SPDX-License-Identifier: MIT -->

Dependency-manifest supply-chain guard (advisory).

> Advisory: this hook reports; it does not block. Mechanical enforcement runs in CI.

Scope. Fires on Write/Edit to dependency manifests and their lockfiles: `pyproject.toml`, `requirements*.txt`, `package.json`, `Cargo.toml`, `go.mod`, `Gemfile`, and the matching lockfiles (`uv.lock`, `poetry.lock`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `Cargo.lock`, `go.sum`, `Gemfile.lock`). Non-matching paths pass unaffected.

This guard protects the operator's supply-chain posture per `rules/production-ready-prs.md` §3. It is advisory — it never blocks a correct manifest; it surfaces a dependency the operator should ratify before it lands.

Trigger / inspected patterns. The guard diffs the new content against the prior manifest and flags a newly-introduced or changed dependency line that matches any of three classes:

- **Unpinned where the host pins exact.** A version range, caret, tilde, or wildcard (`^1.2.0`, `~=2.3`, `>=4`, `*`, `latest`, an unbounded constraint) on a dependency in a manifest whose sibling dependencies are pinned to exact versions (`==1.2.3`, `=1.2.3`, an exact lockfile hash). The discriminator is the host's own ratified pinning policy discovered from the surrounding lines, not an absolute rule — library manifests legitimately carry ranges; production manifests pin.
- **Untrusted or unknown source.** A dependency pointing at a registry, index URL, or scope the manifest's siblings do not already use (`--index-url`, `--extra-index-url`, a private registry host, an unrecognized npm scope, a non-default crates source).
- **Git or URL dependency.** A dependency resolved from a git ref or a direct URL (`git+https://…`, a `git = …` table, a `path`/`url` source, a tarball link) rather than a published registry release.

Action — advisory flag. On any flagged line: surface the dependency through the structured-inquiry channel per `rules/interactive-questions.md` with a three-option set — **pin-to-exact (Recommended)** / **accept-as-proposed** / **cancel** — annotated per the canonical option-set discipline at `rules/interactive-questions-canonical-shapes.md` §2 (three-segment body, concrete-driver rationale, named default). The recommended option pins the flagged dependency to the exact resolvable version, citing the supply-chain posture as the driver. The operator's pick is the gate; the guard does not pin silently.

Fail-disposition. Two layers govern failure. (a) The Python dispatcher at `hooks/dispatch.py` is fail-open: a hook error — the diff cannot be parsed, the manifest cannot be read, or any Python exception inside the predicate — converts to a structured failure envelope on stdout and the Write proceeds, so a harness error never silently blocks the tool call. (b) The assistant's interpretation of this context is fail-closed on a detected finding: when a flagged dependency line is found, the directive is to surface it through the structured-inquiry channel and let the operator decide before the line lands. The two layers are non-redundant: the dispatcher protects the runtime, this context protects the supply-chain discipline, which is enforced mechanically in CI and pre-commit.

Non-matching paths. No action. The guard is scoped to the dependency-manifest and lockfile patterns above; every other path class passes unaffected.
