"""Tests for the leads loader: holding-feature helpers, loading, validation."""

import pytest

from bridge.play import leads_loader as ll

# --- holding-feature helpers -----------------------------------------------


def test_sorted_ranks_orders_high_to_low():
    assert ll.sorted_ranks("6KJQ") == ["K", "Q", "J", "6"]
    assert ll.sorted_ranks("2 9 t") == ["T", "9", "2"]  # case/space tolerant


def test_sorted_ranks_rejects_bad_input():
    with pytest.raises(ValueError):
        ll.sorted_ranks("KX2")  # X not a rank
    with pytest.raises(ValueError):
        ll.sorted_ranks("KK2")  # duplicate in one suit


def test_top_sequence_detection():
    assert ll.holding_features("KQJ6")["top_sequence"] == 3
    assert ll.holding_features("T98")["top_sequence"] == 3  # ten heads a sequence
    assert ll.holding_features("9876")["top_sequence"] == 0  # nine does not
    assert ll.holding_features("KQ842")["top_sequence"] == 2


def test_interior_sequence_detection():
    f = ll.holding_features("KJT4")
    assert f["interior_sequence"] == 2 and f["interior_top"] == "J"
    f = ll.holding_features("AQJ2")
    assert f["interior_sequence"] == 2 and f["interior_top"] == "Q"
    f = ll.holding_features("KT9")  # K, gap, T-9 touching -> interior top ten
    assert f["interior_sequence"] == 2 and f["interior_top"] == "T"
    # A true top sequence is not an interior sequence.
    assert ll.holding_features("KQJ6")["interior_sequence"] == 0


def test_honor_and_shape_flags():
    f = ll.holding_features("8642")
    assert f["has_honor"] is False and f["length"] == 4
    f = ll.holding_features("A3")
    assert f["is_doubleton"] and f["has_ace"]
    f = ll.holding_features("973")
    assert f["three_small"] is True
    f = ll.holding_features("Q72")
    assert f["three_small"] is False  # has an honour
    assert ll.holding_features("AK4")["ak_top"] is True
    assert ll.holding_features("KQ4")["ak_top"] is False


# --- loading + validation --------------------------------------------------


def test_load_rules_nonempty_and_valid():
    rules = ll.load_rules()
    assert len(rules) > 10
    assert ll.validate_rules(rules) == []  # ships clean


def test_load_meta():
    meta = ll.load_meta()
    assert meta["default_system"] == "sayc"
    assert "three_five" in meta["systems"]


def test_validate_rule_flags_problems():
    bad = {"id": "x", "lead": "not_a_role", "holding": {"length": [4]}}
    problems = ll.validate_rule(bad)
    assert any("lead" in p for p in problems)
    assert any("length" in p for p in problems)


def test_validate_rules_flags_duplicate_ids():
    rules = [
        {"id": "dup", "lead": "top", "why": "a"},
        {"id": "dup", "lead": "top", "why": "b"},
    ]
    assert any("duplicate" in p for p in ll.validate_rules(rules))


# --- card-selection roles --------------------------------------------------


def test_resolve_card_roles():
    f = ll.holding_features("KJ863")  # K J 8 6 3
    assert ll.resolve_card("top", f) == "K"
    assert ll.resolve_card("lowest", f) == "3"
    assert ll.resolve_card("fourth_highest", f) == "6"
    assert ll.resolve_card("third_highest", f) == "8"
    # third_or_fifth: five cards (odd) -> fifth highest (the lowest).
    assert ll.resolve_card("third_or_fifth", f) == "3"
    # four cards (even) -> third highest.
    assert ll.resolve_card("third_or_fifth", ll.holding_features("KJ73")) == "7"


def test_resolve_card_too_short_returns_none():
    # No fourth card in a three-card holding.
    assert ll.resolve_card("fourth_highest", ll.holding_features("K72")) is None
