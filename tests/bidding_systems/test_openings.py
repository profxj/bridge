"""Golden-hand tests for SAYC opening bids (all seats).

All test hands are legal 13-card holdings (T == ten).
"""

import pytest

from bridge.bidding_systems import sayc_loader as sl


@pytest.fixture(scope="module")
def rules():
    return sl.load_rules()


def opening(rules, hand, seat=1, vulnerability="any"):
    """Convenience: the opening call for a hand in a given seat (empty auction)."""
    return sl.choose_call(
        rules, hand, auction=[], seat=seat, vulnerability=vulnerability
    )


# --- notrump openings ------------------------------------------------------


def test_open_1nt_balanced_16(rules):
    # 4-3-3-3, 16 HCP -> strong notrump.
    hand = {"S": "AQJ2", "H": "KJ4", "D": "KQ5", "C": "432"}
    assert sl.high_card_points(hand) == 16
    assert opening(rules, hand) == "1NT"


def test_open_1nt_with_five_card_major(rules):
    # 5-3-3-2, 15 HCP balanced -> still 1NT (NT outranks the major opening).
    hand = {"S": "AQ432", "H": "KJ4", "D": "KQ5", "C": "32"}
    assert sl.high_card_points(hand) == 15
    assert opening(rules, hand) == "1NT"


def test_open_2nt_balanced_20(rules):
    hand = {"S": "AKQ", "H": "KQ4", "D": "KJ5", "C": "Q432"}  # 20 HCP, 4-3-3-3
    assert sl.high_card_points(hand) == 20
    assert opening(rules, hand) == "2NT"


def test_open_2c_strong(rules):
    # 25 HCP -> strong artificial 2C (beats 2NT/1S).
    hand = {"S": "AKQ4", "H": "AKQ", "D": "AK5", "C": "432"}
    assert sl.high_card_points(hand) >= 22
    assert opening(rules, hand) == "2C"


# --- five-card majors ------------------------------------------------------


def test_open_1s_five_three_three_two_14(rules):
    # 14 HCP, 5 spades, below the 1NT range -> 1S.
    hand = {"S": "AQ432", "H": "KJ4", "D": "Q84", "C": "Q2"}
    assert sl.high_card_points(hand) == 14
    assert opening(rules, hand) == "1S"


def test_open_1h_six_card(rules):
    hand = {"S": "K3", "H": "AQJ432", "D": "KQ4", "C": "32"}
    assert opening(rules, hand) == "1H"


def test_open_1s_with_five_five_majors(rules):
    # 5-5 in the majors: open the higher-ranking suit, 1S.
    hand = {"S": "AQ432", "H": "KJ432", "D": "A4", "C": "3"}
    assert opening(rules, hand) == "1S"


def test_open_1h_when_hearts_longer(rules):
    # 6 hearts / 5 spades: open the longer suit, 1H.
    hand = {"S": "AQ432", "H": "KJ4321", "D": "A", "C": "3"}
    assert opening(rules, hand) == "1H"


# --- minor openings --------------------------------------------------------


def test_open_1d_four_four_minors(rules):
    # 14 HCP, no five-card major, 4-4 minors -> 1D.
    hand = {"S": "KQ3", "H": "K3", "D": "KQ32", "C": "J432"}
    assert sl.high_card_points(hand) == 14
    assert opening(rules, hand) == "1D"


def test_open_1c_three_three_minors(rules):
    # 14 HCP, 4-3-3-3 with a four-card major and 3-3 minors -> 1C.
    hand = {"S": "AQ32", "H": "KJ4", "D": "Q43", "C": "Q42"}
    assert sl.high_card_points(hand) == 14
    assert opening(rules, hand) == "1C"


def test_open_1c_longer_clubs(rules):
    # 5 clubs vs 2 diamonds, no five-card major -> 1C.
    hand = {"S": "AQ3", "H": "KJ3", "D": "43", "C": "K9842"}
    assert opening(rules, hand) == "1C"


def test_open_1d_longer_diamonds(rules):
    hand = {"S": "AQ3", "H": "KJ3", "D": "K9842", "C": "43"}
    assert opening(rules, hand) == "1D"


def test_open_1d_better_minor_4432(rules):
    # 14 HCP, 4-4 majors, 3-2 minors (3 diamonds, 2 clubs): no four-card minor
    # and no five-card major, so open the longer minor -> 1D (better minor).
    hand = {"S": "AK32", "H": "AQ32", "D": "J54", "C": "98"}
    assert sl.high_card_points(hand) == 14
    assert sl.suit_lengths(hand) == {"S": 4, "H": 4, "D": 3, "C": 2}
    assert opening(rules, hand) == "1D"


# --- light openers: Rule of 20 (seats 1-2) ---------------------------------


def test_rule_of_20_opens_light_in_first_seat(rules):
    # 11 HCP, 5-5 majors: 11 + 10 = 21 >= 20 -> open 1S in seat 1.
    hand = {"S": "KQT98", "H": "AQ982", "D": "43", "C": "2"}
    assert sl.high_card_points(hand) == 11
    assert opening(rules, hand, seat=1) == "1S"


def test_rule_of_20_does_not_open_in_first_seat(rules):
    # 11 HCP, 4-4-3-2: 11 + 8 = 19 < 20 -> pass in seat 1.
    hand = {"S": "KQJ2", "H": "AJ92", "D": "43", "C": "432"}
    assert sl.high_card_points(hand) == 11
    assert opening(rules, hand, seat=1) == "P"


# --- light openers: Rule of 15 (seats 3-4) ---------------------------------


def test_rule_of_15_opens_light_third_seat(rules):
    # 10 HCP, 5 spades: 10 + 5 = 15 >= 15 -> open 1S in seat 3.
    hand = {"S": "KQT98", "H": "AJ3", "D": "432", "C": "43"}
    assert opening(rules, hand, seat=3) == "1S"


def test_third_seat_light_passes_without_spades(rules):
    # 12 HCP, 2 spades: Rule of 15 fails (12+2=14) and the Rule of 20 light
    # opener only applies in seats 1-2 -> pass in seat 3.
    hand = {"S": "K3", "H": "AQ32", "D": "J432", "C": "Q43"}
    assert opening(rules, hand, seat=3) == "P"


# --- preempts and weak twos ------------------------------------------------


def test_weak_two_spades(rules):
    hand = {"S": "KQT984", "H": "K32", "D": "432", "C": "2"}  # 8 HCP, 6 spades
    assert opening(rules, hand) == "2S"


def test_three_level_preempt(rules):
    hand = {"S": "2", "H": "32", "D": "KQT9842", "C": "432"}  # 7 diamonds, weak
    assert opening(rules, hand) == "3D"


def test_four_level_preempt_major(rules):
    hand = {"S": "KQT98432", "H": "3", "D": "432", "C": "2"}  # 8 spades, weak
    assert opening(rules, hand) == "4S"


def test_strong_hand_with_long_suit_opens_one_level_not_preempt(rules):
    # 7 spades but 16 HCP -> a one-level opening, never a preempt.
    hand = {"S": "AKQ9842", "H": "K3", "D": "A4", "C": "32"}
    assert opening(rules, hand) == "1S"
