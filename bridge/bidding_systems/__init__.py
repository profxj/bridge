"""Bidding systems for the bridge bot.

This package holds the SAYC knowledge base loader/validator and the thin
rule-matcher used to turn a hand (plus auction context) into a recommended
call. The bidding rules themselves are *data* under
``bridge/data/bidding/sayc/``; the logic here is plain functions over that
data (see CLAUDE.md coding guidelines).
"""
