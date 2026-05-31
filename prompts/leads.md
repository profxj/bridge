# Leading

## Goals

We will develop a database and code for Bots to make leads.

## Coding

See CLAUDE.md for coding guidelines.

## Architecture

We will save a file or set of files in bridge/data/leads that contains standard leads, e.g. K from KQJ.

## Skills

## Tests

## Examples

## Planning

### Core idea: a declarative *leads database*, mirroring the SAYC bidder

The bidding side encodes SAYC as declarative YAML rules (`hand` + `when` →
`call`) loaded/validated/matched by `bridge/bidding_systems/sayc_loader.py`.
Leads should follow the **same proven pattern**: YAML rules under
`bridge/data/leads/` that map a *card holding* (in the suit being led) +
*contract type* → the **card to lead**, plus the *message* that lead sends to
partner. A small loader/validator/matcher module returns the card and its
reasoning.

**v1 scope = which CARD to lead from a given suit** — exactly the architecture
example, "K from KQJ". Choosing *which suit* to lead (auction-driven defensive
strategy) is a larger, separate layer; deferred (see Q1).

### Two spot-card styles: SAYC 4th-best + 3rd/5th-best (per Q3)

The honor-lead rules (top of a sequence, A from A K x, top of an interior
sequence, doubleton) are **system-independent** — every standard partnership
leads them the same way. The styles differ only in **which spot card you lead
from length**:

- **SAYC / 4th-best** (the base): lead the 4th-highest from a 4+ card suit.
  Partner applies the **Rule of 11**.
- **3rd/5th-best** (the added variant): lead the **3rd-highest from an
  even-length** suit and the **5th-highest (= lowest) from an odd-length**
  suit, so the spot encodes length parity. Partner applies the **Rule of 10/12**.

So a holding like `K J 7 3` leads the `3` under SAYC but the `7` (3rd) under
3rd/5th; `K J 8 6 3` leads the `6` under SAYC but the `3` (5th/lowest) under
3rd/5th. This is the *only* family of rules that branches on system.

Per Q8/Q9: **SAYC / 4th-best is the default**; 3rd/5th is **opt-in** (a
`system="three_five"` argument) and applies **only vs suit (trump)
contracts** — vs notrump, even when 3rd/5th is selected, the lead stays
4th-best. So 4th-best is the shared/`any` spot rule and the 3rd/5th rule is a
suit-context override (`system: three_five`, `context: [suit]`, higher
priority) that fires only when that system is requested.

### Learning the leads from the web (the sourcing process)

- **Primary, authoritative, project-aligned source: the ACBL SAYC System
  Booklet, "Defensive Leads and Signals."** Since the bidder already uses this
  booklet, the leads stay consistent with the system. It specifies (verbatim):
  fourth best from 4+; from three low cards lead **low vs a suit / high vs
  notrump**; from 4+ cards **without an honor** lead the **second highest**;
  **top of touching honors** and **top of an interior sequence**; and **the
  ace from A K x vs suits**. Signals are attitude (high = encourage) and
  count (high-low = even).
- **SAYC is sparse** on specific honor combinations (broken sequences like
  KQ10, interior sequences under the ace like AQJ, honor doubletons, two-card
  sequences in long suits, NT-specific honor leads). These will be
  **supplemented from standard, widely-agreed lead tables**, each rule
  **cross-checked against ≥2 independent sources** and **cited**; any
  disagreement among sources is flagged for a decision rather than guessed.
- Every rule carries a `tag`: `sayc` (explicit in the booklet) vs `standard`
  (supplemented & cross-checked). Sourcing is data entry + verification, not
  free invention.

### Data schema (one rule; same shape as a SAYC rule)

```yaml
- id: lead_top_of_sequence
  context: [suit, nt]          # contract types this rule applies to
  system: any                  # any | sayc | three_five  (honor rules are shared)
  holding:                     # predicate over the chosen suit's ranks
    sequence_from_top: 3       # 3+ touching cards headed by the top card
  lead: top                    # card-selection role (see vocabulary below)
  shows: "Top of a 3+ card honor sequence: promises the next touching
          card(s), denies a higher honor."
  signal: attitude             # what partner reads (attitude/count/none)
  priority: 90                 # higher wins when several rules match
  example: "KQJ6 -> K"         # a golden case the tests pin
  source: "ACBL SAYC booklet — Defensive Leads and Signals."
  tag: sayc
```

- **Holding predicates** (over one suit's sorted ranks): `length: [min,max]`,
  `sequence_from_top: n`, `interior_sequence: n` (touching honors not headed
  by the top card, e.g. KJ10), `broken_sequence` (e.g. KQ10), `contains:
  [A,K]` (for A K x), `has_honor`/`no_honor`, `three_small`, `doubleton`,
  `singleton`.
- **Card-selection roles** (`lead`): `top`, `lowest`, `second_highest`,
  `fourth_highest`, `third_highest`, `fifth_highest`, `third_or_fifth`
  (parity-aware: 3rd from even length, 5th/lowest from odd),
  `top_of_interior_sequence`, `ace`, `card: <rank>`. Encoding a *role* (not a
  literal rank) lets one rule cover infinitely many holdings — the matcher
  applies the role to the actual cards.

### Module layout (proposed — mirror `sayc_loader`)

```
bridge/data/leads/
  meta.yaml                 # system name, signal method, sources
  card_from_holding.yaml    # the lead-card rules (suit + NT contexts)
bridge/play/leads_loader.py # holding-feature helpers, load/validate, choose_lead
tests/play/test_leads_loader.py
tests/play/test_leads.py    # golden card-combination examples
```

Pure, deterministic functions over simple data (no I/O beyond loading the
YAML), exactly like the bidder. (Module home is Q5.)

### Increments (each independently testable; suite stays green)

1. **Holding-feature helpers + loader/validator** — parse a one-suit holding
   string into features (length, sequences, interior sequence, honors,
   doubleton/three-small), and load+validate the YAML rules. Tests for the
   feature parser.
2. **Encode the SAYC-explicit rules** in `card_from_holding.yaml` and add
   `choose_lead(rules, holding, context, system="sayc")` (priority match →
   role → concrete card + reason), mirroring `match_rules`/`choose_call`.
   Golden tests: KQJ→K, QJ10→Q, KJ10→J (interior), A K x→A (suit), three
   small→low (suit)/high (NT), 4+ no honor→2nd highest, H x x x→4th best,
   doubleton→top.
3. **Add the 3rd/5th-best variant** (per Q3/Q8): a `system: three_five`,
   `context: [suit]` override for the spot-from-length case using
   `third_or_fifth`. Golden tests: vs a suit, `K J 7 3`→3 (sayc) vs 7
   (three_five) and `K J 8 6 3`→6 (sayc) vs 3 (three_five); vs **NT**,
   `system="three_five"` still gives the 4th-best card (override is
   suit-only). Shared honor rules (`system: any`) are unaffected.
4. **Supplement** the honor combinations SAYC omits (broken/interior
   sequences, NT honor leads, honor doubletons), each cited + cross-checked +
   tagged `standard`.
5. **(Later) suit-selection layer** — the auction-driven choice of *which*
   suit to lead.

### Synergy with the inference engine

Each lead's `shows`/`signal` is exactly the raw material for **play-based
inferences**: an opening lead is the first card-play clue, and the inference
KB already reserves a `play=True` channel. So the leads DB does double duty —
it lets a bot *make* leads and later lets a bot *read* partner's/opponents'
leads. Worth keeping the `shows` field from day one.

### Sources (checked while drafting this plan)

- ACBL SAYC System Booklet (primary): https://web2.acbl.org/documentLibrary/play/sayc_book.pdf
- Opening lead — Wikipedia: https://en.wikipedia.org/wiki/Opening_lead
- Standard leads — Bridge Bum: https://www.bridgebum.com/standard_leads.php
- Opening Leads table (Cornell / J. Belk): https://pi.math.cornell.edu/~belk/Leads.htm
- Rusinow leads (a variant) — Wikipedia: https://en.wikipedia.org/wiki/Rusinow_leads
- 3rd/5th-best & the Rule of 10/12 (to verify in dev): https://en.wikipedia.org/wiki/Rule_of_eleven

### Clarifying questions

Defaults below are what I'll assume if there's no objection.

1. **Scope** — start with which **card** to lead from a given suit (the "K
   from KQJ" table), deferring which **suit** to lead (auction-driven
   strategy)? *Default: yes, card-from-holding first.*

yes, start with the card to lead from a given suit.

2. **Lead system** — encode the **ACBL SAYC booklet** leads as the base
   (4th best; A from A K x vs suits; low/high from three small; 2nd-highest
   from 4+ without an honor; top of touching/interior sequences), to stay
   consistent with the bidder? *Default: yes, SAYC.*

yes, encode the ACBL SAYC booklet leads as the base.

3. **Variants** — support common alternatives now (King-from-AK, MUD,
   3rd/5th best, Rusinow/Journalist) or leave room to add them later via a
   `system`/`tag` field? *Default: SAYC only in v1; schema leaves room.*

Only add 3rd/5th best for now.

4. **Representation** — declarative *pattern rules* (honor-structure
   predicates + a card-selection role + priority), mirroring `sayc_loader` —
   vs a flat shorthand table (`Hxxx`, `KQJx`, …)? *Default: pattern rules.*

Use pattern rules.

5. **Module home** — `bridge/play/leads_loader.py` (leads are card-play /
   defense) vs a new top-level `bridge/leads/`? *Default: `bridge/play/`.*

Use bridge/play/leads_loader.py.

6. **Carry the lead's message** — include `shows`/`signal` on each rule so it
   can feed the inference engine's play-based inferences later? *Default: yes.*

yes

7. **Sourcing rigor** — cross-check each supplemented (non-SAYC) rule against
   ≥2 independent web sources, cite it, and flag source disagreements rather
   than guess? *Default: yes.*

yes

---

New questions raised by adding 3rd/5th-best leads (Q3):

8. **Where does 3rd/5th apply?** As a full-time agreement (both suit *and* NT
   contracts), or only vs notrump (with 4th-best kept vs suits)? *Default:
   full-time — it's a selectable `system`, so the bot uses whichever you ask
   for in both contexts.*

Only apply 3rd/5th best to trump contracts, and only when that option is selected.

9. **Default style** — keep **SAYC / 4th-best** as `choose_lead`'s default and
   make 3rd/5th opt-in via `system="three_five"` (since Q2 set SAYC as the
   base)? *Default: yes, SAYC is the default; 3rd/5th is opt-in.*

yes, SAYC is the default; 3rd/5th is opt-in.

## Development

1. Generate the code according to the plan.  Generate a Python Notebook in nb/ named leads.ipynb.  Use it to show how well the leads work. 

## Docs

1. Generate a markdown file describing our standard leads

## Prompts

1. Read this file.  Generate a plan to develop the process for learning how to make leads from resources you can find on the web. If you have any questions, put them under the Clarifying questions section.
2. Read this file.  See my answers to the clarifying questions.  Make any necessary adjustments to the plan and ask any additional questions as needed.
3. Read this file.  See my answers to the new clarifying questions.  Make any necessary adjustments to the plan.  Then proceed with the 1st item in the Development section.