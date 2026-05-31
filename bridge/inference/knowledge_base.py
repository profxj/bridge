"""The bidding-inference *knowledge base* (KB): structure, merging, I/O.

A bot watching an auction accumulates *inferences* about the other players'
hands. We store them in a knowledge base shaped as a dict of dicts::

    kb[position][inference_id] = inference_record

The first level is keyed by table position (``"N"``, ``"E"``, ``"S"``,
``"W"``); the second by an auto-generated inference id. Each
``inference_record`` is a plain dict (see ``prompts/bidding_inferences.md``)::

    {
        "constraint": {...},   # absolute, intersectable hand bounds
        "confidence": float,   # 0..1
        "reason": str,         # human-readable explanation
        "bidding": bool,       # derived from the auction
        "play": bool,          # derived from card play (always False for now)
        "violated": bool,      # later evidence contradicts this inference
        "negated": bool,       # True => this is a denial
        "foldable": bool,      # denial that tightens the numeric profile
        "denied": {...},       # (denials) the raw denied hand block, for display
        "call": str,           # the call that produced the inference
        "auction_index": int,  # index of that call in the auction
        "rule_ids": [str],     # SAYC rule ids backing the inference
    }

A *constraint* is the machine-usable core: a dict whose keys are drawn from a
small, fixed vocabulary of **absolute** hand facts (so two constraints can be
intersected by simple range/boolean logic):

- ``hcp``, ``aces``, ``kings`` and the four suit letters ``S H D C`` map to a
  ``[min, max]`` pair;
- ``balanced``, ``rule_of_20``, ``rule_of_15`` map to a bool.

Relational rule predicates (``longest_suit``, ``longer_than``,
``atleast_as_long_as``) are *not* absolute — they cannot be folded into a
per-suit range independently — so they are deliberately omitted from the
constraint vocabulary and surface only in the human ``reason`` text.

Per CLAUDE.md these are module-level functions over simple data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# --- Constants -------------------------------------------------------------

# Table positions in clockwise order. Seat 1 (the dealer) maps to some
# position; each later seat advances one step clockwise.
POSITIONS: tuple[str, ...] = ("N", "E", "S", "W")

# Constraint keys whose value is a ``[min, max]`` integer pair.
RANGE_KEYS: tuple[str, ...] = ("hcp", "S", "H", "D", "C", "aces", "kings")

# Constraint keys whose value is a bool.
BOOL_KEYS: tuple[str, ...] = ("balanced", "rule_of_20", "rule_of_15")

# The maximum each range key can take, used when negating one-sided denials
# and as the open upper bound of a fresh constraint.
RANGE_MAX: dict[str, int] = {
    "hcp": 40,
    "S": 13,
    "H": 13,
    "D": 13,
    "C": 13,
    "aces": 4,
    "kings": 4,
}


class ContradictionError(ValueError):
    """Raised when two constraints cannot be satisfied simultaneously.

    Bridge intent: a later call (or a misread/psych) implies a hand that is
    incompatible with what earlier calls implied — e.g. disjoint HCP ranges.
    """


# --- Construction ----------------------------------------------------------


def empty_kb() -> dict[str, dict[str, dict[str, Any]]]:
    """Return a fresh, empty knowledge base keyed by the four positions.

    Returns
    -------
    dict
        ``{"N": {}, "E": {}, "S": {}, "W": {}}`` — each an empty mapping of
        inference id -> inference record.
    """
    return {pos: {} for pos in POSITIONS}


def seat_to_position(dealer: str, seat: int) -> str:
    """Map a 1-based seat to a table position given who dealt.

    Parameters
    ----------
    dealer:
        Position of seat 1 (the dealer): one of ``"N" "E" "S" "W"``.
    seat:
        Seat number 1-4 (1 = dealer), as produced by
        ``sayc_loader.seat_from_auction``.

    Returns
    -------
    str
        The position (``N/E/S/W``) sitting in that seat, advancing clockwise
        N -> E -> S -> W from the dealer.
    """
    if dealer not in POSITIONS:
        raise ValueError(f"dealer must be one of {POSITIONS}, got {dealer!r}")
    if seat not in (1, 2, 3, 4):
        raise ValueError(f"seat must be 1..4, got {seat!r}")
    return POSITIONS[(POSITIONS.index(dealer) + seat - 1) % 4]


def add_inference(
    kb: dict[str, dict[str, dict[str, Any]]],
    position: str,
    record: dict[str, Any],
) -> str:
    """Store one inference record under a position and return its id.

    The id is generated deterministically from the position's current size
    (so runs are reproducible — no clocks or RNG) combined with the call and
    polarity for readability, e.g. ``"03_1NT_pos"`` or ``"05_2C_neg"``.

    Parameters
    ----------
    kb:
        The knowledge base to mutate.
    position:
        One of ``N/E/S/W``.
    record:
        The inference record (see module docstring).

    Returns
    -------
    str
        The generated inference id (the key under ``kb[position]``).
    """
    if position not in kb:
        raise ValueError(f"unknown position {position!r}")
    ordinal = len(kb[position])
    polarity = "neg" if record.get("negated") else "pos"
    inference_id = f"{ordinal:02d}_{record.get('call', '?')}_{polarity}"
    kb[position][inference_id] = record
    return inference_id


# --- Merging / folding -----------------------------------------------------


def merge_constraints(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Intersect two constraint dicts into their tightest common constraint.

    Range keys take ``[max(min), min(max)]``; boolean keys must agree. Keys
    present in only one side carry through unchanged. The empty dict is the
    identity element, so a list of constraints can be folded with this.

    Raises
    ------
    ContradictionError
        If a range collapses (min > max) or two booleans disagree.
    """
    out: dict[str, Any] = {}
    for key in set(a) | set(b):
        if key in a and key in b:
            if key in RANGE_KEYS:
                lo = max(a[key][0], b[key][0])
                hi = min(a[key][1], b[key][1])
                if lo > hi:
                    raise ContradictionError(
                        f"{key}: ranges {a[key]} and {b[key]} do not overlap"
                    )
                out[key] = [lo, hi]
            elif key in BOOL_KEYS:
                if a[key] != b[key]:
                    raise ContradictionError(f"{key}: {a[key]} contradicts {b[key]}")
                out[key] = a[key]
            else:  # pragma: no cover - vocabulary is fixed above
                out[key] = a[key]
        else:
            out[key] = a.get(key, b.get(key))
    return out


def fold_constraints(constraints: list[dict[str, Any]]) -> dict[str, Any]:
    """Intersect a list of constraints into one (left fold of merge).

    Raises ``ContradictionError`` if the set is jointly unsatisfiable.
    """
    result: dict[str, Any] = {}
    for constraint in constraints:
        result = merge_constraints(result, constraint)
    return result


def hand_profile(
    kb: dict[str, dict[str, dict[str, Any]]],
    position: str,
) -> dict[str, Any]:
    """Summarise everything currently known about one player's hand.

    Folds the ``constraint`` of every *non-violated* inference for the
    position into a single intersected picture, and gathers the human reasons
    of annotation-only denials (which carry no foldable numeric bound)
    separately.

    Returns
    -------
    dict
        ``{"constraint": {...}, "satisfiable": bool, "annotations": [str],
        "min_confidence": float, "based_on": [inference_id]}``.
    """
    foldable: list[dict[str, Any]] = []
    ids: list[str] = []
    annotations: list[str] = []
    confidences: list[float] = []
    for inference_id, record in kb.get(position, {}).items():
        if record.get("violated"):
            continue
        confidences.append(record.get("confidence", 0.0))
        # Annotation-only denials contribute prose, not numeric bounds.
        if record.get("negated") and not record.get("foldable"):
            annotations.append(record.get("reason", ""))
            continue
        if record.get("constraint"):
            foldable.append(record["constraint"])
            ids.append(inference_id)

    satisfiable = True
    try:
        constraint = fold_constraints(foldable)
    except ContradictionError:
        # Should not happen once mark_violations has run, but stay robust.
        satisfiable = False
        constraint = {}

    return {
        "constraint": constraint,
        "satisfiable": satisfiable,
        "annotations": annotations,
        "min_confidence": min(confidences) if confidences else 1.0,
        "based_on": ids,
    }


def mark_violations(kb: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    """Flag inferences that contradict earlier, more-established ones.

    Walks each position's foldable inferences in storage order (which is
    auction order) and greedily folds them. The first inference that would
    make the running profile unsatisfiable is marked ``violated=True`` and
    skipped, so the *earlier consensus* is kept and the offending later call
    is the one flagged. Returns the ids that were marked.

    Bridge intent: a player whose later bid is inconsistent with the hand
    their earlier bids promised has (in our SAYC model) psyched or erred; we
    record the conflict rather than silently dropping information.
    """
    flagged: list[str] = []
    for position in kb:
        running: dict[str, Any] = {}
        for inference_id, record in kb[position].items():
            if record.get("negated") and not record.get("foldable"):
                continue  # annotations never participate in folding
            constraint = record.get("constraint")
            if not constraint:
                continue
            try:
                running = merge_constraints(running, constraint)
                record["violated"] = False
            except ContradictionError:
                record["violated"] = True
                flagged.append(inference_id)
    return flagged


# --- Persistence -----------------------------------------------------------


def write_knowledge_base(
    kb: dict[str, dict[str, dict[str, Any]]],
    path: str | Path,
) -> None:
    """Write the knowledge base to ``path`` as indented JSON.

    The KB uses only JSON-native types (dicts, lists, strings, numbers,
    bools), so this is a faithful round-trip with ``read_knowledge_base``.
    """
    path = Path(path)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(kb, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def read_knowledge_base(path: str | Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Read a knowledge base previously written by ``write_knowledge_base``."""
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data
