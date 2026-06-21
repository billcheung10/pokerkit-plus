""":mod:`pokerkit_plus.draws` implements hero draw detection by
evaluation.

A draw is read off PokerKit's evaluator, never off hand-rolled suit/rank
bookkeeping: for every live one-card runout the hero's best five is
re-evaluated with ``hand_type.from_game``, and the runouts that turn a
non-flush/non-straight into a flush or straight are grouped to derive the
:class:`pokerkit_plus.texture.FlushDraw` / :class:`StraightDraw` level. The
nut-ness of the strongest immediate draw is ranked against the same-draw
completions a villain could hold, on the single
:class:`pokerkit.utilities.RankOrder` scale (wheel and broadway handled by
that scale and by PokerKit's lookup total order, never by ace-as-1/14
magic).

This module also defines the shared :class:`NutRank`, imported by
:mod:`pokerkit_plus.tags` and :mod:`pokerkit_plus.facade`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum, unique
from functools import lru_cache
from itertools import combinations

from pokerkit.hands import Hand, StandardHighHand
from pokerkit.lookups import Label
from pokerkit.utilities import Card, CardsLike, Rank, RankOrder

from pokerkit_plus._semantic import _live_cards, _used
from pokerkit_plus.texture import FlushDraw, StraightDraw, _rank_positions

__STRAIGHT_LABELS: frozenset[Label] = frozenset(
    {Label.STRAIGHT, Label.STRAIGHT_FLUSH},
)
__FLUSH_LABELS: frozenset[Label] = frozenset(
    {Label.FLUSH, Label.STRAIGHT_FLUSH},
)


@unique
class NutRank(StrEnum):
    """The enum class for how close to the nuts a made hand or draw is.

    This is the one nut-ness vocabulary shared across the semantic layer:
    :mod:`pokerkit_plus.draws` ranks a completed draw with it, and
    :mod:`pokerkit_plus.tags` reuses it (imported via
    ``from pokerkit_plus.draws import NutRank``) for the nut-ness of a made
    flush or straight. It is a relative position, not an absolute strength,
    so it is always read against the same-draw completions a villain could
    hold rather than against a fixed table.

    Compare with ``is`` against a member, never by truth value (a
    :class:`enum.StrEnum` member is never falsy).

    >>> NutRank.NUT
    <NutRank.NUT: 'Nut'>
    >>> NutRank.NON_NUT
    <NutRank.NON_NUT: 'Non-nut'>
    """

    NUT = 'Nut'
    """The rank of a hand or draw that no completion can beat."""
    SECOND_NUT = 'Second nut'
    """The rank beaten only by the single best completion."""
    THIRD_NUT = 'Third nut'
    """The rank beaten only by the two best completions."""
    NON_NUT = 'Non-nut'
    """The rank beaten by three or more completions."""


NUT_RANK_ORDER: tuple[NutRank, ...] = (
    NutRank.NON_NUT,
    NutRank.THIRD_NUT,
    NutRank.SECOND_NUT,
    NutRank.NUT,
)
"""The nut ranks, ordered from furthest to closest to the nuts."""

__NUT_RANK_BY_BEATEN: tuple[NutRank, ...] = (
    NutRank.NUT,
    NutRank.SECOND_NUT,
    NutRank.THIRD_NUT,
)


def _nut_rank_from_beaten(beaten: int) -> NutRank:
    """Map a count of strictly better completions to a :class:`NutRank`.

    Zero better completions is the nuts, one is second nut, two is third
    nut, and three or more is non-nut. The ladder is shared by the flush
    and straight nut-rank reads so they never drift.

    >>> _nut_rank_from_beaten(0)
    <NutRank.NUT: 'Nut'>
    >>> _nut_rank_from_beaten(2)
    <NutRank.THIRD_NUT: 'Third nut'>
    >>> _nut_rank_from_beaten(5)
    <NutRank.NON_NUT: 'Non-nut'>

    :param beaten: The number of strictly better same-draw completions.
    :return: The nut rank for that many better completions.
    """
    if beaten < len(__NUT_RANK_BY_BEATEN):
        return __NUT_RANK_BY_BEATEN[beaten]

    return NutRank.NON_NUT


def _completing(
        hole: tuple[Card, ...],
        board: tuple[Card, ...],
        labels: frozenset[Label],
        *,
        hand_type: type[Hand],
) -> tuple[tuple[Card, Hand], ...]:
    """Return the live runouts that complete a draw into ``labels``.

    A runout completes the draw when adding it makes the hero's best five
    land in ``labels`` while the current best five does not yet: this is
    read straight off ``hand_type.from_game`` for every live card, never
    inferred from suits or gaps. Each completing card is paired with the
    hand it makes so callers never re-evaluate.

    >>> hole = Card.clean('AsKs')
    >>> board = Card.clean('Qs7s2c')
    >>> [str(card) for card, _ in _completing(
    ...     hole, board, frozenset({Label.FLUSH, Label.STRAIGHT_FLUSH}),
    ...     hand_type=StandardHighHand,
    ... )][:1]
    ['DEUCE OF SPADES (2s)']

    :param hole: The cleaned hole cards.
    :param board: The cleaned board cards.
    :param labels: The made-hand labels that count as completing the draw.
    :param hand_type: The hand type to evaluate with.
    :return: The completing ``(card, hand)`` pairs, in deck order.
    """
    base = hand_type.from_game_or_none(hole, board)

    if base is not None and base.entry.label in labels:
        return ()

    completing: list[tuple[Card, Hand]] = []

    for card in _live_cards(hole, board):
        hand = hand_type.from_game_or_none(hole, (*board, card))

        if hand is not None and hand.entry.label in labels:
            completing.append((card, hand))

    return tuple(completing)


def _made_flush(
        hole: tuple[Card, ...],
        board: tuple[Card, ...],
        *,
        hand_type: type[Hand],
) -> bool:
    """Return whether the hero has already completed a flush.

    A made flush (or straight flush) is not a flush draw, so this guards
    the flush-draw read. The label is taken straight off the evaluator.

    >>> _made_flush(
    ...     Card.clean('AsKs'), Card.clean('QsJs2s'),
    ...     hand_type=StandardHighHand,
    ... )
    True
    >>> _made_flush(
    ...     Card.clean('AsKs'), Card.clean('Qs7s2c'),
    ...     hand_type=StandardHighHand,
    ... )
    False

    :param hole: The cleaned hole cards.
    :param board: The cleaned board cards.
    :param hand_type: The hand type to evaluate with.
    :return: ``True`` if the hero already holds a flush.
    """
    made = hand_type.from_game_or_none(hole, board)

    return made is not None and made.entry.label in __FLUSH_LABELS


def _straight_completing(
        hole: tuple[Card, ...],
        board: tuple[Card, ...],
        *,
        hand_type: type[Hand],
) -> tuple[tuple[Card, Hand], ...]:
    """Return the runouts completing the hero's hand into a straight.

    A thin module-level wrapper over :func:`_completing` that bakes in the
    straight labels, so the class body never references the name-mangled
    label constant.

    >>> bool(_straight_completing(
    ...     Card.clean('JhTd'), Card.clean('9c8s2h'),
    ...     hand_type=StandardHighHand,
    ... ))
    True

    :param hole: The cleaned hole cards.
    :param board: The cleaned board cards.
    :param hand_type: The hand type to evaluate with.
    :return: The straight completing ``(card, hand)`` pairs.
    """
    return _completing(hole, board, __STRAIGHT_LABELS, hand_type=hand_type)


def _straight_nut_rank(
        hole: tuple[Card, ...],
        board: tuple[Card, ...],
        completing: tuple[tuple[Card, Hand], ...],
        *,
        hand_type: type[Hand],
) -> NutRank:
    """Rank a straight draw against the villain straights that beat it.

    The nut rank is taken over the *worst* completing runout: for each card
    that completes the draw, the runout board is fixed and the distinct
    strictly-stronger villain straight strengths are counted, and the most
    dominated runout wins. Anchoring on the worst case is what keeps a draw
    that a higher straight can dominate (e.g. a low or wheel run that a
    broadway run beats) honestly non-nut, with no broadway-as-wheel
    asymmetry: the wheel completion never grants a free nut pass. Straights
    carry no kicker, so distinct strengths map one-to-one onto nut tiers.

    >>> hole = Card.clean('JhTd')
    >>> board = Card.clean('9c8s2h')
    >>> _straight_nut_rank(
    ...     hole, board,
    ...     _completing(hole, board,
    ...                 frozenset({Label.STRAIGHT, Label.STRAIGHT_FLUSH}),
    ...                 hand_type=StandardHighHand),
    ...     hand_type=StandardHighHand,
    ... )
    <NutRank.NUT: 'Nut'>

    A low run that a higher straight can dominate ranks below the nuts.

    >>> hole = Card.clean('2h3d')
    >>> board = Card.clean('4c5s9h')
    >>> _straight_nut_rank(
    ...     hole, board,
    ...     _completing(hole, board,
    ...                 frozenset({Label.STRAIGHT, Label.STRAIGHT_FLUSH}),
    ...                 hand_type=StandardHighHand),
    ...     hand_type=StandardHighHand,
    ... )
    <NutRank.THIRD_NUT: 'Third nut'>

    :param hole: The cleaned hole cards.
    :param board: The cleaned board cards.
    :param completing: The completing ``(card, hand)`` pairs.
    :param hand_type: The hand type to evaluate with.
    :return: The nut rank of the straight draw.
    """
    by_rank: dict[Rank, tuple[Card, Hand]] = {}

    for runout, hero in completing:
        by_rank.setdefault(runout.rank, (runout, hero))

    return _nut_rank_from_beaten(
        max(
            _straight_beaten(
                hole, (*board, runout), hero, hand_type=hand_type,
            )
            for runout, hero in by_rank.values()
        ),
    )


def _straight_beaten(
        hole: tuple[Card, ...],
        full_board: tuple[Card, ...],
        hero: Hand,
        *,
        hand_type: type[Hand],
) -> int:
    """Count distinct villain hands beating the hero on one runout.

    Every live villain two-card combo is evaluated once on the completed
    board, and the distinct strengths of those that strictly beat the hero
    are counted. Comparison is pokerkit's :class:`pokerkit.hands.Hand` total
    order, so a stronger completion of ANY category counts — in particular a
    villain straight flush on a straight-completing runout, which a
    label-only filter would silently miss and over-rank the draw. This is
    the per-runout component of :func:`_straight_nut_rank`.

    >>> hole = Card.clean('JhTd')
    >>> board = Card.clean('9c8s2h7c')
    >>> hero = StandardHighHand.from_game(hole, board)
    >>> _straight_beaten(hole, board, hero, hand_type=StandardHighHand)
    0

    :param hole: The cleaned hole cards.
    :param full_board: The board including the completing runout.
    :param hero: The hero's hand on that runout.
    :param hand_type: The hand type to evaluate with.
    :return: The number of distinct stronger villain hand strengths.
    """
    strengths: set[int] = set()

    for villain in combinations(_live_cards(hole, full_board), 2):
        hand = hand_type.from_game_or_none(villain, full_board)

        if hand is not None and hand > hero:
            strengths.add(hand.entry.index)

    return len(strengths)


def _flush_nut_rank(
        hole: tuple[Card, ...],
        board: tuple[Card, ...],
) -> NutRank | None:
    """Rank a flush draw by the higher live cards of its suit.

    The draw suit is the one with exactly four cards across hero and board
    (one more completes a flush). A villain holding any higher card of that
    suit that is neither on the board nor in the hero's hand beats the hero
    on a shared runout, so the count of those higher live suited ranks is
    the nut tier. This is evaluation-consistent yet free of the kicker
    inflation that distinct-strength counting would suffer for flushes, and
    it ranks a hero who holds only a middle suited card (the nut card being
    an undealt out) as non-nut rather than letting the hero grab the nut
    runout for themselves.

    >>> _flush_nut_rank(Card.clean('AsKs'), Card.clean('Qs7s2c'))
    <NutRank.NUT: 'Nut'>
    >>> _flush_nut_rank(Card.clean('KsQs'), Card.clean('9s7s2c'))
    <NutRank.SECOND_NUT: 'Second nut'>

    :param hole: The cleaned hole cards.
    :param board: The cleaned board cards.
    :return: The nut rank of the flush draw, or ``None`` if the hero holds
             no card of the draw suit (so the flush is not the hero's).
    """
    cards = (*hole, *board)
    counts = Counter(card.suit for card in cards)
    suit = next((s for s, count in counts.items() if count == 4), None)

    if suit is None:
        return None

    hero_ranks = {card.rank for card in hole if card.suit is suit}

    if not hero_ranks:
        return None

    seen = {card.rank for card in cards if card.suit is suit}
    hero_high = max(RankOrder.STANDARD.index(rank) for rank in hero_ranks)
    beaten = sum(
        1
        for rank in RankOrder.STANDARD
        if RankOrder.STANDARD.index(rank) > hero_high and rank not in seen
    )

    return _nut_rank_from_beaten(beaten)


def _flush_level(
        hole: tuple[Card, ...],
        board: tuple[Card, ...],
) -> FlushDraw | None:
    """Return the hero's flush draw level, or ``None``.

    The level is read off the suit counts across hero and board, requiring
    the hero to actually contribute a card of the suit (a flush on the
    board alone is not the hero's draw): four of a suit needs one more card
    (live), three of a suit needs two more (backdoor). With no qualifying
    suit the result is ``None``.

    >>> _flush_level(Card.clean('AsKs'), Card.clean('Qs7s2c'))
    <FlushDraw.LIVE: 'Live'>
    >>> _flush_level(Card.clean('AsKh'), Card.clean('Qs7s2c'))
    <FlushDraw.BACKDOOR: 'Backdoor'>
    >>> _flush_level(Card.clean('AhKh'), Card.clean('Qs7s2c')) is None
    True

    :param hole: The cleaned hole cards.
    :param board: The cleaned board cards.
    :return: The flush draw level, or ``None``.
    """
    counts = Counter(card.suit for card in (*hole, *board))
    hero_suits = {card.suit for card in hole}
    levels = {
        counts[suit]
        for suit in hero_suits
        if counts[suit] in (4, 3)
    }

    if 4 in levels:
        return FlushDraw.LIVE

    if 3 in levels:
        return FlushDraw.BACKDOOR

    return None


def _has_run_of_four(cards: tuple[Card, ...]) -> bool:
    """Return whether four cards form four consecutive ranks.

    The check is over the distinct rank positions of the cards (with the
    ace-low wheel variant) reusing
    :func:`pokerkit_plus.texture._rank_positions`, so the wheel wraps off
    the single :class:`pokerkit.utilities.RankOrder` scale. Four
    consecutive ranks (a span of three over four positions) are what makes
    a two-card straight draw open-ended rather than a double gutshot.

    >>> _has_run_of_four(Card.clean('JhTd9c8s'))
    True
    >>> _has_run_of_four(Card.clean('9c3d6c5d7c'))
    False

    :param cards: The cards to test.
    :return: ``True`` if any four cards are consecutive in rank.
    """
    for positions in _rank_positions(cards):
        for index in range(len(positions) - 3):
            if positions[index + 3] - positions[index] == 3:
                return True

    return False


def _straight_level(
        completing_ranks: int,
        cards: tuple[Card, ...],
) -> StraightDraw:
    """Return the straight draw level from its completions and shape.

    A single distinct one-card completing rank is a gutshot. With two or
    more completing ranks the draw is open-ended when the hero plus board
    cards contain four consecutive ranks (completable at one or both ends),
    and a double gutshot otherwise (two separate inside completions with no
    four-in-a-row). The shape check is the wheel-aware
    :func:`_has_run_of_four`, never an adjacency heuristic on the
    completing ranks themselves (the two ends of an open-ended draw are not
    adjacent).

    >>> _straight_level(1, Card.clean('QhTd' 'Kc9s2h'))
    <StraightDraw.GUTSHOT: 'Gutshot'>
    >>> _straight_level(2, Card.clean('JhTd' '9c8s2h'))
    <StraightDraw.OPEN_ENDED: 'Open-ended'>
    >>> _straight_level(2, Card.clean('9c3d' '6c5d7c'))
    <StraightDraw.DOUBLE_GUTSHOT: 'Double gutshot'>

    :param completing_ranks: The number of distinct completing ranks.
    :param cards: The hero plus board cards.
    :return: The straight draw level.
    """
    if completing_ranks <= 1:
        return StraightDraw.GUTSHOT

    if _has_run_of_four(cards):
        return StraightDraw.OPEN_ENDED

    return StraightDraw.DOUBLE_GUTSHOT


@dataclass(frozen=True)
class Draws:
    """The hero's immediate draws on a flop or turn, read by evaluation.

    Use :meth:`from_hand`. Each draw level comes from grouping the live
    one-card runouts that complete the hero's hand into a flush or straight
    (every runout evaluated once via ``hand_type.from_game``), and
    :attr:`nut_rank` is the nut-ness of the strongest immediate draw (the
    straight draw is ranked when present, otherwise the flush draw; both
    levels are always exposed). A backdoor straight needing two more cards
    is not an immediate draw and so is not reported here.

    >>> draws = Draws.from_hand('AsKs', 'Qs7s2c')
    >>> draws.flush_draw
    <FlushDraw.LIVE: 'Live'>
    >>> draws.straight_draw is None
    True
    >>> draws.nut_rank
    <NutRank.NUT: 'Nut'>

    An open-ended straight draw held by the nut end ranks as the nuts.

    >>> draws = Draws.from_hand('JhTd', '9c8s2h')
    >>> draws.straight_draw
    <StraightDraw.OPEN_ENDED: 'Open-ended'>
    >>> draws.nut_rank
    <NutRank.NUT: 'Nut'>

    A king-high flush draw with the ace still live is the second nut draw.

    >>> Draws.from_hand('KsQs', '9s7s2c').nut_rank
    <NutRank.SECOND_NUT: 'Second nut'>

    No draw reads as all ``None``.

    >>> empty = Draws.from_hand('Ah7c', 'Kd9s2h')
    >>> empty.flush_draw is None
    True
    >>> empty.straight_draw is None
    True
    >>> empty.nut_rank is None
    True

    :param straight_draw: The immediate straight draw, or ``None``.
    :param flush_draw: The immediate flush draw, or ``None``.
    :param nut_rank: The nut rank of the strongest immediate draw, or
                     ``None`` when there is no draw.
    """

    straight_draw: StraightDraw | None
    """The immediate straight draw the hero holds, or ``None``."""
    flush_draw: FlushDraw | None
    """The immediate flush draw the hero holds, or ``None``."""
    nut_rank: NutRank | None
    """The nut rank of the strongest immediate draw, or ``None``."""

    @classmethod
    def from_hand(
            cls,
            hole: CardsLike,
            board: CardsLike,
            *,
            hand_type: type[Hand] = StandardHighHand,
    ) -> Draws:
        """Read the hero's immediate draws on a flop or turn.

        Both hole and board are cleaned via
        :meth:`pokerkit.utilities.Card.clean`; the board must be a flop or
        turn (three or four cards), since a draw is an immediate one-card
        completion. The flush and straight completing runouts are each
        evaluated once, and :attr:`Draws.nut_rank` ranks the stronger of the
        two draws against the same-draw completions a villain could hold.

        >>> Draws.from_hand('Th9h', 'Jh8c2s').straight_draw
        <StraightDraw.OPEN_ENDED: 'Open-ended'>
        >>> Draws.from_hand('Ah2h', 'Kh7h3c').flush_draw
        <FlushDraw.LIVE: 'Live'>

        :param hole: The hero's hole cards.
        :param board: The flop or turn board (three or four cards).
        :param hand_type: The hand type to evaluate with, defaults to
                          :class:`pokerkit.hands.StandardHighHand`.
        :return: The hero's immediate draws.
        :raises ValueError: If the board is not a flop or turn.
        """
        board_cards = Card.clean(board)

        if len(board_cards) not in (3, 4):
            raise ValueError(
                f'The board {repr(board)} must be a flop or turn for'
                ' draws.',
            )

        return _draws_core(_used(hole), _used(board_cards), hand_type)

    @staticmethod
    def _nut_rank(
            hole: tuple[Card, ...],
            board: tuple[Card, ...],
            straight_completing: tuple[tuple[Card, Hand], ...],
            flush_draw: FlushDraw | None,
            *,
            hand_type: type[Hand],
    ) -> NutRank | None:
        """Rank the strongest immediate draw, preferring the flush.

        When the hero holds both draws the flush is the stronger one (a
        completed flush outranks a completed straight on PokerKit's total
        order), so the flush draw is ranked by the higher live cards of its
        suit; otherwise the straight draw is ranked against villain
        straights. With neither draw the result is ``None``. A backdoor
        flush is not an immediate draw and never sets the rank on its own.

        :param hole: The cleaned hole cards.
        :param board: The cleaned board cards.
        :param straight_completing: The straight completing pairs.
        :param flush_draw: The flush draw level, or ``None``.
        :param hand_type: The hand type to evaluate with.
        :return: The nut rank of the strongest draw, or ``None``.
        """
        if flush_draw is FlushDraw.LIVE:
            flush_rank = _flush_nut_rank(hole, board)

            if flush_rank is not None:
                return flush_rank

        if straight_completing:
            return _straight_nut_rank(
                hole, board, straight_completing, hand_type=hand_type,
            )

        if flush_draw is not None:
            return _flush_nut_rank(hole, board)

        return None


@lru_cache(maxsize=None)
def _draws_core(
        hole: frozenset[Card],
        board: frozenset[Card],
        hand_type: type[Hand],
) -> Draws:
    """Compute a board's draws once, memoized by hand, board, and type.

    This holds the per-call enumeration (the flush/straight completing
    runouts and the villain-completion nut-rank passes) behind a cache
    keyed on :class:`frozenset` of :class:`pokerkit.utilities.Card`, so a
    repeated query — and the facade composing draws alongside texture, tier,
    and outs — never re-enumerates. The keys are hashable and immutable, the
    function is pure, and the cached :class:`Draws` is frozen, so sharing it
    is safe.

    :param hole: The hero's hole cards as a frozen set.
    :param board: The flop or turn board as a frozen set.
    :param hand_type: The hand type to evaluate with.
    :return: The hero's immediate draws.
    """
    hole_cards = tuple(hole)
    board_cards = tuple(board)
    straight_completing = _straight_completing(
        hole_cards, board_cards, hand_type=hand_type,
    )
    flush_draw = (
        None
        if _made_flush(hole_cards, board_cards, hand_type=hand_type)
        else _flush_level(hole_cards, board_cards)
    )
    straight_draw = (
        _straight_level(
            len({card.rank for card, _ in straight_completing}),
            (*hole_cards, *board_cards),
        )
        if straight_completing
        else None
    )
    nut_rank = Draws._nut_rank(
        hole_cards,
        board_cards,
        straight_completing,
        flush_draw,
        hand_type=hand_type,
    )

    return Draws(straight_draw, flush_draw, nut_rank)