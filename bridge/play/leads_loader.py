"""Load, validate, and apply the standard *opening-lead* knowledge base.

Mirroring the SAYC bidder (`bridge/bidding_systems/sayc_loader.py`), the leads
system is encoded as declarative *rules* in YAML under
``bridge/data/leads/``. Each rule maps a *card holding* in one suit plus the
*contract type* (vs a suit contract or vs notrump) to the **card to lead**,
together with the *message* that lead sends to partner.

This module provides:

- **holding-feature helpers** — parse a one-suit holding string into the
  features the rules test (length, sequences, interior sequences, honors,
  doubleton/three-small, …);
- **a loader / validator** — read and sanity-check the rule files;
- **a thin matcher** — rank the rules that apply to a (holding, context,
  system) and resolve the single card to lead.

Per CLAUDE.md these are module-level functions over simple data.

Data conventions
----------------
A *holding* is the ranks held in a single suit, written high-to-low or in any
order, e.g. ``"KQJ6"``, ``"AK4"``, ``"8642"``. Ranks use
``A K Q J T 9 8 7 6 5 4 3 2`` (``T`` = ten). A *context* is ``"suit"`` (a
trump contract) or ``"nt"`` (notrump). A *system* selects the spot-lead style:
``"sayc"`` (fourth best; the default) or ``"three_five"`` (third/fifth best,
applied only vs suit contracts).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bridge.bidding_systems.sayc_loader import RANKS

# --- Constants -------------------------------------------------------------

# Cards that count as honours for the "has an honour" / "lead 4th best" test.
# The ten is deliberately *excluded* here: a suit headed by the ten is still
# "nothing" for the fourth-best-vs-second-highest decision.
HONORS: frozenset[str] = frozenset("AKQJ")

# Cards that may *head a sequence* (the ten can: T9 8, J T 9, …).
SEQUENCE_HONORS: frozenset[str] = frozenset("AKQJT")

# Contract types and lead systems the matcher understands.
CONTEXTS: frozenset[str] = frozenset({"suit", "nt"})
SYSTEMS: frozenset[str] = frozenset({"sayc", "three_five"})

# Default location of the leads data files, relative to this file:
# bridge/play/leads_loader.py -> bridge/data/leads
DEFAULT_LEADS_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "leads"

# Rank order index (0 = ace, high) for sorting and adjacency tests.
_RANK_INDEX: dict[str, int] = {rank: i for i, rank in enumerate(RANKS)}


# --- Holding-feature helpers -----------------------------------------------


def sorted_ranks(holding: str) -> list[str]:
    """Return the holding's ranks as a list sorted high-to-low.

    Parameters
    ----------
    holding:
        Ranks held in one suit (e.g. ``"KQJ6"``); case-insensitive, order
        irrelevant.

    Returns
    -------
    list[str]
        The ranks, highest first (e.g. ``["K", "Q", "J", "6"]``).

    Raises
    ------
    ValueError
        On an unknown rank or a duplicated rank (illegal in one suit).
    """
    ranks = list(holding.upper().replace(" ", ""))
    for rank in ranks:
        if rank not in _RANK_INDEX:
            raise ValueError(f"unknown rank {rank!r} in holding {holding!r}")
    if len(set(ranks)) != len(ranks):
        raise ValueError(f"duplicate rank in single-suit holding {holding!r}")
    return sorted(ranks, key=_RANK_INDEX.get)  # type: ignore[arg-type]


def _adjacent(high: str, low: str) -> bool:
    """Return True if two ranks are consecutive (e.g. K & Q, T & 9)."""
    return _RANK_INDEX[low] - _RANK_INDEX[high] == 1


def _top_sequence(ranks: list[str]) -> int:
    """Length of the touching run from the top, if the top card is an honour.

    Bridge intent: ``KQJ6`` has a top sequence of 3 (K-Q-J); ``T98`` has 3
    (ten heads a sequence); ``9876`` has 0 (a nine does not head an honour
    sequence). Returns 0 when there is no qualifying sequence.
    """
    if not ranks or ranks[0] not in SEQUENCE_HONORS:
        return 0
    length = 1
    for high, low in zip(ranks, ranks[1:], strict=False):
        if _adjacent(high, low):
            length += 1
        else:
            break
    return length if length >= 2 else 0


def _interior_sequence(ranks: list[str]) -> tuple[int, str | None]:
    """Find an interior sequence: an honour, a gap, then a touching run.

    Bridge intent: ``KJT`` (K, gap, J-T) and ``AQJ`` (A, gap, Q-J) and
    ``K109`` (K, gap, T-9) all carry an interior sequence whose top is the
    card to lead (J, Q, and T respectively). Returns ``(run_length,
    run_top)`` or ``(0, None)`` if there is no interior sequence.
    """
    # Need a top honour, then a gap to the second card.
    if len(ranks) < 3 or ranks[0] not in SEQUENCE_HONORS:
        return 0, None
    if _adjacent(ranks[0], ranks[1]):
        return 0, None  # top two touch -> that's a (top) sequence, not interior
    # The interior run begins at ranks[1] and must itself start with an honour.
    if ranks[1] not in SEQUENCE_HONORS:
        return 0, None
    run = 1
    for high, low in zip(ranks[1:], ranks[2:], strict=False):
        if _adjacent(high, low):
            run += 1
        else:
            break
    return (run, ranks[1]) if run >= 2 else (0, None)


def holding_features(holding: str) -> dict[str, Any]:
    """Bundle the derived features the lead rules test.

    Returns
    -------
    dict
        Keys: ``ranks`` (high-to-low list), ``length`` (int),
        ``has_honor``/``has_ace`` (bool), ``honor_count`` (int),
        ``top_sequence`` (int), ``interior_sequence`` (int),
        ``interior_top`` (str|None), ``two_touching_top`` (bool),
        ``ak_top`` (bool), ``is_singleton``/``is_doubleton`` (bool),
        ``three_small`` (bool — exactly three cards, no honour).
    """
    ranks = sorted_ranks(holding)
    length = len(ranks)
    has_honor = any(r in HONORS for r in ranks)
    interior_len, interior_top = _interior_sequence(ranks)
    two_touching_top = (
        length >= 2 and ranks[0] in SEQUENCE_HONORS and _adjacent(ranks[0], ranks[1])
    )
    ak_top = length >= 2 and ranks[0] == "A" and ranks[1] == "K"
    return {
        "ranks": ranks,
        "length": length,
        "has_honor": has_honor,
        "has_ace": "A" in ranks,
        "honor_count": sum(1 for r in ranks if r in HONORS),
        "top_sequence": _top_sequence(ranks),
        "interior_sequence": interior_len,
        "interior_top": interior_top,
        "two_touching_top": two_touching_top,
        "ak_top": ak_top,
        "is_singleton": length == 1,
        "is_doubleton": length == 2,
        "three_small": length == 3 and not has_honor,
    }


# --- Loading ---------------------------------------------------------------


def load_meta(leads_dir: Path = DEFAULT_LEADS_DIR) -> dict[str, Any]:
    """Load ``meta.yaml`` (system name, signal method, sources); ``{}`` if absent."""
    meta_path = leads_dir / "meta.yaml"
    if not meta_path.exists():
        return {}
    with meta_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_rules(leads_dir: Path = DEFAULT_LEADS_DIR) -> list[dict[str, Any]]:
    """Load every lead rule from the data tree into one flat list.

    All ``*.yaml`` files except ``meta.yaml`` are read; each must hold a YAML
    list of rule mappings. The originating file (relative to ``leads_dir``) is
    recorded under ``_file`` for provenance.
    """
    rules: list[dict[str, Any]] = []
    for path in sorted(leads_dir.rglob("*.yaml")):
        if path.name == "meta.yaml":
            continue
        with path.open(encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        if doc is None:
            continue
        if not isinstance(doc, list):
            raise ValueError(
                f"{path}: expected a YAML list of rules, got {type(doc).__name__}"
            )
        rel = path.relative_to(leads_dir).as_posix()
        for rule in doc:
            rule = dict(rule)
            rule["_file"] = rel
            rules.append(rule)
    return rules


# --- Validation ------------------------------------------------------------

# Card-selection roles the matcher can resolve against a holding.
LEAD_ROLES: frozenset[str] = frozenset(
    {
        "top",
        "lowest",
        "second_highest",
        "third_highest",
        "fourth_highest",
        "fifth_highest",
        "third_or_fifth",
        "top_of_interior_sequence",
    }
)

# Holding-predicate keys a rule may use.
_RANGE_PREDICATES = {"length"}
_INT_PREDICATES = {"sequence_from_top", "interior_sequence"}
_BOOL_PREDICATES = {
    "has_honor",
    "has_ace",
    "two_touching_top",
    "ak_top",
    "singleton",
    "doubleton",
    "three_small",
}


def validate_rule(rule: dict[str, Any]) -> list[str]:
    """Validate one lead rule; return a list of human-readable problems."""
    problems: list[str] = []
    where = rule.get("id", rule.get("_file", "<unknown rule>"))

    for key in ("id", "lead", "why"):
        if key not in rule and not (key == "why" and "shows" in rule):
            problems.append(f"{where}: missing required field '{key}'")

    lead = rule.get("lead")
    if isinstance(lead, dict):
        if set(lead) != {"card"} or lead["card"] not in _RANK_INDEX:
            problems.append(f"{where}: lead.card must be a single valid rank")
    elif lead not in LEAD_ROLES:
        problems.append(f"{where}: 'lead' must be a role {sorted(LEAD_ROLES)} or card")

    for ctx in rule.get("context", []):
        if ctx not in CONTEXTS:
            problems.append(f"{where}: context {ctx!r} not in {sorted(CONTEXTS)}")
    system = rule.get("system", "any")
    if system not in (SYSTEMS | {"any"}):
        problems.append(
            f"{where}: system {system!r} not in {sorted(SYSTEMS | {'any'})}"
        )
    if "priority" in rule and not isinstance(rule["priority"], int):
        problems.append(f"{where}: 'priority' must be an int")

    holding = rule.get("holding", {})
    if not isinstance(holding, dict):
        problems.append(f"{where}: 'holding' must be a mapping")
        holding = {}
    for key, val in holding.items():
        if key in _RANGE_PREDICATES:
            if not (isinstance(val, list) and len(val) == 2):
                problems.append(f"{where}: holding.{key} must be a [min, max] pair")
        elif key in _INT_PREDICATES:
            if not isinstance(val, int):
                problems.append(f"{where}: holding.{key} must be an int")
        elif key in _BOOL_PREDICATES:
            if not isinstance(val, bool):
                problems.append(f"{where}: holding.{key} must be a bool")
        else:
            problems.append(f"{where}: unknown holding predicate '{key}'")
    return problems


def validate_rules(rules: list[dict[str, Any]]) -> list[str]:
    """Validate a list of rules; collect all problems and flag duplicate ids."""
    problems: list[str] = []
    seen: set[str] = set()
    for rule in rules:
        problems.extend(validate_rule(rule))
        rid = rule.get("id")
        if isinstance(rid, str):
            if rid in seen:
                problems.append(f"duplicate rule id '{rid}'")
            seen.add(rid)
    return problems


# --- Matching --------------------------------------------------------------


def _holding_matches(predicate: dict[str, Any], features: dict[str, Any]) -> bool:
    """Return True if a holding's features satisfy every predicate key."""
    for key, val in predicate.items():
        if key == "length":
            lo, hi = val
            if not (lo <= features["length"] <= hi):
                return False
        elif key == "sequence_from_top":
            if features["top_sequence"] < val:
                return False
        elif key == "interior_sequence":
            if features["interior_sequence"] < val:
                return False
        elif key in _BOOL_PREDICATES:
            # Map predicate name to the matching feature key.
            feature_key = {
                "singleton": "is_singleton",
                "doubleton": "is_doubleton",
            }.get(key, key)
            if features[feature_key] != val:
                return False
        else:  # pragma: no cover - validator rejects unknown keys
            return False
    return True


def _context_system_ok(rule: dict[str, Any], context: str, system: str) -> bool:
    """Return True if a rule applies in this contract context and lead system."""
    contexts = rule.get("context", list(CONTEXTS))
    if context not in contexts:
        return False
    rule_system = rule.get("system", "any")
    return rule_system == "any" or rule_system == system


def resolve_card(role: Any, features: dict[str, Any]) -> str | None:
    """Resolve a card-selection role to a concrete rank in this holding.

    Returns the rank to lead, or ``None`` if the holding is too short for the
    requested role (e.g. a fourth-best from a three-card suit).
    """
    ranks: list[str] = features["ranks"]
    length = features["length"]
    if isinstance(role, dict):  # explicit {"card": "K"}
        card = role["card"]
        return card if card in ranks else None
    index = {
        "top": 0,
        "second_highest": 1,
        "third_highest": 2,
        "fourth_highest": 3,
        "fifth_highest": 4,
    }.get(role)
    if index is not None:
        return ranks[index] if index < length else None
    if role == "lowest":
        return ranks[-1]
    if role == "top_of_interior_sequence":
        return features["interior_top"]
    if role == "third_or_fifth":
        # Third highest from an even-length suit; fifth highest (the lowest in
        # a five-card suit) from an odd-length suit.
        if length % 2 == 0:
            return ranks[2] if length >= 3 else None
        return ranks[4] if length >= 5 else ranks[-1]
    return None  # pragma: no cover - validator restricts roles


def match_leads(
    rules: list[dict[str, Any]],
    holding: str,
    context: str = "suit",
    system: str = "sayc",
) -> list[dict[str, Any]]:
    """Return the lead rules that apply, ranked best-first by ``priority``.

    Parameters
    ----------
    rules:
        The loaded lead rules.
    holding:
        The ranks held in the suit being led (e.g. ``"KQJ6"``).
    context:
        ``"suit"`` (a trump contract) or ``"nt"``.
    system:
        ``"sayc"`` (default, fourth best) or ``"three_five"``.

    Returns
    -------
    list[dict]
        One entry per matching rule, each with the resolved ``card`` to lead,
        sorted by descending priority (ties keep file order).
    """
    if context not in CONTEXTS:
        raise ValueError(f"context must be one of {sorted(CONTEXTS)}, got {context!r}")
    if system not in SYSTEMS:
        raise ValueError(f"system must be one of {sorted(SYSTEMS)}, got {system!r}")
    features = holding_features(holding)

    candidates: list[dict[str, Any]] = []
    for rule in rules:
        if not _context_system_ok(rule, context, system):
            continue
        if not _holding_matches(rule.get("holding", {}), features):
            continue
        card = resolve_card(rule["lead"], features)
        if card is None:
            continue  # role not applicable to this holding (e.g. too short)
        candidates.append(
            {
                "id": rule.get("id"),
                "card": card,
                "priority": rule.get("priority", 0),
                "shows": rule.get("shows", rule.get("why", "")),
                "signal": rule.get("signal", "none"),
                "tag": rule.get("tag", "standard"),
                "source": rule.get("source", ""),
            }
        )
    candidates.sort(key=lambda c: c["priority"], reverse=True)
    return candidates


def choose_lead(
    rules: list[dict[str, Any]],
    holding: str,
    context: str = "suit",
    system: str = "sayc",
) -> str:
    """Return the single card to lead from a holding, or ``""`` if no rule fits.

    This is the externally-facing decision: it ranks candidates internally
    (see :func:`match_leads`) and returns only the top card's rank.
    """
    candidates = match_leads(rules, holding, context, system)
    return candidates[0]["card"] if candidates else ""
