""":mod:`pokerkit_plus.combos` implements board-relative made-hand
categories and nut enumeration.

The made-hand category vocabulary is PokerKit's own
:class:`pokerkit.lookups.Label` (nine members, no royal); strength
ordering lives in :data:`CATEGORY_ORDER` (mirroring how rank ordering
lives in :class:`pokerkit.utilities.RankOrder` rather than on
:class:`pokerkit.utilities.Rank` itself), threshold comparison is
:func:`meets`, and royal flushes are refined with
:func:`pokerkit_plus._semantic._is_royal`. Nut and per-category combo
enumeration reuse a single memoized pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokerkit.hands import Hand, StandardHighHand
from pokerkit.lookups import Label
from pokerkit.utilities import CardsLike

from pokerkit_plus._semantic import (
    HoleCombo as HoleCombo,
    _is_royal,
    _nuts_core,
    _used,
)

CATEGORY_ORDER: tuple[Label, ...] = (
    Label.HIGH_CARD,
    Label.ONE_PAIR,
    Label.TWO_PAIR,
    Label.THREE_OF_A_KIND,
    Label.STRAIGHT,
    Label.FLUSH,
    Label.FULL_HOUSE,
    Label.FOUR_OF_A_KIND,
    Label.STRAIGHT_FLUSH,
)
"""The made-hand categories in ascending strength order.

This mirrors :class:`pokerkit.lookups.Label`'s definition order, which is
itself ascending in strength. PokerKit's ``Label`` has exactly nine
members and intentionally has no ``ROYAL_FLUSH``; royal flushes are
refined out with :func:`pokerkit_plus._semantic._is_royal` rather than by
adding a tenth label.

>>> CATEGORY_ORDER[0]
<Label.HIGH_CARD: 'High card'>
>>> CATEGORY_ORDER[-1]
<Label.STRAIGHT_FLUSH: 'Straight flush'>
>>> len(CATEGORY_ORDER)
9
"""

__CATEGORY_RANKS: dict[Label, int] = {
    label: index for index, label in enumerate(CATEGORY_ORDER)
}


def meets(label: Label, floor: Label) -> bool:
    """Return whether the category is at least as strong as the floor.

    Strength is compared by position in :data:`CATEGORY_ORDER` (a single
    scale shared with PokerKit's ``Label`` ordering), never by hardcoded
    numbers.

    >>> meets(Label.FLUSH, Label.TWO_PAIR)
    True
    >>> meets(Label.ONE_PAIR, Label.ONE_PAIR)
    True
    >>> meets(Label.ONE_PAIR, Label.STRAIGHT)
    False

    :param label: The category being tested.
    :param floor: The minimum acceptable category.
    :return: ``True`` if ``label`` is at least as strong as ``floor``.
    """
    return __CATEGORY_RANKS[label] >= __CATEGORY_RANKS[floor]


def made_label(
        hole: CardsLike,
        board: CardsLike = (),
        *,
        hand_type: type[Hand] = StandardHighHand,
) -> Label | None:
    """Return the made-hand category for the hole cards on the board.

    The category is read straight off PokerKit's evaluator
    (``hand_type.from_game_or_none(...).entry.label``); no suit/rank
    bookkeeping is done by hand. Returns ``None`` (never raising) when no
    valid hand can be formed for ``hand_type`` from the given cards.

    >>> made_label('AsAc', 'Kh3sAd')
    <Label.THREE_OF_A_KIND: 'Three of a kind'>
    >>> made_label('7h2c', '9d4s5c')
    <Label.HIGH_CARD: 'High card'>
    >>> made_label('AsKs', 'QsJsTs')
    <Label.STRAIGHT_FLUSH: 'Straight flush'>
    >>> made_label('Ac', '') is None
    True

    :param hole: The hole cards.
    :param board: The optional board cards.
    :param hand_type: The hand type to evaluate with, defaults to
                      :class:`pokerkit.hands.StandardHighHand`.
    :return: The made-hand category, or ``None`` if no valid hand.
    """
    hand = hand_type.from_game_or_none(hole, board)

    if hand is None:
        return None

    return hand.entry.label


@dataclass(frozen=True)
class Nuts:
    """The nuts for a board: the strongest makeable hand and its combos.

    Use :meth:`from_board` to construct. The result reuses the memoized
    :func:`pokerkit_plus._semantic._nuts_core`, so repeated queries on the
    same board (and the category-combo consumer) share a single
    enumeration.

    >>> nuts = Nuts.from_board('AsKsQs')
    >>> nuts.label
    <Label.STRAIGHT_FLUSH: 'Straight flush'>
    >>> nuts.is_royal
    True
    >>> sorted(map(repr, nuts.combos[0].cards))
    ['Js', 'Ts']

    When the board is itself the nuts, every live combo ties, so
    :attr:`board_is_nuts` is ``True`` (no hole card can block the nuts).

    >>> nuts = Nuts.from_board('AcAdAhAsKc')
    >>> nuts.label
    <Label.FOUR_OF_A_KIND: 'Four of a kind'>
    >>> nuts.board_is_nuts
    True

    A board shorter than three cards yields an honest empty result rather
    than ``None`` or an exception.

    >>> empty = Nuts.from_board('AsKs')
    >>> empty.hand is None
    True
    >>> empty.combos
    ()
    >>> empty.label is None
    True

    :param hand: The strongest makeable hand, or ``None`` for a short
                 board.
    :param combos: The combos tying the strongest hand.
    :param candidate_count: The number of live two-card combos enumerated.
    """

    hand: Hand | None
    """The strongest makeable hand, or ``None`` for a short board."""
    combos: tuple[HoleCombo, ...]
    """The combos tying the strongest hand."""
    candidate_count: int
    """The number of live two-card combos enumerated."""

    @classmethod
    def from_board(
            cls,
            board: CardsLike,
            *,
            hand_type: type[Hand] = StandardHighHand,
            dead: CardsLike = (),
    ) -> Nuts:
        """Create the nuts for a board.

        Input is normalized via :meth:`pokerkit.utilities.Card.clean` and
        the work is delegated to the memoized
        :func:`pokerkit_plus._semantic._nuts_core`, so this never
        re-enumerates a board it has already seen for the same dead cards
        and hand type.

        >>> Nuts.from_board('7h2c9d').label
        <Label.THREE_OF_A_KIND: 'Three of a kind'>
        >>> Nuts.from_board('Ah').hand is None
        True

        :param board: The board cards.
        :param hand_type: The hand type to evaluate with, defaults to
                          :class:`pokerkit.hands.StandardHighHand`.
        :param dead: The optional dead cards to remove from the live deck.
        :return: The nuts result (never ``None``).
        """
        core = _nuts_core(_used(board), hand_type, _used(dead))

        return cls(core.hand, core.combos, core.candidate_count)

    @property
    def label(self) -> Label | None:
        """Return the category of the nut hand.

        >>> Nuts.from_board('7h2c9d').label
        <Label.THREE_OF_A_KIND: 'Three of a kind'>
        >>> Nuts.from_board('As').label is None
        True

        :return: The nut category, or ``None`` if the board is too short.
        """
        if self.hand is None:
            return None

        return self.hand.entry.label

    @property
    def is_royal(self) -> bool:
        """Return whether the nut hand is a royal flush.

        >>> Nuts.from_board('AsKsQs').is_royal
        True
        >>> Nuts.from_board('7h2c9d').is_royal
        False

        :return: ``True`` if the nuts is a royal flush, otherwise
                 ``False``.
        """
        if self.hand is None:
            return False

        return _is_royal(self.hand)

    @property
    def board_is_nuts(self) -> bool:
        """Return whether the board itself is the nuts.

        This is ``True`` when every live combo ties the strongest hand
        (e.g. a quad board), which means no hole card can block the nuts.
        Blocker logic (a later module) must special-case this to avoid
        reporting phantom blockers.

        >>> Nuts.from_board('AcAdAhAsKc').board_is_nuts
        True
        >>> Nuts.from_board('7h2c9d').board_is_nuts
        False
        >>> Nuts.from_board('Ah').board_is_nuts
        False

        :return: ``True`` if every live combo ties the nuts.
        """
        if not self.combos:
            return False

        return len(self.combos) == self.candidate_count


@dataclass(frozen=True)
class CategoryCombos:
    """All live two-card combos on a board, grouped by made category.

    Use :meth:`from_board`. This reuses the same memoized
    :func:`pokerkit_plus._semantic._nuts_core` enumeration as
    :class:`Nuts`; the per-category grouping is built in that single pass,
    so a warm board is O(1) and ``from_game`` is called exactly once per
    combo.

    >>> cc = CategoryCombos.from_board('7h2c9d')
    >>> cc.nuts.label
    <Label.THREE_OF_A_KIND: 'Three of a kind'>
    >>> Label.THREE_OF_A_KIND in cc.by_category
    True
    >>> all(c.hand.entry.label is Label.FLUSH
    ...     for c in cc.for_(Label.FLUSH))
    True

    :param by_category: A mapping from each made category to the combos
                        that make it, in ascending strength order.
    :param nuts: The nuts for the board (shares the memoized core).
    """

    by_category: dict[Label, tuple[HoleCombo, ...]]
    """A mapping from each made category to the combos that make it."""
    nuts: Nuts
    """The nuts for the board."""

    @classmethod
    def from_board(
            cls,
            board: CardsLike,
            *,
            hand_type: type[Hand] = StandardHighHand,
            dead: CardsLike = (),
    ) -> CategoryCombos:
        """Create the category-grouped combos for a board.

        Both the nut hand and the per-category grouping come from the one
        memoized :func:`pokerkit_plus._semantic._nuts_core` pass; this
        method only re-orders the grouping by :data:`CATEGORY_ORDER` and
        never re-evaluates a combo.

        >>> CategoryCombos.from_board('AsKsQs').nuts.is_royal
        True

        :param board: The board cards.
        :param hand_type: The hand type to evaluate with, defaults to
                          :class:`pokerkit.hands.StandardHighHand`.
        :param dead: The optional dead cards to remove from the live deck.
        :return: The category-grouped combos.
        """
        core = _nuts_core(_used(board), hand_type, _used(dead))
        nuts = Nuts(core.hand, core.combos, core.candidate_count)
        by_category = {
            label: core.by_category[label]
            for label in CATEGORY_ORDER
            if label in core.by_category
        }

        return cls(by_category, nuts)

    def for_(self, category: Label) -> tuple[HoleCombo, ...]:
        """Return the combos that make exactly the given category.

        >>> cc = CategoryCombos.from_board('7h2c9d')
        >>> combos = cc.for_(Label.THREE_OF_A_KIND)
        >>> all(c.hand.entry.label is Label.THREE_OF_A_KIND
        ...     for c in combos)
        True
        >>> cc.for_(Label.STRAIGHT_FLUSH)
        ()

        :param category: The made category to filter by.
        :return: The combos making exactly that category, possibly empty.
        """
        return self.by_category.get(category, ())
