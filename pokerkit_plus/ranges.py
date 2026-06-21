""":mod:`pokerkit_plus.ranges` implements range construction and the
range/nut advantage.

Ranges are the exact shape pokerkit speaks: a ``set`` of ``frozenset`` of
:class:`pokerkit.utilities.Card` (the output of
:func:`pokerkit.analysis.parse_range` and the input of
:func:`pokerkit.analysis.calculate_equities`). This module adds canonical
hole-class notation (``AA``/``KQs``/``KQo``), a board-aware value-range
builder keyed by a made-hand category floor, real Monte-Carlo *equity*
advantage (delegated to pokerkit), and an exact combo-count *nut* advantage.

The value-range category floors are a documented, overridable default (a
product choice, not a correctness one); pass an explicit ``floor`` to tune.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum, unique

from pokerkit.analysis import calculate_equities, parse_range
from pokerkit.hands import Hand, StandardHighHand
from pokerkit.lookups import Label
from pokerkit.utilities import Card, CardsLike, Deck, Rank, RankOrder

from pokerkit_plus._semantic import _live_cards
from pokerkit_plus.combos import Nuts, made_label, meets

Combos = frozenset[frozenset[Card]]
"""The canonical range shape: a set of two-card combos.

This matches :func:`pokerkit.analysis.parse_range` output and
:func:`pokerkit.analysis.calculate_equities` input, so ranges round-trip
through pokerkit untouched.
"""


@unique
class AdvantageBasis(StrEnum):
    """The metric a range advantage is measured on.

    >>> AdvantageBasis.EQUITY
    <AdvantageBasis.EQUITY: 'Equity'>
    >>> AdvantageBasis.NUT_SHARE
    <AdvantageBasis.NUT_SHARE: 'Nut share'>
    """

    EQUITY = 'Equity'
    """Share of pooled all-in equity (Monte-Carlo)."""
    NUT_SHARE = 'Nut share'
    """Share of the nut-category combos (exact combo count)."""


@unique
class Aggression(StrEnum):
    """A coarse postflop aggression level for value-range construction.

    Higher aggression maps to a stronger made-hand floor. The mapping is a
    documented default (see :func:`build_value_range`), not a rule.

    >>> Aggression.RAISED
    <Aggression.RAISED: 'Raised'>
    """

    NO_BET = 'No bet'
    """No bet yet this street (checked)."""
    SINGLE_BET = 'Single bet'
    """A single bet."""
    RAISED = 'Raised'
    """A bet and at least one raise."""


AGGRESSION_ORDER: tuple[Aggression, ...] = (
    Aggression.NO_BET,
    Aggression.SINGLE_BET,
    Aggression.RAISED,
)
"""The aggression levels, ordered from least to most aggressive."""

__VALUE_FLOOR: dict[Aggression, Label] = {
    Aggression.NO_BET: Label.ONE_PAIR,
    Aggression.SINGLE_BET: Label.TWO_PAIR,
    Aggression.RAISED: Label.THREE_OF_A_KIND,
}
"""Default made-hand category floor for each aggression level.

A documented, overridable product default: a checked street keeps any
pair or better, a single bet wants two pair or better, a raise wants a set
or better. Pass ``floor`` to :func:`build_value_range` to override.
"""


@dataclass(frozen=True)
class ComboClass:
    """A canonical preflop hole class: a pair, suited, or offsuit holding.

    Use :meth:`from_cards`. This is the hole-class axis (the 169 starting
    hands), distinct from a made-hand category. Pairedness and suitedness
    are read from pokerkit's own card helpers; no flat ``Suitedness`` enum
    is introduced.

    >>> ComboClass.from_cards('AsKs').notation
    'AKs'
    >>> ComboClass.from_cards('AsKd').notation
    'AKo'
    >>> ComboClass.from_cards('AsAd').notation
    'AA'

    :param high: The higher of the two ranks.
    :param low: The lower of the two ranks (equal to ``high`` for a pair).
    :param suited: Whether the two cards share a suit.
    """

    high: Rank
    """The higher of the two ranks."""
    low: Rank
    """The lower of the two ranks (equal to ``high`` for a pair)."""
    suited: bool
    """Whether the two cards share a suit."""

    @classmethod
    def from_cards(
            cls,
            cards: CardsLike,
            *,
            rank_order: RankOrder = RankOrder.STANDARD,
    ) -> ComboClass:
        """Create the hole class of exactly two cards.

        >>> ComboClass.from_cards('KdQh').notation
        'KQo'

        :param cards: The two hole cards.
        :param rank_order: The rank ordering, defaults to
                           :attr:`pokerkit.utilities.RankOrder` ``.STANDARD``.
        :return: The hole class.
        :raises ValueError: If not exactly two cards are given.
        """
        cleaned = Card.clean(cards)

        if len(cleaned) != 2:
            raise ValueError(
                f'A hole class needs exactly two cards, got {repr(cards)}.',
            )

        first, second = cleaned
        high, low = sorted(
            (first.rank, second.rank),
            key=rank_order.index,
            reverse=True,
        )

        return cls(high, low, first.suit is second.suit)

    @property
    def notation(self) -> str:
        """Return the canonical notation (``AA`` / ``KQs`` / ``KQo``).

        >>> ComboClass.from_cards('QsQd').notation
        'QQ'
        >>> ComboClass.from_cards('JsTs').notation
        'JTs'

        :return: The canonical hole-class notation.
        """
        if self.high is self.low:
            return f'{self.high.value}{self.low.value}'

        return f'{self.high.value}{self.low.value}{"s" if self.suited else "o"}'


@dataclass(frozen=True)
class Advantage:
    """One side's share of a two-player range advantage.

    Shares always sum to ``1.0`` (``0.5``/``0.5`` when neither side has any
    qualifying holding). :attr:`basis` records how the share was measured.

    :param hero_share: The hero's share, in ``[0.0, 1.0]``.
    :param villain_share: The villain's share (``1 - hero_share``).
    :param basis: The metric the share was measured on.
    """

    hero_share: float
    """The hero's share, in ``[0.0, 1.0]``."""
    villain_share: float
    """The villain's share (``1 - hero_share``)."""
    basis: AdvantageBasis
    """The metric the share was measured on."""


def expand_range(
        *notation: str,
        rank_order: RankOrder = RankOrder.STANDARD,
) -> Combos:
    """Expand range notation into concrete two-card combos.

    A thin typed wrapper over :func:`pokerkit.analysis.parse_range`; the
    result is the canonical :data:`Combos` shape.

    >>> rng = expand_range('AKs', 'QQ+')
    >>> frozenset(Card.parse('AsKs')) in rng
    True
    >>> len(rng)  # AKs (4) + QQ, KK, AA (18)
    22

    :param notation: The range notation tokens (e.g. ``'AKs'``, ``'QQ+'``).
    :param rank_order: The rank ordering, defaults to
                       :attr:`pokerkit.utilities.RankOrder` ``.STANDARD``.
    :return: The expanded combos.
    """
    return frozenset(parse_range(*notation, rank_order=rank_order))


def build_value_range(
        board: CardsLike,
        aggression: Aggression = Aggression.SINGLE_BET,
        *,
        hand_type: type[Hand] = StandardHighHand,
        floor: Label | None = None,
        dead: CardsLike = (),
) -> Combos:
    """Build the value range on a board: combos meeting a category floor.

    Every live two-card combo is evaluated on the board, and those whose
    made category meets the floor are kept. The floor defaults to the
    documented per-aggression default (:data:`__VALUE_FLOOR`); pass
    ``floor`` to override it directly.

    >>> rng = build_value_range('Kh7c2d', Aggression.SINGLE_BET)
    >>> frozenset(Card.parse('KsKd')) in rng  # a set meets two-pair floor
    True
    >>> frozenset(Card.parse('7h7s')) in rng  # trip sevens, kept
    True
    >>> frozenset(Card.parse('Ah3h')) in rng  # ace high, below floor
    False

    :param board: The board cards.
    :param aggression: The aggression level selecting the default floor.
    :param hand_type: The hand type to evaluate with, defaults to
                      :class:`pokerkit.hands.StandardHighHand`.
    :param floor: An explicit category floor, overriding ``aggression``.
    :param dead: The optional dead cards to remove from the live deck.
    :return: The value-range combos.
    """
    board_cards = Card.clean(board)
    threshold = floor if floor is not None else __VALUE_FLOOR[aggression]
    live = tuple(_live_cards(board_cards, dead))
    value: set[frozenset[Card]] = set()

    for i, first in enumerate(live):
        for second in live[i + 1:]:
            label = made_label((first, second), board_cards, hand_type=hand_type)

            if label is not None and meets(label, threshold):
                value.add(frozenset((first, second)))

    return frozenset(value)


def calculate_range_advantage(
        hero: Iterable[Iterable[Card]],
        villain: Iterable[Iterable[Card]],
        board: CardsLike,
        *,
        hand_type: type[Hand] = StandardHighHand,
        deck: Deck = Deck.STANDARD,
        sample_count: int = 10000,
) -> Advantage:
    """Return the equity advantage of hero vs villain on a board.

    Pooled all-in equity is delegated to
    :func:`pokerkit.analysis.calculate_equities` (Monte-Carlo); the result
    is stochastic, so seed :mod:`random` and raise ``sample_count`` for
    reproducible, tighter estimates. An empty range on either side yields a
    neutral ``0.5``/``0.5``.

    :param hero: The hero's range (combos).
    :param villain: The villain's range (combos).
    :param board: The board cards.
    :param hand_type: The hand type to evaluate with, defaults to
                      :class:`pokerkit.hands.StandardHighHand`.
    :param deck: The deck, defaults to
                 :attr:`pokerkit.utilities.Deck.STANDARD`.
    :param sample_count: The Monte-Carlo sample count.
    :return: The equity advantage.
    """
    hero_range = [list(combo) for combo in hero]
    villain_range = [list(combo) for combo in villain]

    if not hero_range or not villain_range:
        return Advantage(0.5, 0.5, AdvantageBasis.EQUITY)

    hero_equity, villain_equity = calculate_equities(
        (hero_range, villain_range),
        Card.clean(board),
        2,
        5,
        deck,
        (hand_type,),
        sample_count=sample_count,
    )
    total = hero_equity + villain_equity

    if total == 0:
        return Advantage(0.5, 0.5, AdvantageBasis.EQUITY)

    return Advantage(
        hero_equity / total,
        villain_equity / total,
        AdvantageBasis.EQUITY,
    )


def nut_advantage(
        hero: Iterable[Iterable[Card]],
        villain: Iterable[Iterable[Card]],
        board: CardsLike,
        *,
        hand_type: type[Hand] = StandardHighHand,
) -> Advantage:
    """Return the nut advantage: each side's share of nut-category combos.

    Exact (no sampling): the board's nut category is read from
    :meth:`pokerkit_plus.combos.Nuts.from_board`, and each side's combos
    that make that category or better are counted. The share is the hero's
    count over the combined count, ``0.5``/``0.5`` when neither side has a
    nut-category holding (or the board is too short).

    :param hero: The hero's range (combos).
    :param villain: The villain's range (combos).
    :param board: The board cards.
    :param hand_type: The hand type to evaluate with, defaults to
                      :class:`pokerkit.hands.StandardHighHand`.
    :return: The nut advantage.
    """
    board_cards = Card.clean(board)
    nuts = Nuts.from_board(board_cards, hand_type=hand_type)

    if nuts.hand is None:
        return Advantage(0.5, 0.5, AdvantageBasis.NUT_SHARE)

    floor = nuts.hand.entry.label

    def count(range_: Iterable[Iterable[Card]]) -> int:
        total = 0

        for combo in range_:
            label = made_label(combo, board_cards, hand_type=hand_type)

            if label is not None and meets(label, floor):
                total += 1

        return total

    hero_count = count(hero)
    villain_count = count(villain)
    total = hero_count + villain_count

    if total == 0:
        return Advantage(0.5, 0.5, AdvantageBasis.NUT_SHARE)

    return Advantage(
        hero_count / total,
        villain_count / total,
        AdvantageBasis.NUT_SHARE,
    )
