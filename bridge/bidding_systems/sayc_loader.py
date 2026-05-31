"""Load, validate, and apply the SAYC bidding knowledge base.

The SAYC system is encoded as declarative *rules* stored in YAML under
``bridge/data/bidding/sayc/``. Each rule maps an auction context + a hand
description to a recommended *call*. This module provides:

- **hand-feature helpers** — derive HCP, suit lengths, shape, "balanced",
  Rule of 20 / Rule of 15 from a plain hand dict;
- **a loader** — read every rule file under the SAYC data directory;
- **a validator** — check each rule has the required, well-typed fields;
- **a thin matcher** — rank the rules that apply to a (hand, auction, seat,
  vulnerability) and return ranked candidates and a single best call.

The full bidding *engine* (managing a live auction across four players) is a
later milestone; this matcher is deliberately small so the rule data can be
tested hand-by-hand. Per CLAUDE.md these are module-level functions over
simple data, not behaviour-bearing classes.

Data conventions
----------------
A *hand* is a dict of suit letter -> ranks string, e.g.
``{"S": "AKQ", "H": "T98", "D": "7654", "C": "32"}``. Suit letters are
``S H D C``; ranks use ``A K Q J T 9 8 7 6 5 4 3 2`` (``T`` = ten). A *call*
is written ``"1NT"``, ``"1S"``, ``"2C"``, ``"P"`` (pass), ``"X"`` (double),
``"XX"`` (redouble).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# --- Constants -------------------------------------------------------------

# Milton Work / Goren high-card-point values.
HCP_VALUES: dict[str, int] = {"A": 4, "K": 3, "Q": 2, "J": 1}

# Valid card ranks, high to low (T == ten).
RANKS: str = "AKQJT98765432"

# Suit letters in descending rank order (spades high).
SUITS: tuple[str, ...] = ("S", "H", "D", "C")

# Map the long suit names used in rule predicates to their letter.
SUIT_NAMES: dict[str, str] = {
    "spades": "S",
    "hearts": "H",
    "diamonds": "D",
    "clubs": "C",
}

# Calls that count as a pass when deciding whether an opening rule applies.
PASS_CALLS: frozenset[str] = frozenset({"P", "PASS", "PASS."})

# Default location of the SAYC data files, relative to this file:
# bridge/bidding_systems/sayc_loader.py -> bridge/data/bidding/sayc
DEFAULT_SAYC_DIR: Path = (
    Path(__file__).resolve().parent.parent / "data" / "bidding" / "sayc"
)


# --- Hand-feature helpers --------------------------------------------------


def suit_lengths(hand: dict[str, str]) -> dict[str, int]:
    """Return the number of cards held in each suit.

    Parameters
    ----------
    hand:
        Mapping of suit letter (``S H D C``) to a ranks string. Missing
        suits are treated as void (length 0).

    Returns
    -------
    dict[str, int]
        Length of each of the four suits, keyed by suit letter.
    """
    return {suit: len(hand.get(suit, "")) for suit in SUITS}


def high_card_points(hand: dict[str, str]) -> int:
    """Return the Goren high-card-point total of a hand (A=4 K=3 Q=2 J=1).

    Bridge intent: HCP is the primary strength measure for most SAYC
    decisions (opening ranges, NT ranges, responses).
    """
    return sum(HCP_VALUES.get(card, 0) for suit in SUITS for card in hand.get(suit, ""))


def hand_shape(hand: dict[str, str]) -> tuple[int, ...]:
    """Return the suit lengths sorted high-to-low, e.g. ``(5, 3, 3, 2)``.

    Bridge intent: the shape (ignoring which suit is which) classifies a hand
    as balanced / one- or two-suited and drives many opening choices.
    """
    return tuple(sorted(suit_lengths(hand).values(), reverse=True))


def is_balanced(hand: dict[str, str]) -> bool:
    """Return True for a balanced hand: shape 4-3-3-3, 4-4-3-2, or 5-3-3-2.

    Bridge intent: balanced hands are the ones eligible for natural notrump
    openings (1NT/2NT) in SAYC. No voids, no singletons, at most one doubleton.
    """
    return hand_shape(hand) in {(4, 3, 3, 3), (4, 4, 3, 2), (5, 3, 3, 2)}


def count_rank(hand: dict[str, str], rank: str) -> int:
    """Return how many cards of a given rank the hand holds (e.g. aces).

    Bridge intent: ace/king counts drive ace-asking conventions such as
    Blackwood (4NT) and Gerber (4C).
    """
    return sum(suit.count(rank) for suit in hand.values())


def two_longest_sum(hand: dict[str, str]) -> int:
    """Return the combined length of the hand's two longest suits.

    Bridge intent: the length component of the Rule of 20 opening test.
    """
    lengths = sorted(suit_lengths(hand).values(), reverse=True)
    return lengths[0] + lengths[1]


def satisfies_rule_of_20(hand: dict[str, str]) -> bool:
    """Return True if HCP + (two longest suit lengths) >= 20.

    Bridge intent: the Rule of 20 lets shapely 11-12 HCP hands open at the
    one level in 1st/2nd seat (per the user's chosen treatment).
    """
    return high_card_points(hand) + two_longest_sum(hand) >= 20


def satisfies_rule_of_15(hand: dict[str, str]) -> bool:
    """Return True if HCP + (spade length) >= 15.

    Bridge intent: the Rule of 15 (a.k.a. Pearson points / Rule of 15) guides
    light 3rd/4th-seat openings — open light only with spade length, so you
    are not outgunned in the battle for the spade suit.
    """
    return high_card_points(hand) + suit_lengths(hand)["S"] >= 15


def compute_features(hand: dict[str, str]) -> dict[str, Any]:
    """Bundle the derived features used by the matcher into one dict.

    Returns
    -------
    dict
        Keys: ``hcp`` (int), ``lengths`` (suit-letter -> int), ``shape``
        (tuple), ``balanced`` (bool), ``rule_of_20`` (bool),
        ``rule_of_15`` (bool).
    """
    return {
        "hcp": high_card_points(hand),
        "lengths": suit_lengths(hand),
        "shape": hand_shape(hand),
        "balanced": is_balanced(hand),
        "rule_of_20": satisfies_rule_of_20(hand),
        "rule_of_15": satisfies_rule_of_15(hand),
        "aces": count_rank(hand, "A"),
        "kings": count_rank(hand, "K"),
    }


# --- Loading ---------------------------------------------------------------


def load_meta(sayc_dir: Path = DEFAULT_SAYC_DIR) -> dict[str, Any]:
    """Load ``meta.yaml`` (system name, evaluation method, sources).

    Returns an empty dict if the file is absent.
    """
    meta_path = sayc_dir / "meta.yaml"
    if not meta_path.exists():
        return {}
    with meta_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or {}


def load_rules(sayc_dir: Path = DEFAULT_SAYC_DIR) -> list[dict[str, Any]]:
    """Load every rule from the SAYC data tree into one flat list.

    All ``*.yaml`` files under ``sayc_dir`` are read except ``meta.yaml``.
    Each file must contain a YAML list of rule mappings; the originating file
    (relative to ``sayc_dir``) is recorded on each rule under ``_file`` so
    errors and provenance are traceable.

    Returns
    -------
    list[dict]
        All rules, in a stable order (sorted by file path, then file order).
    """
    rules: list[dict[str, Any]] = []
    for path in sorted(sayc_dir.rglob("*.yaml")):
        if path.name == "meta.yaml":
            continue
        with path.open(encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        if doc is None:
            continue  # empty file is allowed (e.g. a deferred stub)
        if not isinstance(doc, list):
            raise ValueError(
                f"{path}: expected a YAML list of rules, got {type(doc).__name__}"
            )
        rel = path.relative_to(sayc_dir).as_posix()
        for rule in doc:
            rule = dict(rule)
            rule["_file"] = rel
            rules.append(rule)
    return rules


# --- Validation ------------------------------------------------------------

# Suit-length predicate keys accepted inside a rule's ``hand`` block.
_LENGTH_KEYS = set(SUIT_NAMES)
# Integer-count predicates whose value is a [min, max] pair.
_COUNT_KEYS = {"aces", "kings"}
# Boolean feature predicates.
_BOOL_KEYS = {"balanced", "rule_of_20", "rule_of_15"}
# Comparison predicates: value is a [suitA, suitB] pair of suit names.
_COMPARE_KEYS = {"longer_than", "atleast_as_long_as"}
_VULN_VALUES = {"none", "we", "they", "both", "any"}


def validate_rule(rule: dict[str, Any]) -> list[str]:
    """Validate one rule mapping; return a list of human-readable problems.

    An empty list means the rule is well-formed. This is a manual validator
    (no extra dependency) covering the fields the matcher relies on.
    """
    problems: list[str] = []
    where = rule.get("id", rule.get("_file", "<unknown rule>"))

    # Required top-level fields.
    for key in ("id", "call", "why"):
        if key not in rule:
            problems.append(f"{where}: missing required field '{key}'")
    if "call" in rule and not isinstance(rule["call"], str):
        problems.append(f"{where}: 'call' must be a string")
    if "priority" in rule and not isinstance(rule["priority"], int):
        problems.append(f"{where}: 'priority' must be an int")
    if "alertable" in rule and not isinstance(rule["alertable"], bool):
        problems.append(f"{where}: 'alertable' must be a bool")

    # 'when' block.
    when = rule.get("when", {})
    if not isinstance(when, dict):
        problems.append(f"{where}: 'when' must be a mapping")
        when = {}
    if "auction" in when and not isinstance(when["auction"], list):
        problems.append(f"{where}: when.auction must be a list of calls")
    if "seat" in when:
        seats = when["seat"]
        if not isinstance(seats, list) or not all(s in (1, 2, 3, 4) for s in seats):
            problems.append(f"{where}: when.seat must be a list drawn from 1..4")
    if "vulnerability" in when and when["vulnerability"] not in _VULN_VALUES:
        problems.append(
            f"{where}: when.vulnerability must be one of {sorted(_VULN_VALUES)}"
        )

    # 'hand' block predicates.
    hand = rule.get("hand", {})
    if not isinstance(hand, dict):
        problems.append(f"{where}: 'hand' must be a mapping")
        hand = {}
    for key, val in hand.items():
        if key == "hcp" or key in _LENGTH_KEYS or key in _COUNT_KEYS:
            if not (isinstance(val, list) and len(val) == 2):
                problems.append(f"{where}: hand.{key} must be a [min, max] pair")
        elif key in _BOOL_KEYS:
            if not isinstance(val, bool):
                problems.append(f"{where}: hand.{key} must be a bool")
        elif key in _COMPARE_KEYS:
            if not (
                isinstance(val, list)
                and len(val) == 2
                and all(s in SUIT_NAMES for s in val)
            ):
                problems.append(
                    f"{where}: hand.{key} must be [suitA, suitB] of suit names"
                )
        elif key == "longest_suit":
            if val not in SUIT_NAMES:
                problems.append(
                    f"{where}: hand.longest_suit must be one of {sorted(SUIT_NAMES)}"
                )
        else:
            problems.append(f"{where}: unknown hand predicate '{key}'")
    return problems


def validate_rules(rules: list[dict[str, Any]]) -> list[str]:
    """Validate a list of rules; return all problems found, and flag dup ids."""
    problems: list[str] = []
    seen: set[str] = set()
    for rule in rules:
        problems.extend(validate_rule(rule))
        rid = rule.get("id")
        if isinstance(rid, str):
            if rid in seen:
                problems.append(f"duplicate rule id '{rid}'")
            seen.add(rid)
    return problems


# --- Matching --------------------------------------------------------------


def seat_from_auction(auction: list[str]) -> int:
    """Infer the seat (1-4) of the player about to call from the auction.

    Bridge intent: the dealer is seat 1; each subsequent call advances the
    seat. With ``n`` calls already made, the next caller is seat
    ``n mod 4 + 1``.
    """
    return len(auction) % 4 + 1


def _auction_matches(pattern: list[str], auction: list[str]) -> bool:
    """Return True if ``pattern`` matches the auction context.

    - An empty pattern means "no genuine call has been made yet" — every prior
      call is a pass — i.e. this player is making the *opening* call.
    - Otherwise the pattern is matched against the *end* (suffix) of the
      auction so leading passes (from earlier seats) are ignored. ``"*"`` in
      the pattern matches any single call.
    """
    if not pattern:
        return all(call.upper() in PASS_CALLS for call in auction)
    if len(auction) < len(pattern):
        return False
    tail = auction[-len(pattern) :]
    return all(p == "*" or p == got for p, got in zip(pattern, tail, strict=True))


def _hand_matches(hand_pred: dict[str, Any], features: dict[str, Any]) -> bool:
    """Return True if a hand's features satisfy every predicate in ``hand_pred``."""
    lengths: dict[str, int] = features["lengths"]
    for key, val in hand_pred.items():
        if key == "hcp":
            lo, hi = val
            if not (lo <= features["hcp"] <= hi):
                return False
        elif key in _COUNT_KEYS:
            lo, hi = val
            if not (lo <= features[key] <= hi):
                return False
        elif key in SUIT_NAMES:
            lo, hi = val
            if not (lo <= lengths[SUIT_NAMES[key]] <= hi):
                return False
        elif key in _BOOL_KEYS:
            if features[key] != val:
                return False
        elif key == "longest_suit":
            target = SUIT_NAMES[val]
            if any(lengths[s] > lengths[target] for s in SUITS):
                return False
        elif key == "longer_than":
            a, b = (SUIT_NAMES[s] for s in val)
            if not (lengths[a] > lengths[b]):
                return False
        elif key == "atleast_as_long_as":
            a, b = (SUIT_NAMES[s] for s in val)
            if not (lengths[a] >= lengths[b]):
                return False
        else:
            # Unknown predicate: be conservative and refuse to match. The
            # validator surfaces this as an error separately.
            return False
    return True


def _context_matches(
    rule: dict[str, Any],
    auction: list[str],
    seat: int,
    vulnerability: str,
) -> bool:
    """Return True if a rule's ``when`` block fits the current auction context."""
    when = rule.get("when", {})
    if not _auction_matches(when.get("auction", []), auction):
        return False
    if "seat" in when and seat not in when["seat"]:
        return False
    rule_vuln = when.get("vulnerability", "any")
    if rule_vuln != "any" and vulnerability != "any" and rule_vuln != vulnerability:
        return False
    return True


def match_rules(
    rules: list[dict[str, Any]],
    hand: dict[str, str],
    auction: list[str] | None = None,
    seat: int | None = None,
    vulnerability: str = "any",
) -> list[dict[str, Any]]:
    """Return the rules that apply, ranked best-first by ``priority``.

    Parameters
    ----------
    rules:
        The loaded SAYC rules.
    hand:
        The hand to bid (suit-letter -> ranks string).
    auction:
        Calls made so far (oldest first); defaults to an empty auction.
    seat:
        Seat (1-4) of the player to call; inferred from the auction if omitted.
    vulnerability:
        ``none``/``we``/``they``/``both``/``any`` (default ``any``).

    Returns
    -------
    list[dict]
        One entry per matching rule: ``{"id", "call", "priority", "why",
        "alertable", "source"}``, sorted by descending priority (ties keep
        the data file's order, which is the conventional preference order).
    """
    auction = auction or []
    if seat is None:
        seat = seat_from_auction(auction)
    features = compute_features(hand)

    candidates: list[dict[str, Any]] = []
    for rule in rules:
        if not _context_matches(rule, auction, seat, vulnerability):
            continue
        if not _hand_matches(rule.get("hand", {}), features):
            continue
        candidates.append(
            {
                "id": rule.get("id"),
                "call": rule["call"],
                "priority": rule.get("priority", 0),
                "why": rule.get("why", ""),
                "alertable": rule.get("alertable", False),
                "source": rule.get("source", ""),
            }
        )

    # Stable sort by descending priority: equal-priority rules keep load order.
    candidates.sort(key=lambda c: c["priority"], reverse=True)
    return candidates


def choose_call(
    rules: list[dict[str, Any]],
    hand: dict[str, str],
    auction: list[str] | None = None,
    seat: int | None = None,
    vulnerability: str = "any",
) -> str:
    """Return the single best call for a hand, or ``"P"`` if no rule applies.

    This is the externally-facing decision: it ranks candidates internally
    (see :func:`match_rules`) and returns only the top call. With no matching
    rule the SAYC default is to pass.
    """
    candidates = match_rules(rules, hand, auction, seat, vulnerability)
    return candidates[0]["call"] if candidates else "P"
