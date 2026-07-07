<!-- SPDX-License-Identifier: MIT -->

# Getting support

This document routes you to the right channel for the question or issue you have. Pick the channel that matches the shape of your request — using the wrong channel slows the response.

## Quick routing

| What you need | Channel |
|---|---|
| A general question, a workflow tip, or a discussion-style thread | [GitHub Discussions](https://github.com/ahmed-g-gad/apothem/discussions) |
| To report a defect (bug) | [GitHub Issues — Bug report](https://github.com/ahmed-g-gad/apothem/issues/new?template=bug-report.yml) |
| To suggest a new capability or improvement | [GitHub Issues — Feature request](https://github.com/ahmed-g-gad/apothem/issues/new?template=feature-request.yml) |
| To ask a clarification question that needs an actionable answer | [GitHub Issues — Question](https://github.com/ahmed-g-gad/apothem/issues/new?template=question.yml) |
| To report a security vulnerability | [SECURITY.md](SECURITY.md) — use Private Vulnerability Reporting via the repository's Security tab |
| To contribute changes | [CONTRIBUTING.md](CONTRIBUTING.md) |

## Primary channel — GitHub Discussions

For everything that is not a defect, a concrete feature request, or a security report, **start in [Discussions](https://github.com/ahmed-g-gad/apothem/discussions)**. Discussions is the right venue for:

- Questions about how a rule, skill, command, hook, or agent works.
- Workflow patterns and operator-experience reports.
- Proposals you want to socialise before opening a feature request.
- Open-ended threads about the project's direction.

Discussions are publicly searchable, so a single answered thread benefits every operator who runs into the same question later.

## Secondary channel — GitHub Issues

Open an issue when:

- You can reproduce a defect against a specific Apothem version (Bug report).
- You have a concrete proposal that names the problem, the proposed solution, and the part of the project's conformance checks it touches (Feature request).
- You have a clarification question that needs an actionable answer and is anchored on a specific artifact path (Question).

The issue templates at [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE) enforce the minimum-information bar for each shape. Fill every required field — incomplete reports get closed with a request to refile.

## Security reports — separate channel

Security vulnerabilities have their own channel. They do **not** go through Discussions or Issues. Use [Private Vulnerability Reporting](https://github.com/ahmed-g-gad/apothem/security) via the repository's Security tab. The full policy, the supported-version matrix, and the response timelines are at [SECURITY.md](SECURITY.md).

## Last resort — email

When none of the channels above fits — for instance, an issue with the GitHub account itself, or a coordination request that cannot start in public — email [`me@ahmedgad.com`](mailto:me@ahmedgad.com). Email is the slowest channel: response times are best-effort and not bound by the SLA that applies to security reports. For routine support, prefer Discussions.

## Response expectations

- **Discussions:** best-effort response from the maintainer or the community; no guaranteed SLA.
- **Issues:** triage within 7 days; resolution timeline depends on severity, scope, and the maintainer's availability.
- **Security:** acknowledgement within 48 hours, triage within 7 days, fix-or-disclosure within 90 days per [SECURITY.md](SECURITY.md).
- **Email:** best-effort response; no guaranteed SLA.

If a thread or issue stalls, a polite ping after a week is welcome.
