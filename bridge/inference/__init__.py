"""Bidding-inference engine: deduce hand constraints from an auction.

This package watches an auction and, by *inverting* the SAYC bidding rules,
records what each call reveals about the caller's hand into a knowledge base.

- :mod:`bridge.inference.knowledge_base` — the KB structure, constraint
  merging, contradiction/violation detection, and JSON persistence.
- :mod:`bridge.inference.bidding` — turning observed calls into positive and
  negative (denial) inferences, and walking a whole auction.
"""

from __future__ import annotations

from .bidding import (
    candidate_rules_for_call,
    denied_rules_for_call,
    describe_constraint,
    infer_from_auction,
    infer_negatives,
    infer_positive,
    rule_constraint,
)
from .knowledge_base import (
    ContradictionError,
    add_inference,
    empty_kb,
    fold_constraints,
    hand_profile,
    mark_violations,
    merge_constraints,
    read_knowledge_base,
    seat_to_position,
    write_knowledge_base,
)

__all__ = [
    "ContradictionError",
    "add_inference",
    "candidate_rules_for_call",
    "denied_rules_for_call",
    "describe_constraint",
    "empty_kb",
    "fold_constraints",
    "hand_profile",
    "infer_from_auction",
    "infer_negatives",
    "infer_positive",
    "mark_violations",
    "merge_constraints",
    "read_knowledge_base",
    "rule_constraint",
    "seat_to_position",
    "write_knowledge_base",
]
