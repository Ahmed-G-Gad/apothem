<!-- SPDX-License-Identifier: MIT -->

# What each part needs from the source

A part is written only when the source gives it what it needs. When it does not,
the part is replaced by a thin notice (see the templates) and the Return Contract
lists it as thin. A section that was never opened is a different case: it is
`not read`, and nothing is taught from it.

## Minimum per part

| Part | Needs from the source | Thin when |
|------|----------------------|-----------|
| Goals | Stated aims, contributions, or conclusions, or at least three sections whose content can be turned into outcomes | The text offers an abstract and nothing else, or only a title and headings |
| Curriculum | Three or more sections that each carry a separate idea, with dependencies between them visible. A single section is thin when it holds no more than a line or two of teachable content | The document is one undivided argument, or a short note under about two pages; for one section, a heading with a line under it |
| Walk-throughs | A formula or algorithm with its symbols or inputs defined somewhere in the source and a result that depends on it | No formula or procedure appears, or its symbols are never defined and cannot be inferred from context |
| Worked examples | A walk-through, plus either the source's own numbers or enough definition to build a small instance whose result can be computed and checked | The walk-through is itself thin, or the quantities cannot be instantiated without outside assumptions |
| Quiz | At least one goal, and for each question a passage that settles the key | Fewer than three distinct stated claims or definitions to ask about |
| Glossary | Terms the source defines, or uses in a sentence that fixes their sense | The audience needs glosses for terms the source never explains; those entries are marked `[not in source]` and counted, not hidden |

The glossary is the one part that may carry outside glosses, because a newcomer
needs them. Every such entry is marked and the count is reported.

## Reading bases

| Basis | What may be written |
|-------|---------------------|
| `read in full` | Every part the source supports |
| `read in part` | Parts built only from the sections read; each part names the sections it used, and the sections not read are listed as `not read` |
| `abstract only` | Goals and glossary entries for terms the abstract defines, each flagged as abstract-only; everything else is a thin notice |

## Reading other types of document

The parts keep their names; what fills them changes with the type of document.

| Type | Counts as a claim | Counts as a key formula or algorithm | Natural example |
|------|-------------------|--------------------------------------|-----------------|
| Research paper | A stated result, theorem, or finding | An equation or procedure a result depends on | A small instance of the method, or one row of the paper's own table |
| Specification or standard | A requirement and its conditions | A state machine, message exchange, or encoding rule | One exchange traced step by step, with one compliant and one non-compliant case |
| Design document | A decision and its stated reason | A data flow or control flow the decision rests on | One scenario followed through the design |
| White paper | An assertion with its supporting figure | A calculation behind a headline number | The calculation redone with the stated inputs |

For a specification, the `limits` module lists what the document says is out of
scope, and quiz items test the exact wording of the requirement terms it defines.

## Signs a part is padded

- A step in a walk-through that the source does not contain and that no marker
  traces to a section.
- An example whose numbers appear nowhere in the source and are not marked
  `[built from §x]`.
- A quiz key that rests on `[not in source]`.
- A curriculum module with no sections attached.
- A limits module that lists limits the source never states.
