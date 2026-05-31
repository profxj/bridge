"""Tests for inferring hand constraints from the bidding (rule inversion)."""

import pytest

from bridge.bidding_systems import sayc_loader as sl
from bridge.inference import bidding as bi
from bridge.inference import knowledge_base as kb_mod


@pytest.fixture(scope="module")
def rules():
    return sl.load_rules()


# --- translating rule predicates into absolute constraints -----------------


def test_rule_constraint_translates_and_drops_relational():
    # Suit names become letters; the relational predicate is dropped.
    hand_pred = {"hcp": [13, 21], "spades": [5, 13], "longest_suit": "spades"}
    assert bi.rule_constraint(hand_pred) == {"hcp": [13, 21], "S": [5, 13]}
    assert bi.rule_constraint({"hcp": [15, 17], "balanced": True}) == {
        "hcp": [15, 17],
        "balanced": True,
    }


def test_fold_denial_one_sided_and_interior():
    # Denying 22+ HCP caps the hand at 21 (one-sided -> foldable).
    assert bi._fold_denial({"hcp": [22, 40]}) == {"hcp": [0, 21]}
    # Denying a 5+ suit caps it at 4.
    assert bi._fold_denial({"S": [5, 13]}) == {"S": [0, 4]}
    # A two-sided interior band negates to a disjunction -> not foldable.
    assert bi._fold_denial({"hcp": [15, 17]}) is None
    # Multiple predicates -> not foldable.
    assert bi._fold_denial({"hcp": [15, 17], "balanced": True}) is None
    # A boolean negates cleanly.
    assert bi._fold_denial({"balanced": True}) == {"balanced": False}


# --- candidate / denied rule selection -------------------------------------


def test_candidate_rules_for_1nt_opening(rules):
    cands = bi.candidate_rules_for_call(rules, "1NT", [], 1, "any")
    assert [r["id"] for r in cands] == ["open_1nt"]


def test_denied_rules_for_1nt_are_strictly_higher(rules):
    denied = {r["id"] for r in bi.denied_rules_for_call(rules, "1NT", [], 1, "any")}
    # 2C (200) and 2NT (190) outrank 1NT (180); nothing equal/lower is denied.
    assert denied == {"open_2c_strong", "open_2nt"}


def test_denied_rules_empty_when_call_unexplained(rules):
    # A pass matches no rule's call, so we cannot bound denials this way.
    assert bi.denied_rules_for_call(rules, "P", [], 1, "any") == []


# --- positive inference ----------------------------------------------------


def test_infer_positive_1nt(rules):
    rec = bi.infer_positive(rules, "1NT", [], 1, "any", 0)
    assert rec["constraint"] == {"hcp": [15, 17], "balanced": True}
    assert rec["confidence"] == bi.SINGLE_RULE_CONFIDENCE
    assert rec["negated"] is False


def test_infer_positive_weak_two(rules):
    rec = bi.infer_positive(rules, "2H", [], 1, "any", 0)
    assert rec["constraint"] == {"hcp": [5, 11], "H": [6, 6]}


def test_infer_positive_jacoby_transfer(rules):
    # 2H over 1NT-P is a transfer showing 5+ spades.
    rec = bi.infer_positive(rules, "2H", ["1NT", "P"], 3, "any", 2)
    assert rec["constraint"] == {"S": [5, 13]}


def test_infer_positive_stayman_envelope_lowers_confidence(rules):
    # Two Stayman rules (4 spades / 4 hearts) produce 2C: envelope keeps only
    # the shared HCP band and the extra rule lowers confidence.
    rec = bi.infer_positive(rules, "2C", ["1NT", "P"], 3, "any", 2)
    assert rec["constraint"] == {"hcp": [8, 16]}
    assert rec["confidence"] < bi.SINGLE_RULE_CONFIDENCE


def test_infer_positive_unexplained_call_is_flagged(rules):
    rec = bi.infer_positive(rules, "5S", [], 1, "any", 0)
    assert rec["constraint"] == {}
    assert rec["confidence"] == 0.0
    assert "no SAYC rule" in rec["reason"]


def test_positive_confidence_grading():
    assert bi._positive_confidence(1) == bi.SINGLE_RULE_CONFIDENCE
    assert bi._positive_confidence(2) < bi._positive_confidence(1)
    assert bi._positive_confidence(50) == bi.MIN_POSITIVE_CONFIDENCE


# --- negative inference ----------------------------------------------------


def test_infer_negatives_one_suit_opening_caps_points(rules):
    negs = bi.infer_negatives(rules, "1S", [], 1, "any", 0)
    foldable = [n for n in negs if n["foldable"]]
    # The foldable denial is the 2C point cap.
    assert any(n["constraint"] == {"hcp": [0, 21]} for n in foldable)
    # Denials are discounted below a single-rule positive.
    assert all(n["confidence"] < bi.SINGLE_RULE_CONFIDENCE for n in negs)


def test_infer_negatives_opening_pass_caps_hcp(rules):
    negs = bi.infer_negatives(rules, "P", [], 1, "any", 0)
    assert len(negs) == 1
    cap = negs[0]
    assert cap["constraint"] == {"hcp": [0, bi.OPENING_PASS_MAX_HCP]}
    assert cap["foldable"] is True
    assert cap["confidence"] == bi.PASS_CAP_CONFIDENCE


def test_infer_negatives_non_opening_pass_is_silent(rules):
    # A pass after partner has opened is not modelled in v1 -> no denial.
    assert bi.infer_negatives(rules, "P", ["1NT", "P"], 3, "any", 2) == []


# --- whole-auction walk ----------------------------------------------------


def test_infer_from_auction_assigns_positions_and_constraints(rules):
    kb = bi.infer_from_auction(rules, ["1NT", "P", "2C", "P"], dealer="N")
    # North opened 1NT.
    north = kb_mod.hand_profile(kb, "N")
    assert north["constraint"] == {"hcp": [15, 17], "balanced": True}
    # South used Stayman: 8-16 HCP, and denying the transfers caps both majors.
    south = kb_mod.hand_profile(kb, "S")
    assert south["constraint"]["hcp"] == [8, 16]
    assert south["constraint"]["S"] == [0, 4]
    assert south["constraint"]["H"] == [0, 4]
    # The passing opponents carry no inference.
    assert kb_mod.hand_profile(kb, "E")["constraint"] == {}
    assert kb_mod.hand_profile(kb, "W")["constraint"] == {}


def test_infer_from_auction_dealer_offset(rules):
    # With East dealing, the 1NT opener sits East.
    kb = bi.infer_from_auction(rules, ["1NT", "P", "P", "P"], dealer="E")
    assert kb_mod.hand_profile(kb, "E")["constraint"] == {
        "hcp": [15, 17],
        "balanced": True,
    }
    # Seat-1 opener is East; the others passed in a live (post-opening) auction.
    assert kb_mod.hand_profile(kb, "N")["constraint"] == {}


def test_infer_from_auction_clean_has_no_violations(rules):
    kb = bi.infer_from_auction(rules, ["1NT", "P", "2C", "P", "2H", "P"], dealer="N")
    for pos in kb:
        for record in kb[pos].values():
            assert record["violated"] is False
