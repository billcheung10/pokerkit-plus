"""Keep the usage guide honest: every example in docs/USAGE.md must run.

This doctests the published usage guide so its code samples can never drift
from the real API.
"""

import doctest
from pathlib import Path


def test_usage_guide_examples_run() -> None:
    path = Path(__file__).resolve().parent.parent / 'docs' / 'USAGE.md'
    failures, _ = doctest.testfile(str(path), module_relative=False)

    assert failures == 0
