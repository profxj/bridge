# SAYC Bidding

## Goals

We will develop a SAYC bidding system that will be used to bid the game.

## Coding

See CLAUDE.md for coding guidelines.

## System Architecture

We will scrape the SAYC bidding system from the internet and save it as a set of files in bridge/data/bidding/sayc.  You may use whatever machine learning format you prefer.

Keep a running list of all the conventions you know in an .rst file in docs/conventions.rst.

## Skills

## Tests

## Examples

Generate a series of examples that demonstrate the capability of the Robot to bid.

## Planning

### What the deliverable is

A **data-driven SAYC knowledge base** under `bridge/data/bidding/sayc/`,
plus a thin **loader/validator** under `bridge/bidding_systems/`. The data
files encode SAYC as declarative *rules*; a later stage (Roadmap stage 6)
builds the engine that matches a rule against the live auction + hand and
returns a call. Per CLAUDE.md, all logic is module-level **functions over
plain data** — the rules are data, the matcher is functions.

### Sources surveyed (web)

- ACBL **SAYC System Booklet** (rev. Jan 2006) — the canonical spec
  (`web2.acbl.org/.../SP3 (bk) single pages.pdf`) and the one-page
  convention card (`.../sayc_card.pdf`).
- Korpela SAYC summary (`jkorpela.fi/sayc.html`) — compact full structure.
- BridgeBum SAYC pages (`bridgebum.com/sayc.php`) — per-opening detail.
- Gatech "SAYC Expanded System Summary" (Casinovi) — thorough edge cases.

These agree on the core; the ACBL booklet is the tie-breaker / ground truth.

### SAYC content to encode (scope map)

- **Evaluation:** HCP (A=4 K=3 Q=2 J=1) + length/short-suit adjustments;
  "balanced" shapes (4333/4432/5332).
- **Openings:** 1NT 15–17 bal; 2NT 20–21; 3NT 25–27; 1♥/1♠ = 5+ & ~13–21;
  1♣ 3+ / 1♦ 3+ (minor tie-break rules); 2♣ strong artificial (22+ or
  ~9 tricks); 2♦/♥/♠ weak (6-card, 5–11); 3-level & 4-level preempts
  (Rule of 2/3/4).
- **Responses & rebids:** to majors (limit raises, new-suit forcing, jump
  shifts), to minors, to 1NT (Stayman, Jacoby transfers), to 2♣ (2♦
  waiting), to weak twos (RONF / 2NT ask), opener's rebids, responder's
  rebids.
- **Slam tools:** Blackwood 4NT, Gerber 4♣, Grand Slam Force 5NT.
- **Competitive:** overcalls (1-level, 1NT 15–18), takeout doubles,
  negative doubles, Michaels cue-bid, Unusual 2NT, penalty doubles.

### Decisions locked (from answers above)

- **Format: YAML** + `PyYAML` dependency. `requirements.txt` (runtime) and
  `pyproject.toml` (installable, `[dev]` extra for pytest/ruff/mypy) — **done**.
- **Environment: conda env `astro14` (Python 3.14.5).** Packaging now targets
  `>=3.14` (ruff `py314`, mypy `3.14`). Run tooling via
  `conda run -n astro14 …`.
- **v1 = constructive/uncontested SAYC only.** Competitive bidding goes in a
  **single separate file** (`competitive.yaml`), built as a follow-up.
- **No automated scraper** — rules are hand-curated from the canonical
  sources, each citing its `source`.
- **Non-forcing 1NT** response to a major (plain SAYC).
- Engine returns **ranked candidates internally, a single call externally.**
- **All four seats modeled from the start.** Every rule carries optional
  `seat` (1/2/3/4) and `vulnerability` (none/we/they/both) predicates;
  3rd/4th-seat light openings (Rule of 15/20) and vul-sensitive preempt
  discipline (Rule of 2/3/4) are encoded as first-class rules, not deferred.
- **A thin generic rule-matcher ships now** in `sayc_loader.py` (returns
  ranked candidates) so tests can assert hand → call. The full bidding
  engine remains Roadmap stage 6.
- **`docs/conventions.rst`** holds a running list of known conventions,
  updated as each is encoded — **stub created**.

### Proposed file layout (`bridge/data/bidding/sayc/`)

```
meta.yaml                 # system name/version, eval method, shape defs, sources
openings.yaml             # opening-bid rules
responses/
  to_1nt.yaml             # Stayman, transfers, raises, signoffs
  to_major.yaml           # raises, 1NT response, new suits, jump shifts
  to_minor.yaml
  to_2c.yaml
  to_weak_two.yaml
rebids/
  opener.yaml
  responder.yaml
conventions/
  blackwood.yaml  gerber.yaml  grand_slam_force.yaml
competitive.yaml          # DEFERRED: overcalls, takeout/negative X, Michaels,
                          # Unusual 2NT, preempt defense — single follow-up file
```

### Rule schema (each entry is one declarative rule)

```yaml
- id: open_1nt
  call: "1NT"                  # the recommended call (or Pass/X/XX)
  when:                        # auction-context predicate
    auction: []                # prior calls this rule applies after (here: opening)
    by: opener                 # role, for clarity
    seat: [1, 2, 3, 4]         # seats this rule applies in (omit = any)
    vulnerability: any         # none/we/they/both/any (omit = any)
  hand:                        # hand predicate over plain features
    hcp: [15, 17]
    balanced: true
  priority: 100                # higher wins when several rules match
  alertable: false
  why: "15-17 balanced; the SAYC strong notrump."
  source: "ACBL booklet p.X"

# Seat-sensitive example: 3rd-seat light opening (Rule of 15 — HCP + spades).
- id: open_1s_3rd_seat_light
  call: "1S"
  when: { auction: [], by: opener, seat: [3] }
  hand: { hcp: [10, 12], spades: [5, 13], rule_of_15: true }
  priority: 90
  why: "Light 3rd-seat opening with spades; Rule of 15 (HCP + spade length >= 15)."
  source: "SAYC common practice; ACBL booklet (3rd/4th seat)."
```

The engine (stage 6) computes hand features (hcp, suit lengths, shape,
fit with partner) and the current auction, filters rules whose `when`/`hand`
predicates match, and picks the highest `priority`. Keeping the matcher
generic means new conventions are added as **data, not code**.

### Build steps (this milestone)

1. ~~Resolve clarifying questions; lock format + v1 scope.~~ **Done.**
2. Write `meta.yaml` + the rule **schema doc**, plus
   `bridge/bidding_systems/sayc_loader.py` containing **(a)** a schema
   validator and **(b)** the thin generic rule-matcher (ranked candidates →
   single best call), with hand-feature helpers (hcp, suit lengths, shape,
   `rule_of_15`/`rule_of_20`) honoring `seat`/`vulnerability` predicates.
3. Encode **openings.yaml** first (smallest, highest-value), including
   3rd/4th-seat light openings, with tests that load it, validate the schema,
   and assert canonical hands map to the right opening (e.g. 16 bal → 1NT;
   5-3-3-2 with 5♠ & 14 → 1♠; seat-3 light → 1♠ via Rule of 15).
4. Encode responses → rebids → slam tools, each with a small golden-hand
   test set, keeping the suite green per file. Update `docs/conventions.rst`
   as each convention moves from `planned` → `encoded`.
5. Generate the **Examples** (see that section) as end-to-end auctions once
   enough rules exist. Competitive `competitive.yaml` is the follow-up.

### Notes / non-goals for v1

- The *engine* itself is stage 6; this milestone delivers the **data +
  loader/validator + tests**, not a full bidding bot.
- 2/1 Game Force is explicitly later (per CLAUDE.md).

### Clarifying questions

1. **Data format:** I recommend **YAML** (human-readable, supports comments
   and `why`/`source` annotations) — it adds a `PyYAML` dependency. JSON
   (stdlib, no comments) or TOML are alternatives. OK to add PyYAML?

Yes, use YAML and add PyYAML to the dependencies.  Generate a requirements.txt file with the dependencies and a pyproject.toml file for installing.

2. **v1 scope:** Encode **constructive/uncontested SAYC first** (openings,
   responses, rebids, 1NT conventions, slam tools) and defer competitive
   bidding (overcalls, doubles, Michaels, Unusual NT) to a follow-up — or do
   you want competitive bidding in the first pass too?

Encode constructive/uncontested SAYC first.  Encode competitive bidding in a separate file.

3. **"Scrape" interpretation:** The architecture says *scrape from the
   internet*. A literal HTML scraper is brittle and still needs heavy manual
   curation to become structured rules. I propose **hand-curating the rules
   from the canonical ACBL booklet** (citing sources in each rule) rather
   than building an automated scraper. Acceptable, or do you specifically
   want an automated scraping script?

Nevermind.

4. **Forcing-NT treatment:** Plain SAYC uses a **non-forcing 1NT** response
   to a major (6–9, may be passed). Confirm we follow standard SAYC
   (non-forcing 1NT), not the 2/1 forcing-NT variant.

Correct, non-forcing 1NT.

5. **Engine output:** For each decision, should the data/engine return a
   **single recommended call**, or a **ranked list of candidate calls** with
   explanations (more useful for debugging/teaching)? I lean
   ranked-internally, single-call externally.

Correct, ranked-internally, single-call externally.

### Additional questions (round 2)

6. **Python version mismatch:** CLAUDE.md targets **Python 3.14**, but only
   **3.13.13** is installed on this machine. I set `requires-python = ">=3.13"`
   and `target-version = py313` so the project installs *today*. Do you want
   me to (a) keep 3.13 for now, or (b) install/build Python 3.14 and target it?

Use the "astro14" environment.  It has Python 3.14.

7. **Seat & vulnerability:** Several SAYC choices depend on seat and
   vulnerability — 3rd/4th-seat light openings (Rule of 15/20), preempt
   discipline (vul vs. non-vul), light competitive actions. For the v1
   *constructive* pass I propose modeling these as **optional rule predicates**
   (`seat`, `vulnerability`) but **encoding 1st/2nd-seat, not-vulnerable
   rules first** and adding seat/vul refinements later. OK, or should seat/vul
   be fully modeled from the start?

Encode all seats from the start

8. **Minimal matcher now?** To make the openings tests meaningful (assert
   "16 bal → 1NT"), I'd include a small **generic rule-matcher** in
   `sayc_loader.py` alongside the validator (returns ranked candidates). The
   full engine remains Roadmap stage 6. OK to include this thin matcher now?

Yes, include this thin matcher now.

### Additional questions (round 3)

9. **Opening discipline / light openers:** Now that all seats are modeled, how
   strict should 1st/2nd-seat openings be? Options: (a) **strict 13+ HCP**
   (book SAYC), or (b) allow **Rule of 20** light openers (HCP + two longest
   suits ≥ 20) for shapely 11-12 counts. For 3rd/4th seat I'll use **Rule of
   15** (HCP + spades) regardless. I lean (b) Rule of 20, as it's common SAYC
   practice — confirm your preference.

Rule of 20 

10. **Hand input representation (assumption — confirm):** Until the Stage-1
    core model exists, the matcher will accept a hand as a simple dict of
    suit → ranks, e.g. `{"S": "AKQ", "H": "T98", "D": "7654", "C": "32"}`,
    and derive features (HCP, lengths, shape) internally. Calls are written
    `"1NT"`, `"1S"`, `"2C"`, `"P"`, `"X"`, `"XX"` (suits as `S/H/D/C`). I'll
    proceed with this unless you prefer another representation.

That is fine

## Development

1. Generate a Python Notebook in nb/ named sayc_bidding.ipynb.  Use it to show how well the bidding system works.  Also, proceed to include Stayman/transfers over 2NT, positive 2♣ responses, inverted minor responses.  We will work on competitive bidding next.

## Prompts

1. Read this doc.  Explore the web for SAYC bidding systems.  Generate a plan to generate a set of files that will be used to bid the game.  If you have any questions, put them under the Clarifying questions section.

2. Read this doc.  See my answers to the clarifying questions.  Make any necessary adjustments to the plan and ask any additional questions as needed.

3. Read this doc.  See my answers to the additional clarifying questions.  Make any necessary adjustments to the plan and ask any additional questions as needed.

4. Read this doc.  Proceed with the plan.

5. Read this doc.  Proceed with the first item in the Development section.