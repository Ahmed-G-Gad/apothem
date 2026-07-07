<!-- SPDX-License-Identifier: MIT -->

# Security Policy

This document describes how to report security vulnerabilities in this project, the support matrix for active versions, and the response and disclosure timelines the maintainer commits to.

## Supported versions

| Version  | Supported          |
| -------- | ------------------ |
| 1.0.x    | ✓                  |

The support matrix updates with each minor release. The latest minor is always under active support and receives all security fixes. When multiple public minors exist, any previous-minor critical-fix-only window is listed here explicitly. Unlisted minors are unsupported; reporters should upgrade to a supported version before requesting a fix.

## Reporting a vulnerability

Two reporting channels are available. Use the primary channel whenever possible — it produces a private, auditable record that supports coordinated disclosure end-to-end.

**Primary (preferred): GitHub Private Vulnerability Reporting.** Visit the repository's **Security** tab and click **Report a vulnerability**. The repository has Private Vulnerability Reporting enabled, which opens a private workspace shared between the reporter and the maintainer, supports draft CVE allocation, and gives a controlled publication step at the end.

**Secondary: email.** Send a report to `me@ahmedgad.com`. Use this channel only when GitHub Security Advisories are unavailable, when the report concerns the GitHub account itself, or when the reporter has an established preference for email.

Every report — regardless of channel — should include:

- A clear description of the issue, including the security impact in plain language.
- Steps to reproduce, ideally as a minimal proof-of-concept.
- The affected version(s), with commit SHA when known.
- Any suggested mitigations, workarounds, or patches the reporter has already validated.

PGP-encrypted reporting may be supported in the future. Reporters who require encrypted email today should email the security contact above to request the current public key before sending sensitive material.

## Code of Conduct reports

[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) routes enforcement concerns to the same private channels described above. A conduct report reaches the right place here — it is received privately and handled with the same confidentiality as a security report, though security vulnerabilities and conduct concerns are triaged as separate tracks. The reproduction detail requested above applies to security reports; a conduct report needs only a clear account of what happened and when.

## Release signing

Release tags (`vMAJOR.MINOR.PATCH`) are GPG-signed, and the artifacts attached to each GitHub Release (sdist, wheel, SBOM) carry Sigstore cosign signatures plus SLSA provenance. The one-shot installers verify the tag signature with `git verify-tag` before materializing any configuration and abort, fail-closed, when verification does not succeed. Third-party `git verify-tag` needs the maintainer public key in the local keyring; until its fingerprint is published (see below), set `APOTHEM_ALLOW_UNVERIFIED=1` to proceed without local tag verification.

To verify a release tag locally: import the maintainer signing key, confirm the imported key's fingerprint, then run `git verify-tag <tag>` inside the clone. The maintainer signing-key fingerprint will be published at this location once the maintainer records it; until then, cross-check the signing identity against the signature metadata on the GitHub Release page and against the key fingerprint that `git verify-tag <tag>` itself reports.

<!-- TODO(clarify): publish the maintainer GPG signing-key fingerprint here.
The fingerprint value is an operator input that cannot be derived from the
repository; until the maintainer records it, verifiers should cross-check the
signing identity against the signature metadata on the GitHub Release page. -->

## Response timeline

The maintainer commits to the following service levels, measured from the moment the report is received through the channels above:

- **Acknowledgement:** within 48 hours of receipt. The reporter receives confirmation that the report was received and is under review.
- **Triage and severity assessment:** within 7 days. The maintainer assigns a severity rating (Low / Medium / High / Critical) and confirms scope.
- **Fix or public-disclosure decision:** within 90 days from triage. The maintainer either ships a fix, publishes a mitigation advisory, or — in exceptional cases — extends the window with the reporter's agreement.

## Public-disclosure timeline

This project follows coordinated disclosure. Public disclosure happens after the fix lands in a supported release, or 90 days after triage, whichever is sooner. For High or Critical issues, the maintainer coordinates with the reporter on the exact disclosure date so that downstream consumers have time to upgrade. Reporters who need an embargo extension should request it before the 90-day window closes; the maintainer will grant reasonable extensions when a fix is in active progress.

## Out of scope

The following are not in scope for this policy:

- Social-engineering attacks against contributors, maintainers, or end users.
- Denial-of-service or volumetric abuse of public APIs that does not exploit a specific vulnerability.
- Vulnerabilities in third-party services, dependencies, or platforms not maintained by this project — report those upstream.

## Acknowledgement

Responsible reporters make this project safer for every user. The maintainer thanks every researcher who follows this policy and welcomes coordinated disclosure. Reporters who wish to be credited will be acknowledged in the release notes that ship the fix; reporters who prefer to remain anonymous will have their preference respected.
