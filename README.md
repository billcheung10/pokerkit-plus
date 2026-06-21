# PokerKit Plus

Fork-free capability extensions on top of [PokerKit](https://github.com/uoftcprg/pokerkit).

`pokerkit_plus` is a **drop-in superset** of `pokerkit`: it re-exports the entire
upstream surface unchanged and adds new capabilities on top via subclasses, free
functions, and thin wrappers. The upstream package is never modified, so PokerKit
Plus keeps riding upstream's maintenance (correctness fixes, new parsers, etc.).

```python
# Anywhere you used pokerkit, you can use pokerkit_plus instead:
from pokerkit_plus import NoLimitTexasHoldem, Automation, State   # all of pokerkit
# ...plus the PokerKit Plus additions as they land.
```

## Design

- **Form:** standalone extension package, `pip`-depends on `pokerkit==0.7.3` (pinned).
- **No fork, no monkeypatch.** PokerKit is built for fork-free extension
  (`_begin_/_update_/_end_` phase hooks, mixin-composed variants, injectable
  `rake`/`divmod`, `ClassVar` registries). Most additions need zero core edits.
- **`compat.py`** pins the pokerkit version and is the single home for stable
  aliases of version-fragile upstream names.

## Status

Semantic layer P0/P1 implemented (drop-in superset of pokerkit + first
capabilities):

- `pokerkit_plus.texture` — `BoardTexture.from_board` plus `Wetness`,
  `Connectivity`, `RankBand`, `StraightDraw`, `FlushDraw`, and
  `are_two_tone`/`are_monotone`/`are_rainbow`.
- `pokerkit_plus.combos` — `Nuts.from_board`, `CategoryCombos.from_board`,
  `HoleCombo`, `made_label`, `meets`, `CATEGORY_ORDER` (made-hand category is
  pokerkit's own `Label`).
- `pokerkit_plus.draws` — `Draws.from_hand` (hero flush/straight draw + nut
  rank) and the shared `NutRank`.
- `pokerkit_plus.tags` — `HandTier.from_hand` (made-hand tier + `labels()`)
  with `PairTier`/`KickerTier`/`TwoPairTier`/`ThreeOfAKindTier`.
- `pokerkit_plus.outs` — `Outs.from_hand` (category-upgrade outs, grouped).
- `pokerkit_plus.facade` — `HandReport.from_hand` and `BoardReport.from_board`,
  the one-call composed entry points for callers wanting a complete reading.

Built on pokerkit's lookup-table total order (no hand-rolled scoring); every
per-board / per-hand enumeration is memoized. Verified: mypy `--strict` clean,
ruff clean, unit tests + doctests green, `Nuts`/`Outs` match a brute-force
oracle on random hands, and a 2000-hand sweep shows no `is_nut`/`nut_rank`
contradictions. Blocker analysis and a range/advantage module are planned next.

### Candidate capabilities (menu, not yet scheduled)

| Capability | Category | Effort |
|---|---|---|
| FastState: snapshot/restore + undo for tree search | performance | L |
| Exact + deterministic equity engine with sampled-hand callbacks | equity | M |
| Range engine v2: weights, %-ranges, removal-aware combos | equity | M |
| Structured action-history & rich State view layer | dev-experience | M |
| Positions + multi-hand Table/session object | dev-experience | M |
| Bot/agent framework + baseline agents | AI/bots | M |
| Missing variants: 5/6-card PLO, Big O, Courchevel, 5-Card Draw, A-5 | variants | M |
| Mixed-game rotation (HORSE / 8-Game) | variants | M |
| Variant registry + parse-by-name + uniform create | integration | S |
| Fast lookup-table hand evaluator (5/6/7-card) | performance | L |
| Robust async multi-variant hand-history I/O | integration | L |
| State visualization & serialization (ASCII / SVG / JSON) | visualization | S |
| compat shim + Decimal/currency value type | dev-experience | S |

## Development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

MIT (same as PokerKit).
