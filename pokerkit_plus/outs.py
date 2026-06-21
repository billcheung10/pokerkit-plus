""":mod:`pokerkit_plus.outs` implements flop/turn out enumeration.

An *out* is a single live card whose arrival raises hero's made-hand
CATEGORY (its :class:`pokerkit.lookups.Label` moves up
:data:`pokerkit_plus.combos.CATEGORY_ORDER`) — the poker sense of "outs"
(a flush-completing card, a card that pairs a high card), not a mere kicker
bump within the same category. The question is answered by PokerKit's
evaluator, never by hand-rolled suit/rank bookkeeping: hero's current
category is read off ``hand_type.from_game`` once, every live runout card
is evaluated the same way, and a card is an out exactly when its made hand
lands in a strictly higher category. The result is grouped by the made-hand
:class:`pokerkit.lookups.Label` the card produces, so callers can ask
"which cards give me a flush" without the module ever inspecting a suit by
hand.

This evaluate-every-live-card design is deliberate (see the semantic-layer
plan, §3.2): the candidate set is only ~47 cards, so brute re-evaluation
is cheap, deterministic, and impossible to drift from PokerKit. It also
sidesteps the source implementation's bugs, which special-cased each
category by hand and silently dropped full-house and two-pair outs.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import ClassVar

from pokerkit.hands import Hand, StandardHighHand
from pokerkit.lookups import Label
from pokerkit.utilities import Card, CardsLike

from pokerkit_plus._semantic import _live_cards, _used
from pokerkit_plus.combos import CATEGORY_ORDER


@lru_cache(maxsize=None)
def _outs_core(
        hole: frozenset[Card],
        board: frozenset[Card],
        hand_type: type[Hand],
        dead: frozenset[Card],
) -> dict[Label, tuple[Card, ...]]:
    """Enumerate hero's outs once, memoized by hand, board, and dead set.

    Hero's baseline category is evaluated once with
    ``hand_type.from_game_or_none(hole, board)``. Each live runout card is
    then evaluated once with the card appended to the board, and is kept as
    an out iff its made hand lands in a strictly higher category than the
    baseline on :data:`pokerkit_plus.combos.CATEGORY_ORDER` (a kicker bump
    within the same category is not an out; the wheel is handled by the
    lookup, never by ace magic). The kept cards are bucketed by the
    made-hand :class:`pokerkit.lookups.Label` they produce, in live-deck
    (deterministic) order, so no card is ever re-evaluated or re-classified.

    The cache is keyed on :class:`frozenset` of
    :class:`pokerkit.utilities.Card` because ``Card`` is a frozen, hashable
    dataclass, so two equal card sets hash and compare equal regardless of
    order; ``hand_type`` is a hashable class. A baseline that cannot be
    formed (a board too short to make a five-card hand) yields an empty
    mapping rather than raising.

    >>> by_category = _outs_core(
    ...     _used('7h7s'), _used('Kd7c2s'), StandardHighHand, frozenset(),
    ... )
    >>> by_category[Label.FOUR_OF_A_KIND]
    (7d,)
    >>> len(by_category[Label.FULL_HOUSE])
    6

    :param hole: Hero's hole cards as a frozen set.
    :param board: The board cards as a frozen set.
    :param hand_type: The hand type to evaluate with.
    :param dead: Additional dead (used) cards as a frozen set.
    :return: A mapping from made category to the outs producing it.
    """
    hole_cards = tuple(hole)
    board_cards = tuple(board)
    baseline = hand_type.from_game_or_none(hole_cards, board_cards)

    if baseline is None:
        return {}

    baseline_rank = CATEGORY_ORDER.index(baseline.entry.label)
    grouped: dict[Label, list[Card]] = {}

    for card in _live_cards(hole, board, dead):
        hand = hand_type.from_game_or_none(hole_cards, (*board_cards, card))

        if hand is None:
            continue

        label = hand.entry.label

        if CATEGORY_ORDER.index(label) <= baseline_rank:
            continue

        grouped.setdefault(label, []).append(card)

    return {label: tuple(cards) for label, cards in grouped.items()}


@dataclass(frozen=True)
class Outs:
    """Hero's outs on a flop or turn, grouped by resulting category.

    Use :meth:`from_hand` to construct. An out is any single live card that
    raises hero's made-hand CATEGORY, decided entirely by PokerKit's
    evaluator (see :func:`_outs_core`). The outs are grouped by the
    made-hand :class:`pokerkit.lookups.Label` the card produces;
    :attr:`count` is the number of distinct outs across all categories.

    A flopped flush draw yields one out per remaining card of the suit,
    plus the cards that pair hero up into one pair.

    >>> outs = Outs.from_hand('AhKh', '2h7h9s')
    >>> len(outs.by_category[Label.FLUSH])
    9
    >>> outs.count
    23

    A flopped set enumerates every improving card, including the
    full-house and quad outs the source implementation dropped.

    >>> outs = Outs.from_hand('7h7s', 'Kd7c2s')
    >>> outs.by_category[Label.FOUR_OF_A_KIND]
    (7d,)
    >>> len(outs.by_category[Label.FULL_HOUSE])
    6

    Top pair with top kicker keeps its two-pair outs (the off-suit kings
    that pair hero's kicker), an out class the source dropped on ace-high
    boards.

    >>> outs = Outs.from_hand('AhKs', 'As8d3c')
    >>> sorted(
    ...     repr(card)
    ...     for card in outs.by_category[Label.TWO_PAIR]
    ...     if card.rank is next(Card.parse('Kc')).rank
    ... )
    ['Kc', 'Kd', 'Kh']

    A board shorter than a flop, or longer than a turn, is rejected.

    >>> Outs.from_hand('AhKh', 'As')
    Traceback (most recent call last):
        ...
    ValueError: The board 'As' must have 3 or 4 cards for outs.

    :param by_category: A mapping from each made category to the outs that
                        produce it, in live-deck order.
    """

    MIN_BOARD_SIZE: ClassVar[int] = 3
    """The minimum number of board cards for an out query (flop)."""
    MAX_BOARD_SIZE: ClassVar[int] = 4
    """The maximum number of board cards for an out query (turn)."""
    by_category: dict[Label, tuple[Card, ...]]
    """A mapping from each made category to the outs that produce it."""

    @classmethod
    def from_hand(
            cls,
            hole: CardsLike,
            board: CardsLike,
            *,
            hand_type: type[Hand] = StandardHighHand,
            dead: CardsLike = (),
    ) -> Outs:
        """Enumerate hero's outs on a flop or turn board.

        Input is normalized via :meth:`pokerkit.utilities.Card.clean`, and
        the work is delegated to the memoized :func:`_outs_core`, so a
        repeated query with the same hand, board, type, and dead set never
        re-evaluates. The board must have three or four cards (flop or
        turn); any other length raises, replacing the source's silent empty
        list.

        >>> Outs.from_hand('Ac', '')
        Traceback (most recent call last):
            ...
        ValueError: The board '' must have 3 or 4 cards for outs.
        >>> outs = Outs.from_hand('Td9d', 'Jc8s2h')
        >>> bool(outs.by_category[Label.STRAIGHT])
        True

        :param hole: Hero's hole cards.
        :param board: The flop or turn board cards.
        :param hand_type: The hand type to evaluate with, defaults to
                          :class:`pokerkit.hands.StandardHighHand`.
        :param dead: The optional dead cards to remove from the live deck.
        :return: Hero's outs grouped by made category.
        :raises ValueError: If the board is not a flop or turn.
        """
        board_cards = Card.clean(board)

        if not cls.MIN_BOARD_SIZE <= len(board_cards) <= cls.MAX_BOARD_SIZE:
            raise ValueError(
                f'The board {repr(board)} must have 3 or 4 cards for'
                ' outs.',
            )

        return cls(
            _outs_core(_used(hole), _used(board), hand_type, _used(dead)),
        )

    @property
    def count(self) -> int:
        """Return the number of distinct improving live cards.

        Each out belongs to exactly one resulting category (the label of
        the best hand it makes), so summing the per-category buckets counts
        every out once.

        >>> Outs.from_hand('AhKh', '2h7h9s').count
        23
        >>> Outs.from_hand('Kc9s4d', 'Ah7h2c').count > 0
        True

        :return: The total number of distinct outs.
        """
        return sum(len(cards) for cards in self.by_category.values())