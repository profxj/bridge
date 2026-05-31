# Bidding Inferences

## Goals

We will develop a process for a given Bot to make inferences about each player's hand from the bidding and keep track of the inferences in a knowledge base.  

## Coding

See CLAUDE.md for coding guidelines.

## Architecture

The Bot will have a knowledge base that will be used to store the inferences.  The knowledge base will be a dictionary of dictionaries.  The first level of the dictionary will be the player's position (East, South, West, North).  The second level of the dictionary will be the inference.  The inference will be a dictionary with the following keys:

- confidence: a float between 0 and 1
- reason: a string describing the inference
- bidding: a boolean indicating if the inference is based on the bidding
- play: a boolean indicating if the inference is based on the play
- violated: a boolean indicating if the inference is violated by the bidding or the play
- The inferences will be held in memory, but write a function to write them to a file.

## Skills

## Tests

## Examples

1. The Notebooks are not rendering on GitHub, only in my JupyterLab.  Can you check this?  

## Planning

### Core idea: invert the SAYC rules

The SAYC engine (`bridge/bidding_systems/sayc_loader.py`) is *forward*:
`match_rules(rules, hand, auction, seat, vulnerability)` takes a **known** hand
and returns the candidate calls, ranked by priority. Inference is the
**inverse** problem: given an **observed** call plus its context (auction so
far + seat + vulnerability), recover the `hand`-predicate blocks of the rules
that could have produced that call. Each rule's `hand` block
(`hcp: [min,max]`, per-suit `[min,max]`, `balanced`, `longest_suit`,
`longer_than`, `aces/kings`, ...) *is* the inference, read backwards.

This lets us reuse, not reinvent: the loader already knows how to match a
rule's `when` context to an auction/seat/vulnerability, and `compute_features`
already defines every predicate's meaning. We only add the inverse direction.

**Positive inference (v1):** if a player makes call `X` in context `C` at seat
`S` (assuming they play our SAYC), their hand satisfies the *disjunction* of
the `hand` blocks of every rule whose `when` matches `C/S` and whose `call ==
X`. When several rules qualify, take the **envelope** (loosest bounds: min of
mins, max of maxs; booleans only if all matching rules agree) so we never
wrongly exclude a hand. Confidence reflects the ambiguity (1 rule → high; many
divergent rules → lower).

**Negative inference (also v1 — per your answer to Q4):** under our SAYC, a
player who makes call `X` chose it as the *highest-priority* matching rule.
So every context-matching rule with **strictly higher priority** and a
**different call** must have *failed* on their hand — that is a denial (e.g.
"opened 1♦, not 2♣ ⇒ fewer than 22 HCP"; "opened 1♦, not 1NT ⇒ not balanced
15–17"). The opening **pass** falls straight out of this same mechanism: `P`
is the chosen call, every opening rule is a higher-priority different call,
so all are denied ⇒ "sub-opening values."

The catch: negating a rule's `hand` block (a *conjunction* of predicates)
yields a *disjunction* (`NOT(balanced AND 15–17) = unbalanced OR <15 OR >17`),
which doesn't fold cleanly into our simple intersectable constraint dict.
v1 handles this honestly in two tiers (see Q7):
- **Foldable denials** — when the denied block reduces to a single binding
  bound, we negate it into a tightened bound and merge it into the numeric
  profile. The most valuable case is point caps: denying a `2♣` rule
  (`hcp:[22,40]`) tightens the upper bound to `hcp ≤ 21`.
- **Annotation-only denials** — genuinely multi-predicate denials (e.g.
  "not balanced 15–17") are still **recorded** as KB inferences with a reason
  and lower confidence, but are *not* merged into the numeric ranges.

Ties (two different-call rules at equal priority) are *not* treated as denials
— neither is strictly higher, so a denial there would be unsound.

### Knowledge base shape

```python
# kb[position][inference_id] = inference_record   (dict of dicts, per the doc)
inference_record = {
    "constraint": { "hcp": [15, 17], "balanced": True, ... },  # structured, intersectable
    "confidence": 0.95,        # float 0–1
    "reason": "Opened 1NT: balanced 15–17 HCP.",  # human string
    "bidding": True,           # derived from the auction
    "play": False,             # derived from card play (always False in v1)
    "violated": False,         # later evidence contradicts this inference
    # provenance (extends the doc's minimum keys):
    "negated": False,          # True = denial (constraint is the *denied* hand block)
    "foldable": True,          # negated denial that tightens the numeric profile
    "call": "1NT",
    "auction_index": 0,        # which call in the sequence produced it
    "rule_ids": ["open_1nt"],
}
```

`constraint` is structured (same vocabulary as a rule `hand` block) so
inferences are machine-usable, not just prose. A derived view,
`hand_profile(kb, position)`, intersects all that player's non-violated
constraints into a single running hand picture (tightest hcp range, per-suit
length ranges, known booleans).

### Module layout (proposed)

```
bridge/inference/
  __init__.py
  knowledge_base.py   # empty_kb, add_inference, hand_profile, write/read (JSON)
  bidding.py          # invert rules → constraints; walk an auction → populate kb
tests/inference/
  test_knowledge_base.py
  test_bidding.py
```

Pure functions, no I/O except the explicit persistence helpers; depends on
`bidding_systems` for rule data. (See Q1 — could instead live under
`bridge/agents/`.)

### Increments (each independently testable, suite stays green)

1. **KB primitives** — `knowledge_base.py`: `empty_kb()` (keyed N/E/S/W,
   each an empty dict), `add_inference(kb, position, record)` (auto-generates
   the `inference_id` key), `merge_constraints(a, b)` (intersect two positive
   constraint dicts + apply foldable denials as tightened bounds, with
   contradiction detection), `hand_profile(kb, position)` (fold all
   non-violated inferences into one picture; lists the annotation-only
   denials separately), and `write_knowledge_base(kb, path)` /
   `read_knowledge_base(path)` (JSON; tuples→lists is fine — the file-writer
   the doc asks for). `seat_to_position(dealer, seat)` rotates clockwise
   N→E→S→W. Unit tests for intersection, foldable-denial tightening,
   contradiction, seat mapping, and round-trip.

2. **Positive rule inversion** — `bidding.py`: factor a context-only matcher
   out of `sayc_loader.match_rules` (`_context_matches(rule, auction, seat,
   vuln)`) and add `candidate_rules_for_call(rules, call, auction_before,
   seat, vuln)` → rules whose context matches and `call` equals the observed
   call. Then `infer_positive(rules, call, auction_before, seat, vuln)` builds
   the envelope constraint + graded confidence + reason. Tests: 1NT→
   `hcp[15,17]`+balanced; weak-2♥→6♥ & `hcp[5,11]`; Jacoby transfer →
   responder constraint; unexplained call → empty/low-confidence (flagged).

3. **Negative rule inversion** — `denied_rules_for_call(rules, call,
   auction_before, seat, vuln)` → context-matching rules with strictly higher
   priority and a different call (skip ties). `infer_negatives(...)` turns
   each into a denial record, classifying `foldable` (single binding bound,
   esp. point caps) vs annotation-only, and applying the **denial-confidence
   discount** (Q8): a denial's confidence is the would-be positive confidence
   of the denied rule × `DENIAL_DISCOUNT` (≈0.8, a named module constant).
   Tests: 1-of-suit opening denies 2♣ (⇒ `hcp ≤ 21`, foldable) and 1NT
   (annotation-only); opening **pass** ⇒ sub-opening cap; a tie produces no
   denial; denial confidence < the matching positive confidence.

4. **Auction walker** — `infer_from_auction(rules, auction, dealer,
   vulnerability, kb=None)`: step call-by-call, derive seat via
   `seat_from_auction`, map to position, run both `infer_positive` and
   `infer_negatives`, and `add_inference` each. Returns the populated KB
   (all four players, since all bid our SAYC). Tests on full sequences from
   `sayc_examples.py`.

5. **Violation detection** — after each `add_inference`, recompute the
   player's `hand_profile`; if the folded constraints become unsatisfiable
   (e.g. disjoint hcp ranges), mark the conflicting inference(s)
   `violated=True` rather than dropping them (auditable log). Test with a
   deliberately inconsistent (psych) auction.

Play-based inferences (`play=True`) wait on the card-play engine (Roadmap
stage 7); the keys and code paths are reserved now but unused. Richer
disjunctive denials (beyond the foldable subset) are a natural later
enhancement.

### Clarifying questions

Defaults below are what I'll assume if there's no objection.

1. **Module home** — put this in a new `bridge/inference/` module (my
   proposal), or under `bridge/agents/` since it's bot knowledge? *Default:
   `bridge/inference/`.*

Use bridge/inference/

2. **KB second level** — the doc says "dictionary of dictionaries." I read
   that as `kb[position][inference_id] = record` with auto-generated
   `inference_id`s, plus a derived `hand_profile` view. Is a keyed dict right,
   or would you rather a list of records per position? *Default: keyed dict +
   derived profile.*

Use a keyed dictionary.

3. **Positions vs seats** — the engine uses integer seats 1–4 (seat 1 =
   dealer); the KB is keyed by N/E/S/W. I'll map seat→position from a
   `dealer_position` argument, rotating clockwise N→E→S→W. The doc lists the
   order "East, South, West, North" — is that meaningful, or just
   illustrative? *Default: standard clockwise N→E→S→W from a given dealer.*

N, E, S, W is good

4. **v1 scope** — start with **positive** inferences from actual bids only,
   and defer negative inferences (denials) and the opening-pass inference to a
   later increment? *Default: yes, positive-only first.*

Make an attempt to do both.

5. **System symmetry** — do we assume **all four** players bid our SAYC (so we
   can infer about opponents too), and infer for all three other players (and
   optionally self)? *Default: yes, single shared system; infer all opponents
   and partner.*

Yes, all four players bid our SAYC.

6. **Confidence heuristic** — assign confidence from rule ambiguity (1 matching
   rule → ~0.95; several with divergent constraints → lower; none → ~0.0 and
   flagged)? Or keep it binary 1.0/0.0 for v1? *Default: the graded heuristic.*

Use the graded heuristic.

---

New questions raised by the decision to do negative inferences in v1 (Q4):

7. **Denial folding (the key new one)** — negating a rule's multi-predicate
   `hand` block is a disjunction that doesn't fit the simple constraint dict.
   My plan: *fold* only single-binding-bound denials into the numeric profile
   (chiefly point caps like "didn't bid 2♣ ⇒ ≤21 HCP"), and *record but not
   fold* multi-predicate denials (e.g. "not balanced 15–17") as lower-
   confidence annotations. Good for v1, or do you want fuller disjunctive
   reasoning now? *Default: foldable subset + annotations.*
   
Use the foldable subset + annotations.

8. **Negative-inference confidence** — denials assume the opponent bid *exactly*
   our SAYC with our priorities, so they're more brittle than positive
   inferences. Should denials carry a lower baseline confidence than the
   matching positive inference (e.g. ×0.8)? *Default: yes, discount denials.*

Use yes, discount denials.

## Development

1. Generate the code according to the plan.  Generate a Python Notebook in nb/ named bidding_inferences.ipynb.  Use it to show how well the bidding inferences work.

## Docs

1. Because I am struggling to render the Notebooks on GitHub, please generate a markdown version and place it in the docs/bidding_inferences.md file.  Please do the same for the other Notebook in nb/ named sayc_bidding.ipynb.

## Prompts

1. Read this file.  Generate a plan to develop the process for making inferences from the bidding and keeping track of the inferences in a knowledge base.  If you have any questions, put them under the Clarifying questions section.
2. Read this file.  See my answers to the clarifying questions.  Make any necessary adjustments to the plan and ask any additional questions as needed.
3. Read this file.  See my answers to the new clarifying questions.  Make any necessary adjustments to the plan and ask any additional questions as needed.
4. Read this file.  Proceed with the plan by executing the first item in the Development section.
5. Read this file.  Execute the 1st directive under Examples
6. Read this file.  Execute the 1st directive under Docs