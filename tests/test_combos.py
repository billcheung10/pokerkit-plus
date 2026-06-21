"""Tests for pokerkit_plus.combos: category vocab + nut enumeration.

Correctness is checked against PokerKit's own evaluator as the oracle, and
the efficiency contract (one from_game per live combo, shared between Nuts
and CategoryCombos) is asserted by counting evaluator calls.
"""

import itertools
import math
import random

import pokerkit.hands
from pokerkit import Card, Deck, Label, StandardHighHand

from pokerkit_plus import (
    CATEGORY_ORDER,
    CategoryCombos,
    Nuts,
    made_label,
    meets,
)
from pokerkit_plus._semantic import _nuts_core

DECK = tuple(Deck.STANDARD)


def _oracle_nuts(board):
    used = set(Card.clean(board))
    live = [card for card in DECK if card not in used]
    best = None
    combos: set[frozenset[Card]] = set()

    for a, b in itertools.combinations(live, 2):
        hand = StandardHighHand.from_game_or_none((a, b), board)

        if hand is None:
            continue

        if best is None or hand > best:
            best = hand
            combos = {frozenset((a, b))}
        elif hand == best:
            combos.add(frozenset((a, b)))

    return best.entry.label, combos


def test_nuts_matches_oracle_on_random_flops():
    rng = random.Random(0)

    for _ in range(60):
        board = tuple(rng.sample(DECK, 3))
        oracle_label, oracle_combos = _oracle_nuts(board)
        nuts = Nuts.from_board(board)

        assert nuts.label is oracle_label
        assert {combo.as_frozenset for combo in nuts.combos} == oracle_combos


def test_nuts_never_none_on_short_board():
    nuts = Nuts.from_board('AsKs')

    assert nuts.hand is None
    assert nuts.combos == ()
    assert nuts.label is None
    assert nuts.board_is_nuts is False


def test_board_is_nuts_on_quad_board():
    assert Nuts.from_board('AcAdAhAsKc').board_is_nuts is True
    assert Nuts.from_board('7h2c9d').board_is_nuts is False


def test_is_royal_refinement():
    assert Nuts.from_board('AsKsQs').is_royal is True
    assert Nuts.from_board('7h2c9d').is_royal is False


def test_meets_is_category_ordering():
    assert meets(Label.FLUSH, Label.TWO_PAIR) is True
    assert meets(Label.ONE_PAIR, Label.ONE_PAIR) is True
    assert meets(Label.ONE_PAIR, Label.STRAIGHT) is False


def test_made_label():
    assert made_label('AsAc', 'Kh3sAd') is Label.THREE_OF_A_KIND
    assert made_label('7h2c', '9d4s5c') is Label.HIGH_CARD
    assert made_label('Ac', '') is None


def test_category_combos_partition_and_order():
    cc = CategoryCombos.from_board('7h2c9d')
    total = sum(len(combos) for combos in cc.by_category.values())

    assert total == math.comb(52 - 3, 2)
    assert list(cc.by_category) == [
        label for label in CATEGORY_ORDER if label in cc.by_category
    ]
    for label, combos in cc.by_category.items():
        assert all(combo.hand.entry.label is label for combo in combos)


def test_single_evaluation_shared_across_nuts_and_category(monkeypatch):
    calls = {'n': 0}
    original = pokerkit.hands.StandardHighHand.from_game_or_none.__func__

    def counting(cls, hole_cards, board_cards=()):
        calls['n'] += 1

        return original(cls, hole_cards, board_cards)

    monkeypatch.setattr(
        pokerkit.hands.StandardHighHand,
        'from_game_or_none',
        classmethod(counting),
    )
    _nuts_core.cache_clear()

    board = '7h2c9d'
    Nuts.from_board(board)
    cold = calls['n']

    assert cold == math.comb(52 - 3, 2)  # exactly one eval per live combo

    CategoryCombos.from_board(board)

    assert calls['n'] == cold  # warm cache: grouping adds zero evaluations

    _nuts_core.cache_clear()


def test_short_board_combos_are_empty():
    cc = CategoryCombos.from_board('Ah')

    assert cc.by_category == {}
    assert cc.nuts.hand is None
    assert cc.for_(Label.HIGH_CARD) == ()
