"""Tests for pokerkit_plus.blockers (count-based nut blocking)."""

import random

from pokerkit import Card, Deck
from pokerkit_plus import BlockerReport, Nuts

DECK = tuple(Deck.STANDARD)


def _oracle(hole, board):
    hole_cards = set(Card.clean(hole))
    nuts = Nuts.from_board(board)
    blocked = 0
    cards: set[Card] = set()

    for combo in nuts.combos:
        overlap = set(combo.cards) & hole_cards
        if overlap:
            blocked += 1
            cards |= overlap

    return len(nuts.combos), blocked, frozenset(cards)


def test_matches_count_oracle_on_random_flops():
    rng = random.Random(5)

    for _ in range(60):
        cards = rng.sample(DECK, 5)
        hole, board = tuple(cards[:2]), tuple(cards[2:])
        total, blocked, blocker_cards = _oracle(hole, board)
        report = BlockerReport.from_hand(hole, board)

        # board-is-nuts is reported empty by rule; oracle ignores that case
        if Nuts.from_board(board).board_is_nuts:
            continue

        assert report.nut_combos_total == total
        assert report.nut_combos_blocked == blocked
        assert report.blocker_cards == blocker_cards


def test_load_bearing_card_blocks_every_nut_combo():
    # The case deuce is in every quad-deuce nut combo.
    report = BlockerReport.from_hand('2s3c', '2c2d2h')

    assert report.blocks_nuts is True
    assert report.nut_combos_blocked == report.nut_combos_total
    assert report.block_fraction == 1.0
    assert report.blocker_cards == frozenset(Card.parse('2s'))


def test_interchangeable_kicker_blocks_only_its_combo():
    report = BlockerReport.from_hand('AhAd', '2c2d2h')

    assert report.nut_combos_blocked == 2


def test_board_is_nuts_blocks_nothing():
    report = BlockerReport.from_hand('2c3c', 'AsKsQsJsTs')

    assert report.blocks_nuts is False
    assert report.nut_combos_blocked == 0
    assert report.blocker_cards == frozenset()


def test_no_block_on_unrelated_holding():
    report = BlockerReport.from_hand('7h8h', '2c2d2h')

    assert report.blocks_nuts is False
    assert report.block_fraction == 0.0
