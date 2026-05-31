"""Tests for the advanced conventions added in the Development phase:
Stayman/transfers over 2NT, positive 2C responses, and inverted minors.

All test hands are legal 13-card holdings (T == ten).
"""

import pytest

from bridge.bidding_systems import sayc_loader as sl


@pytest.fixture(scope="module")
def rules():
    return sl.load_rules()


def call(rules, hand, auction):
    return sl.choose_call(rules, hand, auction=auction)


# --- Stayman / transfers over 2NT ------------------------------------------


def test_2nt_stayman(rules):
    hand = {"S": "K32", "H": "AQ32", "D": "Q432", "C": "32"}  # 4 hearts, no 5-card
    assert call(rules, hand, ["2NT", "P"]) == "3C"


def test_2nt_transfer_to_hearts(rules):
    hand = {"S": "32", "H": "KQ432", "D": "432", "C": "432"}  # 5 hearts
    assert call(rules, hand, ["2NT", "P"]) == "3D"


def test_2nt_transfer_to_spades(rules):
    hand = {"S": "KQ432", "H": "32", "D": "432", "C": "432"}  # 5 spades
    assert call(rules, hand, ["2NT", "P"]) == "3H"


def test_2nt_no_major_3nt(rules):
    hand = {"S": "K32", "H": "Q32", "D": "AQ32", "C": "K32"}  # no four-card major
    assert call(rules, hand, ["2NT", "P"]) == "3NT"


def test_2nt_stayman_reply_hearts(rules):
    hand = {"S": "AQ3", "H": "KQ32", "D": "AK3", "C": "KQ2"}  # 20-21, 4 hearts
    assert call(rules, hand, ["2NT", "P", "3C", "P"]) == "3H"


def test_2nt_complete_transfer_to_hearts(rules):
    hand = {"S": "AQ3", "H": "K32", "D": "AK32", "C": "KQ2"}
    assert call(rules, hand, ["2NT", "P", "3D", "P"]) == "3H"


# --- positive 2C responses -------------------------------------------------


def test_2c_positive_spades(rules):
    hand = {
        "S": "AKQ32",
        "H": "432",
        "D": "432",
        "C": "32",
    }  # good 5-card spades, 9 HCP
    assert call(rules, hand, ["2C", "P"]) == "2S"


def test_2c_positive_clubs(rules):
    hand = {"S": "32", "H": "432", "D": "32", "C": "AKQ432"}  # 6 clubs, 9 HCP
    assert call(rules, hand, ["2C", "P"]) == "3C"


def test_2c_balanced_eight_count_still_waits(rules):
    hand = {"S": "K32", "H": "Q32", "D": "K432", "C": "Q32"}  # 10 HCP, no 5-card suit
    assert call(rules, hand, ["2C", "P"]) == "2D"


def test_2c_weak_waits(rules):
    hand = {"S": "432", "H": "432", "D": "432", "C": "5432"}
    assert call(rules, hand, ["2C", "P"]) == "2D"


# --- inverted minor responses ----------------------------------------------


def test_inverted_club_strong_single_raise(rules):
    hand = {
        "S": "K32",
        "H": "32",
        "D": "K3",
        "C": "AQ9432",
    }  # 12 HCP, 6 clubs, no major
    assert call(rules, hand, ["1C", "P"]) == "2C"


def test_inverted_club_weak_jump_raise(rules):
    hand = {"S": "K32", "H": "32", "D": "32", "C": "K98432"}  # 6 HCP, 6 clubs, no major
    assert call(rules, hand, ["1C", "P"]) == "3C"


def test_inverted_diamond_strong_single_raise(rules):
    hand = {
        "S": "K32",
        "H": "32",
        "D": "AQ9432",
        "C": "K3",
    }  # 12 HCP, 6 diamonds, no major
    assert call(rules, hand, ["1D", "P"]) == "2D"


def test_inverted_diamond_weak_jump_raise(rules):
    hand = {
        "S": "K32",
        "H": "32",
        "D": "K98432",
        "C": "32",
    }  # 6 HCP, 6 diamonds, no major
    assert call(rules, hand, ["1D", "P"]) == "3D"
