==================
Bidding Conventions
==================

A running list of the bidding conventions and treatments known to the bot,
maintained as the SAYC knowledge base is built (see
``prompts/sayc_bidding.md``). Each entry notes the convention, a one-line
meaning, and its status in our data files
(``bridge/data/bidding/sayc/``).

Status legend: ``planned`` (scoped, not yet encoded), ``encoded`` (rules
written + tested), ``deferred`` (intentionally later).

Constructive / uncontested (v1)
===============================

Openings (``openings.yaml``)
----------------------------

- **Strong 1NT** — 15-17 HCP, balanced. *encoded*
- **2NT opening** — 20-21 HCP, balanced. *encoded*
- **Five-card majors** — 1\ |H|/1\ |S| promise 5+ cards (longest suit; higher of two five-card suits). *encoded*
- **Minor openings** — 1\ |C| (3+), 1\ |D| (3+); longer minor, 1\ |C| with 3-3, 1\ |D| with 4-4. *encoded*
- **Strong, artificial 2**\ |C| — 22+ HCP; game-forcing. *encoded*
- **Weak two-bids** — 2\ |D|/2\ |H|/2\ |S|, six-card suit, 5-11 HCP. *encoded*
- **Preempts** — 3-level (7-card) and 4-level (8-card), 5-11 HCP, Rule of 2/3/4 noted. *encoded*
- **Light openers — Rule of 20** (1st/2nd seat, 11-12 shapely). *encoded*
- **Light openers — Rule of 15** (3rd/4th seat, with spades). *encoded*
- **3NT gambling/25-27 opening** — not used in plain SAYC (22+ balanced opens 2\ |C|). *deferred*

Responses & rebids (``responses/``, ``rebids/``)
-----------------------------------------------

- **Major-suit limit raise** — 3\ |H|/3\ |S| jump, 4+ trumps, 10-12. *encoded*
- **Simple raise** of opener's major — 3+ trumps, 6-9. *encoded*
- **Game raise** of opener's major — 5+ trumps, 13-16, to play. *encoded*
- **Non-forcing 1NT response** to a major — 6-9 (plain SAYC, not 2/1). *encoded*
- **New suit by responder** — one-level (4+, forcing) and two-level (4+, 11+, forcing). *encoded*
- **Natural 2NT/3NT responses** — invitational / game, balanced. *encoded*
- **Responses to a minor up the line** — show four-card suits cheapest-first. *encoded* (basic; length tie-breaks *planned*)
- **Inverted minor raises** — single raise (2\ |C|/2\ |D|) strong/forcing (10+); jump raise (3\ |C|/3\ |D|) weak/preemptive (5-9); both deny a four-card major. *encoded*
- **2C waiting (2**\ |D|\ **)** — universal relay response to strong 2\ |C|. *encoded*
- **Positive 2C responses** — natural 5+ suit, ~8+ HCP (suit-quality test *planned*). *encoded*
- **Weak-two responses** — preemptive raise; 2NT feature/Ogust ask. *encoded* (RONF new-suit *planned*)
- **Opener completes Jacoby transfer** — forced. *encoded*
- **Stayman replies** — 2\ |H|/2\ |S|/2\ |D| by opener. *encoded*
- **2C opener's 2NT rebid** — balanced 22-24. *encoded*
- **Responder's rebids** (preference, fourth-suit-forcing, invitational sequences). *planned*
- **Jump shift by responder** — strong, ~17+, forcing to game. *planned*

Notrump conventions (``responses/to_1nt.yaml``)
----------------------------------------------

- **Stayman** — 2\ |C| over 1NT asks for a 4-card major. *encoded*
- **Jacoby transfers** — over 1NT, 2\ |D| → hearts, 2\ |H| → spades. *encoded*
- **Stayman / transfers over 2NT** — 3\ |C| Stayman; 3\ |D| → hearts, 3\ |H| → spades (with opener's replies/completions). *encoded*

Slam tools (``conventions/``)
-----------------------------

- **Blackwood** — 4NT asks for aces (5\ |C|=0/4, 5\ |D|=1, 5\ |H|=2, 5\ |S|=3). *encoded*
- **Gerber** — 4\ |C| over 1NT asks for aces (4\ |D|=0/4, 4\ |H|=1, 4\ |S|=2, 4NT=3). *encoded*
- **Grand Slam Force** — 5NT asks partner to bid a grand with top trump honours. *planned*

Competitive (separate file, follow-up)
======================================

- **Overcalls** — 1-level natural (8-16, 5+ cards); 1NT overcall 15-18 balanced. *deferred*
- **Takeout double** — shorter in opponent's suit, support for the unbid suits. *deferred*
- **Negative double** — responder's double showing the unbid suit(s). *deferred*
- **Michaels cue-bid** — two-suited overcall. *deferred*
- **Unusual 2NT** — lowest two unbid suits, 5-5. *deferred*
- **Penalty / responsive doubles** — *deferred*

.. |C| replace:: ♣
.. |D| replace:: ♦
.. |H| replace:: ♥
.. |S| replace:: ♠
