<!-- SPDX-License-Identifier: MIT -->

# Sample Artifact — Notation Drift in Bindings

This fixture is the FAIL case for `binding-reciprocity-grep`. The Bindings
section uses ASCII substitute arrows (`->`, `<-`, `<->`) instead of the
canonical Unicode arrows. The grep flags each occurrence.

## Body

This artifact has substantive content. The Bindings section below drifts
from the canonical notation.

## Bindings (§0.j five-direction)

- **Drives ->** Every downstream consumer of this artifact's output.
- **Driven by <-** The upstream producer that triggers this artifact.
- **Satisfies ->** The end-state criterion this artifact establishes.
- **Cross-bound with <->** Every sibling that mutually reinforces this artifact.
