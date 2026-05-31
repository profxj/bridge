"""Tests for the inference knowledge base: structure, merging, violations, I/O."""

import pytest

from bridge.inference import knowledge_base as kb_mod
from bridge.inference.knowledge_base import ContradictionError


def _record(
    constraint,
    *,
    confidence=0.9,
    call="1NT",
    index=0,
    negated=False,
    foldable=False,
    reason="",
):
    """Build a minimal inference record for tests."""
    return {
        "constraint": constraint,
        "confidence": confidence,
        "reason": reason,
        "bidding": True,
        "play": False,
        "violated": False,
        "negated": negated,
        "foldable": foldable,
        "call": call,
        "auction_index": index,
        "rule_ids": [],
    }


# --- structure -------------------------------------------------------------


def test_empty_kb_has_four_positions():
    kb = kb_mod.empty_kb()
    assert set(kb) == {"N", "E", "S", "W"}
    assert all(kb[pos] == {} for pos in kb)


def test_seat_to_position_clockwise_from_north():
    assert [kb_mod.seat_to_position("N", s) for s in (1, 2, 3, 4)] == [
        "N",
        "E",
        "S",
        "W",
    ]


def test_seat_to_position_clockwise_from_east():
    # Dealer East: seat 1 is E, then S, W, and seat 4 wraps to N.
    assert [kb_mod.seat_to_position("E", s) for s in (1, 2, 3, 4)] == [
        "E",
        "S",
        "W",
        "N",
    ]


def test_seat_to_position_rejects_bad_input():
    with pytest.raises(ValueError):
        kb_mod.seat_to_position("X", 1)
    with pytest.raises(ValueError):
        kb_mod.seat_to_position("N", 5)


def test_add_inference_stores_and_returns_id():
    kb = kb_mod.empty_kb()
    iid = kb_mod.add_inference(kb, "N", _record({"hcp": [15, 17]}))
    assert iid == "00_1NT_pos"
    assert kb["N"][iid]["constraint"] == {"hcp": [15, 17]}
    # A second, negated record gets a distinct, ordered id.
    iid2 = kb_mod.add_inference(kb, "N", _record({}, call="2C", negated=True))
    assert iid2 == "01_2C_neg"


# --- merging ---------------------------------------------------------------


def test_merge_ranges_intersect():
    merged = kb_mod.merge_constraints({"hcp": [13, 21]}, {"hcp": [0, 21]})
    assert merged == {"hcp": [13, 21]}
    merged = kb_mod.merge_constraints({"hcp": [11, 21]}, {"hcp": [15, 17]})
    assert merged == {"hcp": [15, 17]}


def test_merge_carries_through_disjoint_keys():
    merged = kb_mod.merge_constraints({"hcp": [8, 16]}, {"S": [0, 4]})
    assert merged == {"hcp": [8, 16], "S": [0, 4]}


def test_merge_booleans_must_agree():
    assert kb_mod.merge_constraints({"balanced": True}, {"balanced": True}) == {
        "balanced": True
    }
    with pytest.raises(ContradictionError):
        kb_mod.merge_constraints({"balanced": True}, {"balanced": False})


def test_merge_disjoint_ranges_contradict():
    with pytest.raises(ContradictionError):
        kb_mod.merge_constraints({"hcp": [15, 17]}, {"hcp": [0, 12]})


def test_fold_constraints_identity_and_list():
    assert kb_mod.fold_constraints([]) == {}
    folded = kb_mod.fold_constraints(
        [{"hcp": [0, 21]}, {"hcp": [13, 40]}, {"S": [5, 13]}]
    )
    assert folded == {"hcp": [13, 21], "S": [5, 13]}


# --- profile ---------------------------------------------------------------


def test_hand_profile_folds_and_separates_annotations():
    kb = kb_mod.empty_kb()
    kb_mod.add_inference(kb, "N", _record({"hcp": [15, 17], "balanced": True}))
    kb_mod.add_inference(
        kb, "N", _record({"hcp": [0, 21]}, call="2C", negated=True, foldable=True)
    )
    kb_mod.add_inference(
        kb,
        "N",
        _record(
            {}, call="2NT", negated=True, foldable=False, reason="denies 20-21 balanced"
        ),
    )
    profile = kb_mod.hand_profile(kb, "N")
    assert profile["constraint"] == {"hcp": [15, 17], "balanced": True}
    assert profile["satisfiable"]
    assert profile["annotations"] == ["denies 20-21 balanced"]
    # Two foldable inferences folded; the annotation is not counted in based_on.
    assert len(profile["based_on"]) == 2


def test_hand_profile_excludes_violated():
    kb = kb_mod.empty_kb()
    kb_mod.add_inference(kb, "S", _record({"hcp": [15, 17]}))
    bad = _record({"hcp": [0, 12]}, call="P", index=4)
    bad["violated"] = True
    kb_mod.add_inference(kb, "S", bad)
    profile = kb_mod.hand_profile(kb, "S")
    assert profile["constraint"] == {"hcp": [15, 17]}


# --- violation detection ---------------------------------------------------


def test_mark_violations_flags_inconsistent_later_inference():
    # A "psych": an early bid promises 15-17, a later one implies <=12.
    kb = kb_mod.empty_kb()
    kb_mod.add_inference(kb, "W", _record({"hcp": [15, 17]}, call="1NT", index=0))
    kb_mod.add_inference(kb, "W", _record({"hcp": [0, 12]}, call="P", index=4))
    flagged = kb_mod.mark_violations(kb)
    assert flagged == ["01_P_pos"]
    # The earlier consensus is preserved; the later call is flagged.
    assert kb["W"]["00_1NT_pos"]["violated"] is False
    assert kb["W"]["01_P_pos"]["violated"] is True


def test_mark_violations_clean_auction_flags_nothing():
    kb = kb_mod.empty_kb()
    kb_mod.add_inference(kb, "N", _record({"hcp": [15, 17], "balanced": True}))
    kb_mod.add_inference(
        kb, "N", _record({"hcp": [0, 21]}, negated=True, foldable=True)
    )
    assert kb_mod.mark_violations(kb) == []


# --- persistence -----------------------------------------------------------


def test_write_read_round_trip(tmp_path):
    kb = kb_mod.empty_kb()
    kb_mod.add_inference(kb, "N", _record({"hcp": [15, 17], "balanced": True}))
    kb_mod.add_inference(kb, "S", _record({"hcp": [8, 16], "S": [0, 4]}, call="2C"))
    path = tmp_path / "kb.json"
    kb_mod.write_knowledge_base(kb, path)
    restored = kb_mod.read_knowledge_base(path)
    assert restored == kb
