<!-- SPDX-License-Identifier: MIT -->

# Link-check fixture — dead `/docs` site route

This fixture plants a root-absolute `/docs` link to a route backed by no page
under `site/content/docs/`. The link-check validator MUST flag it as a dead
route — a user-facing 404. It exists only to exercise the matcher's failure
path and is exempt from the corpus sweep as a `tests/conformity/**` fixture.

- [Intentionally dead route](/docs/this-route-does-not-exist)
