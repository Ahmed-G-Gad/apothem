<!-- SPDX-License-Identifier: MIT -->

# Governance

This document describes how decisions are made in Apothem, how the
maintainer team evolves, and how conflicts are resolved. It complements
[MAINTAINERS.md](MAINTAINERS.md) (who the maintainers are) and
[CODEOWNERS](.github/CODEOWNERS) (the review-ownership partition).

## Decision-making model

Apothem follows a **BDFL** (Benevolent Dictator For Life) model. The
project lead — [Ahmed G. Gad (@ahmed-g-gad)](https://github.com/ahmed-g-gad) — holds
final authority over technical direction, releases, and the acceptance or
rejection of contributions.

In practice, the lead governs by consensus wherever possible: most
decisions are made openly through pull-request review and issue discussion,
and contributor input is actively sought. The BDFL role exists to resolve
deadlock and to keep the project coherent, not to bypass discussion.

## Maintainer lifecycle

### Adding a maintainer

A contributor becomes a maintainer through:

1. **Sustained contribution** — a track record of high-quality pull
   requests, issue triage, or review participation over time.
2. **Demonstrated judgement** — sound technical decisions and alignment
   with the project's conventions and direction.
3. **Invitation** — the project lead extends an invitation; on acceptance,
   the new maintainer is added to [MAINTAINERS.md](MAINTAINERS.md) and the
   relevant [CODEOWNERS](.github/CODEOWNERS) rows.

### Removing a maintainer

A maintainer may step down at any time (moving to the Emeritus list). The
project lead may also remove a maintainer for sustained inactivity (see
below) or for conduct that violates the
[Code of Conduct](CODE_OF_CONDUCT.md).

### Inactive-maintainer policy

A maintainer with no substantive activity for 12 months is moved to the
Emeritus list after a good-faith attempt to reach them. Emeritus
maintainers are welcomed back on renewed activity.

## Conflict resolution

Technical disagreements are resolved first through discussion on the
relevant pull request or issue. When discussion does not converge, the
project lead makes the final call, stating the rationale publicly. Conduct
disputes are handled per the [Code of Conduct](CODE_OF_CONDUCT.md)
enforcement guidelines.

## Forking clause

Apothem is MIT-licensed (see [LICENSE](LICENSE)). Anyone may fork the
project at any time for any reason. This right is the ultimate check on
the governance model: if the project's direction no longer serves part of
the community, that part is free to continue the work independently.
