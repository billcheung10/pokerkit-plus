"""Version-pinning guard + a home for stable aliases of fragile pokerkit names.

PokerKit Plus pins ``pokerkit==0.7.3``. This module is the single place that
knows that fact, so:

* downstream code can call :func:`assert_pokerkit_version` to fail fast (or warn)
  if an unexpected pokerkit is installed, instead of breaking deep inside a call;
* version-fragile enum/method names (the ones downstream consumers flag as likely
  to be renamed upstream) get re-exported here behind stable aliases as they come
  up — keeping the churn contained to one file.

This is intentionally minimal until the compat capability is built out.
"""

from __future__ import annotations

import warnings
from importlib.metadata import PackageNotFoundError, version

PINNED_POKERKIT_VERSION = "0.7.3"


def installed_pokerkit_version() -> str | None:
    """Return the installed pokerkit version, or ``None`` if it is not installed."""
    try:
        return version("pokerkit")
    except PackageNotFoundError:
        return None


def assert_pokerkit_version(
    expected: str = PINNED_POKERKIT_VERSION,
    *,
    strict: bool = False,
) -> None:
    """Check the installed pokerkit against the pinned version.

    With ``strict=False`` (default) a mismatch emits a :class:`UserWarning`; with
    ``strict=True`` it raises :class:`RuntimeError`. A missing pokerkit always
    raises.
    """
    actual = installed_pokerkit_version()
    if actual is None:
        raise RuntimeError("pokerkit is not installed; pokerkit_plus requires it.")
    if actual != expected:
        message = (
            f"pokerkit_plus pins pokerkit=={expected} but {actual} is installed. "
            "Re-test pokerkit_plus against this version before relying on it."
        )
        if strict:
            raise RuntimeError(message)
        warnings.warn(message, UserWarning, stacklevel=2)
