<!-- SPDX-License-Identifier: MIT -->

# Security Policy

This document describes how to report security vulnerabilities in this project, the support matrix for active versions, and the response and disclosure timelines the maintainer commits to.

## Supported versions

| Version | Supported                                      |
| ------- | ---------------------------------------------- |
| 1.5.x   | ✓                                              |
| 1.4.x   | Critical security fixes only, until 2027-04-28 |
| 1.3.x   | Critical security fixes only, until 2027-04-26 |
| 1.2.x   | Critical security fixes only, until 2027-04-25 |
| 1.1.x   | Critical security fixes only, until 2027-04-15 |
| 1.0.x   | ✗                                              |

The support matrix updates with each minor release; `scripts/release/bump_version.py` adds the new minor's row. The latest minor is always under active support and receives all security fixes. When multiple public minors exist, any previous-minor critical-fix-only window is listed here explicitly. Unlisted minors are unsupported; reporters should upgrade to a supported version before requesting a fix.

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

Release tags (`vMAJOR.MINOR.PATCH`) are GPG-signed, and the artifacts attached to each GitHub Release (sdist, wheel, SBOM, the platform archives and their `SHA256SUMS` manifest) carry Sigstore cosign signatures plus SLSA provenance. The one-shot installers check a release before materializing any configuration and abort, fail-closed, when the check does not succeed:

- **With cosign installed** (the default whenever `cosign` is on PATH and `APOTHEM_HOME` is not a git clone), two checks are required, and either failing aborts the install before `APOTHEM_HOME` changes. First, the release tag must carry a valid signature from the maintainer key, checked as in the next item, and the signed tag object must be the one named for that release: a validly signed tag for another release, re-pointed at this name, is refused. Then the installer downloads the release's platform archive, `SHA256SUMS` and `SHA256SUMS.cosign.bundle`. cosign must confirm that the release workflow at that tag (`https://github.com/Ahmed-G-Gad/apothem/.github/workflows/release.yml@refs/tags/<tag>`, issuer `https://token.actions.githubusercontent.com`) signed `SHA256SUMS`, and, through its `--certificate-github-workflow-sha` check, that the certificate it verified was issued to a run on the commit the signed tag points at. The installer does not read the certificate itself; cosign makes that comparison. The archive's SHA-256 must then match `SHA256SUMS`. Both signatures are needed because each proves something the other does not: the release workflow runs for any tag that is pushed, so its signature alone does not show that the maintainer released that commit, and the tag signature alone says nothing about the archive. This path needs `git`, `gpg` with the maintainer public key imported, and cosign.
- **Without cosign**, or when `APOTHEM_HOME` already holds a git clone, the installer clones the repository (or fetches into the existing clone) and runs `git verify-tag`. The signature must be valid and made by the maintainer key below: the installer compares GnuPG's primary-key fingerprint with the one published here and refuses a tag signed by any other key, even one the local keyring trusts. The signed tag object must also name the release being installed. An existing clone is fetched and its new tag is checked before the clone is checked out, so a failed check leaves the clone where it was, and a clone with changes to its tracked files, or other local changes that the checkout would overwrite, stops the update rather than losing them. The update scripts follow the same order. A git tag names its commit by a SHA-1 object ID; the cosign path adds the SHA-256 digest of the archive. This check needs `gpg` and the maintainer public key in the local keyring; import the key once as shown under [Maintainer signing key](#maintainer-signing-key).

`APOTHEM_VERIFY` picks a path explicitly: `release` (require both checks, and so cosign), `signature` (require the tag check), or `checksum` (the archive's SHA-256 alone). Checksum mode does not verify the release. SHA256SUMS comes from the same release as the archive, so a match only shows the download isn't damaged; anyone who can change the release's files can change both. The installers therefore run `checksum` only when `APOTHEM_ALLOW_UNVERIFIED=1` is also set, and warn before they download. `APOTHEM_ALLOW_UNVERIFIED=1` can also downgrade a failed tag check to a warning on the clone path only; it never relaxes the `release` path or the check that the signed tag names the release. Because it lets an unsigned tag, or one signed by another key, through, that re-pointed-tag check protects only tags that carry the maintainer key's signature. The installers build the new source beside `APOTHEM_HOME`, swap it in only after every check has passed, and put the earlier install back unchanged if a step fails. The [install guide](https://apothem.ahmedgad.com/docs/install#trust-model) lists every mode.

A piped one-liner (`curl ... | sh`, `irm ... | iex`) never runs a local tree. It does not look in the current folder or its parent folders. The installers use a local tree only when you run the checkout's own `scripts/installer/install.sh` (or `install.ps1`) by its path, from any folder, or when `APOTHEM_SOURCE` names it. The engine and the `apothem` command never import `click`, `rich` or `apothem` modules from the current folder. The installers' `git` commands that do not work on a clone do not read a repository in the current folder. Empty and relative entries in your own `PYTHONPATH` are not passed on to the engine by any launcher (the installers, updaters, uninstallers, the POSIX and Windows `apothem` shims, and the npm launcher). A kept entry must be a full path: on Windows a drive path such as `C:\lib` or a network path, elsewhere a path that starts with `/`. A rooted `\lib` or a drive-relative `C:lib` is dropped. The sh scripts ask the Python they run which form it reads, and the `apothem` shim they write keeps that form. A Windows Python (the usual one under Git Bash) gets the engine paths in Windows form, joined with `;`, and keeps only the drive and network paths of your `PYTHONPATH`. A POSIX Python, including Cygwin's and MSYS2's own `python3`, gets POSIX paths joined with `:` and keeps only entries that start with `/`. The updaters do not rewrite an existing `apothem` shim: to replace a shim written by release 1.0.1 to 1.5.0, run the installer (`install.sh` or `install.ps1`) again.

To verify a release tag locally: import the maintainer signing key, confirm the imported key's fingerprint, then run `git verify-tag <tag>` inside the clone.

### Release tags are not all the same kind of object

| Tag | Tag object | How to verify it |
| --- | --- | --- |
| `v1.5.0` | annotated, GPG-signed | `git verify-tag v1.5.0` |
| `v1.4.0` | annotated, GPG-signed | `git verify-tag v1.4.0` |
| `v1.3.0` | annotated, GPG-signed | `git verify-tag v1.3.0` |
| `v1.2.2` | annotated, GPG-signed | `git verify-tag v1.2.2` |
| `v1.2.1` | annotated, GPG-signed | `git verify-tag v1.2.1` |
| `v1.2.0` | annotated, GPG-signed | `git verify-tag v1.2.0` |
| `v1.1.0` | annotated, GPG-signed | `git verify-tag v1.1.0` |
| `v1.0.2` | annotated, GPG-signed | `git verify-tag v1.0.2` |
| `v1.0.1` | lightweight (no tag object) | `git verify-commit v1.0.1` — the commit it names is GPG-signed |

`v1.0.1` was pushed as a lightweight tag. A lightweight tag has no object to sign, so `git verify-tag v1.0.1` fails ("cannot verify a non-tag object") and the one-shot installer, when it checks the tag (every network install does, except in `checksum` mode), aborts with its "unsigned or its signature did not verify" message when `APOTHEM_REF=v1.0.1`. The release commit itself is signed, so `git verify-commit v1.0.1` verifies it. Published tags are kept as they are rather than rewritten, so this limit is permanent for `v1.0.1`: pin `v1.0.2` or later for a verified install. Every release from `v1.0.2` on is an annotated, signed tag (`git tag -a -s`).

### Maintainer signing key

Release tags are signed with this key. The installers pin its fingerprint, so a tag signed by any other key is refused:

| Field | Value |
| --- | --- |
| Owner | Ahmed G. Gad `<me@ahmedgad.com>` |
| Algorithm | ed25519 |
| Fingerprint | `5C89 98F9 F241 7204 45D3  F28B 7039 6FED 9C63 4163` |
| Published at | <https://github.com/ahmed-g-gad.gpg> |

Import it once, then check that `gpg` prints the fingerprint above:

```shell
curl -fsSL https://github.com/ahmed-g-gad.gpg | gpg --import
gpg --fingerprint 70396FED9C634163
```

On Windows, `git verify-tag` reads the keyring of the `gpg` that ships with
Git for Windows, so run the same commands through Git's own `bash`:

```powershell
& "$env:ProgramFiles\Git\bin\bash.exe" -c 'curl -fsSL https://github.com/ahmed-g-gad.gpg | gpg --import && gpg --fingerprint 70396FED9C634163'
```

If the fingerprint differs, do not install: report it through the channels
above.

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
