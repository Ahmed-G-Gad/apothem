<!-- SPDX-License-Identifier: MIT -->

# Slide outline and hand-off

Produced only when slides are requested. The outline is a Markdown file that any
slide or document skill can read; it fixes the content and leaves the look to the
skill that builds the deck.

## Shape of the outline

```markdown
# <Document title as seen> - slide outline

Source: <path>. Basis: <read in full | read in part | abstract only>.
Audience: <level>. Talk length: <as given by the user, or "not given">.
Style constraints: <as given by the user, or "none given">.

## Slide 1. <Title as seen>
Authors, venue, year as seen: <text, or "not seen">. Builds from: pack header.

## Slide 2. <A full sentence that states the point of the slide>
- <Point, at most one line.> [§<x>]
- <Point.> [built from §<x>]
Visual: <figure or table by number as seen, or a diagram to be drawn: what it shows>.
Notes: <what to say, with locators>. Builds from: <G, M, W, E, or Q ids>.
```

## Order of slides

1. Title slide, naming the document exactly as seen.
2. The question the document answers and why a learner would care.
3. The learning goals.
4. One to three slides per curriculum module, in curriculum order.
5. A slide for each walk-through, with the formula or algorithm and its steps, followed by a slide for its worked example.
6. The assumptions and limits the source states.
7. Quiz slides carrying questions only. The key goes in the notes of a final slide, never on the question slides.
8. A glossary slide for the terms the talk leans on most.

The count follows from the modules and walk-throughs. A talk length given by the
user trims the outline by dropping lowest-priority modules, and the dropped ones
are listed in the outline's footer rather than deleted silently.

## Rules for slide text

- A slide title is a full sentence that states the point, not a topic label.
- At most four points per slide and one line per point.
- Figures and tables are referred to by number and placed by the deck builder from
  the user's own copy; the outline never reproduces them.
- Every point carries a marker, as in the pack.
- A claim that the source makes only in passing is not promoted to a headline.

## Hand-off

1. Look for a slide or document skill among those the host exposes, through the
   discovery steps in `rules/host-discovery.md`. Match on capability (it builds
   presentations or documents), not on a name.
2. With one candidate, pass it the outline file path, the audience, the talk length,
   and any style constraints the user gave. With several, ask which to use. With
   none, deliver the outline and say that no deck was built.
3. When the builder returns a deck, open it if it can be read and compare slide
   titles with the outline. Report slides that are missing, merged, or reordered.
4. Record in the Return Contract which skill was used and which file was passed.
   A deck the builder did not produce is never reported as made.
