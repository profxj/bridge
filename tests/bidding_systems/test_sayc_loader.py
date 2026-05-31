"""Tests for the SAYC loader, hand-feature helpers, validator, and matcher.

All test hands are legal 13-card holdings (T == ten).
"""

from bridge.bidding_systems import sayc_loader as sl

# --- hand-feature helpers --------------------------------------------------


def test_high_card_points():
    hand = {"S": "AKQ2", "H": "T98", "D": "765", "C": "432"}  # 4-3-3-3
    # A+K+Q = 4+3+2 = 9; no other honours.
    assert sl.high_card_points(hand) == 9


def test_suit_lengths_and_shape():
    hand = {"S": "AKQ2", "H": "T98", "D": "765", "C": "432"}
    assert sl.suit_lengths(hand) == {"S": 4, "H": 3, "D": 3, "C": 3}
    assert sl.hand_shape(hand) == (4, 3, 3, 3)


def test_is_balanced():
    assert sl.is_balanced({"S": "AKQ2", "H": "T98", "D": "765", "C": "432"})  # 4-3-3-3
    assert sl.is_balanced({"S": "AKQ32", "H": "T98", "D": "765", "C": "43"})  # 5-3-3-2
    # 6-3-2-2 is not balanced.
    assert not sl.is_balanced({"S": "AKQ432", "H": "T98", "D": "76", "C": "43"})
    # A void (5-4-4-0) is not balanced.
    assert not sl.is_balanced({"S": "AKQ98", "H": "T987", "D": "7654", "C": ""})


def test_rule_of_20():
    # 12 HCP with 4-4-3-2: 12 + (4+4) = 20 -> opens.
    assert sl.satisfies_rule_of_20({"S": "AKQJ", "H": "Q432", "D": "765", "C": "43"})
    # 11 HCP with 4-4-3-2: 11 + 8 = 19 -> does not.
    assert not sl.satisfies_rule_of_20(
        {"S": "AK32", "H": "KJ32", "D": "765", "C": "43"}
    )


def test_rule_of_15():
    # 10 HCP + 5 spades = 15 >= 15 -> light 3rd-seat opener qualifies.
    assert sl.satisfies_rule_of_15({"S": "KQ432", "H": "AJ3", "D": "765", "C": "43"})
    # 11 HCP + 2 spades = 13 < 15 -> does not.
    assert not sl.satisfies_rule_of_15(
        {"S": "K3", "H": "AJ432", "D": "QJ5", "C": "432"}
    )


# --- loading + validation --------------------------------------------------


def test_load_meta():
    meta = sl.load_meta()
    assert "SAYC" in meta["system"]
    assert meta["evaluation"]["high_card_points"] == {"A": 4, "K": 3, "Q": 2, "J": 1}


def test_load_rules_nonempty_and_tagged():
    rules = sl.load_rules()
    assert rules, "expected to load some SAYC rules"
    assert all("_file" in r for r in rules), "every rule records its source file"


def test_all_rules_valid():
    rules = sl.load_rules()
    problems = sl.validate_rules(rules)
    assert problems == [], f"rule validation problems: {problems}"


def test_validator_flags_missing_fields():
    bad = {"id": "x", "when": {}}  # missing 'call' and 'why'
    problems = sl.validate_rule(bad)
    assert any("call" in p for p in problems)
    assert any("why" in p for p in problems)


# --- matcher core behaviours -----------------------------------------------


def test_seat_from_auction():
    assert sl.seat_from_auction([]) == 1
    assert sl.seat_from_auction(["P"]) == 2
    assert sl.seat_from_auction(["P", "P", "P"]) == 4


def test_choose_call_passes_when_nothing_matches():
    rules = sl.load_rules()
    # A flat 2-count Yarborough opens nothing -> pass.
    junk = {"S": "8432", "H": "765", "D": "5432", "C": "J2"}
    assert sl.choose_call(rules, junk) == "P"
