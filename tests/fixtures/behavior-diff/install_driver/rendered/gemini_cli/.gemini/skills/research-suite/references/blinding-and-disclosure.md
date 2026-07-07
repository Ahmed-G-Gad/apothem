<!-- SPDX-License-Identifier: MIT -->

# Blinding & Staged Disclosure

Reference surface for the [`research-suite`](../SKILL.md) skill. Houses the
blinding and staged-disclosure discipline that keeps intermediate and
submission deliverables within a target venue's anonymity policy while holding
identity for a designated later restore. Loads selectively, beside `SKILL.md`,
so the router's entry-point stays tight.

This surface adds operational detail to R6 (ethics and conflicts) and extends
the CM-7 natural-domain-language discipline at `rules/operational-mandates.md`;
it introduces **no** new rigor mandate — R1–R10 is a closed set of ten. Where
R6 obliges the pipeline to state ethics, conflict-of-interest, and
availability declarations at the right time, this surface governs the *inverse*
timing problem: which identity a deliverable withholds now, and the stage at
which that identity is restored. CM-7 suppresses suite-internal references so a
deliverable reads as ordinary domain prose; blinding extends that same
natural-language reflex from suite-internal names to author, institution,
funding, and the identity of the system under study.

## What the anonymity policy governs

- **Carry only what the policy permits.** An intermediate or submission deliverable MUST carry only the identity that the target venue's anonymity policy permits at that stage. Where the policy is single-blind the author identity MAY remain; where it is double-blind the author, institution, and funding identity MUST be held out of the deliverable body. The discipline is invariant to venue naming — the rule is stated against the *policy category* (single-blind, double-blind, open), never against a named venue.
- **Extend CM-7 to system and tool identity.** CM-7 already requires a deliverable to describe its subject in natural domain language rather than by suite-internal reference. This surface extends that reflex: the system under study MUST be described in ordinary domain usage — what it does and how it behaves — **without** naming the product, tool, or system. A double-blind deliverable that de-anonymizes itself by naming its own system fails the policy as surely as one that names its author.
- **Author and institution anonymization.** Under a double-blind policy the deliverable body MUST NOT name the author, the author's institution, or the funding identity, and MUST NOT carry acknowledgements, grant numbers, or repository handles that reconstruct them. Placeholders stand in the deliverable body; the held-out strings live only in the attestation.

## Staged disclosure

Blinding is a **staging** discipline, not permanent suppression. The held-out
identity — author, institution, funding, and the identity of the system or tool
under study — is the designated **de-anonymization payload**: the exact set of
strings the deliverable withholds now and restores later.

- **The payload is designated, not discarded.** The held-out identity MUST be recorded in the deliverable's attestation as the designated restore set. Identity is never *permanently* withheld — withholding without a recorded restore path is a leak of a different kind, an unrecoverable deliverable.
- **Restore at the designated stage.** The payload SHOULD be restored at the stage the policy designates for de-anonymization — the camera-ready or post-acceptance stage — and MUST NOT be restored earlier than that stage. Restoration replaces every placeholder in the deliverable body with the recorded string from the payload.
- **One payload, one attestation.** A deliverable carries a single de-anonymization payload; the attestation is the sole authoritative record of what was held out, so a later stage restores from one place rather than reconstructing identity from memory.

## Double-blind readiness is a gated check

Double-blind readiness MUST be treated as a **gated check** run against the
deliverable, not an assumption that anonymization happened. The gate clears
only when every bar below holds:

- **No residual identity leak in the body.** The deliverable body MUST carry no residual author, institution, funding, or system/tool identity — not in prose, not in captions, not in acknowledgements, not in metadata, not in repository or artifact handles that reconstruct identity.
- **Self-citations are de-anonymization-safe.** A reference to the author's own prior contribution MUST be phrased so it does not de-anonymize the author — a neutral third-person reference to a prior contribution, never a first-person one that reveals authorship.
- **The attestation records the held-out identity.** The attestation MUST record the de-anonymization payload — the held-out author, institution, funding, and system/tool identity — so the designated later stage restores it exactly. A gate that clears the body checks but records no payload is incomplete: it produces a deliverable that can never be de-anonymized.

A deliverable that does not clear every bar is not double-blind-ready and MUST
NOT advance to a stage that assumes a clean anonymity surface; the leak is
remediated and the gate re-run, never waived.

## Bindings (§0.j five-direction)

- **Drives →** ● The anonymization and staged-disclosure decisions in `/research-paper`, `/research-review`, `/research-publish`, and `/research-disseminate` (which identity a deliverable withholds now and the stage at which it is restored).
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the blinding and staged-disclosure surface loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R6 mandate this surface operationalizes).
- **Cross-bound with ↔** ↔ `rules/operational-mandates.md` (CM-7 natural-domain-language, which this surface extends from suite-internal references to author, institution, funding, and system/tool identity). ↔ `rules/authority-inquiry.md` (the naming of public surfaces is an authority-inquiry category, routed through the structured-inquiry channel on host silence). ↔ [`references/advancement-gate.md`](advancement-gate.md) (review is the advance gate that checks blinding integrity before a deliverable clears).
