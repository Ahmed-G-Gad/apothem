<!-- SPDX-License-Identifier: MIT -->

# Surface Classes

Reference for the [`ui-design`](../SKILL.md) skill. Every interface is assigned exactly one class before shaping begins. The class decides what the design optimises for, which dial settings apply when the user gave none, and which failures matter most.

## Choosing the class

Ask what the person on the screen is trying to do.

| Class | The person is trying to | Typical surfaces |
|-------|-------------------------|------------------|
| persuade | Decide whether to act: sign up, buy, contact, believe | Landing pages, pricing, campaign pages, product tours |
| operate | Complete work repeatedly and accurately | Dashboards, admin tools, editors, forms, settings, tables |
| read | Take in sustained text and follow an argument | Documentation, articles, reports, help centres, changelogs |
| experience | Be absorbed in the surface itself | Games, interactive stories, creative tools, immersive showcases |

When a surface mixes classes, classify each screen on its own. A product site is persuade at the landing page and operate inside the account. A page that mixes classes within one screen takes the class of its primary job, and the secondary job borrows only the rules that do not conflict.

If two classes fit equally, ask the user which job comes first; do not pick one silently.

## What each class optimises

| Class | Optimise for | Favour | Avoid |
|-------|--------------|--------|-------|
| persuade | One clear next action, credibility, first-screen comprehension | A single dominant call to action per view, large type contrast, proof near the claim, generous whitespace, short sections | Competing calls to action, hidden pricing, carousels that bury content, decorative motion that delays reading |
| operate | Speed, accuracy, recoverability, low error rate | Density suited to the task, stable layout, keyboard paths for frequent actions, inline validation, visible system status, undo over confirm dialogs | Ornament that costs rows on screen, modal chains, layout that moves under the cursor, icon-only controls without labels |
| read | Sustained comprehension and comfort | Measure of 45 to 75 characters, steady vertical rhythm, high contrast, clear heading ladder, quiet chrome, stable anchors for linking | Full-width text lines, low-contrast grey body text, auto-playing media, sticky elements that cover text |
| experience | Immersion, feedback, a coherent world | A deliberate visual language, responsive feedback to every input, expressive motion with an off switch, clear exits | Unlabelled controls with no learnable pattern, motion with no reduced-motion path, content that traps keyboard focus |

## Default dials by class

The user's setting always wins. Where the user set none, apply the default below and state it in the closing report.

| Class | Variance | Motion | Density |
|-------|----------|--------|---------|
| persuade | distinctive | subtle | airy |
| operate | conventional | none | compact |
| read | conventional | none | comfortable |
| experience | distinctive | expressive | comfortable |

### Dial meanings

- **Variance** is how far the design departs from familiar patterns. `conventional` reuses standard components and layouts so users succeed without learning anything. `balanced` keeps standard structure and spends distinctiveness on type, colour, and imagery. `distinctive` allows unusual layout and interaction, and costs more testing, so it needs a reason in the brief.
- **Motion** is how much the interface animates. `none` allows only state feedback with no travel. `subtle` allows short transitions on state changes and entrances under 300 ms. `expressive` allows choreographed sequences and continuous animation, and every such effect needs a reduced-motion alternative.
- **Density** is how much content fits per screen. `airy` uses large spacing and few elements per view. `comfortable` is the standard rhythm. `compact` shrinks row height and padding but never below the pointer-target minimum for the input types the surface supports.

## Class-specific priority shifts

The category order in `rule-catalog.md` is fixed. The class changes how much effort each category receives inside its slot:

- persuade: spend extra on performance of the first screen and on typography and colour; a slow or unreadable first view loses the visit.
- operate: spend extra on forms, data display, and keyboard paths; these are where daily time goes.
- read: spend extra on typography and layout measure; navigation matters mainly for orientation within long pages.
- experience: spend extra on motion and feedback, then verify the accessibility floor deliberately, since expressive surfaces fail it most often.
