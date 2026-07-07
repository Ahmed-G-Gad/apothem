<!-- SPDX-License-Identifier: MIT -->

# Plain artifact without provenance

This fixture has no frontmatter, no provenance marker, and no Bindings
section. The grep flags the absence of provenance attribution. When
the smoke test invokes the grep via stdin, the path is also absent so
only the provenance arm fires.
