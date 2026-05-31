# Bidding Inferences — Demonstration

This notebook shows how well the **bidding-inference engine** works. As an
auction unfolds, a bot can deduce constraints on each player's hand by
*inverting* the SAYC bidding rules and storing what it learns in a
**knowledge base** (`bridge/inference/`).

The idea in one line: the SAYC matcher is *forward* (known hand → best call);
inference runs it *backward* (observed call → the hand facts that justify it).

For each observed call we extract two kinds of inference:

- **Positive** — the hand must satisfy one of the rules that *produce* this
  call, so we keep the loosest envelope of their hand requirements.
- **Negative (denials)** — the matcher always picks the highest-priority
  rule, so any higher-priority rule with a *different* call must have failed:
  e.g. *opened 1♦, not 2♣ ⇒ ≤ 21 HCP*. A pass denies every opening.

A **constraint** is a small dict of absolute hand facts (HCP / suit-length
ranges and the balanced/Rule-of-20/15 booleans) — chosen so two constraints
intersect by simple range logic.


```python
from pathlib import Path
import random

from bridge.bidding_systems import sayc_loader as sl
from bridge.inference import bidding as bi
from bridge.inference import knowledge_base as kb_mod

rules = sl.load_rules()
print(f"Loaded {len(rules)} SAYC rules; validator problems:",
      len(sl.validate_rules(rules)))
```

    Loaded 101 SAYC rules; validator problems: 0


## 1. Inverting a single call

Take a **1NT opening**. The positive inference recovers the 1NT requirements;
the denials record what the opener *didn't* have (the stronger calls 2♣ and
2NT they passed over).


```python
def show_records(records):
    for r in records:
        kind = "DENY " if r["negated"] else "INFER"
        fold = "" if not r["negated"] else (" [foldable]" if r["foldable"] else " [note]")
        print(f"  {kind}{fold}  conf={r['confidence']:.2f}  "
              f"constraint={r['constraint'] or '{}'}")
        print(f"         {r['reason']}")

pos = bi.infer_positive(rules, "1NT", auction_before=[], seat=1,
                        vulnerability="any", auction_index=0)
neg = bi.infer_negatives(rules, "1NT", auction_before=[], seat=1,
                         vulnerability="any", auction_index=0)
print("Observed call: 1NT (opening, seat 1)\n")
show_records([pos])
print()
show_records(neg)
```

    Observed call: 1NT (opening, seat 1)
    
      INFER  conf=0.95  constraint={'hcp': [15, 17], 'balanced': True}
             1NT: Balanced 15-17 HCP; the SAYC strong notrump (may hold a five-card suit).
    
      DENY  [foldable]  conf=0.76  constraint={'hcp': [0, 21]}
             Did not bid 2C: denies 22+ HCP => <=21 HCP.
      DENY  [note]  conf=0.76  constraint={}
             Did not bid 2NT: denies 20-21 HCP, balanced.


## 2. Walking a whole auction

`infer_from_auction` steps through every call, works out who is bidding
(seat → table position, clockwise from the dealer), and files each inference
under that player. `hand_profile` then folds a player's inferences into one
running picture.

Here is a classic **Stayman** auction — North opens 1NT and South asks for a
four-card major:


```python
def show_profiles(kb):
    for pos in ("N", "E", "S", "W"):
        prof = kb_mod.hand_profile(kb, pos)
        desc = bi.describe_constraint(prof["constraint"])
        print(f"{pos}: {desc}")
        for note in prof["annotations"]:
            print(f"      · also: {note}")
        if not prof["constraint"] and not prof["annotations"]:
            print("      (nothing inferred)")

auction = ["1NT", "P", "2C", "P", "2H", "P"]
kb = bi.infer_from_auction(rules, auction, dealer="N")
print("Auction:", " ".join(auction), "  (dealer North)\n")
show_profiles(kb)
```

    Auction: 1NT P 2C P 2H P   (dealer North)
    
    N: 15-17 HCP, 4+ hearts, balanced
          · also: Did not bid 2NT: denies 20-21 HCP, balanced.
    E: nothing specific
          (nothing inferred)
    S: 8-16 HCP, <=4 spades, <=4 hearts
    W: nothing specific
          (nothing inferred)


Notice South's profile: Stayman shows 8–16 HCP, and because South *didn't*
make a Jacoby transfer (which would show a five-card major), the engine folds
in **≤ 4 spades and ≤ 4 hearts** — a deduction that emerges purely from the
denial machinery.

## 3. Soundness & informativeness over random deals

The acid test: deal many random hands, let the SAYC bot pick the opening call,
then infer from that call and check the **real hand actually satisfies the
inferred constraint**. Because inference inverts the very rules the bot bid
with, soundness should be 100% — this confirms the implementation matches the
theory. We also measure how *informative* the inference is (how tightly it
pins the HCP).

(This very sweep is also a useful *auditor of the rule base*: an early run
flagged a handful of 13+ HCP hands the opening rules failed to open — the
4-4-3-2 "better-minor" shape — which we then closed with `open_1d_better_minor`
in `openings.yaml`.)


```python
SUITS = "SHDC"
DECK = [r + s for s in SUITS for r in sl.RANKS]

def deal_hand(rng):
    """Deal one random 13-card hand as a {suit: ranks} dict."""
    cards = rng.sample(DECK, 13)
    hand = {s: "" for s in SUITS}
    for rank, suit in cards:
        hand[suit] += rank
    # Sort each suit high-to-low for readability.
    order = {r: i for i, r in enumerate(sl.RANKS)}
    return {s: "".join(sorted(h, key=order.get)) for s, h in hand.items()}

def constraint_contains(constraint, hand):
    """True if a hand satisfies every bound in a constraint."""
    feats = sl.compute_features(hand)
    for key, val in constraint.items():
        if key == "hcp":
            if not (val[0] <= feats["hcp"] <= val[1]):
                return False
        elif key in ("aces", "kings"):
            if not (val[0] <= feats[key] <= val[1]):
                return False
        elif key in ("S", "H", "D", "C"):
            if not (val[0] <= feats["lengths"][key] <= val[1]):
                return False
        else:  # boolean feature
            if feats[key] != val:
                return False
    return True

rng = random.Random(20260530)
N = 5000
sound = 0
nonpass_total = nonpass_sound = 0
hcp_widths = []
call_counts = {}

for _ in range(N):
    hand = deal_hand(rng)
    call = sl.choose_call(rules, hand, auction=[], seat=1, vulnerability="any")
    call_counts[call] = call_counts.get(call, 0) + 1
    kb = bi.infer_from_auction(rules, [call], dealer="N")
    constraint = kb_mod.hand_profile(kb, "N")["constraint"]
    ok = constraint_contains(constraint, hand)
    sound += ok
    if call != "P":
        nonpass_total += 1
        nonpass_sound += ok
    if "hcp" in constraint:
        hcp_widths.append(constraint["hcp"][1] - constraint["hcp"][0] + 1)

print(f"Deals: {N}")
print(f"Sound inferences (all calls): {sound}/{N}  ({100 * sound / N:.1f}%)")
print(f"Sound inferences (actual bids): {nonpass_sound}/{nonpass_total}  "
      f"({100 * nonpass_sound / nonpass_total:.1f}%)")
avg_w = sum(hcp_widths) / len(hcp_widths) if hcp_widths else float("nan")
print(f"Avg inferred HCP-range width (when bounded): {avg_w:.1f} points "
      f"(out of 0-40)")
```

    Deals: 5000
    Sound inferences (all calls): 5000/5000  (100.0%)
    Sound inferences (actual bids): 2269/2269  (100.0%)
    Avg inferred HCP-range width (when bounded): 11.3 points (out of 0-40)



```python
# Opening-call distribution and the HCP each call pins down.
print(f"{'call':>5} {'count':>6}  inferred HCP range")
for call in sorted(call_counts, key=lambda c: -call_counts[c]):
    kb = bi.infer_from_auction(rules, [call], dealer="N")
    c = kb_mod.hand_profile(kb, "N")["constraint"]
    hcp = c.get("hcp", "—")
    print(f"{call:>5} {call_counts[call]:>6}  {hcp}")
```

     call  count  inferred HCP range
        P   2731  [0, 12]
       1D    488  [11, 21]
       1C    472  [11, 21]
       1H    303  [11, 21]
       1S    297  [11, 21]
      1NT    250  [15, 17]
       2D    114  [5, 11]
       2H    112  [5, 11]
       2S     94  [5, 11]
       3D     27  [5, 11]
      2NT     24  [20, 21]
       3C     22  [5, 11]
       3H     21  [5, 11]
       2C     18  [22, 40]
       3S     16  [5, 11]
       4H      5  [5, 11]
       4C      3  [5, 11]
       4D      2  [5, 11]
       4S      1  [5, 11]


Every deal's real hand falls inside the inferred bounds — the engine never
claims something false — while still pinning HCP to a useful window (and a
*pass* is correctly read as a sub-opening ≤ 12 HCP).

## 3b. Inference vs. the truth, hand by hand

A closer look at a few deals: the dealt hand, the call our SAYC bot makes, and
the constraint the engine then infers from that call alone.


```python
rng2 = random.Random(7)
print(f"{'hand':<46} {'call':>4}   inferred")
for _ in range(8):
    hand = deal_hand(rng2)
    shown = " ".join(f"{s}:{hand[s] or '-'}" for s in "SHDC")
    call = sl.choose_call(rules, hand, auction=[], seat=1, vulnerability="any")
    kb = bi.infer_from_auction(rules, [call], dealer="N")
    desc = bi.describe_constraint(kb_mod.hand_profile(kb, "N")["constraint"])
    print(f"{shown:<46} {call:>4}   {desc}")
```

    hand                                           call   inferred
    S:JT85 H:A742 D:863 C:Q6                          P   <=12 HCP
    S:QJT97 H:KQ D:AK54 C:43                         1S   11-21 HCP, 5+ spades
    S:QJ6 H:K92 D:543 C:K542                          P   <=12 HCP
    S:87532 H:8 D:A6543 C:T6                          P   <=12 HCP
    S:JT8 H:A74 D:K9654 C:A8                         1D   11-21 HCP, 3+ diamonds
    S:93 H:Q84 D:J743 C:9762                          P   <=12 HCP
    S:T754 H:96 D:AQ982 C:73                          P   <=12 HCP
    S:QT H:765 D:A95432 C:J2                         2D   5-11 HCP, exactly 6 diamonds


## 4. How denials sharpen a profile

Denials are the difference between "*some* hand that could bid this" and a
genuinely *narrow* read. Below, the same 1♠ opening with vs. without the
folded denials:


```python
hand_call = "1S"
pos = bi.infer_positive(rules, hand_call, [], 1, "any", 0)
print("1S — positive only:      ", bi.describe_constraint(pos["constraint"]))

kb = bi.infer_from_auction(rules, [hand_call], dealer="N")
full = kb_mod.hand_profile(kb, "N")["constraint"]
print("1S — with folded denials:", bi.describe_constraint(full))
print("\nDenial details:")
for iid, rec in kb["N"].items():
    if rec["negated"]:
        tier = "foldable" if rec["foldable"] else "note"
        print(f"  [{tier}] {rec['reason']}")
```

    1S — positive only:       11-21 HCP, 5+ spades
    1S — with folded denials: 11-21 HCP, 5+ spades
    
    Denial details:
      [foldable] Did not bid 2C: denies 22+ HCP => <=21 HCP.
      [note] Did not bid 2NT: denies 20-21 HCP, balanced.
      [note] Did not bid 1NT: denies 15-17 HCP, balanced.
      [note] Did not bid 1D: denies 13-21 HCP, 5+ diamonds.


## 5. Catching an inconsistency (psych / error)

If a later inference contradicts what a player already promised, the engine
keeps the earlier consensus and flags the later call `violated` rather than
silently discarding information. Here we hand-build North's record set with a
1NT opening (15–17) followed by a later call implying ≤ 12 HCP.


```python
kb = kb_mod.empty_kb()
kb_mod.add_inference(kb, "N", {
    "constraint": {"hcp": [15, 17], "balanced": True}, "confidence": 0.95,
    "reason": "Opened 1NT.", "bidding": True, "play": False, "violated": False,
    "negated": False, "foldable": False, "call": "1NT", "auction_index": 0,
    "rule_ids": ["open_1nt"]})
kb_mod.add_inference(kb, "N", {
    "constraint": {"hcp": [0, 12]}, "confidence": 0.85,
    "reason": "A later call implied <=12 HCP.", "bidding": True, "play": False,
    "violated": False, "negated": False, "foldable": False, "call": "P",
    "auction_index": 4, "rule_ids": []})

flagged = kb_mod.mark_violations(kb)
print("Flagged as violated:", flagged)
for iid, rec in kb["N"].items():
    print(f"  {iid}: violated={rec['violated']}  {rec['reason']}")
print("\nResulting profile (violated inference dropped):",
      bi.describe_constraint(kb_mod.hand_profile(kb, "N")["constraint"]))
```

    Flagged as violated: ['01_P_pos']
      00_1NT_pos: violated=False  Opened 1NT.
      01_P_pos: violated=True  A later call implied <=12 HCP.
    
    Resulting profile (violated inference dropped): 15-17 HCP, balanced


## 6. Persisting the knowledge base

The KB is plain JSON-friendly data, so it writes and reads back faithfully.


```python
auction = ["1NT", "P", "2C", "P"]
kb = bi.infer_from_auction(rules, auction, dealer="N")
path = Path("kb_demo.json")
kb_mod.write_knowledge_base(kb, path)
restored = kb_mod.read_knowledge_base(path)
print("Round-trip identical:", restored == kb)
print("\nFirst 600 chars of the saved file:\n")
print(path.read_text()[:600])
path.unlink()  # tidy up
```

    Round-trip identical: True
    
    First 600 chars of the saved file:
    
    {
      "N": {
        "00_1NT_pos": {
          "constraint": {
            "hcp": [
              15,
              17
            ],
            "balanced": true
          },
          "confidence": 0.95,
          "reason": "1NT: Balanced 15-17 HCP; the SAYC strong notrump (may hold a five-card suit).",
          "bidding": true,
          "play": false,
          "violated": false,
          "negated": false,
          "foldable": false,
          "call": "1NT",
          "auction_index": 0,
          "rule_ids": [
            "open_1nt"
          ]
        },
        "01_1NT_neg": {
          "bidding": true,
          "play": false,
          "violated": false,
          "negated": true,
        


## Summary

- **Inversion works.** Inferences are the SAYC rules read backward — positive
  envelopes plus higher-priority denials, all in one intersectable constraint
  vocabulary.
- **Sound by construction**, and verified sound on thousands of random deals,
  while still pinning HCP to a useful window.
- **Denials add real information** (e.g. Stayman ⇒ no five-card major; pass ⇒
  ≤ 12 HCP), with the disjunctive ones kept as honest annotations.
- **Inconsistencies are flagged**, not hidden, and the KB **persists** as JSON.

Next steps (per `prompts/bidding_inferences.md`): responder-rebid and
competitive rules will extend the rule base the inference engine inverts, and
play-based inferences (`play=True`) arrive with the card-play engine.
