"""Tests that the curated end-to-end bidding examples produce stable auctions."""

import pytest

from bridge.bidding_systems import sayc_examples as ex
from bridge.bidding_systems import sayc_loader as sl


@pytest.fixture(scope="module")
def rules():
    return sl.load_rules()


def calls_only(rules, opener, responder, max_calls=3):
    return [
        c for _, c, _ in ex.run_partnership_auction(rules, opener, responder, max_calls)
    ]


def test_stayman_heart_fit_auction(rules):
    e = ex.PARTNERSHIP_EXAMPLES[0]
    assert calls_only(rules, e["opener"], e["responder"]) == ["1NT", "2C", "2H"]


def test_jacoby_transfer_auction(rules):
    e = ex.PARTNERSHIP_EXAMPLES[1]
    assert calls_only(rules, e["opener"], e["responder"]) == ["1NT", "2H", "2S"]


def test_strong_2c_auction(rules):
    e = ex.PARTNERSHIP_EXAMPLES[2]
    assert calls_only(rules, e["opener"], e["responder"]) == ["2C", "2D", "2NT"]


def test_limit_raise_auction(rules):
    e = ex.PARTNERSHIP_EXAMPLES[4]
    assert calls_only(rules, e["opener"], e["responder"], 2) == ["1H", "3H"]


def test_format_examples_runs(rules):
    report = ex.format_examples(rules)
    assert "SAYC bidding examples" in report
    assert "Blackwood" in report
