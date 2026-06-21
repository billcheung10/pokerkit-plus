""":mod:`pokerkit_plus._semantic` implements private foundations shared
by the semantic layer.

Nothing here is part of the public surface; these helpers centralize live
card enumeration, royal-flush refinement, and the single memoized nut
enumeration that :mod:`pokerkit_plus.combos` (and later blocker/range
modules) build on. Everything is expressed in terms of :mod:`pokerkit`
primitives so that strength and category come from PokerKit's lookup-table
total order rather than any hand-rolled scoring.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from typing import TYPE_CHECKING

from pokerkit.hands import Hand
from pokerkit.lookups import Label
from pokerkit.utilities import Card, CardsLike, Deck, Rank, RankOrder

if TYPE_CHECKING:
    from collections.abc import Mapping

__BROADWAY: frozenset[Rank] = frozenset(RankOrder.STANDARD[-5:])


def _used(*groups: CardsLike) -> frozenset[Card]:
    """Return the set of cards used (and hence dead) across the groups.

    Each group is normalized through :meth:`pokerkit.utilities.Card.clean`,
    so hole cards, board cards, and dead cards can be supplied in any
    cards-like form (a string, a single card, or an iterable of cards).

    >>> sorted(map(repr, _used('AsKs', 'Qd')))
    ['As', 'Ks', 'Qd']
    >>> _used() == frozenset()
    True

    :param groups: The card groups to union together.
    :return: The frozen set of all used cards.
    """
    used: set[Card] = set()

    for group in groups:
        used.update(Card.clean(group))

    return frozenset(used)


def _live_cards(
        *groups: CardsLike,
        deck: Deck = Deck.STANDARD,
) -> Iterator[Card]:
    """Yield the live cards: deck cards not used by any group.

    The deck is iterated in its native (deterministic) order, so the live
    cards are yielded deterministically. This is a generator; callers
    materialize it with ``tuple(...)`` only when they need a collection.

    >>> live = tuple(_live_cards('AsKsQs'))
    >>> len(live)
    49

    :param groups: The card groups whose cards are dead.
    :param deck: The deck of candidate cards, defaults to
                 :attr:`pokerkit.utilities.Deck.STANDARD`.
    :return: The iterator of live cards in deck order.
    """
    used = _used(*groups)

    for card in deck:
        if card not in used:
            yield card


def _is_royal(hand: Hand) -> bool:
    """Return whether the hand is a royal flush.

    PokerKit reports a royal flush as :attr:`pokerkit.lookups.Label`
    ``.STRAIGHT_FLUSH``; this refines that by checking the five card ranks
    are exactly the broadway set (ten through ace). The check is on the
    rank *set*, not on the top card by index, because the steel wheel
    (``As2s3s4s5s``) also has the ace as its highest card by
    :attr:`pokerkit.utilities.RankOrder` ``.STANDARD`` index yet is not a
    royal flush.

    >>> from pokerkit.hands import StandardHighHand
    >>> _is_royal(StandardHighHand.from_game('AsKs', 'QsJsTs'))
    True
    >>> _is_royal(StandardHighHand.from_game('As2s', '3s4s5s'))
    False
    >>> _is_royal(StandardHighHand.from_game('AcAd', 'AhAsKc'))
    False

    :param hand: The hand to test.
    :return: ``True`` if the hand is a royal flush, otherwise ``False``.
    """
    if hand.entry.label is not Label.STRAIGHT_FLUSH:
        return False

    return frozenset(card.rank for card in hand.cards) == __BROADWAY


@dataclass(frozen=True)
class HoleCombo:
    """A two-card hole combination together with its made hand.

    Instances are produced by the nut enumeration core and never
    constructed by users directly; the embedded :attr:`hand` is the
    already-evaluated best hand for these hole cards on the enumerated
    board, so consumers never re-evaluate.

    >>> from pokerkit.hands import StandardHighHand
    >>> hand = StandardHighHand.from_game('TsJs', 'AsKsQs')
    >>> combo = HoleCombo(tuple(Card.parse('TsJs')), hand)
    >>> sorted(map(repr, combo.cards))
    ['Js', 'Ts']
    >>> combo.as_frozenset == frozenset(Card.parse('TsJs'))
    True

    :param cards: The two hole cards, in deck order.
    :param hand: The evaluated best hand these cards make on the board.
    """

    cards: tuple[Card, ...]
    """The two hole cards, in deck order."""
    hand: Hand
    """The evaluated best hand these cards make on the board."""

    @property
    def as_frozenset(self) -> frozenset[Card]:
        """Return the hole cards as a frozen set.

        This is the exact shape consumed by
        :func:`pokerkit.analysis.parse_range` output and
        :func:`pokerkit.analysis.calculate_equities` input, so a combo can
        round-trip into an equity call.

        >>> from pokerkit.hands import StandardHighHand
        >>> hand = StandardHighHand.from_game('TsJs', 'AsKsQs')
        >>> combo = HoleCombo(tuple(Card.parse('TsJs')), hand)
        >>> combo.as_frozenset == frozenset(Card.parse('JsTs'))
        True

        :return: The hole cards as a frozen set.
        """
        return frozenset(self.cards)


@dataclass(frozen=True)
class _NutsCore:
    """The shared, immutable result of one nut enumeration over a board.

    This is the value cached by :func:`_nuts_core`. A single enumeration
    pass produces both the nut hand (and the combos tying it) and the
    per-category grouping of every live combo, so consumers never
    re-evaluate.

    :param hand: The strongest hand makeable on the board, or ``None`` if
                 the board is too short to enumerate.
    :param combos: Every two-card combo whose best hand ties the strongest
                   hand, each carrying its already-evaluated hand.
    :param candidate_count: The number of live two-card combos enumerated.
    :param by_category: Every live combo grouped by its made-hand label, in
                        enumeration order.
    """

    hand: Hand | None
    """The strongest hand makeable on the board, or ``None``."""
    combos: tuple[HoleCombo, ...]
    """The combos tying the strongest hand, with evaluated hands."""
    candidate_count: int
    """The number of live two-card combos enumerated."""
    by_category: Mapping[Label, tuple[HoleCombo, ...]]
    """Every live combo grouped by its made-hand label."""


@lru_cache(maxsize=None)
def _nuts_core(
        board: frozenset[Card],
        hand_type: type[Hand],
        dead: frozenset[Card],
) -> _NutsCore:
    """Enumerate a board once, memoized by board, type, and dead cards.

    This is the single source of nut enumeration shared by
    :class:`pokerkit_plus.combos.Nuts` and
    :class:`pokerkit_plus.combos.CategoryCombos`. It enumerates every live
    two-card combo ONCE, calls ``hand_type.from_game_or_none`` exactly once
    per combo, and in that same pass tracks the running maximum hand (with
    every tying combo) and groups every combo by its made-hand label. No
    combo is ever re-classified, and nothing uses ``list.index`` or rebuilds
    a set per element.

    The cache is keyed on :class:`frozenset` of
    :class:`pokerkit.utilities.Card`, which is a correct key because
    ``Card`` is a frozen, hashable dataclass: two boards with the same card
    set hash and compare equal regardless of order.
    ``functools.lru_cache`` is chosen over a hand-rolled module dict because
    all three arguments are already hashable and immutable, the function is
    pure, and ``lru_cache`` gives thread-safe memoization plus
    ``cache_info``/``cache_clear`` introspection for free.

    A board with fewer than three cards returns an honest empty core
    (``hand is None``, no combos) rather than raising or returning ``None``.
    A board that is itself the nuts (e.g. a quad board) yields *every* live
    combo as a tying combo, exposed via :attr:`_NutsCore.combos` and
    :attr:`_NutsCore.candidate_count` so blockers can detect the
    "no blocker possible" case.

    :param board: The board cards as a frozen set.
    :param hand_type: The hand type to evaluate with.
    :param dead: Additional dead (used) cards as a frozen set.
    :return: The cached enumeration result.
    """
    board_cards = tuple(board)

    if len(board_cards) < 3:
        return _NutsCore(None, (), 0, {})

    max_hand: Hand | None = None
    tying: list[HoleCombo] = []
    grouped: dict[Label, list[HoleCombo]] = {}
    candidate_count = 0

    for hole in combinations(_live_cards(board, dead), 2):
        candidate_count += 1
        hand = hand_type.from_game_or_none(hole, board_cards)

        if hand is None:
            continue

        combo = HoleCombo(hole, hand)
        grouped.setdefault(hand.entry.label, []).append(combo)

        if max_hand is None or hand > max_hand:
            max_hand = hand
            tying = [combo]
        elif hand == max_hand:
            tying.append(combo)

    by_category = {
        label: tuple(combos) for label, combos in grouped.items()
    }

    return _NutsCore(max_hand, tuple(tying), candidate_count, by_category)
