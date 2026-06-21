""":mod:`pokerkit_plus.facade` implements the composed report entry points.

The facade is the recommended one-call surface for callers that want a
complete reading rather than a single axis. It does
no analysis of its own: :class:`HandReport` composes the hero-relative
sub-objects (:class:`pokerkit_plus.texture.BoardTexture`,
:class:`pokerkit_plus.tags.HandTier`, :class:`pokerkit_plus.draws.Draws`,
and :class:`pokerkit_plus.outs.Outs`) and :class:`BoardReport` composes the
hero-independent ones (:class:`pokerkit_plus.texture.BoardTexture` and
:class:`pokerkit_plus.combos.Nuts`). Each sub-object is exposed as a field,
so the granular APIs remain first-class; the facade only wires them up,
each from its own ``from_*`` constructor, and re-shares the memoized nut
core through :class:`pokerkit_plus.combos.Nuts` and
:class:`pokerkit_plus.tags.HandTier`.

The shared :class:`pokerkit_plus.draws.NutRank` is re-exported here so the
nut-ness vocabulary is reachable from the facade module too, with a single
definition (in :mod:`pokerkit_plus.draws`) and no drift.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokerkit.hands import Hand, StandardHighHand
from pokerkit.utilities import CardsLike

from pokerkit_plus.combos import Nuts
from pokerkit_plus.draws import Draws
from pokerkit_plus.draws import NutRank as NutRank
from pokerkit_plus.outs import Outs
from pokerkit_plus.tags import HandTier
from pokerkit_plus.texture import BoardTexture


@dataclass(frozen=True)
class HandReport:
    """The composed hero-relative reading of a hand on a board.

    Construct with :meth:`from_hand`. The report bundles the four
    hero-relative sub-objects into one frozen value; it computes nothing
    itself and re-evaluates nothing, delegating each field to that
    sub-object's own ``from_*`` constructor. Every sub-object is a field,
    so a caller can drill into, say, ``report.draws.flush_draw`` or iterate
    ``report.outs.by_category`` without a second call.

    >>> report = HandReport.from_hand('AsKd', 'Ah7c2d')
    >>> report.texture.flush_draw is None
    True
    >>> report.tier.pair_tier
    <PairTier.TOP_PAIR: 'Top pair'>
    >>> report.tier.labels()
    ('Top pair', 'Top kicker')

    A hero on a live flush draw reads the draw and its improving outs while
    still tiering the made hand underneath.

    >>> draw = HandReport.from_hand('AhKh', 'Qh7h2c')
    >>> draw.draws.flush_draw
    <FlushDraw.LIVE: 'Live'>
    >>> draw.draws.nut_rank
    <NutRank.NUT: 'Nut'>
    >>> from pokerkit.lookups import Label
    >>> Label.FLUSH in draw.outs.by_category
    True

    The facade re-evaluates nothing the sub-objects already evaluated: each
    field is exactly the value its standalone constructor returns.

    >>> report.texture == BoardTexture.from_board('Ah7c2d')
    True
    >>> report.tier == HandTier.from_hand('AsKd', 'Ah7c2d')
    True

    :param texture: The hero-independent texture of the board.
    :param tier: The board-relative made-hand reading for the hero.
    :param draws: The hero's immediate draws, read by evaluation.
    :param outs: The hero's improving live cards, grouped by category.
    """

    texture: BoardTexture
    """The hero-independent texture of the board."""
    tier: HandTier
    """The board-relative made-hand reading for the hero."""
    draws: Draws
    """The hero's immediate draws, read by single-card evaluation."""
    outs: Outs
    """The hero's improving live cards, grouped by made category."""

    @classmethod
    def from_hand(
            cls,
            hole: CardsLike,
            board: CardsLike,
            *,
            hand_type: type[Hand] = StandardHighHand,
    ) -> HandReport:
        """Compose a full hero-relative report for a hand on a board.

        This is pure composition: it forwards ``hole``, ``board``, and
        ``hand_type`` to each sub-object's own ``from_*`` constructor and
        bundles the results. Input normalization, evaluation, and board
        validation all happen inside those constructors, so the facade owns
        no card bookkeeping. The board must be a flop or turn (the draws and
        outs readings are defined only there); the sub-objects raise
        :class:`ValueError` for an out-of-range board.

        >>> report = HandReport.from_hand('AhKh', 'Qh7h2c')
        >>> report.draws.flush_draw
        <FlushDraw.LIVE: 'Live'>
        >>> report.outs.count > 0
        True

        :param hole: The hero's hole cards.
        :param board: The flop or turn board cards.
        :param hand_type: The hand type to evaluate with, defaults to
                          :class:`pokerkit.hands.StandardHighHand`.
        :return: The composed hero-relative report.
        :raises ValueError: If the board is not a flop or turn.
        """
        return cls(
            texture=BoardTexture.from_board(board),
            tier=HandTier.from_hand(hole, board, hand_type=hand_type),
            draws=Draws.from_hand(hole, board, hand_type=hand_type),
            outs=Outs.from_hand(hole, board, hand_type=hand_type),
        )


@dataclass(frozen=True)
class BoardReport:
    """The composed hero-independent reading of a board.

    Construct with :meth:`from_board`. The report bundles the board's
    texture and its nuts into one frozen value; like :class:`HandReport` it
    computes nothing itself, exposing both sub-objects as fields so a caller
    can read ``report.texture.wetness`` and ``report.nuts.label`` from one
    call.

    >>> report = BoardReport.from_board('AsKsQs')
    >>> report.texture.wetness
    <Wetness.WET: 'Wet'>
    >>> report.nuts.is_royal
    True
    >>> report.nuts.label
    <Label.STRAIGHT_FLUSH: 'Straight flush'>

    The fields are exactly the standalone constructors' results, so the
    facade adds no second pass over the board.

    >>> report.texture == BoardTexture.from_board('AsKsQs')
    True
    >>> report.nuts == Nuts.from_board('AsKsQs')
    True

    A dry, disconnected board reads dry with the board's honest nuts.

    >>> dry = BoardReport.from_board('2c7dKs')
    >>> dry.texture.wetness
    <Wetness.DRY: 'Dry'>
    >>> dry.nuts.label
    <Label.THREE_OF_A_KIND: 'Three of a kind'>

    :param texture: The hero-independent texture of the board.
    :param nuts: The strongest makeable hand and the combos tying it.
    """

    texture: BoardTexture
    """The hero-independent texture of the board."""
    nuts: Nuts
    """The strongest makeable hand and the combos tying it."""

    @classmethod
    def from_board(
            cls,
            board: CardsLike,
            *,
            hand_type: type[Hand] = StandardHighHand,
    ) -> BoardReport:
        """Compose a hero-independent report for a board.

        Pure composition: it forwards ``board`` (and ``hand_type`` for the
        nut enumeration) to each sub-object's own ``from_*`` constructor.
        :class:`pokerkit_plus.combos.Nuts` reuses the memoized nut core, so
        a board already seen for the same hand type adds no enumeration.
        Texture requires a flop, turn, or river and raises
        :class:`ValueError` for a shorter board; nuts returns an honest
        empty result there rather than raising, so this method surfaces the
        texture constraint.

        >>> BoardReport.from_board('7h2c9d').nuts.label
        <Label.THREE_OF_A_KIND: 'Three of a kind'>

        :param board: The board cards (a flop, turn, or river).
        :param hand_type: The hand type to evaluate with, defaults to
                          :class:`pokerkit.hands.StandardHighHand`.
        :return: The composed hero-independent report.
        :raises ValueError: If the board has too few cards for a texture.
        """
        return cls(
            texture=BoardTexture.from_board(board),
            nuts=Nuts.from_board(board, hand_type=hand_type),
        )