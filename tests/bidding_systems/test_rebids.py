"""Tests for opener's rebids: transfer completion, Stayman replies, 2C-2NT."""

import pytest

from bridge.bidding_systems import sayc_loader as sl


@pytest.fixture(scope="module")
def rules():
    return sl.load_rules()


def test_complete_transfer_to_hearts(rules):
    # Responder transferred with 2D; opener must bid 2H regardless of hand.
    hand = {"S": "AQ32", "H": "K3", "D": "KQ32", "C": "AQ2"}
    assert sl.choose_call(rules, hand, auction=["1NT", "P", "2D", "P"]) == "2H"


def test_complete_transfer_to_spades(rules):
    hand = {"S": "AQ32", "H": "K3", "D": "KQ32", "C": "AQ2"}
    assert sl.choose_call(rules, hand, auction=["1NT", "P", "2H", "P"]) == "2S"


def test_stayman_reply_hearts(rules):
    hand = {"S": "AQ32", "H": "KQ32", "D": "K3", "C": "AQ2"}  # 4 hearts
    assert sl.choose_call(rules, hand, auction=["1NT", "P", "2C", "P"]) == "2H"


def test_stayman_reply_spades_denies_hearts(rules):
    hand = {"S": "AQ32", "H": "K3", "D": "KQ32", "C": "AQ2"}  # 4 spades, 2 hearts
    assert sl.choose_call(rules, hand, auction=["1NT", "P", "2C", "P"]) == "2S"


def test_stayman_reply_no_major(rules):
    hand = {"S": "AQ3", "H": "K32", "D": "KQ32", "C": "AQ2"}  # no four-card major
    assert sl.choose_call(rules, hand, auction=["1NT", "P", "2C", "P"]) == "2D"


def test_2c_opener_rebids_2nt_with_balanced_23(rules):
    hand = {"S": "AKQ4", "H": "KQ3", "D": "AQ3", "C": "K32"}  # 23 HCP balanced
    assert sl.high_card_points(hand) == 23
    assert sl.choose_call(rules, hand, auction=["2C", "P", "2D", "P"]) == "2NT"
