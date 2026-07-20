# Signs of AI Writing — Full Catalog

Adapted for marketing copy from Wikipedia's *Signs of AI writing* field guide. These are patterns
readers (and editors, and customers) have learned to recognize as machine-generated. Any single
occurrence is fine; density is what kills credibility. Scan every draft against this catalog before
delivering.

**Key insight from the research:** AI-vocabulary words don't appear alone — where one appears,
others follow predictably. One "vibrant" is a word choice; "vibrant" + "boasts" + "seamless" +
"elevate" in the same section is a fingerprint. Heavy LLM users spot this instantly (~90% accuracy).

---

## 1. Vocabulary Tells

### Overused AI words (avoid, or use at most once per page)

**Verbs:** delve, boast, underscore, showcase, foster, garner, bolster, elevate, empower,
streamline, leverage, harness, unlock, unleash, navigate, embark, revolutionize, transform,
supercharge, enhance, ensure, facilitate, optimize, utilize

**Adjectives:** vibrant, crucial, pivotal, key, seamless, robust, cutting-edge, groundbreaking,
game-changing, innovative, meticulous, intricate, enduring, renowned, comprehensive, holistic,
dynamic, unparalleled, effortless

**Nouns:** landscape, tapestry, testament, journey, realm, synergy, ecosystem (metaphorical),
interplay, intricacies, insights ("valuable insights"), solutions (generic)

**Connectives:** additionally, moreover, furthermore, notably, importantly, "in today's
fast-paced world," "in the ever-evolving landscape of," "at its core," "when it comes to"

### Substitution guide

| AI tell | Write instead |
| --- | --- |
| delve into | look at, dig into, cover |
| leverage / harness / utilize | use |
| seamless | say what actually happens ("no re-login," "one click") |
| robust | say the number ("handles 10k req/s") |
| empower / enable | let, help |
| streamline / optimize | name the saved step or time |
| unlock / unleash | get, start |
| elevate / enhance | improve — or name the improvement |
| journey | setup, first week, onboarding — the concrete thing |
| ecosystem / landscape | market, tools, product — the concrete thing |

---

## 2. Sentence-Pattern Tells

### Negative parallelisms

The single most recognizable AI construction family. All variants:

- "It's not just X, it's Y" / "Not just X — Y"
- "Not only... but also..."
- "It's not about X; it's about Y"
- "No X, no Y, just Z"
- "X rather than Y" (as a recurring pattern)

**Fix:** State Y directly. "It's not just a dashboard, it's a command center" → "See every
deployment, alert, and rollback in one screen."

### Rule of three

Triplets everywhere: "faster, simpler, smarter" • "plan, build, and ship" • three adjectives, three
benefits, three bullet groups, three of everything. One deliberate triad per page is rhetoric; a
triad in every section is a template.

**Fix:** Vary list lengths. Two strong items beat three padded ones.

### Superficial "-ing" analysis clauses

Present-participle tails that bolt hollow significance onto a sentence:

- "...**ensuring** your team stays aligned"
- "...**highlighting** our commitment to quality"
- "...**empowering** users to do more"
- "...**reflecting** our dedication to innovation"
- also: fostering, showcasing, underscoring, emphasizing, contributing to, cultivating

**Fix:** Cut the clause, or promote it to its own sentence with a concrete claim.

### Avoidance of "is" and "has"

AI swaps plain copulas for inflated verbs:

- "serves as / stands as / represents / marks / operates as" → **is**
- "boasts / features / offers / maintains" → **has**

"The platform serves as a comprehensive solution for..." → "The platform is..."
(or better: just say what it does).

### Significance inflation

Generic claims of importance replacing specific facts: "plays a vital/pivotal/crucial role,"
"is a testament to," "marks a key turning point," "leaves an indelible mark," "sets the stage for,"
"reflects broader trends," "cementing its position as." Marketing equivalent: "trusted by
industry leaders" with no names, "award-winning" with no award.

**Fix:** Replace every importance claim with the fact that would prove it.

### Vague attribution

"Experts agree," "industry reports show," "studies suggest," "many teams find" — weasel
authority with no source. In copy this reads as fabrication and creates legal risk.

**Fix:** Name the source, the number, and the date — or delete the claim.

### Formulaic conclusions

"Despite these challenges, X continues to..." • section-ending summaries that restate the
section • "In conclusion" • "The future looks bright." Endings should land on a CTA or a
concrete next step, not a recap.

### Didactic disclaimers

"It's important to note that..." • "It's worth mentioning..." • "Keep in mind that..." •
"Remember," — lecture framing, not copy.

### Elegant variation (synonym cycling)

Calling the product "the platform," then "the solution," then "the tool," then "the system" to
avoid repeating its name. Humans repeat the product's name; that's branding. Repeat it.

---

## 3. Tone Tells

- **Press-release voice:** "We are thrilled/excited/proud to announce..." — nobody reads a
  landing page to learn how the company feels.
- **Travel-brochure adjectives:** nestled, vibrant, rich, "in the heart of," "natural beauty,"
  "a diverse array of."
- **Uniform enthusiasm:** every feature described with the same energy. Real copy has a
  hierarchy — one hero claim, supporting facts stated plainly.
- **Relentless positivity with zero specifics:** if every sentence could describe a competitor
  equally well, it's filler.

---

## 4. Formatting Tells

- **Em-dash overuse** — like this — several times per paragraph — becomes a tic. Max ~1 per
  paragraph; prefer commas, periods, or parentheses.
- **Boldface overuse:** bolding **key phrases** in **every sentence** as mechanical emphasis.
  Bold at most one decisive phrase per section.
- **Inline-header bullet lists:** every bullet shaped "**Label:** explanation sentence." One list
  like this is structure; every list like this is a template.
- **Rule-of-three bullet groups:** exactly three bullets under every heading.
- **Title Case in Every Heading And Subheading:** pick sentence case or title case per brand
  style, but AI defaults to rigid Title Case everywhere.
- **Emoji as section markers:** 🚀 ✨ 💡 prefixing headings or bullets.
- **Thematic breaks (`---`) before every heading** and heading levels that skip (## → ####).
- **Curly quotes/apostrophes mixed with straight ones** — sign of unedited paste; normalize to
  one style.
- **Tables used for prose** that should be sentences.

---

## 5. Structure Tells

- Every section has the same shape: heading → one intro sentence → three bullets → wrap-up line.
- Section-ending summary sentences that restate what was just said.
- An explicit "Conclusion" section on a landing page.
- Uniform paragraph lengths throughout. Humans write long-short-long; vary rhythm.
- Headline, subheadline, and first section that all say the same thing three ways.

---

## 6. Leftover-Artifact Tells (instant credibility killers)

Always search the final text for these before delivering:

- Placeholder text: `[Company Name]`, `[insert benefit]`, `{product}`, "Lorem"
- LLM citation debris: `oaicite`, `contentReference`, `turn0search0`, `attribution`, `:::`
- Markdown syntax leaking into rendered HTML (`**bold**`, `##`)
- `utm_source=` / `utm_campaign=` parameters in copied links
- Knowledge-cutoff or self-referential language: "As of my last update," "I cannot browse,"
  "As an AI"
- Prompt-refusal fragments or an answer that begins "Certainly! Here's..."

---

## 7. What NOT to over-correct (weak indicators)

These are *not* reliable AI tells on their own — don't contort copy to avoid them:

- Lists and bullets per se (humans use them; the tell is uniform, templated lists)
- Positive language per se (it's marketing; the tell is unspecific positivity)
- Any single word from the vocabulary list used once, deliberately
- Long copy (long ≠ generated; padded ≠ long)
- Occasional em dashes, an occasional triad — the tell is density and regularity

The goal is not to pass a detector. It's copy so specific to this product, this customer, and
this voice that it *couldn't* have been generated from a generic prompt.

---

## Final sweep checklist

1. Count AI-vocabulary words (§1) — more than ~2 per page section = rewrite.
2. Grep for "not just", "not only", "isn't just", "rather than" — rewrite each hit.
3. Count triads — keep at most one deliberate one per page.
4. Find every "-ing" tail clause — cut or make concrete.
5. Replace "serves as / boasts / features" with "is / has" (or a concrete verb).
6. Every importance claim → replaced by the fact that proves it, or deleted.
7. Every vague attribution → named source or deleted.
8. Em dashes ≤ 1 per paragraph; bold ≤ 1 phrase per section; no emoji bullets.
9. Vary bullet counts, paragraph lengths, and sentence openings.
10. Search for artifacts (§6): brackets, `oaicite`, `utm_`, markdown leaks, "As an AI".
11. Read aloud. Anything you'd never say to a customer face-to-face gets rewritten.
