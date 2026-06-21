"""Tests for pokerkit_plus.texture.

Covers the named regression cases the evaluation flagged (paired-board
connectivity must not double-count; the A-2-3 wheel must wrap) plus golden
draws/bands and an exhaustive C(52, 3) invariant sweep.
"""

import itertools

import pytest
from pokerkit import Deck

from pokerkit_plus import (
    BoardTexture,
    Connectivity,
    FlushDraw,
    RankBand,
    StraightDraw,
    Wetness,
)


def test_paired_board_connectivity_not_double_counted():
    # Regression: 6h7c7d8s must read like its three distinct ranks 6-7-8.
    assert (
        BoardTexture.from_board('6h7c7d8s').connectivity
        is BoardTexture.from_board('6h7c8s').connectivity
    )
    assert BoardTexture.from_board('6h7c7d8s').connectivity is Connectivity.HIGH


def test_wheel_wraps_off_single_scale():
    # Regression: the A-2-3 wheel must wrap, never ace-as-1/14 magic.
    texture = BoardTexture.from_board('As2c3d')

    assert texture.connectivity is Connectivity.HIGH
    assert texture.straight_draw is StraightDraw.OPEN_ENDED


def test_dry_board():
    texture = BoardTexture.from_board('2c7dKs')

    assert texture.wetness is Wetness.DRY
    assert texture.connectivity is Connectivity.DISCONNECTED
    assert texture.straight_draw is None
    assert texture.flush_draw is None


def test_flush_draw_levels():
    assert BoardTexture.from_board('AsKsQs').flush_draw is FlushDraw.LIVE
    assert BoardTexture.from_board('Ah7h2c').flush_draw is FlushDraw.BACKDOOR
    assert BoardTexture.from_board('Ac7d2h').flush_draw is None


def test_straight_draw_kinds():
    assert BoardTexture.from_board('9h8c7d').straight_draw is StraightDraw.OPEN_ENDED
    assert BoardTexture.from_board('Th9hQc').straight_draw is StraightDraw.GUTSHOT
    assert BoardTexture.from_board('2h7d9c').straight_draw is StraightDraw.BACKDOOR


def test_rank_band():
    assert BoardTexture.from_board('As2c3d').rank_band is RankBand.HIGH
    assert BoardTexture.from_board('9h8d7c').rank_band is RankBand.MEDIUM
    assert BoardTexture.from_board('6h5d4c').rank_band is RankBand.LOW


def test_short_board_raises():
    with pytest.raises(ValueError):
        BoardTexture.from_board('AsKs')


def test_exhaustive_flop_invariants():
    deck = list(Deck.STANDARD)

    for combo in itertools.combinations(deck, 3):
        texture = BoardTexture.from_board(combo)
        flags = (
            texture.are_monotone,
            texture.are_two_tone,
            texture.are_rainbow,
        )

        # On a three-card board exactly one suit shape holds.
        assert sum(flags) == 1

        if texture.are_monotone:
            assert texture.flush_draw is FlushDraw.LIVE
        if texture.are_rainbow:
            assert texture.flush_draw is None
        if texture.wetness is Wetness.DRY:
            assert texture.flush_draw is not FlushDraw.LIVE
            assert texture.straight_draw not in (
                StraightDraw.OPEN_ENDED,
                StraightDraw.DOUBLE_GUTSHOT,
            )
