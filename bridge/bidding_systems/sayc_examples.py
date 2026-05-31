"""End-to-end SAYC bidding examples.

Demonstrates the bot turning hands into calls across a (constructive,
uncontested) partnership auction: opener opens, responder responds, opener
rebids, with the opponents passing. Each call is produced by the rule-matcher
in :mod:`bridge.bidding_systems.sayc_loader` and annotated with the reason the
rule gives.

Run as a script to print the examples::

    python -m bridge.bidding_systems.sayc_examples
"""

from __future__ import annotations

from typing import Any

from bridge.bidding_systems import sayc_loader as sl

# Seats around the table: opener is the dealer (seat 1), responder is partner
# (seat 3); the opponents in seats 2 and 4 pass throughout these examples.
SEAT_OPENER = 1
SEAT_RESPONDER = 3


def describe_call(
    rules: list[dict[str, Any]],
    hand: dict[str, str],
    auction: list[str],
    seat: int,
) -> tuple[str, str]:
    """Return ``(call, reason)`` for a hand in context (pass if nothing fits)."""
    candidates = sl.match_rules(rules, hand, auction=auction, seat=seat)
    if candidates:
        return candidates[0]["call"], candidates[0]["why"]
    return "P", "No matching rule — pass."


def run_partnership_auction(
    rules: list[dict[str, Any]],
    opener: dict[str, str],
    responder: dict[str, str],
    max_calls: int = 3,
) -> list[tuple[str, str, str]]:
    """Run a constructive auction (opponents passing) up to ``max_calls`` calls.

    Returns a list of ``(who, call, reason)`` tuples for our side's calls, in
    order. The auction stops early if our side passes. A pass by the opponents
    is inserted between our calls so the rule-matcher sees the correct context.
    """
    auction: list[str] = []
    calls: list[tuple[str, str, str]] = []
    for i in range(max_calls):
        is_opener = i % 2 == 0  # opener calls on rounds 0 (open) and 2 (rebid)
        hand = opener if is_opener else responder
        seat = SEAT_OPENER if is_opener else SEAT_RESPONDER
        who = "Opener" if is_opener else "Responder"
        call, reason = describe_call(rules, hand, auction, seat)
        calls.append((who, call, reason))
        auction.append(call)
        if call == "P":
            break
        auction.append("P")  # the opponent passes
    return calls


# Curated partnership deals (opener hand, responder hand). Each shows a
# different facet of the system. Hands are legal 13-card holdings.
PARTNERSHIP_EXAMPLES: list[dict[str, Any]] = [
    {
        "title": "Stayman uncovers a 4-4 heart fit",
        "opener": {"S": "AQ32", "H": "KJ32", "D": "K3", "C": "Q92"},
        "responder": {"S": "K32", "H": "AQ32", "D": "Q432", "C": "32"},
    },
    {
        "title": "Jacoby transfer into spades",
        "opener": {"S": "AQ7", "H": "KJ3", "D": "KQ32", "C": "Q92"},
        "responder": {"S": "KQT98", "H": "32", "D": "432", "C": "432"},
    },
    {
        "title": "Strong, artificial 2C with a balanced 23-count",
        "opener": {"S": "AKQ4", "H": "KQ3", "D": "AQ3", "C": "K32"},
        "responder": {"S": "832", "H": "J32", "D": "9432", "C": "J3"},
    },
    {
        # Responder signs off; opener has nothing further to say.
        "title": "Strong notrump raised straight to game",
        "opener": {"S": "AQ7", "H": "KJ3", "D": "KQ32", "C": "Q92"},
        "responder": {"S": "K32", "H": "Q32", "D": "AQ32", "C": "K32"},
        "max_calls": 2,
    },
    {
        # Opener's acceptance of the limit raise is a planned rebid.
        "title": "Five-card major opening met with a limit raise",
        "opener": {"S": "K3", "H": "AQJ32", "D": "KQ42", "C": "32"},
        "responder": {"S": "Q42", "H": "K432", "D": "AQ2", "C": "432"},
        "max_calls": 2,
    },
    {
        "title": "Weak two preempt furthered by responder",
        "opener": {"S": "KQT984", "H": "K32", "D": "432", "C": "2"},
        "responder": {"S": "J32", "H": "Q32", "D": "K432", "C": "432"},
        "max_calls": 2,
    },
]

# Ask/answer snippets: a given auction prefix and the answerer's hand,
# demonstrating the slam-asking conventions.
ASK_ANSWER_EXAMPLES: list[dict[str, Any]] = [
    {
        "title": "Blackwood: 4NT answered with two aces",
        "auction": ["4NT", "P"],
        "hand": {"S": "AQ32", "H": "AQ3", "D": "Q32", "C": "Q32"},
    },
    {
        "title": "Gerber: 4C over 1NT answered with two aces",
        "auction": ["1NT", "P", "4C", "P"],
        "hand": {"S": "A432", "H": "A32", "D": "K32", "C": "K32"},
    },
]


def format_examples(rules: list[dict[str, Any]]) -> str:
    """Render all examples as a human-readable report string."""
    lines: list[str] = ["SAYC bidding examples", "=" * 21, ""]
    for ex in PARTNERSHIP_EXAMPLES:
        lines.append(f"* {ex['title']}")
        lines.append(f"    Opener   : {ex['opener']}")
        lines.append(f"    Responder: {ex['responder']}")
        calls = run_partnership_auction(
            rules, ex["opener"], ex["responder"], ex.get("max_calls", 3)
        )
        sequence = " - ".join(c for _, c, _ in calls)
        lines.append(f"    Auction  : {sequence}")
        for who, call, reason in calls:
            lines.append(f"        {who:<9} {call:<4} {reason}")
        lines.append("")
    for ex in ASK_ANSWER_EXAMPLES:
        call, reason = describe_call(rules, ex["hand"], ex["auction"], seat=2)
        lines.append(f"* {ex['title']}")
        lines.append(f"    Hand   : {ex['hand']}")
        lines.append(f"    Auction: {' - '.join(ex['auction'])} - {call}")
        lines.append(f"        {call:<4} {reason}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Print all examples (entry point for ``python -m``)."""
    rules = sl.load_rules()
    print(format_examples(rules))


if __name__ == "__main__":
    main()
