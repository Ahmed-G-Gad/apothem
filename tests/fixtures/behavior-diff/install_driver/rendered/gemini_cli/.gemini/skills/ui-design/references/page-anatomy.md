<!-- SPDX-License-Identifier: MIT -->

# Page Anatomy

Reference for the [`ui-design`](../SKILL.md) skill. Page scope only (see [surface classes](surface-classes.md)). This file decides what a page contains and in what order. Two inputs drive it: the material the user supplied and the job the visitor came to do. The page shape decides how each section looks ([page shapes](page-shapes.md)). The theme decorates the anatomy; it never replaces it ([direction and themes](direction-and-themes.md)). Rule ids and grades live in the [rule catalog](rule-catalog.md). A flag in this file that cites no id grades under the catch-all `pag-00.<section>`.

## 1. Material inventory

Before any structure is chosen, write a one-line inventory in three buckets. It feeds the Material row of the decision summary ([build record](build-record.md)).

- **Real.** Each concrete item supplied: the name, claims, figures, locations, dates, prices, people, and images.
- **Pictures.** Everything that will be shown, and its source: the user's own files, captures of the working product, the product rebuilt in HTML, or openly licensed photos ([imagery and data](imagery-and-data.md)).
- **Absent.** Every type of proof the page will lack: logos, quotes, reviews, metrics, press.

Shape follows inventory. A picture-rich inventory opens with pictures. A word-based inventory runs on type and facts. An item in the absent bucket MUST NOT reappear on the page as an invented stand-in (`cpy-02`, [copy and honesty](copy-and-honesty.md)).

## 2. The visitor's job

Name the job with one entry from the list below. The job sets three things:

- where the main action sits: the hero, a sticky bar, beside the content, or at the end;
- which sections native to the category anchor the page;
- how the page closes.

Build the page the way real sites in that category are built.

The stock sequence is a statistics strip, a three-step explainer, and an email-capture band. It MUST NOT be the default for any job (`pag-00.2`). Software anatomy on a restaurant or a band is the largest structural sign of a generated page.

### Rules that hold for all ten jobs

- **Nav.** It names the visitor's verb for this job, such as shop, book, listen, tickets, or start free.
- **Hero.** It shows the real subject: the product's screen, the album cover, the event dates, the dining room ([hero](hero.md)).
- **Proof.** It takes the category's native form: a readership line, a press quote, a project list. Never a generic stats strip.

### The ten jobs

| Job | Main action | Native sections | Close |
|-----|-------------|-----------------|-------|
| **Subscribe** (newsletter, waitlist, podcast) | The sign-up sits at the top. It MAY be the whole hero: name, one line, an email input. A podcast puts the newest episode with a play control below it. | A recent issue shown as a reader receives it; the author; the back catalog as a dated list; a subscriber count only if supplied, set the way a magazine prints its readership. | The archive, or a second email input placed after it. |
| **Book** (restaurant, class, clinic, studio) | A reservation picker (party size, date, time) reachable from nav and hero, or open slots as buttons. Repeated beside the menu or timetable, never only at the foot. | Photos of the room or the food with few headings; the menu, by sitting or as priced rows; the class timetable; directions; a section for opening hours and address. | Hours, location, and the reservation control again. An upscale venue MAY need only one photo, the menu, and booking. |
| **Visit** (shop, gallery, venue, place) | Today's opening hours and the street address in nav or hero. Tickets or donations only if supplied. | The current show or offer as the lead image; upcoming items as dated rows or a this-week and next-week toggle; a shop's real stock as a side scroller or grid; how to get there. | Visiting details and address, or a mailing list for future events. |
| **Attend** (event, festival, race, conference) | A ticket link in the nav from the first screen. Date and place form the headline. | Line-up or speakers with names set large; a day-by-day schedule; priced ticket tiers; venue and travel; FAQ. Figures only if supplied. | Tickets again, the FAQ, or sign-up for next year. Between editions the page shrinks to date, place, and list. |
| **Buy** (physical product, small shop) | An offer block with product, price, and options. It MAY be the hero itself. A buy control after the persuading sections, or a sticky price bar that follows the sticky bottom bar rule in [layout and composition](layout-and-composition.md), "Overflow and stacking guards" (`acc-13`). | The range as priced tiles or a scroller; the product in close-up use; how it is made; shipping and guarantee as plain statements; reviews only if supplied. | The offer again, the latest arrivals, or the guarantee. An email input belongs in the footer, not as the ending. |
| **Try** (app, game, desktop tool) | Download or store buttons directly under the heading, one per named platform. | Key art, a trailer, or the main screen captured from the working product; features as named moments inside real screens (a pinned scroll sequence or a tab switcher), not icon tiles; before and after where it applies; supported platforms. | Download buttons again beside a last screen. For a game, five or six blocks are a full page. |
| **Sign up** (software, API, developer tool) | A start-free button in nav and hero, terms in one line beneath. A developer tool MAY make its install command the main action. | The product in operation, captured or rebuilt; capabilities, each with a name and a moment; sample code or an integration; pricing with a monthly and annual toggle; FAQ. See section 9. | A slim band that repeats the hero's action, or the code example. Never a newsletter. |
| **Hire** (studio, freelancer, architect) | A plain contact route in the nav and again after the work: email, phone, or a link that invites a conversation. A form is optional. | The work carries the page: a project list (name, client, year, place) with images, one opened into a case study; a short services list; location. | Contact details, one set per office when there are several. |
| **Join** (club, community, membership) | Join, or book a first visit, at the top. | An ordinary session, shown rather than described; times and places as a schedule or venue list; membership tiers as priced rows; a guide for first-timers; people shown only in the user's own photos. | The first-visit invitation, the tiers, or a sign-up input. |
| **Listen** (band, film, podcast, publication) | The latest release or issue, with listen, watch, and order buttons in one row. | The work itself (cover, track list, contents); tour or screening dates as rows linking to tickets; earlier releases as covers in a scroller or grid; videos. | Upcoming dates, more releases, or a mailing list. An artist's page MAY run to three sections. With no release to show, lead with the act, treat the job as hiring them, and close on an inquiry. |

## 3. Endings

Real pages end in one of these, from most to least common:

1. The hero's action restated in a slim band. It keeps the hero's label and target, so it counts once (`lay-06.a`).
2. Practical information: hours, location, contacts.
3. More of the catalog: the archive, new stock, more projects.
4. A short trust coda: a guarantee, or press and awards the user supplied.
5. A mailing list. It suits recurring things only.

A mailing list is the least common of these endings, so it is never the default. Close on the thing the visitor came for, in its natural form: open slots, the purchase box, store buttons, the next date and place, the newest issue. Letting the last strong section run into the footer is also a valid close. A page whose hero or sticky bar already holds the action need not repeat it at the foot.

A final email sign-up section is flagged (`pag-00.3`) unless one of these holds:

- The job runs on lists: subscribe, join, attend, listen, or visit, and its anatomy wants one.
- The user asked for it.
- The form does real work: it books, sends an inquiry, places an order, or starts the product.

## 4. Sample content for missing sections

When the category expects a section and nothing was supplied for it, build it as a sample that is plainly swappable. Examples: a specimen issue, dishes typical of the cuisine, products labeled as samples, track titles marked as samples. Each sample section says it is a sample in a `figcaption` under its content, so it is not placeholder text under `cpy-01`. [Copy and honesty](copy-and-honesty.md), section 7, lists that caption among the lines `cpy-04` allows. The notice never sits as a line above or beside the section heading, where it would read as an announcer label (`cpy-04`). A picture position inside it carries no such label; it follows the stand-in rules in [imagery and data](imagery-and-data.md), section 8. List every sample in the handoff material request ([build record](build-record.md)).

A sample shows shape. It asserts nothing that reads as true. Prices, dates, people's names, counts, and reviews MUST NOT appear in a sample section (`cpy-02`). A product rebuilt inside a picture position is different: its sample data MAY show round amounts, as [imagery and data](imagery-and-data.md) and [copy and honesty](copy-and-honesty.md), section 15, allow. Some sections hold nothing but unsupplied facts, such as a line-up or a tour. Cut such a section to one line and a marked blank ([copy and honesty](copy-and-honesty.md), section 13), or leave it out until the facts arrive.

## 5. Order and earned sections

- Order follows the argument of the page shape, never the stock run of hero, three features, an action band, then footer.
- The strongest real asset goes directly after the hero. Every fact sits where it is useful.
- A steps section appears only for a process visitors go through: reserving, joining, buying a ticket.
- A figures row appears only when the brief states at least three numbers outright. A number inferred from wording, such as 365 from "every day", does not count.
- Generated pages carry a steps section and a figures row by reflex. On this skill's pages each one is a decision, recorded in the section list.

## 6. The first screen

- **One visible action.** The opening screen shows exactly one primary action (`lay-04.b`, `lay-06.a`). In a list shape it is the first item's link. In a prose shape it is the first inline link. Elsewhere it is the hero button. Where the shape asks for it, the same action appears once more at the end, with the same label and target, and counts once (`lay-06.a`).
- **The signature.** Decide what a visitor will remember. It is the brief's strongest real asset at full strength. Examples: the photo that defines the place, the product doing its central task, a control the visitor can try. When the price is what is sold, the signature is the price set at display size. Render the signature in the theme's materials and place it in the opening viewport. Log it in the decision summary and in the build record's `signature:` field. A quantity drawn as rows of marks is a gimmick, not a signature.

## 7. Pacing and variety

- After each dense section (grid, table, bento, index) place a quiet one (statement, showcase). End on a real close (section 3).
- Adjacent sections MUST NOT share a composition (`lay-00.compositions`, [layout and composition](layout-and-composition.md)).
- A split MAY be mirrored once. It MUST NOT zigzag down the page (`pag-00.7`).
- A product page carries at least one full-width visual.
- A page carries one or two bands, no more. The count includes the short bands of [layout and composition](layout-and-composition.md), "Balance and height".
- Read the build log first. If the previous build used the most worn beats (statement, steps, figures, closing band), handle each one differently this time.

## 8. Section count and height

- A page keeps the section count in [layout and composition](layout-and-composition.md), "Density budget". That section also says what the count includes and when a page MAY run shorter.
- Height is what the content produces (`note`): 5,000 to 8,000px for a rich brief with imagery, and 3,000 to 4,000px for a thin one.
- Never pad a section or add one to reach a height or a count.

## 9. The SaaS card deck

Applies to SaaS pages built on the modular-grid, figure-hero, capture-tour, or statement-hero shapes ([page shapes](page-shapes.md)). Other shapes do not use it. Cards are defined by role, not by position. The shape decides how each card looks.

### Base cards

A base card asks for no material beyond the brief's own facts. Each still needs those facts: the changelog needs real dates, pricing needs real prices, and the spec sheet needs real limits. A base card whose facts are missing follows the sample-content rule (section 4). It becomes one line and a marked blank, or it is dropped.

| Card | Content |
|------|---------|
| Spec sheet | Shipped limits, formats, versions, regions, as a table or rows. |
| Worked example | The product doing one real task: a command and its output, or a capture with a caption. |
| Changelog | The newest 3 or 4 entries, each with its real date. |
| Comparison | The current way of doing the job against the product, row by row, with no scores. |
| Pricing | Real prices, two or three tiers. A contact-sales button on every tier tells buyers they are not trusted. |
| FAQ | Real objections, answered plainly. |
| Action strip | One button. |
| Footer | Always present. |

### Material cards

Used only when the user supplied the material behind them.

| Card | Without the material |
|------|----------------------|
| Hero visual | The product rebuilt in a replaceable picture position, or a type-only hero. Never a fake interface built from styled boxes. |
| Logo row | Left out, with no "trusted by" line. Only the user's own customers' marks, used with permission. |
| Three features | Each needs a capture or a figure. Otherwise fold them into the spec sheet or the worked example. |
| Testimonials | Left out. When present, quoted word for word with the person's name, title, and organization exactly as supplied. |

### Two required deviations

Every deck selection MUST deviate from the base order in two ways (`pag-00.9`):

1. **Drop.** Remove one or more base cards and name them. By default, drop the action strip. The footer always stays.
2. **Promote or swap.** Either promote a base card into the hero slot, or swap one pair of neighboring cards.
   - A promotion makes the spec sheet or the worked example the hero object.
   - A swap MUST change the argument, such as pricing before the example.

Record both in short form in the decision summary and at the end of the log's `sections:` field ([build record](build-record.md), section 5), for example `drop: action strip / promote: worked example`. `pag-00.9` grades from the built section order against the base order. A deck with fewer than 5 cards is too thin: restore cards or change the shape. Cards use the mixed section gaps from [layout and composition](layout-and-composition.md), and each card fills its whole section.
