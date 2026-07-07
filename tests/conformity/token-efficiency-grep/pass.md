<!-- SPDX-License-Identifier: MIT -->

# Sample Artifact — Terse Prose

The scheduler assigns tasks to workers in round-robin order. Each task
carries a deadline; the scheduler fails the task when the deadline lapses.

The build completes in 5 minutes when the cache is warm and in 12 minutes
on a cold start. Cache warmth is measured by the size of `~/.cache/apothem`
relative to the 200 MB threshold.

```python
# Filler tokens inside fenced blocks are excluded: "very", "quite", "kind of".
result = compute(value)
```

> Quoted material is excluded: "It is important to note that the API is
> very fast." This block reproduces external prose verbatim.

Inline-code citations are excluded: filler such as `kind of` and qualifiers
such as `very` are named inside backticks here, a meta-linguistic citation of
the forbidden vocabulary rather than prose that uses it.

The function returns null when the key is missing.
