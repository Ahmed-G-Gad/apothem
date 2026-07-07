<!-- SPDX-License-Identifier: MIT -->

# Fixture: pass

This fixture demonstrates a single Markdown file whose prose carries
content that is not duplicated anywhere else in the governed corpus.
The matcher operates at corpus scope; a single isolated file cannot
exhibit cross-file duplication by construction, so this fixture passes
trivially when the matcher's walk includes only this file.

The body discusses an entirely fixture-specific topic that no rule,
command, skill, or hook message in the real corpus addresses: the
hypothetical migration of a fixture's own provenance record from one
canonical home to another. The vocabulary here is deliberately
fixture-bound — fixture-bound terms include phrases like provenance
fixture migration ledger, fixture-scope token vocabulary, and the
matcher's own corpus walker semantics described in fixture-local
language. The intent is to keep this paragraph distinct enough from
every other corpus paragraph that no false-positive jaccard hit can
trigger against any sibling document under the four canonical
authoring trees.
