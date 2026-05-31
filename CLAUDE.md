# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository.

## Project

**Goal:** Build a bot that plays winning contract bridge. The bot must
handle the full game: dealing, bidding (auction), card play, and scoring.

**Approach:** Develop incrementally in well-defined stages (see Roadmap).
Each stage should be independently testable and leave the project in a
working state.

**Language:** Python throughout (Python 3.14, pip-managed).

**Key decisions** (resolved in `prompts/start_up.md`):
- **Scoring:** duplicate (IMPs/matchpoints); rubber scoring is out of scope.
- **Bidding system:** start with **SAYC**; add **2/1 Game Force** later.
- **Play strategy:** heuristics first → search (double-dummy / Monte Carlo)
  → a **learning/RL** method is a committed long-term goal.
- **Reference engines:** OK to study and benchmark against existing
  open-source bridge engines (e.g. for double-dummy solving).

## Domain primer (so we share vocabulary)

Bridge is a trick-taking card game for 4 players in two partnerships
(North–South vs East–West), using a standard 52-card deck.

- **Deal:** 13 cards to each of the 4 players.
- **Auction (bidding):** Players bid in turn to decide the *contract*
  (a level 1–7 + a strain: ♣ ♦ ♥ ♠ or NT), or all pass. Bids must
  ascend. Calls also include Pass, Double, Redouble.
- **Declarer / dummy / defenders:** The contract's winning side has a
  declarer; partner's hand becomes the exposed *dummy*.
- **Play:** 13 tricks. Follow suit if able; highest trump, else highest
  card of the led suit, wins the trick.
- **Scoring:** Based on contract level, strain, tricks made vs. contracted,
  vulnerability, and doubles. We use **duplicate scoring** (IMPs/matchpoints);
  rubber scoring is out of scope.

## Architecture (target)

Keep a clean separation between **game rules**, **agents/strategy**, and
**interfaces**. Rules must never depend on a particular bot.

```
bridge/                 # importable package (engine + agents)
  core/                 # cards, deck, hands, deal
  rules/                # legal-call/legal-play validation, trick logic
  scoring/              # contract scoring (duplicate: IMPs/matchpoints)
  auction/              # auction state machine, bidding systems
  play/                 # card-play engine, trick resolution
  agents/               # bot implementations (random, rule-based, search, RL, ...)
  bidding_systems/      # SAYC first, then 2/1; encoded as data/rules
tests/                  # pytest mirror of the package layout
prompts/                # project prompts (existing)
```

Module boundaries:
- `core` and `rules` are pure, deterministic, and have **no I/O**.
- Agents receive an immutable view of game state and return a legal call
  or card; they must not mutate engine state directly.
- Randomness flows through an injectable seed for reproducibility.

## Conventions

- **Python 3.14**, dependencies via **pip** (venv). Type hints on all public
  functions; check with `mypy`.
- Format with `ruff format`; lint with `ruff`.
- Tests with `pytest`; aim for fast, deterministic unit tests. Seed RNG.
- Represent cards/suits/ranks as `enum`s or small frozen dataclasses, not
  bare strings/ints — make illegal states unrepresentable where practical.
- Prefer immutable value objects (`frozen=True` dataclasses) for game state
  snapshots passed to agents.
- Validate legality in `rules/`, not scattered across agents.
- Docstrings explain *bridge intent*, not just code mechanics.

## Dev commands

> These reflect the intended toolchain; wire them up in Stage 0.

```bash
# environment (Python 3.14, pip + venv)
python3.14 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

ruff format .          # format
ruff check .           # lint
mypy bridge            # type check
pytest                 # run tests
pytest -k <expr> -x    # focused run
```

## Roadmap (stages)

Each stage is a milestone; do not start the next before the current one is
tested and green.

0. **Scaffold** — package layout, `pyproject.toml`, tooling, CI-ready test
   harness, this file's commands made real.
1. **Core model** — cards, deck, deal, hands; shuffling with seed.
2. **Rules & play engine** — follow-suit, trick winner, full 13-trick play
   with a trump strain; legal-play validation.
3. **Scoring** — contract scoring with vulnerability and doubles.
4. **Auction engine** — call legality, auction termination, contract
   determination, declarer identification.
5. **Baseline agents** — random-legal bot; simple heuristic defender/declarer.
6. **Bidding system** — encode **SAYC** (opening, responding, basic
   conventions); leave room to add **2/1 Game Force** later.
7. **Card-play strategy** — double-dummy / Monte Carlo search for play;
   stronger declarer & defense.
8. **Self-play & evaluation** — tournament harness, metrics (IMPs/MPs),
   benchmark vs. baselines and reference engines.
9. **Learning/RL** — committed goal: learned policies for bidding and play,
   trained via self-play and evaluated against the baselines above.

## Working agreements for Claude

- Build the smallest correct increment; keep the suite green at each step.
- Write tests alongside code; rules and scoring deserve thorough coverage
  (they're the ground truth everything else relies on).
- When a bridge rule is subtle (e.g. revoke handling, claim/concede,
  alerting), cite the rule intent in a comment.
- Don't introduce a heavy dependency without noting it here and why.
- Update this Roadmap's checkboxes / notes as stages complete.

## Open questions

None currently. The decisions from `prompts/start_up.md` (scoring, bidding
system, play strategy, tooling, reference engines) are resolved and reflected
above. Record new questions here, or in `prompts/start_up.md`, as they arise.
