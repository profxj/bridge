# Getting started 

## Project goals

The goal of this project is to create a bot that can play winning bridge.  We will attempt to developt this in stages.  This file will get us up and running.

## CLAUDE.md

1. Generate a CLAUDE.md file that will guide development of the project.  Be aware that we intend to use Python coding throughout the project.

### Questions from Claude (re: CLAUDE.md)

I generated `CLAUDE.md` at the repo root with sensible defaults. A few
decisions would sharpen it — current assumption listed after each:

1. **Scoring style** — duplicate (IMPs/matchpoints) or rubber bridge?
   *Assumed: duplicate, since "winning bridge" usually means duplicate.*

Duplicate scoring

2. **Bidding system** — which to target first: SAYC, 2/1 Game Force, or ACOL?
   *Assumed: SAYC (simplest well-documented starting point).*

Let's start with SAYC, but we will eventually add 2/1.

3. **AI approach for play** — rule-based heuristics, search
   (double-dummy / Monte Carlo), or learned/RL policies — and in what order?
   *Assumed: heuristics first, then search, then optionally learning.*

We will develop a learning/RL method, eventually.

4. **Tooling** — dependency manager (plain `pip`+venv, Poetry, uv?) and
   minimum Python version. *Assumed: Python 3.11+, pip + venv, ruff + mypy + pytest.*

Assume Python 3.14 and pip

5. **Reference engines** — OK to study/benchmark against existing open-source
   bridge engines (e.g. for double-dummy solving)? *Assumed: yes, for reference.*

yes

## Coding

Here are guidelines for coding: 

- Use Python where possible
- Add inline comments to explain the effort
- Reuse existing code when possible
- Use methods, not classes
- Place import statements at the top of the file.
- Include a description of inputs/outputs in the doc string of all methods
- Place modules under the bridge/ directory.  I have already added a __init__.py file.


### Questions from Claude (re: Coding guidelines)

I updated `CLAUDE.md` to reflect the coding guidelines (functions not classes,
top-of-file imports, input/output docstrings, inline comments, reuse, modules
under `bridge/`). One clarification, with my current assumption:

6. **"Use methods, not classes"** — does this rule out lightweight,
   *behaviour-free* data holders like `Enum` (e.g. Suit/Rank) and `NamedTuple`
   (e.g. a Card as `(suit, rank)`)? They aren't OO classes in spirit — just
   typed, immutable data that functions operate on.
   *Assumed: these lightweight data types are OK; what we avoid is
   logic-bearing classes / inheritance / methods-on-objects. If you'd prefer
   pure tuples/dicts with no `Enum`/`NamedTuple` at all, say so.*

## Skills

## Prompts

1. Perform the 1st command under CLAUDE.md
2. Re-read this file and my answers to the questions from Claude.  Make any necessary adjustments to CLAUDE.md.
3. Re-read this file.  See my guidelines on Coding.  Edit the CLAUDE.md file to reflect the guidelines.