"""The drop-in contract: pokerkit_plus must re-export the whole pokerkit surface.

These tests guard the core promise of the package — that swapping
``import pokerkit`` for ``import pokerkit_plus`` is safe — and will catch drift
the day an upstream bump adds or renames a public name.
"""

import pokerkit

import pokerkit_plus


def test_reexports_every_pokerkit_name() -> None:
    missing = [name for name in pokerkit.__all__ if not hasattr(pokerkit_plus, name)]
    assert not missing, f"pokerkit_plus is missing re-exports: {missing}"


def test_reexported_objects_are_identical() -> None:
    for name in pokerkit.__all__:
        assert getattr(pokerkit_plus, name) is getattr(pokerkit, name), name


def test_all_is_superset_of_pokerkit() -> None:
    assert set(pokerkit.__all__) <= set(pokerkit_plus.__all__)


def test_no_duplicate_names_in_all() -> None:
    names = pokerkit_plus.__all__
    assert len(names) == len(set(names)), "duplicate names in pokerkit_plus.__all__"


def test_has_version() -> None:
    assert isinstance(pokerkit_plus.__version__, str)
