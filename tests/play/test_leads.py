"""Golden card-combination tests for the standard opening-lead rules.

Each case pins (holding, context, system) -> the card to lead, against the
ACBL SAYC booklet and the cross-checked standard tables cited in the data.
"""

import pytest

from bridge.play import leads_loader as ll


@pytest.fixture(scope="module")
def rules():
    return ll.load_rules()


# --- sequences and honour leads (system-independent) -----------------------


@pytest.mark.parametrize(
    "holding, context, expected",
    [
        ("KQJ6", "suit", "K"),  # top of a three-card sequence
        ("KQJ6", "nt", "K"),
        ("QJT2", "suit", "Q"),
        ("JT93", "nt", "J"),
        ("KJT4", "suit", "J"),  # interior sequence (K J 10)
        ("KT9", "suit", "T"),  # interior sequence (K 10 9)
        ("AQJ2", "nt", "Q"),  # interior sequence vs NT keeps the ace
        ("QJ9", "nt", "Q"),  # two-and-a-half touching honours
    ],
)
def test_sequence_and_interior_leads(rules, holding, context, expected):
    assert ll.choose_lead(rules, holding, context) == expected


# --- the ace rules ---------------------------------------------------------


@pytest.mark.parametrize(
    "holding, context, expected",
    [
        ("AK4", "suit", "A"),  # ace from A K x vs a suit (SAYC)
        ("AK4", "nt", "K"),  # king from A K vs NT (unblock/signal)
        ("A8532", "suit", "A"),  # never underlead an ace vs a suit
        ("AQJ2", "suit", "A"),  # ace beats the interior sequence vs a suit
        ("A8642", "nt", "4"),  # vs NT, underleading the ace is fine -> 4th best
    ],
)
def test_ace_leads(rules, holding, context, expected):
    assert ll.choose_lead(rules, holding, context) == expected


# --- two touching honours, suit vs NT --------------------------------------


@pytest.mark.parametrize(
    "holding, context, expected",
    [
        ("KQ842", "suit", "K"),  # top of touching honours vs a suit
        ("KQ842", "nt", "4"),  # fourth best vs NT to set up the long suit
        ("KQ9", "nt", "K"),  # short suit vs NT -> top
    ],
)
def test_two_touching_honours(rules, holding, context, expected):
    assert ll.choose_lead(rules, holding, context) == expected


# --- spot leads from length (SAYC fourth best & the no-honour exception) ----


@pytest.mark.parametrize(
    "holding, context, expected",
    [
        ("KJ73", "suit", "3"),  # fourth best
        ("KJ73", "nt", "3"),
        ("KJ863", "suit", "6"),  # fourth best from five
        ("8642", "suit", "6"),  # 4+ with no honour -> second highest (SAYC)
        ("8642", "nt", "6"),
        ("973", "suit", "3"),  # three small vs a suit -> low
        ("973", "nt", "9"),  # three small vs NT -> high (top of nothing)
        ("K72", "suit", "2"),  # low from an honour in three cards
        ("Q72", "nt", "2"),
    ],
)
def test_spot_and_short_leads(rules, holding, context, expected):
    assert ll.choose_lead(rules, holding, context) == expected


# --- doubletons and singletons ---------------------------------------------


def test_doubleton_and_singleton(rules):
    assert ll.choose_lead(rules, "A3", "suit") == "A"  # top of a doubleton
    assert ll.choose_lead(rules, "K5", "nt") == "K"
    assert ll.choose_lead(rules, "7", "suit") == "7"  # singleton


# --- the 3rd/5th-best variant (suit contracts only; opt-in) -----------------


@pytest.mark.parametrize(
    "holding, sayc_card, three_five_card",
    [
        ("KJ73", "3", "7"),  # four cards (even) -> third highest
        ("KJ863", "6", "3"),  # five cards (odd) -> fifth = lowest
    ],
)
def test_three_five_overrides_only_vs_suit(rules, holding, sayc_card, three_five_card):
    assert ll.choose_lead(rules, holding, "suit", system="sayc") == sayc_card
    assert (
        ll.choose_lead(rules, holding, "suit", system="three_five") == three_five_card
    )
    # Vs notrump, 3rd/5th does not apply -> the lead stays fourth best.
    assert ll.choose_lead(rules, holding, "nt", system="three_five") == sayc_card


def test_match_leads_reports_reason_and_provenance(rules):
    top = ll.match_leads(rules, "KQJ6", "suit")[0]
    assert top["card"] == "K" and top["tag"] == "sayc"
    assert "sequence" in top["shows"].lower()


def test_invalid_context_or_system_raises(rules):
    with pytest.raises(ValueError):
        ll.choose_lead(rules, "KQJ6", "trump")
    with pytest.raises(ValueError):
        ll.choose_lead(rules, "KQJ6", "suit", system="udca")
