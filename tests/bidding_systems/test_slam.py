"""Tests for Blackwood and Gerber ace-asking responses (by ace count)."""

import pytest

from bridge.bidding_systems import sayc_loader as sl


@pytest.fixture(scope="module")
def rules():
    return sl.load_rules()


# --- Blackwood (responses to 4NT) ------------------------------------------


@pytest.mark.parametrize(
    "spades_aces, expected",
    [
        ("", "5C"),  # 0 aces
        ("A", "5D"),  # 1 ace
        ("A", "5H"),  # 2 aces (second ace added below)
    ],
)
def test_blackwood_basic_counts(rules, spades_aces, expected):
    # Build hands with a controlled number of aces.
    if expected == "5C":
        hand = {"S": "KQ32", "H": "KQ3", "D": "Q32", "C": "Q32"}  # 0 aces
    elif expected == "5D":
        hand = {"S": "AQ32", "H": "KQ3", "D": "Q32", "C": "Q32"}  # 1 ace
    else:
        hand = {"S": "AQ32", "H": "AQ3", "D": "Q32", "C": "Q32"}  # 2 aces
    assert sl.choose_call(rules, hand, auction=["4NT", "P"]) == expected


def test_blackwood_three_aces(rules):
    hand = {"S": "AQ32", "H": "AQ3", "D": "A32", "C": "Q32"}  # 3 aces
    assert sl.choose_call(rules, hand, auction=["4NT", "P"]) == "5S"


def test_blackwood_four_aces_is_5c(rules):
    hand = {"S": "AQ32", "H": "A32", "D": "A32", "C": "A32"}  # 4 aces -> 5C
    assert sl.choose_call(rules, hand, auction=["4NT", "P"]) == "5C"


# --- Gerber (responses to 4C after a 1NT opening) --------------------------


def test_gerber_two_aces(rules):
    hand = {"S": "A432", "H": "A32", "D": "K32", "C": "K32"}  # 2 aces
    auction = ["1NT", "P", "4C", "P"]
    assert sl.choose_call(rules, hand, auction=auction) == "4S"


def test_gerber_one_ace(rules):
    hand = {"S": "A432", "H": "K32", "D": "K32", "C": "Q32"}  # 1 ace
    auction = ["1NT", "P", "4C", "P"]
    assert sl.choose_call(rules, hand, auction=auction) == "4H"


def test_natural_4c_not_misread_as_gerber(rules):
    # Without the 1NT-4C context, 4C is not a Gerber ask: a plain opening-hand
    # ace count after just ["4C","P"] should not trigger a Gerber answer.
    hand = {"S": "A432", "H": "A32", "D": "K32", "C": "K32"}
    assert sl.choose_call(rules, hand, auction=["4C", "P"]) != "4S"
