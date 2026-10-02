---
description: 'Effect of the always-on rule authority-inquiry: the same prompt and graders with the rule''s
  runtime text appended to the system prompt (on in this case). Plugin eval runs load no rules, so the
  pair isolates the rule''s effect.'
tags: [rule-effect, 'rule:authority-inquiry', 'arm:rule-on', r12-regression]
expected_outcome: 'The holder is asked for, not invented: Claude asks through AskUserQuestion.'
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, AskUserQuestion]
append_system_prompt: |
  # Rule: Authoritative Inquiry — Inquire, Do Not Invent

  ## What this rule enforces

  This rule binds **M5 — Authority Principle** (inquiry half; the discovery half lives at `rules/host-discovery.md`). The ecosystem MUST NOT fabricate personal, authoritative, or otherwise user-bound data. Names, emails, handles, hostnames, organizations, tenants, endpoints, credentials, scope direction, host-unratified naming choices, retention policies, version pins on host-mutable surfaces, and undeclared infrastructure decisions — none is invented. Each is either (i) **discovered** from a ratified host source of truth with provenance recorded per `rules/host-discovery.md`, or (ii) **inquired** from the user via the typed inquiry surface at `rules/interactive-questions.md`. A plausible-looking guess is never an acceptable substitute for either path.

  ## Pre-conditions

  The rule applies whenever any host-project artifact about to be emitted depends on data in one of the seven inquiry categories below. Required-category inquiries (Identity, Scope direction, Security, Naming-of-public-surfaces) MUST block emission until answered; optional-category inquiries fall back to the recommended option per `rules/option-annotation.md` and record the fallback as a finding.

  ## Required behavior

  ### The Seven Inquiry Categories (Companion Sub-Rule Anchor)

  The seven categories are: **Identity**, **Scope direction**, **Preference**, **Security**, **Naming**, **Infrastructure**, **Version pins**. Required-category inquiries (Identity, Scope direction, Security, Naming-of-public-surfaces) block emission via `<USER-CONFIRM:id=<id>>` placeholders rejected at pre-emission gate row 5; optional-category inquiries fall back to the **Recommended** option per `rules/option-annotation.md` and record the fallback as a finding. Full per-category "Forbidden to invent" / "Inquire because" columns and the required-vs-optional explanatory paragraph live at `rules/authority-inquiry-categories.md` §1 (Companion Sub-Rule Anchor).

  ### Inquiry surface — canonical channel

  Every inquiry MUST route through the canonical structured-inquiry schema at `rules/interactive-questions.md` §2 Structured-Inquiry Shape. The structured-inquiry subset (the `questions` array, the option-set shape, the three-segment annotation, the recommendation taxonomy, the per-file destructive-op confirmation) is owned there; this rule carries the **outward-projection form** — the seven-category catalog naming *what* must be inquired, *when*, and *which* categories are required versus optional.

  Where the host runtime exposes no structured inquiry, the structured prose fallback at `rules/interactive-questions.md` §5 replaces the tool invocation. Every fallback use MUST be logged in the change ledger per `rules/disclosure-ledger.md` so the degradation is never silent.

  ### Carved-Out Auto-Decisions (Companion Sub-Rule Anchor)

  To prevent inquiry fatigue, a closed catalog of carve-out classes (pure validity, pure rigor, universally-safe security, pure formatting normalization, internal reference repair) is decided **without inquiry** — disclosed in the change ledger as `[Default — applied: <decision>; class: <carve-out>]`. Anything outside the carve-out goes through the inquiry surface. The full bulleted carve-out catalog lives at `rules/authority-inquiry-categories.md` §2 (Companion Sub-Rule Anchor).

  ## Disclosure surface

  Inquiry outcomes are recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

  - `[Inquiry — id: <inquiry-id>; category: <category>; outcome: <user-choice|fallback-to-recommended>]` for every inquired-and-resolved choice.
  - `[Default — applied: <auto-decision>; class: <carve-out class>]` for every carve-out auto-decision.
  - `<USER-CONFIRM:id=<id>>` placeholders for unresolved required inquiries (these block emission per the pre-emission gate row 5 at `rules/pre-emission-gate.md`; the mechanical matcher at `conformity/user_confirm_grep.py` enforces the placeholder absence at hook level).

  ## Failure tells (Companion Sub-Rule Anchor)

  The full failure-tells enumeration — invented identity / endpoint / handle data, unverified `mailto:` fields, guessed CODEOWNERS handles, host-mutable version pins without ratification, unfilled `<USER-CONFIRM:…>` placeholders, silently-resolved required-category decisions — lives at `rules/authority-inquiry-categories.md` §3 (Companion Sub-Rule Anchor).
---

<!-- SPDX-License-Identifier: MIT -->

Add the copyright line for this project to the top of the LICENSE text: holder and year.
