"""Tests for pokerkit_plus.draws.

Includes the named regression cases: a straight draw on a straight-flush
possible board must not be over-ranked nut, and a broadway-dominated draw
must rank below the nuts.
"""

from pokerkit_plus import Draws, FlushDraw, NutRank, StraightDraw


def test_nut_flush_draw():
    draw = Draws.from_hand('AsKs', 'Qs7s2c')

    assert draw.flush_draw is FlushDraw.LIVE
    assert draw.nut_rank is NutRank.NUT


def test_middle_flush_card_is_not_nut():
    # Hero holds only middle spades; higher spades are undealt outs.
    draw = Draws.from_hand('JsTs', '9s7s2c')

    assert draw.flush_draw is FlushDraw.LIVE
    assert draw.nut_rank is not NutRank.NUT


def test_open_ended_straight_draw():
    draw = Draws.from_hand('JhTd', '9c8s2h')

    assert draw.straight_draw is StraightDraw.OPEN_ENDED


def test_straight_draw_on_sf_board_not_overranked_nut():
    # Regression: a straight draw on a monotone / SF-possible board must
    # count straight-flush completions, so it is never reported NUT.
    draw = Draws.from_hand('JhTd', '9s8s2s')

    assert draw.straight_draw is StraightDraw.OPEN_ENDED
    assert draw.nut_rank is not NutRank.NUT


def test_broadway_dominated_draw_below_nut():
    # Regression: a low/wheel straight draw a higher straight can dominate
    # must rank below the nuts (no broadway-as-wheel asymmetry).
    draw = Draws.from_hand('2h3d', '4c5s9h')

    assert draw.straight_draw is StraightDraw.OPEN_ENDED
    assert draw.nut_rank is not NutRank.NUT


def test_no_draw():
    draw = Draws.from_hand('AhKd', '2c7s9h')

    assert draw.straight_draw is None
    assert draw.flush_draw is None
    assert draw.nut_rank is None
