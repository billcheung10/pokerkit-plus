""":mod:`pokerkit_plus.tags` implements hero-relative made-hand tiers.

Where :mod:`pokerkit_plus.combos` answers *what category* a hand makes
(reusing PokerKit's :class:`pokerkit.lookups.Label`), this module answers
*how good that category is here*: a one-pair hand becomes a top / second /
under pair with a top / good / weak kicker, a two-pair hand becomes top
two or bottom two, and a three-of-a-kind hand splits into a concealed set
(top / middle / bottom) versus a board-paired trips with a kicker. Every
tier is read on the single :class:`pokerkit.utilities.RankOrder` scale
(the wheel handled by that scale, never ace-as-1/14), category and
strength come straight off PokerKit's evaluator, and nut-ness reuses one
memoized :func:`pokerkit_plus._semantic._nuts_core` pass that excludes the
hero's own cards, so it is blocker-aware (holding the nut card counts).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique

from pokerkit.hands import Hand, StandardHighHand
from pokerkit.lookups import Label
from pokerkit.utilities import Card, CardsLike, Rank, RankOrder

from pokerkit_plus._semantic import _NutsCore, _nuts_core, _used
from pokerkit_plus.draws import NutRank


@unique
class PairTier(StrEnum):
    """The enum class for the tier of a one-pair hand.

    A single-card pair (one hole card matching the board) is tiered by the
    matched rank's position among the board's *distinct* ranks: first
    (:attr:`TOP_PAIR`), second (:attr:`SECOND_PAIR`), third
    (:attr:`THIRD_PAIR`), or fourth-or-lower (:attr:`LOW_PAIR`). A pocket
    pair instead reads as :attr:`OVERPAIR` when it outranks every board
    card and :attr:`UNDER_PAIR` otherwise.

    >>> PairTier.OVERPAIR
    <PairTier.OVERPAIR: 'Overpair'>
    >>> PairTier.TOP_PAIR
    <PairTier.TOP_PAIR: 'Top pair'>
    """

    UNDER_PAIR = 'Under pair'
    """The tier of a pocket pair below the highest board card."""
    LOW_PAIR = 'Low pair'
    """The tier of a pair on the fourth-or-lower board rank."""
    THIRD_PAIR = 'Third pair'
    """The tier of a pair on the third board rank."""
    SECOND_PAIR = 'Second pair'
    """The tier of a pair on the second board rank."""
    TOP_PAIR = 'Top pair'
    """The tier of a pair on the highest board rank."""
    OVERPAIR = 'Overpair'
    """The tier of a pocket pair above every board card."""


PAIR_TIER_ORDER: tuple[PairTier, ...] = (
    PairTier.UNDER_PAIR,
    PairTier.LOW_PAIR,
    PairTier.THIRD_PAIR,
    PairTier.SECOND_PAIR,
    PairTier.TOP_PAIR,
    PairTier.OVERPAIR,
)
"""The pair tiers, ordered from weakest to strongest."""


@unique
class KickerTier(StrEnum):
    """The enum class for the tier of a pair's side card.

    The kicker is graded by the position of the *highest* hole card that
    is not part of the pair, ranked among the ranks still available (those
    neither on the board nor equal to the pair rank): first is
    :attr:`TOP`, second-or-third :attr:`GOOD`, fourth-or-fifth
    :attr:`MEDIUM`, and sixth-or-lower :attr:`WEAK`. It is exposed as an
    optional field with no ``NONE`` member: a hand with no distinct kicker
    (a pocket pair, or two paired hole cards) reads as ``None``.

    >>> KickerTier.TOP
    <KickerTier.TOP: 'Top kicker'>
    >>> KickerTier.WEAK
    <KickerTier.WEAK: 'Weak kicker'>
    """

    WEAK = 'Weak kicker'
    """The tier of a kicker on the sixth-or-lower available rank."""
    MEDIUM = 'Medium kicker'
    """The tier of a kicker on the fourth-or-fifth available rank."""
    GOOD = 'Good kicker'
    """The tier of a kicker on the second-or-third available rank."""
    TOP = 'Top kicker'
    """The tier of a kicker on the highest available rank."""


KICKER_TIER_ORDER: tuple[KickerTier, ...] = (
    KickerTier.WEAK,
    KickerTier.MEDIUM,
    KickerTier.GOOD,
    KickerTier.TOP,
)
"""The kicker tiers, ordered from weakest to strongest."""


@unique
class TwoPairTier(StrEnum):
    """The enum class for the tier of a two-pair hand.

    Pairing the board's top two distinct ranks is :attr:`TOP_TWO`;
    pairing the highest plus a lower rank is :attr:`TOP_AND_BOTTOM`;
    pairing neither top rank is :attr:`BOTTOM_TWO`. A pocket pair above
    the whole board that combines with a board pair also reads as
    :attr:`TOP_TWO`.

    >>> TwoPairTier.TOP_TWO
    <TwoPairTier.TOP_TWO: 'Top two pair'>
    >>> TwoPairTier.BOTTOM_TWO
    <TwoPairTier.BOTTOM_TWO: 'Bottom two pair'>
    """

    BOTTOM_TWO = 'Bottom two pair'
    """The tier of a two-pair using neither highest board rank."""
    TOP_AND_BOTTOM = 'Top and bottom two pair'
    """The tier of a two-pair using the highest and a lower rank."""
    TOP_TWO = 'Top two pair'
    """The tier of a two-pair using the top two board ranks."""


TWO_PAIR_TIER_ORDER: tuple[TwoPairTier, ...] = (
    TwoPairTier.BOTTOM_TWO,
    TwoPairTier.TOP_AND_BOTTOM,
    TwoPairTier.TOP_TWO,
)
"""The two-pair tiers, ordered from weakest to strongest."""


@unique
class ThreeOfAKindTier(StrEnum):
    """The enum class for the tier of a three-of-a-kind hand.

    A concealed set (a pocket pair filled by one board card) is tiered by
    the set rank's position among the board's distinct ranks:
    :attr:`TOP_SET`, :attr:`MIDDLE_SET`, or :attr:`BOTTOM_SET`. Trips made
    by pairing a board pair with one hole card is :attr:`TRIPS`, which
    carries a :class:`KickerTier` on the :class:`HandTier`. Defining a
    tier for every three-of-a-kind (paired boards included) avoids the
    source bug of returning nothing for board-paired trips.

    >>> ThreeOfAKindTier.TOP_SET
    <ThreeOfAKindTier.TOP_SET: 'Top set'>
    >>> ThreeOfAKindTier.TRIPS
    <ThreeOfAKindTier.TRIPS: 'Trips'>
    """

    TRIPS = 'Trips'
    """The tier of trips made by pairing a board pair with a hole card."""
    BOTTOM_SET = 'Bottom set'
    """The tier of a concealed set on the lowest board rank."""
    MIDDLE_SET = 'Middle set'
    """The tier of a concealed set on a middle board rank."""
    TOP_SET = 'Top set'
    """The tier of a concealed set on the highest board rank."""


THREE_OF_A_KIND_TIER_ORDER: tuple[ThreeOfAKindTier, ...] = (
    ThreeOfAKindTier.TRIPS,
    ThreeOfAKindTier.BOTTOM_SET,
    ThreeOfAKindTier.MIDDLE_SET,
    ThreeOfAKindTier.TOP_SET,
)
"""The three-of-a-kind tiers, ordered from weakest to strongest."""

_RUN_AND_FLUSH: frozenset[Label] = frozenset(
    (Label.STRAIGHT, Label.FLUSH, Label.STRAIGHT_FLUSH),
)
__NUT_RANK_BY_INDEX: tuple[NutRank, ...] = (
    NutRank.NUT,
    NutRank.SECOND_NUT,
    NutRank.THIRD_NUT,
)


def _ranked(ranks: frozenset[Rank]) -> tuple[Rank, ...]:
    """Return the ranks in descending strength on the standard scale.

    >>> [r.value for r in _ranked(frozenset(c.rank
    ...     for c in Card.clean('Ah7c2d')))]
    ['A', '7', '2']

    :param ranks: The distinct ranks to order.
    :return: The ranks from strongest to weakest.
    """
    return tuple(
        sorted(ranks, key=RankOrder.STANDARD.index, reverse=True),
    )


def _board_ranks(board: tuple[Card, ...]) -> tuple[Rank, ...]:
    """Return the board's distinct ranks, strongest first.

    >>> [r.value for r in _board_ranks(Card.clean('Ah7c2d'))]
    ['A', '7', '2']
    >>> [r.value for r in _board_ranks(Card.clean('AhAs7c'))]
    ['A', '7']

    :param board: The cleaned board cards.
    :return: The distinct board ranks, strongest first.
    """
    return _ranked(frozenset(card.rank for card in board))


def _pair_tier(
        hole: tuple[Card, ...],
        board: tuple[Card, ...],
) -> PairTier | None:
    """Return the tier of a one-pair hand, board-relative, or ``None``.

    A pocket pair is :attr:`PairTier.OVERPAIR` when it outranks every
    board card and :attr:`PairTier.UNDER_PAIR` otherwise. A single-card
    pair is tiered by the matched rank's position among the board's
    distinct ranks (first / second / third / fourth-or-lower). When the
    one pair is entirely on the board (a paired board the hero merely
    plays, holding no matching card) there is no hero pair to tier, so
    ``None`` is returned. Every comparison uses the single
    :class:`pokerkit.utilities.RankOrder` scale.

    >>> _pair_tier(Card.clean('AsKd'), Card.clean('Ah7c2d'))
    <PairTier.TOP_PAIR: 'Top pair'>
    >>> _pair_tier(Card.clean('Ks7d'), Card.clean('Ah7c2d'))
    <PairTier.SECOND_PAIR: 'Second pair'>
    >>> _pair_tier(Card.clean('QcQd'), Card.clean('Jh7c2d'))
    <PairTier.OVERPAIR: 'Overpair'>
    >>> _pair_tier(Card.clean('5c5d'), Card.clean('Jh7c2d'))
    <PairTier.UNDER_PAIR: 'Under pair'>
    >>> _pair_tier(Card.clean('AcQd'), Card.clean('Kh Ks 2d')) is None
    True

    :param hole: The cleaned hole cards.
    :param board: The cleaned board cards.
    :return: The pair tier of the hand, or ``None`` for a board pair.
    """
    board_ranks = _board_ranks(board)
    hole_ranks = frozenset(card.rank for card in hole)

    if len(hole_ranks) == 1:
        pocket = next(iter(hole_ranks))
        top = RankOrder.STANDARD.index(board_ranks[0])

        if RankOrder.STANDARD.index(pocket) > top:
            return PairTier.OVERPAIR

        return PairTier.UNDER_PAIR

    paired = hole_ranks & frozenset(board_ranks)

    if not paired:
        return None

    position = min(board_ranks.index(rank) for rank in paired)

    if position == 0:
        return PairTier.TOP_PAIR
    elif position == 1:
        return PairTier.SECOND_PAIR
    elif position == 2:
        return PairTier.THIRD_PAIR

    return PairTier.LOW_PAIR


def _kicker_tier(
        hole: tuple[Card, ...],
        board: tuple[Card, ...],
) -> KickerTier | None:
    """Return the tier of a pair's kicker, or ``None``.

    The kicker is the *highest* hole card not part of the pair (taking the
    maximum, never the first card, so it is order-independent), ranked
    among the ranks still available: those neither on the board nor equal
    to the pair rank. Position one is :attr:`KickerTier.TOP`, two or three
    :attr:`KickerTier.GOOD`, four or five :attr:`KickerTier.MEDIUM`, and
    six or lower :attr:`KickerTier.WEAK`. A pocket pair (no distinct
    kicker) returns ``None``.

    >>> _kicker_tier(Card.clean('AsKd'), Card.clean('Ah7c2d'))
    <KickerTier.TOP: 'Top kicker'>
    >>> _kicker_tier(Card.clean('AsQd'), Card.clean('Ah7c2d'))
    <KickerTier.GOOD: 'Good kicker'>
    >>> _kicker_tier(Card.clean('AsTd'), Card.clean('Ah7c2d'))
    <KickerTier.MEDIUM: 'Medium kicker'>
    >>> _kicker_tier(Card.clean('QcQd'), Card.clean('Jh7c2d')) is None
    True

    :param hole: The cleaned hole cards.
    :param board: The cleaned board cards.
    :return: The kicker tier, or ``None`` for a pocket pair.
    """
    board_ranks = frozenset(card.rank for card in board)
    paired = frozenset(card.rank for card in hole) & board_ranks

    if not paired:
        return None

    pair_rank = max(paired, key=RankOrder.STANDARD.index)
    kickers = [card.rank for card in hole if card.rank is not pair_rank]

    if not kickers:
        return None

    kicker = max(kickers, key=RankOrder.STANDARD.index)
    excluded = board_ranks | {pair_rank}
    available = [
        rank for rank in reversed(RankOrder.STANDARD) if rank not in excluded
    ]
    position = available.index(kicker) + 1

    if position == 1:
        return KickerTier.TOP
    elif position <= 3:
        return KickerTier.GOOD
    elif position <= 5:
        return KickerTier.MEDIUM

    return KickerTier.WEAK


def _two_pair_tier(
        hole: tuple[Card, ...],
        board: tuple[Card, ...],
) -> TwoPairTier:
    """Return the tier of a two-pair hand, board-relative.

    The two paired ranks are read off all seven cards. Using the board's
    top two distinct ranks is :attr:`TwoPairTier.TOP_TWO`; using the
    highest plus a lower rank is :attr:`TwoPairTier.TOP_AND_BOTTOM`; using
    neither top rank is :attr:`TwoPairTier.BOTTOM_TWO`. A pocket pair over
    the whole board atop a board pair also reads as
    :attr:`TwoPairTier.TOP_TWO`.

    >>> _two_pair_tier(Card.clean('AsKd'), Card.clean('AhKc2d'))
    <TwoPairTier.TOP_TWO: 'Top two pair'>
    >>> _two_pair_tier(Card.clean('As2c'), Card.clean('AhKc2d'))
    <TwoPairTier.TOP_AND_BOTTOM: 'Top and bottom two pair'>
    >>> _two_pair_tier(Card.clean('Kc2s'), Card.clean('AhKd2c'))
    <TwoPairTier.BOTTOM_TWO: 'Bottom two pair'>

    :param hole: The cleaned hole cards.
    :param board: The cleaned board cards.
    :return: The two-pair tier of the hand.
    """
    counts: dict[Rank, int] = {}

    for card in (*hole, *board):
        counts[card.rank] = counts.get(card.rank, 0) + 1

    pairs = _ranked(frozenset(r for r, c in counts.items() if c >= 2))
    top_pair, bottom_pair = pairs[0], pairs[1]
    board_ranks = _board_ranks(board)
    highest = board_ranks[0]
    second = board_ranks[1] if len(board_ranks) >= 2 else None
    hole_ranks = frozenset(card.rank for card in hole)

    if (
            len(hole_ranks) == 1
            and RankOrder.STANDARD.index(next(iter(hole_ranks)))
            > RankOrder.STANDARD.index(highest)
    ):
        return TwoPairTier.TOP_TWO

    if top_pair is highest and bottom_pair is second:
        return TwoPairTier.TOP_TWO
    elif top_pair is highest:
        return TwoPairTier.TOP_AND_BOTTOM

    return TwoPairTier.BOTTOM_TWO


def _three_of_a_kind_tier(
        hole: tuple[Card, ...],
        board: tuple[Card, ...],
) -> ThreeOfAKindTier:
    """Return the tier of a three-of-a-kind hand, board-relative.

    A concealed set (two hole cards of one rank plus a board card) is
    tiered by the set rank's position among the board's distinct ranks:
    first is :attr:`ThreeOfAKindTier.TOP_SET`, last is
    :attr:`ThreeOfAKindTier.BOTTOM_SET`, anything strictly between is
    :attr:`ThreeOfAKindTier.MIDDLE_SET`. Trips made by pairing a board
    pair with a single hole card is :attr:`ThreeOfAKindTier.TRIPS`. Every
    case returns a tier (paired boards included), unlike the source which
    dropped board-paired trips.

    >>> _three_of_a_kind_tier(Card.clean('7c7d'), Card.clean('7hKc2d'))
    <ThreeOfAKindTier.MIDDLE_SET: 'Middle set'>
    >>> _three_of_a_kind_tier(Card.clean('KcKd'), Card.clean('7hKs2d'))
    <ThreeOfAKindTier.TOP_SET: 'Top set'>
    >>> _three_of_a_kind_tier(Card.clean('AcKd'), Card.clean('AhAs8c'))
    <ThreeOfAKindTier.TRIPS: 'Trips'>

    :param hole: The cleaned hole cards.
    :param board: The cleaned board cards.
    :return: The three-of-a-kind tier of the hand.
    """
    hole_ranks = [card.rank for card in hole]

    if len(hole_ranks) == 2 and hole_ranks[0] is hole_ranks[1]:
        set_rank = hole_ranks[0]
        board_ranks = _board_ranks(board)

        if set_rank in board_ranks:
            position = board_ranks.index(set_rank)

            if position == 0:
                return ThreeOfAKindTier.TOP_SET
            elif position == len(board_ranks) - 1:
                return ThreeOfAKindTier.BOTTOM_SET

            return ThreeOfAKindTier.MIDDLE_SET

    return ThreeOfAKindTier.TRIPS


def _nut_rank(hand: Hand, core: _NutsCore) -> NutRank:
    """Return the nut rank of a made hand against every stronger holding.

    The count is the number of distinct strictly-stronger strengths a live
    two-card combo can reach ACROSS ALL made categories (read from the
    shared :class:`pokerkit_plus._semantic._NutsCore`, whose live pool
    already excludes the hero's cards, making the ranking blocker-aware).
    Ranking across categories — not just within the hero's own — is what
    keeps the read consistent with the nut hand: a made flush or straight on
    a board where a straight flush is possible is correctly below the nuts,
    never reported as nut while ``is_nut`` is false. Ranking is purely
    PokerKit's :class:`pokerkit.hands.Hand` total order, so a straight
    dominated by a higher broadway, or a flush whose nut card is an undealt
    out, lands below the third nut as
    :attr:`pokerkit_plus.draws.NutRank.NON_NUT` with no ace-as-1/14 case.

    :param hand: The hero hand to rank.
    :param core: The shared memoized enumeration, hero cards excluded.
    :return: The nut rank of the hand against all stronger holdings.
    """
    beaten = len({
        combo.hand.entry.index
        for combos in core.by_category.values()
        for combo in combos
        if combo.hand > hand
    })

    if beaten < len(__NUT_RANK_BY_INDEX):
        return __NUT_RANK_BY_INDEX[beaten]

    return NutRank.NON_NUT


@dataclass(frozen=True)
class HandTier:
    """The class for a hero-relative reading of a made hand.

    A hand tier bundles the made category with the board-relative
    refinements that apply to it: a pair tier and kicker tier for one
    pair, a two-pair tier for two pair, a three-of-a-kind tier (plus a
    kicker tier for trips) for three of a kind, and a straight/flush nut
    rank for the run-and-flush categories. Fields that do not apply to the
    made category are ``None``. Construct with :meth:`from_hand`, which
    evaluates the hand once via PokerKit and reuses one memoized
    :func:`pokerkit_plus._semantic._nuts_core` pass (hero cards excluded,
    so ``is_nut`` and the nut rank are blocker-aware).

    >>> tier = HandTier.from_hand('AsKd', 'Ah7c2d')
    >>> tier.category
    <Label.ONE_PAIR: 'One pair'>
    >>> tier.pair_tier
    <PairTier.TOP_PAIR: 'Top pair'>
    >>> tier.kicker_tier
    <KickerTier.TOP: 'Top kicker'>
    >>> tier.labels()
    ('Top pair', 'Top kicker')

    An overpair reports its tier with no kicker.

    >>> tier = HandTier.from_hand('QcQd', 'Jh7c2d')
    >>> tier.pair_tier
    <PairTier.OVERPAIR: 'Overpair'>
    >>> tier.kicker_tier is None
    True

    A concealed set is tiered; board-paired trips carry a kicker.

    >>> HandTier.from_hand('KcKd', '7hKs2d').three_of_a_kind_tier
    <ThreeOfAKindTier.TOP_SET: 'Top set'>
    >>> trips = HandTier.from_hand('AcQd', 'AhAs8c')
    >>> trips.three_of_a_kind_tier
    <ThreeOfAKindTier.TRIPS: 'Trips'>
    >>> trips.kicker_tier
    <KickerTier.GOOD: 'Good kicker'>

    The nut straight reads as the nut; a dominated straight does not, and
    holding the nut flush card on a four-flush board is blocker-aware.

    >>> nut = HandTier.from_hand('KcQc', '9hTcJd2s')
    >>> nut.is_nut
    True
    >>> nut.nut_rank
    <NutRank.NUT: 'Nut'>
    >>> low = HandTier.from_hand('8c7c', '9hTcJd2s')
    >>> low.nut_rank
    <NutRank.THIRD_NUT: 'Third nut'>
    >>> HandTier.from_hand('AsTh', 'Ks9s4s2s7d').nut_rank
    <NutRank.NUT: 'Nut'>
    >>> HandTier.from_hand('TsTh', 'Ks9s4s2s7d').nut_rank
    <NutRank.NON_NUT: 'Non-nut'>

    A straight flush (royal included) is just the nut straight flush; the
    royal-versus-steel-wheel distinction is a hand-level refinement left to
    :func:`pokerkit_plus._semantic._is_royal`, not a made-hand tier.

    >>> HandTier.from_hand('AsKs', 'QsJsTs').nut_rank
    <NutRank.NUT: 'Nut'>

    A hand that makes no valid five-card hand is rejected.

    >>> HandTier.from_hand('Ac', '')
    Traceback (most recent call last):
        ...
    ValueError: The cards 'Ac' on '' make no valid hand.

    :param category: The made-hand category from PokerKit's evaluator.
    :param is_nut: Whether the hand is the best possible (blocker-aware).
    :param pair_tier: The pair tier for a one-pair hand, else ``None``.
    :param two_pair_tier: The two-pair tier for two pair, else ``None``.
    :param three_of_a_kind_tier: The set/trips tier, else ``None``.
    :param kicker_tier: The kicker tier for a pair or trips, else ``None``.
    :param nut_rank: The straight/flush nut rank, else ``None``.
    """

    category: Label
    """The made-hand category from PokerKit's evaluator."""
    is_nut: bool
    """Whether the hand is the best possible hand (blocker-aware)."""
    pair_tier: PairTier | None
    """The pair tier for a one-pair hand, else ``None``."""
    two_pair_tier: TwoPairTier | None
    """The two-pair tier for a two-pair hand, else ``None``."""
    three_of_a_kind_tier: ThreeOfAKindTier | None
    """The set/trips tier for three of a kind, else ``None``."""
    kicker_tier: KickerTier | None
    """The kicker tier for a pair or trips, else ``None``."""
    nut_rank: NutRank | None
    """The straight/flush nut rank, else ``None``."""

    @classmethod
    def from_hand(
            cls,
            hole: CardsLike,
            board: CardsLike,
            *,
            hand_type: type[Hand] = StandardHighHand,
    ) -> HandTier:
        """Read the tier of a made hand on a board.

        Both card groups are cleaned once via
        :meth:`pokerkit.utilities.Card.clean`, the hand is evaluated once
        via ``hand_type.from_game_or_none`` (its category and strength are
        never recomputed by hand), and ``is_nut`` plus the straight/flush
        nut rank reuse one memoized
        :func:`pokerkit_plus._semantic._nuts_core` pass whose live pool
        excludes the hero's cards (so holding a nut card is honored).

        >>> HandTier.from_hand('Kc2s', 'AhKd2c').two_pair_tier
        <TwoPairTier.BOTTOM_TWO: 'Bottom two pair'>
        >>> HandTier.from_hand('AsKs', 'QsJsTs').is_nut
        True

        :param hole: The hero hole cards.
        :param board: The board cards.
        :param hand_type: The hand type to evaluate with, defaults to
                          :class:`pokerkit.hands.StandardHighHand`.
        :return: The tier of the made hand.
        :raises ValueError: If the cards make no valid hand.
        """
        hole_cards = Card.clean(hole)
        board_cards = Card.clean(board)
        hand = hand_type.from_game_or_none(hole_cards, board_cards)

        if hand is None:
            raise ValueError(
                f'The cards {repr(hole)} on {repr(board)} make no valid'
                ' hand.',
            )

        core = _nuts_core(_used(board_cards), hand_type, _used(hole_cards))
        category = hand.entry.label
        is_nut = core.hand is None or hand >= core.hand
        pair_tier: PairTier | None = None
        two_pair_tier: TwoPairTier | None = None
        three_of_a_kind_tier: ThreeOfAKindTier | None = None
        kicker_tier: KickerTier | None = None
        nut_rank: NutRank | None = None

        if category is Label.ONE_PAIR:
            pair_tier = _pair_tier(hole_cards, board_cards)
            kicker_tier = _kicker_tier(hole_cards, board_cards)
        elif category is Label.TWO_PAIR:
            two_pair_tier = _two_pair_tier(hole_cards, board_cards)
        elif category is Label.THREE_OF_A_KIND:
            three_of_a_kind_tier = _three_of_a_kind_tier(
                hole_cards, board_cards,
            )

            if three_of_a_kind_tier is ThreeOfAKindTier.TRIPS:
                kicker_tier = _kicker_tier(hole_cards, board_cards)
        elif category in _RUN_AND_FLUSH:
            nut_rank = _nut_rank(hand, core)

        return cls(
            category=category,
            is_nut=is_nut,
            pair_tier=pair_tier,
            two_pair_tier=two_pair_tier,
            three_of_a_kind_tier=three_of_a_kind_tier,
            kicker_tier=kicker_tier,
            nut_rank=nut_rank,
        )

    def labels(self) -> tuple[str, ...]:
        """Return the human-readable tier labels in display order.

        Each populated tier contributes its sentence-case enum value, in
        the order pair / two-pair / set first, then kicker, then nut rank.
        The result is a flat tuple suitable for joining in a UI; rendering
        (and any royal-flush refinement, which is a hand-level concern via
        :func:`pokerkit_plus._semantic._is_royal`, not a tier) is the
        caller's concern. A made hand with no applicable tier (such as a
        plain high card, or a full house or quads, whose strength is read
        from :attr:`category`) yields an empty tuple.

        >>> HandTier.from_hand('AsKd', 'Ah7c2d').labels()
        ('Top pair', 'Top kicker')
        >>> HandTier.from_hand('AcQd', 'AhAs8c').labels()
        ('Trips', 'Good kicker')
        >>> HandTier.from_hand('KcQc', '9hTcJd2s').labels()
        ('Nut',)
        >>> HandTier.from_hand('7h2c', '9d4sKc').labels()
        ()

        :return: The populated tier labels in display order.
        """
        parts: list[str] = []

        for tier in (
                self.pair_tier,
                self.two_pair_tier,
                self.three_of_a_kind_tier,
                self.kicker_tier,
                self.nut_rank,
        ):
            if tier is not None:
                parts.append(str(tier))

        return tuple(parts)