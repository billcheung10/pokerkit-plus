""":mod:`pokerkit_plus.texture` implements classes related to board
texture.

Board texture is a hero-independent reading of the community cards: how
wet or dry the board is, how connected the ranks are, what rank band the
board lives in, and which straight and flush draws the board makes
available. Every reading is derived from :mod:`pokerkit` primitives so
that ranks live on a single :class:`pokerkit.utilities.RankOrder` scale
(with the ace-low wheel handled by that scale, never by ace-as-1/14
magic) and pairedness/suitedness reuse the
:class:`pokerkit.utilities.Card` class methods.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import ClassVar

from pokerkit.utilities import Card, CardsLike, Rank, RankOrder

__ACE_INDEX = RankOrder.STANDARD.index(Rank.ACE)
__TEN_INDEX = RankOrder.STANDARD.index(Rank.TEN)
__SEVEN_INDEX = RankOrder.STANDARD.index(Rank.SEVEN)
__STRAIGHT_SIZE = 5


@unique
class Wetness(StrEnum):
    """The enum class for board wetness.

    Wetness is a coarse summary of how many draws a board makes
    available. It is *derived* from connectivity together with the
    board's suit and pair structure, not an independent input.

    >>> Wetness.DRY
    <Wetness.DRY: 'Dry'>
    >>> Wetness.WET
    <Wetness.WET: 'Wet'>
    """

    DRY = 'Dry'
    """The wetness of boards offering essentially no draws."""
    SEMI_WET = 'Semi-wet'
    """The wetness of boards offering some, but not many, draws."""
    WET = 'Wet'
    """The wetness of boards offering many draws."""


WETNESS_ORDER: tuple[Wetness, ...] = (
    Wetness.DRY,
    Wetness.SEMI_WET,
    Wetness.WET,
)
"""The wetness levels, ordered from driest to wettest."""


@unique
class Connectivity(StrEnum):
    """The enum class for board connectivity.

    Connectivity grades how close the board's distinct ranks sit on the
    single :class:`pokerkit.utilities.RankOrder` scale, with the ace-low
    wheel handled by that scale. The zero point
    (:attr:`Connectivity.DISCONNECTED`) is a real grade rather than an
    absence, so this enum keeps a member for it.

    Pairs never inflate connectivity: only distinct ranks are
    considered, so ``6h7c7d8s`` reads exactly like ``6h7c8s``.

    >>> Connectivity.DISCONNECTED
    <Connectivity.DISCONNECTED: 'Disconnected'>
    >>> Connectivity.HIGH
    <Connectivity.HIGH: 'High'>
    """

    DISCONNECTED = 'Disconnected'
    """The connectivity of boards whose ranks cannot share a straight."""
    LOW = 'Low'
    """The connectivity of boards with two straight-reachable ranks."""
    MEDIUM = 'Medium'
    """The connectivity of boards with three loosely clustered ranks."""
    HIGH = 'High'
    """The connectivity of boards with tightly clustered ranks."""


CONNECTIVITY_ORDER: tuple[Connectivity, ...] = (
    Connectivity.DISCONNECTED,
    Connectivity.LOW,
    Connectivity.MEDIUM,
    Connectivity.HIGH,
)
"""The connectivity levels, ordered from least to most connected."""


@unique
class RankBand(StrEnum):
    """The enum class for the board's rank band.

    The band reflects the highest card on the board, split as deuce to
    six (low), seven to nine (medium), and ten to ace (high, i.e., the
    broadway ranks, aligning with
    :attr:`pokerkit.utilities.RankOrder` ``.ROYAL_POKER``). It describes
    the board only.

    >>> RankBand.LOW
    <RankBand.LOW: 'Low'>
    >>> RankBand.HIGH
    <RankBand.HIGH: 'High'>
    """

    LOW = 'Low'
    """The band of boards topping out at deuce through six."""
    MEDIUM = 'Medium'
    """The band of boards topping out at seven through nine."""
    HIGH = 'High'
    """The band of boards topping out at ten through ace."""


RANK_BAND_ORDER: tuple[RankBand, ...] = (
    RankBand.LOW,
    RankBand.MEDIUM,
    RankBand.HIGH,
)
"""The rank bands, ordered from lowest to highest."""


@unique
class StraightDraw(StrEnum):
    """The enum class for the straight draw a board offers.

    This describes the strongest straight draw the board makes available
    to a typical two-card hand, derived from the gaps between the board's
    distinct ranks on a single :class:`pokerkit.utilities.RankOrder`
    scale (wheel included). It is exposed as an optional field with no
    ``NONE`` member: a board with no straight draw reads as ``None``.

    >>> StraightDraw.OPEN_ENDED
    <StraightDraw.OPEN_ENDED: 'Open-ended'>
    >>> StraightDraw.GUTSHOT
    <StraightDraw.GUTSHOT: 'Gutshot'>
    """

    BACKDOOR = 'Backdoor'
    """The straight draw needing two more cards (runner-runner)."""
    GUTSHOT = 'Gutshot'
    """The straight draw completed by a single inside rank."""
    OPEN_ENDED = 'Open-ended'
    """The straight draw completed by ranks on either end."""
    DOUBLE_GUTSHOT = 'Double gutshot'
    """The straight draw with two distinct one-card completions."""


STRAIGHT_DRAW_ORDER: tuple[StraightDraw, ...] = (
    StraightDraw.BACKDOOR,
    StraightDraw.GUTSHOT,
    StraightDraw.OPEN_ENDED,
    StraightDraw.DOUBLE_GUTSHOT,
)
"""The straight draws, ordered from weakest to strongest."""


@unique
class FlushDraw(StrEnum):
    """The enum class for the flush draw a board offers.

    A board with three or more cards of one suit is
    :attr:`FlushDraw.LIVE` (a single matching hole card already makes a
    flush draw, or better); a two-tone board is :attr:`FlushDraw.BACKDOOR`
    (a flush needs two more cards). It is exposed as an optional field with
    no ``NONE`` member: a rainbow board reads as ``None``. Nut-ness of a
    flush draw is a hand-relative concept handled elsewhere, not by this
    enum.

    >>> FlushDraw.LIVE
    <FlushDraw.LIVE: 'Live'>
    >>> FlushDraw.BACKDOOR
    <FlushDraw.BACKDOOR: 'Backdoor'>
    """

    BACKDOOR = 'Backdoor'
    """The flush draw needing two more cards of the suit."""
    LIVE = 'Live'
    """The flush draw needing one more card, or already made."""


FLUSH_DRAW_ORDER: tuple[FlushDraw, ...] = (
    FlushDraw.BACKDOOR,
    FlushDraw.LIVE,
)
"""The flush draws, ordered from weakest to strongest."""


def are_two_tone(cards: CardsLike) -> bool:
    """Return whether the cards are two-tone.

    The cards are two-tone if they span exactly two suits.

    >>> are_two_tone('Ah7h2c')
    True
    >>> are_two_tone('AsKsQs')
    False
    >>> are_two_tone('Ac7d2h')
    False
    >>> are_two_tone('Ks7s7d')
    True

    :param cards: The cards to determine two-tone-ness from.
    :return: ``True`` if the cards are two-tone, otherwise ``False``.
    """
    return len(set(Card.get_suits(cards))) == 2


def are_monotone(cards: CardsLike) -> bool:
    """Return whether the cards are monotone.

    The cards are monotone if they all share a common suit. This is an
    alias of :meth:`pokerkit.utilities.Card.are_suited` named for the
    board-texture domain.

    >>> are_monotone('AsKsQs')
    True
    >>> are_monotone('Ah7h2c')
    False
    >>> are_monotone(())
    True

    :param cards: The cards to determine monotone-ness from.
    :return: ``True`` if the cards are monotone, otherwise ``False``.
    """
    return Card.are_suited(cards)


def are_rainbow(cards: CardsLike) -> bool:
    """Return whether the cards are rainbow.

    The cards are rainbow if no two of them share a common suit. This
    delegates to :meth:`pokerkit.utilities.Card.are_rainbow`.

    >>> are_rainbow('Ac7d2h')
    True
    >>> are_rainbow('Ah7h2c')
    False
    >>> are_rainbow('AsKsQs')
    False

    :param cards: The cards to determine rainbow-ness from.
    :return: ``True`` if the cards are rainbow, otherwise ``False``.
    """
    return Card.are_rainbow(cards)


def _rank_positions(
        cards: tuple[Card, ...],
) -> tuple[tuple[int, ...], ...]:
    """Return the distinct rank positions of the cards, wheel variants.

    The positions index into
    :attr:`pokerkit.utilities.RankOrder` ``.STANDARD``, deduplicated so
    that pairs never double-count. When an ace is present, a second
    variant is appended in which the ace sits just below the deuce
    (position ``-1``), so the wheel is read off the same scale rather than
    special-cased.

    >>> _rank_positions(Card.clean('6h7c7d8s'))
    ((4, 5, 6),)
    >>> _rank_positions(Card.clean('As2c3d'))
    ((0, 1, 12), (-1, 0, 1))
    >>> _rank_positions(Card.clean('2c2d2h'))
    ((0,),)

    :param cards: The cleaned cards.
    :return: The distinct rank positions, with wheel variants if any.
    """
    ranks = {card.rank for card in cards}
    base = tuple(sorted(RankOrder.STANDARD.index(rank) for rank in ranks))

    if __ACE_INDEX in base:
        wheel = tuple(
            sorted(-1 if p == __ACE_INDEX else p for p in base),
        )

        return base, wheel

    return (base,)


def _best_window(cards: tuple[Card, ...]) -> tuple[int, ...]:
    """Return the densest straight window of the board's distinct ranks.

    A straight window is five consecutive positions on the
    :class:`pokerkit.utilities.RankOrder` scale. This scans every window
    over every wheel variant and returns the distinct board positions
    inside the window that maximizes the count and, on ties, minimizes
    the span. The result is the shared substrate for both connectivity
    and straight-draw reads, computed once per board.

    >>> _best_window(Card.clean('6h7c7d8s'))
    (4, 5, 6)
    >>> _best_window(Card.clean('As2c3d'))
    (-1, 0, 1)
    >>> _best_window(Card.clean('2c7dKs'))
    (0,)

    :param cards: The cleaned cards.
    :return: The distinct positions inside the densest window.
    """
    best_key = (0, 1)
    best_window: tuple[int, ...] = ()

    for positions in _rank_positions(cards):
        for low in range(-1, __ACE_INDEX - __STRAIGHT_SIZE + 2):
            inside = tuple(
                p
                for p in positions
                if low <= p <= low + __STRAIGHT_SIZE - 1
            )

            if not inside:
                continue

            key = (len(inside), -(inside[-1] - inside[0]))

            if key > best_key:
                best_key = key
                best_window = inside

    return best_window


def _connectivity(window: tuple[int, ...]) -> Connectivity:
    """Return the connectivity for a precomputed densest window.

    The grade is read off the densest straight window (see
    :func:`_best_window`) of the board's *distinct* ranks, so pairs never
    inflate it and the wheel wraps. Two reachable ranks read as
    :attr:`Connectivity.LOW`; three tightly clustered ranks (span of two
    or less) read as :attr:`Connectivity.HIGH`; three looser ranks read as
    :attr:`Connectivity.MEDIUM`; four or more reachable ranks read as
    :attr:`Connectivity.HIGH`.

    >>> _connectivity(_best_window(Card.clean('6h7c7d8s')))
    <Connectivity.HIGH: 'High'>
    >>> _connectivity(_best_window(Card.clean('As2c3d')))
    <Connectivity.HIGH: 'High'>
    >>> _connectivity(_best_window(Card.clean('2h7d9c')))
    <Connectivity.LOW: 'Low'>
    >>> _connectivity(_best_window(Card.clean('Th9hQc')))
    <Connectivity.MEDIUM: 'Medium'>
    >>> _connectivity(_best_window(Card.clean('2c2d2h')))
    <Connectivity.DISCONNECTED: 'Disconnected'>

    :param window: The densest straight window's distinct positions.
    :return: The connectivity of the board.
    """
    count = len(window)

    if count <= 1:
        return Connectivity.DISCONNECTED
    elif count == 2:
        return Connectivity.LOW
    elif count == 3:
        if window[-1] - window[0] <= 2:
            return Connectivity.HIGH

        return Connectivity.MEDIUM

    return Connectivity.HIGH


def _straight_draw(window: tuple[int, ...]) -> StraightDraw | None:
    """Return the straight draw for a precomputed densest window.

    Three or more gapless ranks are open-ended, four or more ranks with
    an internal hole are a double gutshot, three ranks with a single hole
    are a gutshot, and two reachable ranks need runner-runner help
    (backdoor). A window with no straight texture returns ``None``.

    >>> _straight_draw(_best_window(Card.clean('6h7c7d8s')))
    <StraightDraw.OPEN_ENDED: 'Open-ended'>
    >>> _straight_draw(_best_window(Card.clean('As2c3d')))
    <StraightDraw.OPEN_ENDED: 'Open-ended'>
    >>> _straight_draw(_best_window(Card.clean('Th9hQc')))
    <StraightDraw.GUTSHOT: 'Gutshot'>
    >>> _straight_draw(_best_window(Card.clean('2h7d9c')))
    <StraightDraw.BACKDOOR: 'Backdoor'>
    >>> _straight_draw(_best_window(Card.clean('2c7dKs'))) is None
    True

    :param window: The densest straight window's distinct positions.
    :return: The straight draw the board offers, or ``None``.
    """
    count = len(window)

    if count < 2:
        return None

    span = window[-1] - window[0]
    gaps = sum(b - a - 1 for a, b in zip(window, window[1:]))

    if count >= 4:
        if gaps >= 1:
            return StraightDraw.DOUBLE_GUTSHOT

        return StraightDraw.OPEN_ENDED
    elif count == 3:
        if gaps == 0:
            return StraightDraw.OPEN_ENDED

        return StraightDraw.GUTSHOT
    elif span <= __STRAIGHT_SIZE - 2:
        return StraightDraw.BACKDOOR

    return None


def _flush_draw(cards: tuple[Card, ...]) -> FlushDraw | None:
    """Return the flush draw the board offers, or ``None``.

    Three or more cards of one suit make the draw live; exactly two of a
    suit make it a backdoor; a rainbow board returns ``None``.

    >>> _flush_draw(Card.clean('AsKsQs'))
    <FlushDraw.LIVE: 'Live'>
    >>> _flush_draw(Card.clean('Ah7h2c'))
    <FlushDraw.BACKDOOR: 'Backdoor'>
    >>> _flush_draw(Card.clean('Ac7d2h')) is None
    True

    :param cards: The cleaned cards.
    :return: The flush draw the board offers, or ``None``.
    """
    top = max(Counter(card.suit for card in cards).values())

    if top >= 3:
        return FlushDraw.LIVE
    elif top == 2:
        return FlushDraw.BACKDOOR

    return None


def _rank_band(cards: tuple[Card, ...]) -> RankBand:
    """Return the rank band of the board.

    The band is decided by the highest board rank on the single
    :class:`pokerkit.utilities.RankOrder` scale: ten or above is high,
    seven through nine is medium, and below seven is low.

    >>> _rank_band(Card.clean('As2c3d'))
    <RankBand.HIGH: 'High'>
    >>> _rank_band(Card.clean('9h8d7c'))
    <RankBand.MEDIUM: 'Medium'>
    >>> _rank_band(Card.clean('6h5d4c'))
    <RankBand.LOW: 'Low'>

    :param cards: The cleaned cards.
    :return: The rank band of the board.
    """
    top = max(RankOrder.STANDARD.index(card.rank) for card in cards)

    if top >= __TEN_INDEX:
        return RankBand.HIGH
    elif top >= __SEVEN_INDEX:
        return RankBand.MEDIUM

    return RankBand.LOW


def _wetness(
        connectivity: Connectivity,
        straight_draw: StraightDraw | None,
        flush_draw: FlushDraw | None,
) -> Wetness:
    """Return the wetness derived from connectivity and draw structure.

    Wetness is not an independent input: a board is wet when it offers a
    live flush draw, high connectivity, or a backdoor flush atop at least
    medium connectivity; dry when it offers neither a flush nor any
    straight reach beyond a single low pair of ranks; and semi-wet
    otherwise.

    >>> _wetness(Connectivity.HIGH, StraightDraw.OPEN_ENDED, None)
    <Wetness.WET: 'Wet'>
    >>> _wetness(Connectivity.DISCONNECTED, None, None)
    <Wetness.DRY: 'Dry'>
    >>> _wetness(
    ...     Connectivity.LOW, StraightDraw.BACKDOOR, FlushDraw.BACKDOOR,
    ... )
    <Wetness.SEMI_WET: 'Semi-wet'>

    :param connectivity: The board connectivity.
    :param straight_draw: The board straight draw, or ``None``.
    :param flush_draw: The board flush draw, or ``None``.
    :return: The wetness of the board.
    """
    rank = CONNECTIVITY_ORDER.index(connectivity)
    live_flush = flush_draw is FlushDraw.LIVE
    backdoor_flush = flush_draw is FlushDraw.BACKDOOR

    if (
            live_flush
            or rank >= CONNECTIVITY_ORDER.index(Connectivity.HIGH)
            or (
                rank >= CONNECTIVITY_ORDER.index(Connectivity.MEDIUM)
                and backdoor_flush
            )
    ):
        return Wetness.WET
    elif (
            rank <= CONNECTIVITY_ORDER.index(Connectivity.LOW)
            and not backdoor_flush
    ):
        return Wetness.DRY

    return Wetness.SEMI_WET


@dataclass(frozen=True)
class BoardTexture:
    """The class for a hero-independent reading of a board.

    A board texture bundles every texture read into one frozen value
    object, computed once from a single cleaned tuple of cards via
    :meth:`from_board`. The densest straight window is computed once and
    shared by the connectivity and straight-draw reads. Optional draw
    fields are ``None`` when the board offers no such draw.

    >>> texture = BoardTexture.from_board('AsKsQs')
    >>> texture.wetness
    <Wetness.WET: 'Wet'>
    >>> texture.connectivity
    <Connectivity.HIGH: 'High'>
    >>> texture.rank_band
    <RankBand.HIGH: 'High'>
    >>> texture.straight_draw
    <StraightDraw.OPEN_ENDED: 'Open-ended'>
    >>> texture.flush_draw
    <FlushDraw.LIVE: 'Live'>
    >>> texture.are_monotone
    True
    >>> texture.are_rainbow
    False

    A paired connector does not over-count: ``6h7c7d8s`` reads exactly
    like its three distinct ranks.

    >>> BoardTexture.from_board('6h7c7d8s').connectivity
    <Connectivity.HIGH: 'High'>
    >>> BoardTexture.from_board('6h7c7d8s').straight_draw
    <StraightDraw.OPEN_ENDED: 'Open-ended'>

    The wheel wraps off the single rank scale, never via ace-as-1 magic.

    >>> BoardTexture.from_board('As2c3d').connectivity
    <Connectivity.HIGH: 'High'>
    >>> BoardTexture.from_board('As2c3d').straight_draw
    <StraightDraw.OPEN_ENDED: 'Open-ended'>

    A bone-dry board reads dry with no draws.

    >>> dry = BoardTexture.from_board('2c7dKs')
    >>> dry.wetness
    <Wetness.DRY: 'Dry'>
    >>> dry.connectivity
    <Connectivity.DISCONNECTED: 'Disconnected'>
    >>> dry.straight_draw is None
    True
    >>> dry.flush_draw is None
    True

    Boards shorter than a flop are rejected.

    >>> BoardTexture.from_board('AsKs')
    Traceback (most recent call last):
        ...
    ValueError: The board 'AsKs' has too few cards for a texture.

    :param cards: The cleaned board cards.
    :param wetness: The wetness of the board.
    :param connectivity: The connectivity of the board.
    :param rank_band: The rank band of the board.
    :param straight_draw: The straight draw offered, or ``None``.
    :param flush_draw: The flush draw offered, or ``None``.
    :param are_two_tone: Whether the board spans exactly two suits.
    :param are_monotone: Whether the board is monotone.
    :param are_rainbow: Whether the board is rainbow.
    """

    MIN_BOARD_SIZE: ClassVar[int] = 3
    """The minimum number of board cards for a texture."""
    cards: tuple[Card, ...]
    """The cleaned board cards."""
    wetness: Wetness
    """The wetness of the board."""
    connectivity: Connectivity
    """The connectivity of the board."""
    rank_band: RankBand
    """The rank band of the board."""
    straight_draw: StraightDraw | None
    """The straight draw the board offers, or ``None``."""
    flush_draw: FlushDraw | None
    """The flush draw the board offers, or ``None``."""
    are_two_tone: bool
    """Whether the board spans exactly two suits."""
    are_monotone: bool
    """Whether the board is monotone (all one suit)."""
    are_rainbow: bool
    """Whether the board is rainbow (no two suits shared)."""

    @classmethod
    def from_board(cls, board: CardsLike) -> BoardTexture:
        """Read the texture of a board.

        The board is cleaned once via
        :meth:`pokerkit.utilities.Card.clean`, the densest straight window
        is computed once, and every field is derived from that single
        tuple over a single :class:`pokerkit.utilities.RankOrder` scale
        (wheel included).

        >>> BoardTexture.from_board('Th9hQc').straight_draw
        <StraightDraw.GUTSHOT: 'Gutshot'>
        >>> BoardTexture.from_board('Ah7h2c').flush_draw
        <FlushDraw.BACKDOOR: 'Backdoor'>
        >>> BoardTexture.from_board('JhTc9d8s').wetness
        <Wetness.WET: 'Wet'>

        :param board: The board cards.
        :return: The texture of the board.
        :raises ValueError: If the board has too few cards.
        """
        cards = Card.clean(board)

        if len(cards) < cls.MIN_BOARD_SIZE:
            raise ValueError(
                f'The board {repr(board)} has too few cards for a'
                ' texture.',
            )

        window = _best_window(cards)
        connectivity = _connectivity(window)
        straight_draw = _straight_draw(window)
        flush_draw = _flush_draw(cards)

        return cls(
            cards=cards,
            wetness=_wetness(connectivity, straight_draw, flush_draw),
            connectivity=connectivity,
            rank_band=_rank_band(cards),
            straight_draw=straight_draw,
            flush_draw=flush_draw,
            are_two_tone=are_two_tone(cards),
            are_monotone=are_monotone(cards),
            are_rainbow=are_rainbow(cards),
        )
