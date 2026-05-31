"""Golden-hand tests for SAYC responses (uncontested).

All test hands are legal 13-card holdings (T == ten). The auction passed to
the matcher ends with partner's opening and RHO's pass, e.g. ["1NT", "P"].
"""

import pytest

from bridge.bidding_systems import sayc_loader as sl


@pytest.fixture(scope="module")
def rules():
    return sl.load_rules()


def respond(rules, hand, auction):
    return sl.choose_call(rules, hand, auction=auction)


# --- responses to 1NT (Stayman, Jacoby transfers, invites) -----------------


def test_1nt_stayman_with_four_card_major(rules):
    # 11 HCP, four hearts, no five-card suit -> Stayman 2C.
    hand = {"S": "K32", "H": "AQ32", "D": "Q432", "C": "32"}
    assert respond(rules, hand, ["1NT", "P"]) == "2C"


def test_1nt_transfer_to_spades(rules):
    # Five spades (weak) -> 2H Jacoby transfer.
    hand = {"S": "KQT98", "H": "32", "D": "432", "C": "432"}
    assert respond(rules, hand, ["1NT", "P"]) == "2H"


def test_1nt_transfer_to_hearts(rules):
    # Five hearts, longer than spades -> 2D Jacoby transfer.
    hand = {"S": "3", "H": "KQT98", "D": "4322", "C": "432"}
    assert respond(rules, hand, ["1NT", "P"]) == "2D"


def test_1nt_raise_to_3nt(rules):
    # Balanced 14, no four-card major -> 3NT.
    hand = {"S": "K32", "H": "Q32", "D": "AQ32", "C": "K32"}
    assert respond(rules, hand, ["1NT", "P"]) == "3NT"


def test_1nt_invite_2nt(rules):
    # Balanced 9, no four-card major -> invitational 2NT.
    hand = {"S": "K32", "H": "J32", "D": "Q432", "C": "K32"}
    assert respond(rules, hand, ["1NT", "P"]) == "2NT"


def test_1nt_weak_passes(rules):
    hand = {"S": "432", "H": "J32", "D": "Q432", "C": "432"}  # 3 HCP, no suit
    assert respond(rules, hand, ["1NT", "P"]) == "P"


# --- responses to a major --------------------------------------------------


def test_1h_simple_raise(rules):
    hand = {"S": "K32", "H": "Q432", "D": "K432", "C": "32"}  # 8 HCP, 4 hearts
    assert respond(rules, hand, ["1H", "P"]) == "2H"


def test_1h_limit_raise(rules):
    hand = {"S": "K32", "H": "Q432", "D": "KQ32", "C": "32"}  # 10 HCP, 4 hearts
    assert respond(rules, hand, ["1H", "P"]) == "3H"


def test_1h_one_spade_new_suit(rules):
    hand = {
        "S": "KQ32",
        "H": "32",
        "D": "K432",
        "C": "432",
    }  # 8 HCP, 4 spades, 2 hearts
    assert respond(rules, hand, ["1H", "P"]) == "1S"


def test_1h_game_raise(rules):
    hand = {"S": "K32", "H": "KQ432", "D": "AQ3", "C": "32"}  # 14 HCP, 5 hearts
    assert respond(rules, hand, ["1H", "P"]) == "4H"


def test_1h_nonforcing_1nt(rules):
    hand = {"S": "K32", "H": "32", "D": "Q432", "C": "K432"}  # 8 HCP, no fit/major
    assert respond(rules, hand, ["1H", "P"]) == "1NT"


def test_1s_simple_raise(rules):
    hand = {"S": "Q432", "H": "K32", "D": "K432", "C": "32"}  # 8 HCP, 4 spades
    assert respond(rules, hand, ["1S", "P"]) == "2S"


def test_1s_limit_raise(rules):
    hand = {"S": "Q432", "H": "K32", "D": "KQ32", "C": "32"}  # 10 HCP, 4 spades
    assert respond(rules, hand, ["1S", "P"]) == "3S"


def test_1s_two_level_new_suit(rules):
    hand = {"S": "32", "H": "AQ432", "D": "KQ3", "C": "432"}  # 11 HCP, 5 hearts
    assert respond(rules, hand, ["1S", "P"]) == "2H"


def test_1s_nonforcing_1nt(rules):
    hand = {"S": "32", "H": "K432", "D": "Q432", "C": "K32"}  # 8 HCP, 2 spades
    assert respond(rules, hand, ["1S", "P"]) == "1NT"


# --- responses to a minor --------------------------------------------------


def test_1c_response_up_the_line_diamonds(rules):
    hand = {"S": "32", "H": "32", "D": "KQ32", "C": "K432"}  # 4 diamonds, 4 clubs
    assert respond(rules, hand, ["1C", "P"]) == "1D"


def test_1c_response_shows_major_over_minor_raise(rules):
    # Four spades and five clubs: show the major (1S), do not raise clubs.
    hand = {"S": "KQ32", "H": "32", "D": "32", "C": "K9432"}
    assert respond(rules, hand, ["1C", "P"]) == "1S"


def test_1c_nonforcing_1nt(rules):
    hand = {"S": "K32", "H": "Q32", "D": "Q32", "C": "K432"}  # no 4-card major
    assert respond(rules, hand, ["1C", "P"]) == "1NT"


def test_1d_response_heart_up_the_line(rules):
    hand = {"S": "32", "H": "KQ32", "D": "32", "C": "K432"}  # 4 hearts
    assert respond(rules, hand, ["1D", "P"]) == "1H"


# --- responses to 2C and weak twos -----------------------------------------


def test_2c_waiting(rules):
    hand = {"S": "432", "H": "432", "D": "432", "C": "5432"}
    assert respond(rules, hand, ["2C", "P"]) == "2D"


def test_weak_two_preemptive_raise(rules):
    hand = {"S": "432", "H": "K32", "D": "5432", "C": "432"}  # 3 HCP, 3 hearts
    assert respond(rules, hand, ["2H", "P"]) == "3H"


def test_weak_two_strong_ask(rules):
    hand = {"S": "AKQ", "H": "32", "D": "AKQ2", "C": "432"}  # 18 HCP
    assert respond(rules, hand, ["2H", "P"]) == "2NT"
