<!-- SPDX-License-Identifier: MIT -->

# Sample Artifact — Filler-Laden Prose

In this section, we will describe how the scheduler works. Before diving in,
it is worth establishing the context.

To begin with, the scheduler is very fast. As mentioned earlier, the design
favours throughput over latency.

The cache is quite small, and the eviction policy is rather aggressive. The
build is fairly reliable on warm runs.

Without further ado, here is the dispatch loop.
