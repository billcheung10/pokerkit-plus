# PokerKit Plus — usage guide

`pokerkit_plus` is a drop-in superset of [PokerKit](https://github.com/uoftcprg/pokerkit):
it re-exports everything in `pokerkit` unchanged and adds a **board/hand
semantic layer** — the human-readable poker concepts (board texture, draws,
outs, made-hand tiers, nuts, blockers, ranges) that a solver or a coaching tool
needs but that the raw evaluator does not provide.

Every reading is computed on pokerkit's own lookup-table hand evaluator (its
total order over `Hand` objects), so results are exactly consistent with
pokerkit and need no hand-rolled scoring. Functions take pokerkit cards in any
`CardsLike` form (a string like `'AsKs'`, a `Card`, or an iterable of `Card`)
and return frozen, typed result objects.

```bash
pip install pokerkit-plus          # also pulls pokerkit==0.7.3
```

```python
# One namespace for both pokerkit and the additions:
from pokerkit_plus import NoLimitTexasHoldem   # re-exported from pokerkit
from pokerkit_plus import HandReport           # a pokerkit_plus addition
```

Conventions used below: a *board* is 3-5 community cards, a *hole* is the hero's
2 cards. Made-hand categories are pokerkit's own `pokerkit.lookups.Label` (nine
members, ascending in strength; there is no separate `ROYAL_FLUSH` — a royal is
a straight flush, refined by an `is_royal` flag).

---

## Quick start: `HandReport` (the one-call facade)

`HandReport.from_hand(hole, board)` is the recommended entry point: it composes
the board texture, the made-hand tier, the draws, and the outs into one object,
so a caller gets a complete read in a single call. Each piece is also available
on its own (below).

```python
>>> from pokerkit_plus import HandReport
>>> report = HandReport.from_hand('JhTh', 'Qh9s2c')
>>> report.tier.category            # what the hand is right now
<Label.HIGH_CARD: 'High card'>
>>> report.draws.straight_draw      # what it is drawing to
<StraightDraw.OPEN_ENDED: 'Open-ended'>
>>> report.outs.count               # cards that improve the category
23

```

`BoardReport.from_board(board)` is the hero-independent counterpart (texture +
nuts), for describing a board on its own.

```python
>>> from pokerkit_plus import BoardReport
>>> board = BoardReport.from_board('AsKsQs')
>>> board.texture.wetness
<Wetness.WET: 'Wet'>
>>> board.nuts.label
<Label.STRAIGHT_FLUSH: 'Straight flush'>

```

---

## `pokerkit_plus.texture` — board texture

A hero-independent reading of the community cards: how drawy the board is and
what shapes it has. Use it to bucket or describe boards (e.g. "wet, connected,
two-tone") for strategy or reporting.

### `BoardTexture.from_board(board) -> BoardTexture`

Computes every texture field once from a single board.

```python
>>> from pokerkit_plus import BoardTexture
>>> tex = BoardTexture.from_board('Qh9s2c')
>>> tex.wetness
<Wetness.DRY: 'Dry'>
>>> tex.connectivity
<Connectivity.LOW: 'Low'>
>>> tex.rank_band
<RankBand.HIGH: 'High'>
>>> tex.flush_draw is None          # rainbow board offers no flush draw
True
>>> tex.are_rainbow
True

```

A two-tone board offers a backdoor flush:

```python
>>> BoardTexture.from_board('Ah7h2c').flush_draw
<FlushDraw.BACKDOOR: 'Backdoor'>

```

Fields: `wetness`, `connectivity`, `rank_band`, `straight_draw` (or `None`),
`flush_draw` (or `None`), `are_two_tone`, `are_monotone`, `are_rainbow`.

### Suit-shape predicates

`are_two_tone(cards)`, `are_monotone(cards)`, `are_rainbow(cards)` answer the
board's suit shape directly (the latter two reuse pokerkit's
`Card.are_suited` / `Card.are_rainbow`).

```python
>>> from pokerkit_plus import are_two_tone, are_monotone
>>> are_two_tone('Ah7h2c')
True
>>> are_monotone('AsKsQs')
True

```

### Texture enums

| Enum | Members | Meaning |
|---|---|---|
| `Wetness` | `DRY` / `SEMI_WET` / `WET` | how many draws the board offers (derived) |
| `Connectivity` | `DISCONNECTED` / `LOW` / `MEDIUM` / `HIGH` | how close the distinct ranks sit (wheel-aware) |
| `RankBand` | `LOW` / `MEDIUM` / `HIGH` | highest card band (2-6 / 7-9 / T-A) |
| `StraightDraw` | `BACKDOOR` / `GUTSHOT` / `OPEN_ENDED` / `DOUBLE_GUTSHOT` | straight-draw kind (field is optional) |
| `FlushDraw` | `BACKDOOR` / `LIVE` | flush-draw kind (field is optional) |

Each ordered enum has a companion tuple (`WETNESS_ORDER`, `CONNECTIVITY_ORDER`,
`RANK_BAND_ORDER`, `STRAIGHT_DRAW_ORDER`, `FLUSH_DRAW_ORDER`) for ranking.
Compare members with `is`, never by truth value.

---

## `pokerkit_plus.combos` — made-hand category and the nuts

Answers "what does a holding make on this board" and "what is the best possible
hand here". The made-hand category vocabulary is pokerkit's own `Label`.

### `made_label(hole, board) -> Label | None`

The category a holding makes (or `None` if no five-card hand can form).

```python
>>> from pokerkit_plus import made_label
>>> made_label('AsAc', 'Kh3sAd')
<Label.THREE_OF_A_KIND: 'Three of a kind'>
>>> made_label('AsKs', 'QsJsTs')
<Label.STRAIGHT_FLUSH: 'Straight flush'>

```

### `meets(label, floor) -> bool` and `CATEGORY_ORDER`

`meets` tests a category against a floor on the single strength scale
`CATEGORY_ORDER` (the nine `Label`s, weakest to strongest). Use it for
thresholds like "two pair or better".

```python
>>> from pokerkit_plus import meets, CATEGORY_ORDER
>>> from pokerkit import Label
>>> meets(Label.FLUSH, Label.TWO_PAIR)
True
>>> len(CATEGORY_ORDER)
9

```

### `Nuts.from_board(board) -> Nuts`

The strongest hand makeable on the board and every two-card combo that ties it.
Use it to know the nuts, count nut combos, or feed blocker analysis.

```python
>>> from pokerkit_plus import Nuts
>>> nuts = Nuts.from_board('AsKsQs')
>>> nuts.label
<Label.STRAIGHT_FLUSH: 'Straight flush'>
>>> nuts.is_royal
True
>>> len(nuts.combos)                # only TsJs makes the royal here
1

```

`Nuts` also exposes `hand` (the pokerkit `Hand`, or `None` for a sub-flop
board) and `board_is_nuts` (every holding ties — nothing can be blocked).

### `CategoryCombos.from_board(board) -> CategoryCombos`

Every live two-card combo grouped by what it makes; `.for_(label)` returns the
combos making exactly that category, `.nuts` is the board's `Nuts`. Use it for
range composition ("which holdings have a set here").

```python
>>> from pokerkit_plus import CategoryCombos
>>> from pokerkit import Label
>>> cc = CategoryCombos.from_board('7h2c9d')
>>> len(cc.for_(Label.THREE_OF_A_KIND))   # the three pocket pairs that set
9
>>> cc.nuts.label
<Label.THREE_OF_A_KIND: 'Three of a kind'>

```

`HoleCombo` is the combo type yielded above: `.cards` (the two `Card`s) and
`.as_frozenset` (the `frozenset[Card]` shape pokerkit ranges use).

---

## `pokerkit_plus.draws` — hero draw detection

What a holding is *drawing to* on the flop or turn, and how close that draw is
to the nuts. This is the "why" behind continuing with a non-made hand.

### `Draws.from_hand(hole, board) -> Draws`

```python
>>> from pokerkit_plus import Draws
>>> d = Draws.from_hand('JhTh', 'Qh9s2c')
>>> d.straight_draw
<StraightDraw.OPEN_ENDED: 'Open-ended'>
>>> d.flush_draw
<FlushDraw.BACKDOOR: 'Backdoor'>
>>> d.nut_rank
<NutRank.NUT: 'Nut'>

```

Fields: `straight_draw` (or `None`), `flush_draw` (or `None`), `nut_rank` (the
nut-ness of the strongest immediate draw, or `None`). Draws are read by
evaluating every one-card runout, so a draw a straight flush could beat is
correctly ranked below the nuts.

### `NutRank`

| Member | Meaning |
|---|---|
| `NUT` | no completion beats it |
| `SECOND_NUT` | beaten only by the single best completion |
| `THIRD_NUT` | beaten only by the two best |
| `NON_NUT` | beaten by three or more |

Shared with `tags` (a made flush/straight carries a `nut_rank` too). Ordered by
`NUT_RANK_ORDER`.

---

## `pokerkit_plus.tags` — qualitative made-hand tiers

The board-relative strength label of a made hand — the language a coach uses
("top pair top kicker", "top set", "second pair").

### `HandTier.from_hand(hole, board) -> HandTier`

```python
>>> from pokerkit_plus import HandTier
>>> t = HandTier.from_hand('AsKd', 'Ah7c2d')
>>> t.category
<Label.ONE_PAIR: 'One pair'>
>>> t.pair_tier
<PairTier.TOP_PAIR: 'Top pair'>
>>> t.kicker_tier
<KickerTier.TOP: 'Top kicker'>
>>> t.labels()                      # flat, human-readable
('Top pair', 'Top kicker')

```

Fields are populated by category: `pair_tier`, `kicker_tier`, `two_pair_tier`,
`three_of_a_kind_tier`, `nut_rank` (each optional), plus `category`, `is_nut`,
and `labels()`.

### Tier enums

| Enum | Members |
|---|---|
| `PairTier` | `OVERPAIR` / `TOP_PAIR` / `SECOND_PAIR` / `THIRD_PAIR` / `LOW_PAIR` / `UNDER_PAIR` |
| `KickerTier` | `TOP` / `GOOD` / `MEDIUM` / `WEAK` |
| `TwoPairTier` | `TOP_TWO` / `TOP_AND_BOTTOM` / `BOTTOM_TWO` |
| `ThreeOfAKindTier` | `TOP_SET` / `MIDDLE_SET` / `BOTTOM_SET` / `TRIPS` |

---

## `pokerkit_plus.outs` — improving cards

The live cards that raise the hero's made-hand **category** (the poker sense of
"outs"; a kicker bump within the same category is not an out). Useful for
equity intuition and coaching.

### `Outs.from_hand(hole, board) -> Outs`

```python
>>> from pokerkit_plus import Outs
>>> o = Outs.from_hand('Td9d', 'Jc8s2h')
>>> o.count                         # eight straight outs here
23
>>> from pokerkit import Label
>>> len(o.by_category[Label.STRAIGHT])
8

```

`count` is the number of distinct improving cards; `by_category` maps each
reachable `Label` to the cards that produce it. Defined on the flop and turn.

---

## `pokerkit_plus.blockers` — nut blockers

How much a holding *removes* the nuts from a villain's range — the blocker
reasoning behind bluffs and thin value.

### `BlockerReport.from_hand(hole, board) -> BlockerReport`

Count-based: it reports how many of the board's nut combos the hero's cards
remove. The card every nut combo needs blocks them all; an interchangeable
kicker blocks only its own; a board that is itself the nuts blocks nothing.

```python
>>> from pokerkit_plus import BlockerReport
>>> b = BlockerReport.from_hand('2s3c', '2c2d2h')   # the 2s makes every quad
>>> b.blocks_nuts
True
>>> b.block_fraction
1.0
>>> (b.nut_combos_blocked, b.nut_combos_total)
(4, 4)

```

Fields: `nut_combos_total`, `nut_combos_blocked`, `blocker_cards`, plus
`blocks_nuts` and `block_fraction`.

---

## `pokerkit_plus.ranges` — ranges and advantage

Range notation, board-aware value ranges, and the two-player "who has the
advantage" metrics. Ranges are the canonical `set[frozenset[Card]]` shape that
pokerkit's `parse_range` / `calculate_equities` speak, so they round-trip.

### `ComboClass.from_cards(cards).notation -> str`

The canonical preflop hole class (`AA` / `KQs` / `KQo`), order-independent.

```python
>>> from pokerkit_plus import ComboClass
>>> ComboClass.from_cards('AsKd').notation
'AKo'
>>> ComboClass.from_cards('JsTs').notation
'JTs'

```

### `expand_range(*notation) -> frozenset[frozenset[Card]]`

Expands range notation into concrete combos (a typed wrapper over pokerkit's
`parse_range`).

```python
>>> from pokerkit_plus import expand_range
>>> len(expand_range('QQ+'))        # QQ, KK, AA = 18 combos
18

```

### `build_value_range(board, aggression) -> frozenset[frozenset[Card]]`

The holdings that make a value hand on the board — every combo whose category
meets a floor. The floor defaults per `Aggression` level (`NO_BET` -> one pair,
`SINGLE_BET` -> two pair, `RAISED` -> a set; a documented default, overridable
with `floor=`).

```python
>>> from pokerkit_plus import build_value_range, Aggression
>>> from pokerkit import Card
>>> vr = build_value_range('Kh7c2d', Aggression.SINGLE_BET)
>>> frozenset(Card.parse('7h7s')) in vr     # trip sevens is a value hand
True
>>> frozenset(Card.parse('Ah3h')) in vr     # ace-high is not
False

```

### `nut_advantage(hero, villain, board) -> Advantage`

The exact share of nut-category combos each side holds — who has more of the
strongest hand type on the board.

```python
>>> from pokerkit_plus import nut_advantage, expand_range
>>> adv = nut_advantage(expand_range('AhAd'), expand_range('7h7d'), 'Kh7c2d')
>>> adv.villain_share                # 77 holds the set; AA does not
1.0

```

### `calculate_range_advantage(hero, villain, board) -> Advantage`

The pooled all-in **equity** share (Monte-Carlo, delegated to pokerkit). It is
stochastic, so seed `random` and raise `sample_count` for reproducible, tighter
estimates.

```python
>>> import random
>>> from pokerkit_plus import calculate_range_advantage, expand_range
>>> random.seed(0)
>>> adv = calculate_range_advantage(
...     expand_range('AhAd'), expand_range('7h7d'), 'Kh7c2d',
...     sample_count=2000,
... )
>>> adv.villain_share > 0.8          # the set crushes the overpair
True

```

`Advantage` carries `hero_share`, `villain_share` (summing to 1.0; a neutral
0.5/0.5 when a side is empty), and `basis` (`AdvantageBasis.EQUITY` or
`AdvantageBasis.NUT_SHARE`).

---

## Result objects at a glance

| Call | Returns | Key fields |
|---|---|---|
| `BoardTexture.from_board` | `BoardTexture` | `wetness`, `connectivity`, `rank_band`, `straight_draw`, `flush_draw`, `are_*` |
| `made_label` | `Label \| None` | — |
| `Nuts.from_board` | `Nuts` | `label`, `hand`, `is_royal`, `combos`, `board_is_nuts` |
| `CategoryCombos.from_board` | `CategoryCombos` | `by_category`, `nuts`, `.for_(label)` |
| `Draws.from_hand` | `Draws` | `straight_draw`, `flush_draw`, `nut_rank` |
| `HandTier.from_hand` | `HandTier` | `category`, `is_nut`, `*_tier`, `nut_rank`, `.labels()` |
| `Outs.from_hand` | `Outs` | `count`, `by_category` |
| `BlockerReport.from_hand` | `BlockerReport` | `nut_combos_total/blocked`, `blocker_cards`, `blocks_nuts`, `block_fraction` |
| `build_value_range` | `frozenset[frozenset[Card]]` | — |
| `nut_advantage` / `calculate_range_advantage` | `Advantage` | `hero_share`, `villain_share`, `basis` |
| `HandReport.from_hand` | `HandReport` | `texture`, `tier`, `draws`, `outs` |
| `BoardReport.from_board` | `BoardReport` | `texture`, `nuts` |
