"""Infer hand constraints from the bidding by *inverting* the SAYC rules.

The SAYC matcher (``bridge.bidding_systems.sayc_loader``) is *forward*: a known
hand plus auction context yields a ranked list of candidate calls, and the
highest-priority candidate is chosen. Inference runs that backwards.

Given an **observed** call in a known context (the auction so far, the seat,
and vulnerability), we ask the rule set two questions:

**Positive** — which rules could have *produced* this call? The caller's hand
must satisfy at least one of their ``hand`` blocks, so the sound (loosest)
positive inference is the **envelope** of those blocks: a constraint key is
kept only if every candidate rule constrains it, bounded by the widest range
they collectively allow.

**Negative (denials)** — the matcher picks the *highest-priority* matching
rule, so any context-matching rule with strictly higher priority and a
*different* call must have failed on the hand. Negating a rule's conjunctive
``hand`` block is in general a disjunction that does not fit our intersectable
constraint dict, so we split denials into two tiers:

- **foldable** — the denied block reduces to a single one-sided bound
  (chiefly point caps, e.g. "did not bid 2C => <=21 HCP"); we negate it into a
  tightened bound that merges into the numeric profile;
- **annotation-only** — genuinely multi-predicate denials (e.g. "not balanced
  15-17") are recorded with a reason but contribute no numeric bound.

The opening **pass** is handled specially: passing denies every opening, and
since SAYC opens all 13+ HCP hands the sound, foldable inference is a clean
HCP cap (<= 12), which per-rule negation alone would not surface.

Per CLAUDE.md these are module-level functions over simple data; we reuse the
loader's context matcher and feature vocabulary rather than re-deriving them.
"""

from __future__ import annotations

from typing import Any

from bridge.bidding_systems import sayc_loader as sl

from . import knowledge_base as kb_mod
from .knowledge_base import BOOL_KEYS, RANGE_MAX

# --- Tunable constants -----------------------------------------------------

# Confidence for a positive inference backed by a single matching rule.
SINGLE_RULE_CONFIDENCE: float = 0.95

# Floor for ambiguous positives (many divergent rules produce the same call).
MIN_POSITIVE_CONFIDENCE: float = 0.6

# Denials assume the opponent bid *exactly* our SAYC priorities, so they are
# more brittle than positive inferences (Q8): discount them.
DENIAL_DISCOUNT: float = 0.8

# An opening pass is a sound domain fact (SAYC opens all 13+ HCP hands), so it
# is more reliable than a single-rule denial.
PASS_CAP_CONFIDENCE: float = 0.85

# Highest HCP consistent with passing as dealer/opener in SAYC.
OPENING_PASS_MAX_HCP: int = 12

# Map a rule's long suit-name length predicates to constraint suit letters.
_SUIT_NAME_TO_LETTER = sl.SUIT_NAMES  # {"spades": "S", ...}


# --- Translating a rule's hand block into an absolute constraint -----------


def rule_constraint(hand_pred: dict[str, Any]) -> dict[str, Any]:
    """Extract the *absolute* part of a rule's ``hand`` block as a constraint.

    Keeps ``hcp``, ``aces``, ``kings``, the four suit lengths (translated from
    long suit names to letters), and the boolean features. Relational
    predicates (``longest_suit``, ``longer_than``, ``atleast_as_long_as``) are
    dropped because they cannot be folded into independent per-suit ranges;
    they survive only in human reason text. Lists are copied so callers cannot
    mutate the rule data.
    """
    constraint: dict[str, Any] = {}
    for key, val in hand_pred.items():
        if key == "hcp" or key in ("aces", "kings"):
            constraint[key] = list(val)
        elif key in _SUIT_NAME_TO_LETTER:  # "spades" -> "S"
            constraint[_SUIT_NAME_TO_LETTER[key]] = list(val)
        elif key in BOOL_KEYS:
            constraint[key] = val
        # else: relational predicate -> deliberately omitted (see docstring).
    return constraint


def _fold_denial(constraint: dict[str, Any]) -> dict[str, Any] | None:
    """Negate a denied constraint into a positive bound, if it is foldable.

    Foldable iff the denied constraint has exactly one key and that key is a
    boolean, or a one-sided range touching a global extreme. Returns the
    equivalent positive constraint, or ``None`` when the negation would be a
    disjunction (a two-sided interior range, or multiple predicates).
    """
    keys = list(constraint)
    if len(keys) != 1:
        return None
    key = keys[0]
    value = constraint[key]
    if key in BOOL_KEYS:
        return {key: not value}
    lo, hi = value
    maximum = RANGE_MAX[key]
    if hi >= maximum and lo > 0:
        # Denied [lo, max] -> hand lies below the band: [0, lo - 1].
        return {key: [0, lo - 1]}
    if lo <= 0 and hi < maximum:
        # Denied [0, hi] -> hand lies above the band: [hi + 1, max].
        return {key: [hi + 1, maximum]}
    return None


# --- Human-readable description of a constraint ----------------------------

_SUIT_FULL = {"S": "spades", "H": "hearts", "D": "diamonds", "C": "clubs"}
_BOOL_PHRASE = {
    ("balanced", True): "balanced",
    ("balanced", False): "unbalanced",
    ("rule_of_20", True): "Rule of 20",
    ("rule_of_20", False): "not Rule of 20",
    ("rule_of_15", True): "Rule of 15",
    ("rule_of_15", False): "not Rule of 15",
}


def _describe_range(label: str, lo: int, hi: int, maximum: int) -> str:
    """Render a ``[lo, hi]`` range against its maximum as a compact phrase."""
    if lo == hi:
        return f"exactly {lo} {label}"
    if lo <= 0:
        return f"<={hi} {label}"
    if hi >= maximum:
        return f"{lo}+ {label}"
    return f"{lo}-{hi} {label}"


def describe_constraint(constraint: dict[str, Any]) -> str:
    """Return a short human phrase for a constraint, e.g. ``'15-17 HCP, balanced'``."""
    parts: list[str] = []
    if "hcp" in constraint:
        lo, hi = constraint["hcp"]
        parts.append(_describe_range("HCP", lo, hi, RANGE_MAX["hcp"]))
    for letter in ("S", "H", "D", "C"):
        if letter in constraint:
            lo, hi = constraint[letter]
            parts.append(_describe_range(_SUIT_FULL[letter], lo, hi, 13))
    for count in ("aces", "kings"):
        if count in constraint:
            lo, hi = constraint[count]
            parts.append(_describe_range(count, lo, hi, RANGE_MAX[count]))
    for boolean in BOOL_KEYS:
        if boolean in constraint:
            parts.append(_BOOL_PHRASE[(boolean, constraint[boolean])])
    return ", ".join(parts) if parts else "nothing specific"


# --- Selecting candidate / denied rules ------------------------------------


def _is_pass(call: str) -> bool:
    """Return True if a call is a pass (P / PASS)."""
    return call.upper() in sl.PASS_CALLS


def candidate_rules_for_call(
    rules: list[dict[str, Any]],
    call: str,
    auction_before: list[str],
    seat: int,
    vulnerability: str = "any",
) -> list[dict[str, Any]]:
    """Return the rules that could have *produced* ``call`` in this context.

    A rule qualifies when its ``when`` block fits the auction-so-far, seat and
    vulnerability (reusing the loader's context matcher) and its ``call``
    equals the observed call.
    """
    return [
        rule
        for rule in rules
        if rule.get("call") == call
        and sl._context_matches(rule, auction_before, seat, vulnerability)
    ]


def denied_rules_for_call(
    rules: list[dict[str, Any]],
    call: str,
    auction_before: list[str],
    seat: int,
    vulnerability: str = "any",
) -> list[dict[str, Any]]:
    """Return rules denied by choosing ``call``: context-matching rules with a
    different call and *strictly higher* priority than the chosen call's best
    rule.

    Returns ``[]`` if no rule explains ``call`` (we cannot bound denials
    without knowing why the call was made). Equal-priority rules are excluded:
    neither is strictly preferred, so a denial there would be unsound.
    """
    context_rules = [
        rule
        for rule in rules
        if sl._context_matches(rule, auction_before, seat, vulnerability)
    ]
    chosen = [rule for rule in context_rules if rule.get("call") == call]
    if not chosen:
        return []
    chosen_priority = max(rule.get("priority", 0) for rule in chosen)
    return [
        rule
        for rule in context_rules
        if rule.get("call") != call and rule.get("priority", 0) > chosen_priority
    ]


# --- Building inference records --------------------------------------------


def _positive_confidence(num_rules: int) -> float:
    """Grade positive confidence by how ambiguous the call is (Q6).

    One matching rule is the cleanest read; each additional divergent rule
    that produces the same call widens the envelope and lowers confidence,
    down to a floor.
    """
    if num_rules <= 1:
        return SINGLE_RULE_CONFIDENCE
    return max(MIN_POSITIVE_CONFIDENCE, SINGLE_RULE_CONFIDENCE - 0.1 * (num_rules - 1))


def _envelope(constraints: list[dict[str, Any]]) -> dict[str, Any]:
    """Loosest constraint satisfied by *any* of the inputs (a sound OR-bound).

    A key is kept only if every input constrains it (otherwise some producing
    rule leaves it free); ranges widen to ``[min(min), max(max)]`` and booleans
    survive only when all inputs agree.
    """
    if not constraints:
        return {}
    common = set(constraints[0])
    for constraint in constraints[1:]:
        common &= set(constraint)
    envelope: dict[str, Any] = {}
    for key in common:
        if key in BOOL_KEYS:
            values = {c[key] for c in constraints}
            if len(values) == 1:
                envelope[key] = next(iter(values))
        else:
            envelope[key] = [
                min(c[key][0] for c in constraints),
                max(c[key][1] for c in constraints),
            ]
    return envelope


def infer_positive(
    rules: list[dict[str, Any]],
    call: str,
    auction_before: list[str],
    seat: int,
    vulnerability: str,
    auction_index: int,
) -> dict[str, Any]:
    """Build the positive inference record for an observed (non-pass) call.

    Returns one inference record. When no rule explains the call the record
    carries an empty constraint, zero confidence and a flag in its reason so
    the gap is visible rather than silently dropped.
    """
    candidates = candidate_rules_for_call(
        rules, call, auction_before, seat, vulnerability
    )
    if not candidates:
        return {
            "constraint": {},
            "confidence": 0.0,
            "reason": f"{call}: no SAYC rule explains this call in context (unread).",
            "bidding": True,
            "play": False,
            "violated": False,
            "negated": False,
            "foldable": False,
            "call": call,
            "auction_index": auction_index,
            "rule_ids": [],
        }

    constraints = [rule_constraint(rule.get("hand", {})) for rule in candidates]
    envelope = _envelope(constraints)
    # Lead the reason with the highest-priority candidate's own explanation.
    top = max(candidates, key=lambda r: r.get("priority", 0))
    reason = f"{call}: {top.get('why', describe_constraint(envelope))}"
    if len(candidates) > 1:
        reason += f" (one of {len(candidates)} SAYC rules for this call)"
    return {
        "constraint": envelope,
        "confidence": _positive_confidence(len(candidates)),
        "reason": reason,
        "bidding": True,
        "play": False,
        "violated": False,
        "negated": False,
        "foldable": False,
        "call": call,
        "auction_index": auction_index,
        "rule_ids": [r.get("id") for r in candidates],
    }


def _denial_record(
    denied_rule: dict[str, Any],
    call: str,
    auction_index: int,
) -> dict[str, Any]:
    """Build one denial inference record from a denied higher-priority rule."""
    denied = rule_constraint(denied_rule.get("hand", {}))
    folded = _fold_denial(denied)
    base = {
        "bidding": True,
        "play": False,
        "violated": False,
        "negated": True,
        "denied": denied,
        "call": call,
        "auction_index": auction_index,
        "rule_ids": [denied_rule.get("id")],
        "confidence": round(SINGLE_RULE_CONFIDENCE * DENIAL_DISCOUNT, 4),
    }
    denied_call = denied_rule.get("call", "?")
    if folded is not None:
        base["constraint"] = folded
        base["foldable"] = True
        base["reason"] = (
            f"Did not bid {denied_call}: denies "
            f"{describe_constraint(denied)} => {describe_constraint(folded)}."
        )
    else:
        base["constraint"] = {}
        base["foldable"] = False
        base["reason"] = (
            f"Did not bid {denied_call}: denies {describe_constraint(denied)}."
        )
    return base


def infer_negatives(
    rules: list[dict[str, Any]],
    call: str,
    auction_before: list[str],
    seat: int,
    vulnerability: str,
    auction_index: int,
) -> list[dict[str, Any]]:
    """Build the denial inference records implied by an observed call.

    For a normal call: one record per strictly-higher-priority, different-call
    rule. For an *opening* pass: a single foldable HCP cap (<= 12), the sound
    union inference that per-rule negation cannot produce. A non-opening pass
    yields no denials (our v1 SAYC rules do not model later passes).
    """
    if _is_pass(call):
        # Opening context: every prior call is a pass (no genuine bid yet).
        if not sl._auction_matches([], auction_before):
            return []
        return [
            {
                "constraint": {"hcp": [0, OPENING_PASS_MAX_HCP]},
                "confidence": PASS_CAP_CONFIDENCE,
                "reason": (
                    f"Passed in seat {seat}: denies an opening bid "
                    f"(<= {OPENING_PASS_MAX_HCP} HCP; SAYC opens all 13+ hands). "
                    "Light/shapely 10-12 openers are a known exception."
                ),
                "bidding": True,
                "play": False,
                "violated": False,
                "negated": True,
                "foldable": True,
                "denied": {"hcp": [13, RANGE_MAX["hcp"]]},
                "call": call,
                "auction_index": auction_index,
                "rule_ids": [],
            }
        ]
    denied_rules = denied_rules_for_call(
        rules, call, auction_before, seat, vulnerability
    )
    return [_denial_record(rule, call, auction_index) for rule in denied_rules]


# --- Walking a whole auction -----------------------------------------------


def infer_from_auction(
    rules: list[dict[str, Any]],
    auction: list[str],
    dealer: str = "N",
    vulnerability: str = "any",
    kb: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Populate a knowledge base by inferring from every call in an auction.

    Steps call-by-call: derive the caller's seat from the calls *before* it,
    map the seat to a table position from ``dealer``, run positive inference
    (skipped for passes, which carry only denials) and negative inference, and
    store each record. After the walk, ``mark_violations`` flags any call whose
    implied hand contradicts that player's earlier consensus.

    Parameters
    ----------
    rules:
        Loaded SAYC rules (``sayc_loader.load_rules()``).
    auction:
        Calls in order, oldest first (e.g. ``["1NT", "P", "2C", "P"]``).
    dealer:
        Position of seat 1; defaults to North.
    vulnerability:
        ``none/we/they/both/any`` (default ``any``).
    kb:
        An existing KB to extend; a fresh one is created if omitted.

    Returns
    -------
    dict
        The populated knowledge base.
    """
    if kb is None:
        kb = kb_mod.empty_kb()
    for index, call in enumerate(auction):
        auction_before = auction[:index]
        seat = sl.seat_from_auction(auction_before)
        position = kb_mod.seat_to_position(dealer, seat)
        records: list[dict[str, Any]] = []
        if not _is_pass(call):
            records.append(
                infer_positive(rules, call, auction_before, seat, vulnerability, index)
            )
        records.extend(
            infer_negatives(rules, call, auction_before, seat, vulnerability, index)
        )
        for record in records:
            kb_mod.add_inference(kb, position, record)
    kb_mod.mark_violations(kb)
    return kb
