"""Tests for pokerkit_plus.tags.

Includes the named regression cases: nut_rank must never contradict
is_nut (the straight-flush-axis bug), paired-board sets/trips must tier
(not return None), and the kicker must be the max hole card.
"""

import random

from pokerkit import Deck, Label
from pokerkit_plus import (
    HandTier,
    KickerTier,
    NutRank,
    PairTier,
    ThreeOfAKindTier,
)

DECK = tuple(Deck.STANDARD)


def test_top_pair_top_kicker():
    tier = HandTier.from_hand('AsKd', 'Ah7c2d')

    assert tier.category is Label.ONE_PAIR
    assert tier.pair_tier is PairTier.TOP_PAIR
    assert tier.kicker_tier is KickerTier.TOP


def test_kicker_is_order_independent():
    assert (
        HandTier.from_hand('AsKd', 'Ah7c2d').kicker_tier
        is HandTier.from_hand('KdAs', 'Ah7c2d').kicker_tier
    )


def test_set_and_trips_tier_not_none():
    assert (
        HandTier.from_hand('KcKd', '7hKs2d').three_of_a_kind_tier
        is ThreeOfAKindTier.TOP_SET
    )
    trips = HandTier.from_hand('AcQd', 'AhAs8c')
    assert trips.three_of_a_kind_tier is ThreeOfAKindTier.TRIPS
    assert trips.kicker_tier is not None


def test_overpair_vs_underpair():
    assert HandTier.from_hand('AcAd', 'Kh7c2d').pair_tier is PairTier.OVERPAIR
    assert HandTier.from_hand('8c8d', 'Kh7c2d').pair_tier is PairTier.UNDER_PAIR


def test_board_pair_played_has_no_pair_tier():
    # Board is paired and hero holds no matching card: one pair, but the
    # pair is the board's, so there is no hero pair tier to report.
    tier = HandTier.from_hand('AcQd', 'KhKs2d')

    assert tier.category is Label.ONE_PAIR
    assert tier.pair_tier is None


def test_made_straight_on_sf_board_consistent():
    # Regression: a made straight on a straight-flush-possible board has
    # is_nut False, so nut_rank must NOT be NUT.
    tier = HandTier.from_hand('JhTd', '9s8s7sQc')

    assert tier.category is Label.STRAIGHT
    assert tier.is_nut is False
    assert tier.nut_rank is not NutRank.NUT


def test_is_nut_and_nut_rank_never_contradict():
    rng = random.Random(7)

    for _ in range(120):
        cards = rng.sample(DECK, 5)
        tier = HandTier.from_hand(tuple(cards[:2]), tuple(cards[2:]))

        if tier.nut_rank is None:
            continue
        if tier.nut_rank is NutRank.NUT:
            assert tier.is_nut is True
        if tier.is_nut is False:
            assert tier.nut_rank is not NutRank.NUT
