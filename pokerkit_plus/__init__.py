"""PokerKit Plus — a fork-free, drop-in superset of :mod:`pokerkit`.

Everything importable from :mod:`pokerkit` is re-exported here unchanged, so
any ``from pokerkit import X`` can become ``from pokerkit_plus import X`` with
no other change. PokerKit Plus capabilities are layered on top via subclasses,
free functions, and thin wrappers — the upstream package is never modified.

As capabilities land, their public names are appended to ``_PLUS_ALL`` (and the
relevant submodule is imported below) so they show up in ``pokerkit_plus``'s
star-import surface alongside the upstream names.
"""

from __future__ import annotations

# Re-export the entire upstream surface. pokerkit ships a complete ``__all__``,
# so the star import is exact and stable.
from pokerkit import *  # noqa: F401, F403
from pokerkit import __all__ as _POKERKIT_ALL

# PokerKit Plus additions. Submodules own their public names (no per-module
# ``__all__``, matching pokerkit's leaf modules); this aggregator imports and
# registers them, exactly as pokerkit's own ``__init__`` does.
from pokerkit_plus.combos import (  # noqa: F401
    CATEGORY_ORDER,
    CategoryCombos,
    HoleCombo,
    Nuts,
    made_label,
    meets,
)
from pokerkit_plus.texture import (  # noqa: F401
    BoardTexture,
    Connectivity,
    CONNECTIVITY_ORDER,
    FlushDraw,
    FLUSH_DRAW_ORDER,
    RankBand,
    RANK_BAND_ORDER,
    StraightDraw,
    STRAIGHT_DRAW_ORDER,
    Wetness,
    WETNESS_ORDER,
    are_monotone,
    are_rainbow,
    are_two_tone,
)
from pokerkit_plus.draws import (  # noqa: F401
    Draws,
    NutRank,
    NUT_RANK_ORDER,
)
from pokerkit_plus.tags import (  # noqa: F401
    HandTier,
    KickerTier,
    PairTier,
    ThreeOfAKindTier,
    TwoPairTier,
)
from pokerkit_plus.outs import Outs  # noqa: F401
from pokerkit_plus.blockers import BlockerReport  # noqa: F401
from pokerkit_plus.facade import (  # noqa: F401
    BoardReport,
    HandReport,
)

__version__ = "0.0.1"

_PLUS_ALL: tuple[str, ...] = (
    # combos
    'CATEGORY_ORDER',
    'CategoryCombos',
    'HoleCombo',
    'Nuts',
    'made_label',
    'meets',
    # texture
    'BoardTexture',
    'Connectivity',
    'CONNECTIVITY_ORDER',
    'FlushDraw',
    'FLUSH_DRAW_ORDER',
    'RankBand',
    'RANK_BAND_ORDER',
    'StraightDraw',
    'STRAIGHT_DRAW_ORDER',
    'Wetness',
    'WETNESS_ORDER',
    'are_monotone',
    'are_rainbow',
    'are_two_tone',
    # draws
    'Draws',
    'NutRank',
    'NUT_RANK_ORDER',
    # tags
    'HandTier',
    'KickerTier',
    'PairTier',
    'ThreeOfAKindTier',
    'TwoPairTier',
    # outs
    'Outs',
    # blockers
    'BlockerReport',
    # facade
    'BoardReport',
    'HandReport',
)

__all__ = (*_POKERKIT_ALL, *_PLUS_ALL)
