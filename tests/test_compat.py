"""Tests for the version-pinning guard."""

import pytest

from pokerkit_plus import compat


def test_installed_version_matches_pin() -> None:
    assert compat.installed_pokerkit_version() == compat.PINNED_POKERKIT_VERSION


def test_assert_passes_on_pinned_version() -> None:
    compat.assert_pokerkit_version()  # should not raise or warn


def test_assert_warns_on_mismatch() -> None:
    with pytest.warns(UserWarning):
        compat.assert_pokerkit_version("9.9.9")


def test_assert_raises_on_mismatch_when_strict() -> None:
    with pytest.raises(RuntimeError):
        compat.assert_pokerkit_version("9.9.9", strict=True)
