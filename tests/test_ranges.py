"""Tests for pokerkit_plus.ranges."""

import random

from pokerkit import Card, Label
from pokerkit_plus import (
    AdvantageBasis,
    Aggression,
    ComboClass,
    build_value_range,
    calculate_range_advantage,
    expand_range,
    made_label,
    meets,
    nut_advantage,
)


def test_combo_class_notation():
    assert ComboClass.from_cards('AsAd').notation == 'AA'
    assert ComboClass.from_cards('AsKs').notation == 'AKs'
    assert ComboClass.from_cards('AsKd').notation == 'AKo'
    # order-independent
    assert ComboClass.from_cards('KdAs').notation == 'AKo'


def test_expand_range():
    rng = expand_range('AKs', 'QQ+')

    assert frozenset(Card.parse('AsKs')) in rng
    assert frozenset(Card.parse('AcKd')) not in rng  # offsuit excluded
    assert len(rng) == 22  # AKs (4) + QQ/KK/AA (18)


def test_build_value_range_matches_floor_oracle():
    board = 'Kh7c2d'
    floor = Label.TWO_PAIR
    rng = build_value_range(board, floor=floor)
    used = set(Card.clean(board))
    deck = [c for c in Card.parse(
        '2c2d2h2s3c3d3h3s4c4d4h4s5c5d5h5s6c6d6h6s7c7d7h7s8c8d8h8s'
        '9c9d9h9sTcTdThTsJcJdJhJsQcQdQhQsKcKdKhKsAcAdAhAs',
    ) if c not in used]
    oracle = set()
    for i, a in enumerate(deck):
        for b in deck[i + 1:]:
            label = made_label((a, b), board)
            if label is not None and meets(label, floor):
                oracle.add(frozenset((a, b)))

    assert rng == oracle


def test_build_value_range_aggression_tightens():
    board = 'Kh7c2d'
    loose = build_value_range(board, Aggression.NO_BET)
    tight = build_value_range(board, Aggression.RAISED)

    assert tight < loose  # a stronger floor is a strict subset


def test_nut_advantage_is_exact():
    # On K72, a set of sevens has the nut category; an overpair does not.
    adv = nut_advantage(expand_range('AhAd'), expand_range('7h7d'), 'Kh7c2d')

    assert adv.basis is AdvantageBasis.NUT_SHARE
    assert adv.hero_share == 0.0
    assert adv.villain_share == 1.0


def test_nut_advantage_neutral_when_neither_qualifies():
    adv = nut_advantage(expand_range('8h8d'), expand_range('9h9d'), 'Kh7c2d')

    assert adv.hero_share == 0.5
    assert adv.villain_share == 0.5


def test_range_advantage_equity_seeded():
    random.seed(0)
    adv = calculate_range_advantage(
        expand_range('AhAd'), expand_range('7h7d'), 'Kh7c2d',
        sample_count=3000,
    )

    assert adv.basis is AdvantageBasis.EQUITY
    assert abs(adv.hero_share + adv.villain_share - 1.0) < 1e-9
    assert adv.villain_share > 0.8  # the set crushes the overpair


def test_range_advantage_empty_is_neutral():
    adv = calculate_range_advantage(frozenset(), expand_range('AhAd'), 'Kh7c2d')

    assert adv.hero_share == 0.5
    assert adv.villain_share == 0.5
