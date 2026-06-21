"""Tests for pokerkit_plus.outs.

An out is a category upgrade (matching the legacy 'outs by future hand
type'); a kicker bump within the same category is not an out. Verified
against an independent oracle plus the named regression cases the source
dropped (full-house and two-pair outs).
"""

import random

import pytest
from pokerkit import Card, Deck, Label
from pokerkit_plus import CATEGORY_ORDER, Outs, made_label

DECK = tuple(Deck.STANDARD)


def test_outs_match_category_upgrade_oracle():
    rng = random.Random(3)

    for _ in range(40):
        cards = rng.sample(DECK, 5)
        hole, board = tuple(cards[:2]), tuple(cards[2:])
        base_rank = CATEGORY_ORDER.index(made_label(hole, board))
        used = set(hole) | set(board)
        oracle: dict[Label, set[Card]] = {}

        for card in DECK:
            if card in used:
                continue
            label = made_label(hole, (*board, card))
            if label is not None and CATEGORY_ORDER.index(label) > base_rank:
                oracle.setdefault(label, set()).add(card)

        outs = Outs.from_hand(hole, board)
        got = {label: set(cards) for label, cards in outs.by_category.items()}

        assert got == oracle


def test_full_house_and_quad_outs_from_a_set():
    outs = Outs.from_hand('7h7s', 'Kd7c2s')

    assert outs.by_category[Label.FOUR_OF_A_KIND] == tuple(Card.parse('7d'))
    assert len(outs.by_category[Label.FULL_HOUSE]) == 6


def test_two_pair_outs_from_top_pair():
    outs = Outs.from_hand('AhKs', 'As8d3c')
    kings = {
        card
        for card in outs.by_category[Label.TWO_PAIR]
        if card.rank is next(Card.parse('Kc')).rank
    }

    assert len(kings) == 3  # the three off-suit kings pair the kicker


def test_oesd_has_eight_straight_outs():
    outs = Outs.from_hand('Td9d', 'Jc8s2h')

    assert len(outs.by_category[Label.STRAIGHT]) == 8


def test_kicker_bump_is_not_an_out():
    # Trips of sevens: a higher kicker is strictly stronger best-5 but is
    # NOT an out (same category); only FH/quad cards are outs.
    outs = Outs.from_hand('7h7s', 'Kd7c2s')

    assert Label.THREE_OF_A_KIND not in outs.by_category


def test_short_or_long_board_raises():
    with pytest.raises(ValueError):
        Outs.from_hand('AhKh', 'As')
