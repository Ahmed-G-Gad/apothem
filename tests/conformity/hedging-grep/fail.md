<!-- SPDX-License-Identifier: MIT -->

# Sample Artifact — Hedged Prose

This fixture is the FAIL case for `hedging-grep`. Multiple hedging words
appear in prescriptive contexts; the grep flags each.

## Behavior

The function usually returns `null` when the key is missing. It might
also return the empty string in some cases. The build typically completes
within five minutes, though it could take longer on a cold start.

The cache size is generally 100 MB; users should probably tune it for
their workload.

## Conclusion

This artifact must NOT ship until each hedge is promoted to an
unconditional form or demoted to an explicit conditional with branches
named.
