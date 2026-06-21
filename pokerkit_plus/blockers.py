""":mod:`pokerkit_plus.blockers` implements nut-blocker analysis.

A hole card *blocks* the nuts when it sits inside a combo that makes the
nuts, removing that combo from a villain's possible holdings. The reading
is count-based: :class:`BlockerReport` reports how many of the board's nut
combos the hero's cards remove (and which cards do the removing), so the
load-bearing blocker on a trips/quad board — the one card every nut combo
needs — shows up as blocking every combo, while an interchangeable kicker
blocks only its own.

This builds entirely on the memoized nut enumeration in
:mod:`pokerkit_plus.combos`; it adds no evaluation of its own. When the
board is itself the nuts (every holding plays it), no card can block the
nuts, so the report is empty by the explicit rule below.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokerkit.hands import Hand, StandardHighHand
from pokerkit.utilities import Card, CardsLike

from pokerkit_plus._semantic import _used
from pokerkit_plus.combos import Nuts


@dataclass(frozen=True)
class BlockerReport:
    """How much a hero's hole cards block the nuts on a board.

    Use :meth:`from_hand`. The nuts are enumerated over the live deck
    (board and any dead cards removed, but the hero's own cards left in the
    pool so their removal can be measured); a nut combo is *blocked* when it
    contains one of the hero's cards. :attr:`nut_combos_blocked` counts the
    blocked combos and :attr:`blocker_cards` is exactly the hero cards doing
    the blocking.

    >>> report = BlockerReport.from_hand('AsKs', '2c2d2h')
    >>> report.blocks_nuts
    True
    >>> sorted(map(repr, report.blocker_cards))
    ['As']

    The card every nut combo needs (here the case deuce) blocks them all,
    while holding two of the nut kicker cards blocks two combos.

    >>> deuce = BlockerReport.from_hand('2s3c', '2c2d2h')
    >>> deuce.nut_combos_blocked == deuce.nut_combos_total
    True
    >>> BlockerReport.from_hand('AhAd', '2c2d2h').nut_combos_blocked
    2

    When the board is itself the nuts, nothing can block it.

    >>> BlockerReport.from_hand('2c3c', 'AsKsQsJsTs').blocks_nuts
    False

    :param nut_combos_total: The number of combos that make the nuts.
    :param nut_combos_blocked: How many of those the hero's cards remove.
    :param blocker_cards: The hero cards that appear in a nut combo.
    """

    nut_combos_total: int
    """The number of combos that make the nuts."""
    nut_combos_blocked: int
    """How many nut combos the hero's cards remove."""
    blocker_cards: frozenset[Card]
    """The hero cards that appear in at least one nut combo."""

    @classmethod
    def from_hand(
            cls,
            hole: CardsLike,
            board: CardsLike,
            *,
            hand_type: type[Hand] = StandardHighHand,
            dead: CardsLike = (),
    ) -> BlockerReport:
        """Report how much the hero's cards block the board's nuts.

        The nuts come from the memoized
        :meth:`pokerkit_plus.combos.Nuts.from_board` (over the deck minus
        board and ``dead``). When the board is itself the nuts, or is too
        short to make a hand, an empty report is returned: no card blocks an
        unblockable nut.

        >>> BlockerReport.from_hand('AsKs', '7h2c9d').nut_combos_total > 0
        True

        :param hole: The hero's hole cards.
        :param board: The board cards.
        :param hand_type: The hand type to evaluate with, defaults to
                          :class:`pokerkit.hands.StandardHighHand`.
        :param dead: The optional dead cards to remove from the live deck.
        :return: The blocker report.
        """
        hole_cards = _used(hole)
        nuts = Nuts.from_board(board, hand_type=hand_type, dead=dead)

        if nuts.hand is None or nuts.board_is_nuts:
            return cls(len(nuts.combos), 0, frozenset())

        blocked = 0
        blocker_cards: set[Card] = set()

        for combo in nuts.combos:
            overlap = frozenset(combo.cards) & hole_cards

            if overlap:
                blocked += 1
                blocker_cards |= overlap

        return cls(len(nuts.combos), blocked, frozenset(blocker_cards))

    @property
    def blocks_nuts(self) -> bool:
        """Return whether the hero blocks at least one nut combo.

        >>> BlockerReport.from_hand('AsKs', '2c2d2h').blocks_nuts
        True
        >>> BlockerReport.from_hand('7h8h', '2c2d2h').blocks_nuts
        False

        :return: ``True`` if at least one nut combo is blocked.
        """
        return self.nut_combos_blocked > 0

    @property
    def block_fraction(self) -> float:
        """Return the fraction of nut combos the hero blocks.

        This is ``0.0`` when there are no nut combos (a board too short to
        make a hand, or an unblockable board-is-nuts board).

        >>> BlockerReport.from_hand('2s3c', '2c2d2h').block_fraction
        1.0
        >>> BlockerReport.from_hand('7h8h', '2c2d2h').block_fraction
        0.0

        :return: The blocked fraction in ``[0.0, 1.0]``.
        """
        if not self.nut_combos_total:
            return 0.0

        return self.nut_combos_blocked / self.nut_combos_total
