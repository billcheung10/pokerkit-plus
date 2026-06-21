"""Tests for pokerkit_plus.facade — pure composition over the sub-objects."""

from pokerkit_plus import (
    BoardReport,
    BoardTexture,
    Draws,
    HandReport,
    HandTier,
    Nuts,
    Outs,
)


def test_hand_report_composes_sub_objects():
    report = HandReport.from_hand('AhKh', 'Qh7h2c')

    assert report.texture == BoardTexture.from_board('Qh7h2c')
    assert report.tier == HandTier.from_hand('AhKh', 'Qh7h2c')
    assert report.draws == Draws.from_hand('AhKh', 'Qh7h2c')
    assert report.outs == Outs.from_hand('AhKh', 'Qh7h2c')


def test_board_report_composes_sub_objects():
    report = BoardReport.from_board('AsKsQs')

    assert report.texture == BoardTexture.from_board('AsKsQs')
    assert report.nuts == Nuts.from_board('AsKsQs')
    assert report.nuts.is_royal is True
