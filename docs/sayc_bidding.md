# SAYC Bidding — Demonstration

This notebook shows how well the SAYC bidding bot works. The system is a
set of declarative YAML rules under `bridge/data/bidding/sayc/`, applied by
a small rule-matcher in `bridge.bidding_systems.sayc_loader`.

A **hand** is a dict of suit letter → ranks string, e.g.
`{"S": "AKQ", "H": "T98", "D": "7654", "C": "32"}`. A **call** is
`"1NT"`, `"1S"`, `"2C"`, `"P"` (pass), `"X"`, `"XX"`.

Run top-to-bottom (kernel = the `astro14` Python 3.14 environment).


```python
from bridge.bidding_systems import sayc_loader as sl
from bridge.bidding_systems import sayc_examples as ex

rules = sl.load_rules()
meta = sl.load_meta()
print(meta['system'], '— version', meta['version'])
print(f'Loaded {len(rules)} rules from the SAYC knowledge base.')
problems = sl.validate_rules(rules)
print('Schema validation problems:', problems or 'none')
```

    Standard American Yellow Card (SAYC) — version 0.1
    Loaded 100 rules from the SAYC knowledge base.
    Schema validation problems: none


## 1. Hand evaluation

Every decision starts from derived features: high-card points, suit
lengths, shape, whether the hand is balanced, the Rule of 20 / Rule of 15
light-opening tests, and ace/king counts (for Blackwood/Gerber).


```python
hand = {'S': 'AQ432', 'H': 'KJ4', 'D': 'KQ5', 'C': '32'}
f = sl.compute_features(hand)
print('Hand:', hand)
for k in ['hcp', 'lengths', 'shape', 'balanced', 'rule_of_20', 'rule_of_15', 'aces', 'kings']:
    print(f'  {k:11}: {f[k]}')
```

    Hand: {'S': 'AQ432', 'H': 'KJ4', 'D': 'KQ5', 'C': '32'}
      hcp        : 15
      lengths    : {'S': 5, 'H': 3, 'D': 3, 'C': 2}
      shape      : (5, 3, 3, 2)
      balanced   : True
      rule_of_20 : True
      rule_of_15 : True
      aces       : 1
      kings      : 2


## 2. Opening bids across a spectrum of hands

For each hand we ask the matcher for the best opening call (seat 1, nobody
has bid) and print the reason the chosen rule gives.


```python
opening_hands = [
    ('Balanced 16',        {'S': 'AQJ2', 'H': 'KJ4', 'D': 'KQ5', 'C': '432'}),
    ('Balanced 20',        {'S': 'AKQ',  'H': 'KQ4', 'D': 'KJ5', 'C': 'Q432'}),
    ('Strong 25',          {'S': 'AKQ4', 'H': 'AKQ', 'D': 'AK5', 'C': '432'}),
    ('5-card spades, 14',  {'S': 'AQ432','H': 'KJ4', 'D': 'Q84', 'C': 'Q2'}),
    ('6-card hearts, 15',  {'S': 'K3',   'H': 'AQJ432','D': 'KQ4','C': '32'}),
    ('4-4 minors, 14',     {'S': 'KQ3',  'H': 'K3',  'D': 'KQ32','C': 'J432'}),
    ('Weak two spades',    {'S': 'KQT984','H': 'K32','D': '432', 'C': '2'}),
    ('7-card preempt (D)', {'S': '2',    'H': '32',  'D': 'KQT9842','C': '432'}),
    ('Yarborough',         {'S': '8432', 'H': '765', 'D': '5432','C': 'J2'}),
]
for label, h in opening_hands:
    cands = sl.match_rules(rules, h, auction=[], seat=1)
    best = cands[0] if cands else {'call': 'P', 'why': 'no opening — pass'}
    print(f"{label:20} {sl.high_card_points(h):2} HCP  ->  {best['call']:3}  {best['why']}")
```

    Balanced 16          16 HCP  ->  1NT  Balanced 15-17 HCP; the SAYC strong notrump (may hold a five-card suit).
    Balanced 20          20 HCP  ->  2NT  Balanced 20-21 HCP.
    Strong 25            25 HCP  ->  2C   Strong, artificial: 22+ HCP (or ~9 playing tricks). Game-forcing except after 2C-2D-2NT.
    5-card spades, 14    14 HCP  ->  1S   5+ spades, 13-21; spades the longest suit (higher of two five-card suits).
    6-card hearts, 15    15 HCP  ->  1H   5+ hearts, 13-21; hearts the longest suit and longer than spades.
    4-4 minors, 14       14 HCP  ->  1D   No five-card major; open the longer minor — 1D with diamonds >= clubs and 4+ diamonds (covers 4-4 and 5-5 minors).
    Weak two spades       8 HCP  ->  2S   Weak two: a good six-card spade suit, 5-11 HCP.
    7-card preempt (D)    5 HCP  ->  3D   Preempt: seven-card diamond suit, 5-11 HCP.
    Yarborough            1 HCP  ->  P    no opening — pass


## 3. Seat & vulnerability sensitivity

The same shapely 11-count opens light in 1st/2nd seat (Rule of 20) but the
matcher applies the Rule of 15 in 3rd/4th seat — a hand without spade length
is passed there.


```python
light = {'S': 'KQT98', 'H': 'AQ982', 'D': '43', 'C': '2'}  # 11 HCP, 5-5 majors
flat  = {'S': 'K3', 'H': 'AQ32', 'D': 'J432', 'C': 'Q43'}  # 12 HCP, 2 spades
for seat in (1, 2, 3, 4):
    print(f'seat {seat}: 5-5 11-count -> {sl.choose_call(rules, light, auction=[], seat=seat):3}'
          f'   |   flat 12 (2 spades) -> {sl.choose_call(rules, flat, auction=[], seat=seat)}')
```

    seat 1: 5-5 11-count -> 1S    |   flat 12 (2 spades) -> 1D
    seat 2: 5-5 11-count -> 1S    |   flat 12 (2 spades) -> 1D
    seat 3: 5-5 11-count -> 1S    |   flat 12 (2 spades) -> P
    seat 4: 5-5 11-count -> 1S    |   flat 12 (2 spades) -> P


## 4. End-to-end partnership auctions

Opener opens, responder responds, opener rebids (opponents passing). Each
call is produced by the matcher and annotated with its reason.


```python
print(ex.format_examples(rules))
```

    SAYC bidding examples
    =====================
    
    * Stayman uncovers a 4-4 heart fit
        Opener   : {'S': 'AQ32', 'H': 'KJ32', 'D': 'K3', 'C': 'Q92'}
        Responder: {'S': 'K32', 'H': 'AQ32', 'D': 'Q432', 'C': '32'}
        Auction  : 1NT - 2C - 2H
            Opener    1NT  Balanced 15-17 HCP; the SAYC strong notrump (may hold a five-card suit).
            Responder 2C   Stayman: 2C asks for a four-card major (responder holds four hearts).
            Opener    2H   Stayman reply: shows a four-card heart suit (bid hearts first when holding both majors).
    
    * Jacoby transfer into spades
        Opener   : {'S': 'AQ7', 'H': 'KJ3', 'D': 'KQ32', 'C': 'Q92'}
        Responder: {'S': 'KQT98', 'H': '32', 'D': '432', 'C': '432'}
        Auction  : 1NT - 2H - 2S
            Opener    1NT  Balanced 15-17 HCP; the SAYC strong notrump (may hold a five-card suit).
            Responder 2H   Jacoby transfer: 2H shows 5+ spades and asks opener to bid 2S.
            Opener    2S   Accept the transfer: responder's 2H showed spades, so opener bids 2S.
    
    * Strong, artificial 2C with a balanced 23-count
        Opener   : {'S': 'AKQ4', 'H': 'KQ3', 'D': 'AQ3', 'C': 'K32'}
        Responder: {'S': '832', 'H': 'J32', 'D': '9432', 'C': 'J3'}
        Auction  : 2C - 2D - 2NT
            Opener    2C   Strong, artificial: 22+ HCP (or ~9 playing tricks). Game-forcing except after 2C-2D-2NT.
            Responder 2D   Waiting 2D: the standard relay response to a strong 2C, used on weak hands and most others.
            Opener    2NT  Balanced 22-24: rebid 2NT (systems-on continuations apply, e.g. Stayman/transfers).
    
    * Strong notrump raised straight to game
        Opener   : {'S': 'AQ7', 'H': 'KJ3', 'D': 'KQ32', 'C': 'Q92'}
        Responder: {'S': 'K32', 'H': 'Q32', 'D': 'AQ32', 'C': 'K32'}
        Auction  : 1NT - 3NT
            Opener    1NT  Balanced 15-17 HCP; the SAYC strong notrump (may hold a five-card suit).
            Responder 3NT  Balanced 10-15 with no four-card major: raise straight to game.
    
    * Five-card major opening met with a limit raise
        Opener   : {'S': 'K3', 'H': 'AQJ32', 'D': 'KQ42', 'C': '32'}
        Responder: {'S': 'Q42', 'H': 'K432', 'D': 'AQ2', 'C': '432'}
        Auction  : 1H - 3H
            Opener    1H   5+ hearts, 13-21; hearts the longest suit and longer than spades.
            Responder 3H   Limit raise: 4+ hearts, 10-12 support points, invitational.
    
    * Weak two preempt furthered by responder
        Opener   : {'S': 'KQT984', 'H': 'K32', 'D': '432', 'C': '2'}
        Responder: {'S': 'J32', 'H': 'Q32', 'D': 'K432', 'C': '432'}
        Auction  : 2S - 3S
            Opener    2S   Weak two: a good six-card spade suit, 5-11 HCP.
            Responder 3S   Furthering the preempt: 3+ spades, weak — raise to 3S.
    
    * Blackwood: 4NT answered with two aces
        Hand   : {'S': 'AQ32', 'H': 'AQ3', 'D': 'Q32', 'C': 'Q32'}
        Auction: 4NT - P - 5H
            5H   Blackwood answer: 5H shows 2 aces.
    
    * Gerber: 4C over 1NT answered with two aces
        Hand   : {'S': 'A432', 'H': 'A32', 'D': 'K32', 'C': 'K32'}
        Auction: 1NT - P - 4C - P - 4S
            4S   Gerber answer: 4S shows 2 aces.
    


## 5. Convention spotlights

A few specific sequences, including the conventions added most recently:
Stayman/transfers over 2NT, positive 2C responses, and inverted minors.


```python
def show(title, hand, auction, seat=3):
    cands = sl.match_rules(rules, hand, auction=auction, seat=seat)
    best = cands[0] if cands else {'call': 'P', 'why': 'no rule — pass'}
    seq = ' '.join(auction) if auction else '(opening)'
    print(f'{title}')
    print(f"    after [{seq}] with {hand}")
    print(f"    -> {best['call']}   {best['why']}\n")

show('Stayman over 1NT',      {'S': 'K32', 'H': 'AQ32', 'D': 'Q432', 'C': '32'}, ['1NT', 'P'])
show('Jacoby transfer (1NT)', {'S': 'KQT98', 'H': '32', 'D': '432', 'C': '432'}, ['1NT', 'P'])
show('Stayman over 2NT',      {'S': 'K32', 'H': 'AQ32', 'D': 'Q432', 'C': '32'}, ['2NT', 'P'])
show('Transfer over 2NT',     {'S': '32', 'H': 'KQ432', 'D': '432', 'C': '432'}, ['2NT', 'P'])
show('Positive 2C response',  {'S': 'AKQ32', 'H': '432', 'D': '432', 'C': '32'}, ['2C', 'P'])
show('Inverted minor (strong)', {'S': 'K32', 'H': '32', 'D': 'K3', 'C': 'AQ9432'}, ['1C', 'P'])
show('Inverted minor (weak)',   {'S': 'K32', 'H': '32', 'D': '32', 'C': 'K98432'}, ['1C', 'P'])
show('Blackwood: 2 aces',     {'S': 'AQ32', 'H': 'AQ3', 'D': 'Q32', 'C': 'Q32'}, ['4NT', 'P'])
show('Gerber over 1NT: 2 aces', {'S': 'A432', 'H': 'A32', 'D': 'K32', 'C': 'K32'}, ['1NT', 'P', '4C', 'P'], seat=1)
```

    Stayman over 1NT
        after [1NT P] with {'S': 'K32', 'H': 'AQ32', 'D': 'Q432', 'C': '32'}
        -> 2C   Stayman: 2C asks for a four-card major (responder holds four hearts).
    
    Jacoby transfer (1NT)
        after [1NT P] with {'S': 'KQT98', 'H': '32', 'D': '432', 'C': '432'}
        -> 2H   Jacoby transfer: 2H shows 5+ spades and asks opener to bid 2S.
    
    Stayman over 2NT
        after [2NT P] with {'S': 'K32', 'H': 'AQ32', 'D': 'Q432', 'C': '32'}
        -> 3C   Stayman over 2NT: 3C asks for a four-card major (responder holds four hearts).
    
    Transfer over 2NT
        after [2NT P] with {'S': '32', 'H': 'KQ432', 'D': '432', 'C': '432'}
        -> 3D   Jacoby transfer: 3D shows 5+ hearts and asks opener to bid 3H.
    
    Positive 2C response
        after [2C P] with {'S': 'AKQ32', 'H': '432', 'D': '432', 'C': '32'}
        -> 2S   Positive response: a good 5+ card spade suit and ~8+ HCP.
    
    Inverted minor (strong)
        after [1C P] with {'S': 'K32', 'H': '32', 'D': 'K3', 'C': 'AQ9432'}
        -> 2C   Inverted minor: a single raise to 2C is the strong, forcing club raise (10+, no four-card major).
    
    Inverted minor (weak)
        after [1C P] with {'S': 'K32', 'H': '32', 'D': '32', 'C': 'K98432'}
        -> 3C   Inverted minor: the jump raise to 3C is weak and preemptive (5-9, 5+ clubs, no four-card major).
    
    Blackwood: 2 aces
        after [4NT P] with {'S': 'AQ32', 'H': 'AQ3', 'D': 'Q32', 'C': 'Q32'}
        -> 5H   Blackwood answer: 5H shows 2 aces.
    
    Gerber over 1NT: 2 aces
        after [1NT P 4C P] with {'S': 'A432', 'H': 'A32', 'D': 'K32', 'C': 'K32'}
        -> 4S   Gerber answer: 4S shows 2 aces.
    


## 6. Opening-bid distribution over random deals

Deal many random hands (seeded for reproducibility) and tabulate the
dealer's opening call. This sanity-checks coverage — the frequencies match
bridge intuition: roughly half of all hands pass, about a third open one of
a suit, ~6% open 1NT, and the strong (2C/2NT) and preemptive actions are
each rare.


```python
import random
from collections import Counter

RANK_ORDER = 'AKQJT98765432'
SUITS = ('S', 'H', 'D', 'C')

def deal_one(seed):
    deck = [(s, r) for s in SUITS for r in RANK_ORDER]
    random.Random(seed).shuffle(deck)
    cards = deck[:13]
    return {s: ''.join(sorted((r for (cs, r) in cards if cs == s), key=RANK_ORDER.index))
            for s in SUITS}

N = 5000
counts = Counter(sl.choose_call(rules, deal_one(seed), auction=[], seat=1) for seed in range(N))
print(f'Dealer opening call over {N} random deals:')
for c, n in sorted(counts.items(), key=lambda kv: -kv[1]):
    print(f'  {c:4} {n:5}  ({100 * n / N:4.1f}%)')
opened = N - counts.get('P', 0)
print(f'\nOpened the bidding: {opened} / {N}  ({100 * opened / N:.1f}%)')
```

    Dealer opening call over 5000 random deals:
      P     2696  (53.9%)
      1D     481  ( 9.6%)
      1C     428  ( 8.6%)
      1S     325  ( 6.5%)
      1H     305  ( 6.1%)
      1NT    284  ( 5.7%)
      2S     120  ( 2.4%)
      2H     107  ( 2.1%)
      2D     102  ( 2.0%)
      3S      25  ( 0.5%)
      2C      25  ( 0.5%)
      3C      23  ( 0.5%)
      2NT     23  ( 0.5%)
      3H      22  ( 0.4%)
      3D      21  ( 0.4%)
      4S       5  ( 0.1%)
      4C       3  ( 0.1%)
      4H       3  ( 0.1%)
      4D       2  ( 0.0%)
    
    Opened the bidding: 2304 / 5000  (46.1%)


## Summary

The bot evaluates a hand, applies SAYC as data-driven rules, and returns a
single best call with an explanation — covering openings (all seats),
responses, the core notrump and slam conventions, Stayman/transfers over
2NT, positive 2C responses, and inverted minors. Competitive bidding is the
next milestone (see `docs/conventions.rst` for per-convention status).
