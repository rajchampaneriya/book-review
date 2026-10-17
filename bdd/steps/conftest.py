"""Shared set-up for the BDD steps.

1. Puts the code under test on the import path, so `make bdd` (or `pytest bdd/steps`) works from
   the repo root with only the host .venv: the Python stack's application layer and its in-memory
   fake, the harness package, and the drivers next to this file.
2. Turns every scenario or Examples table tagged @known-defect into a strict expected failure.
   While the defect is unfixed the scenario shows as xfail; once it is fixed the scenario passes,
   strict mode reports XPASS as a failure, and that is the cue to remove the tag.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

for path in (
    REPO / "stacks" / "python" / "src",
    REPO / "stacks" / "python" / "tests" / "unit",
    REPO,
    Path(__file__).resolve().parent,
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

KNOWN_DEFECT = "known-defect"


def pytest_configure(config):
    config.addinivalue_line("markers", f"{KNOWN_DEFECT}: the scenario describes an unfixed defect (strict xfail)")


def pytest_collection_modifyitems(items):
    for item in items:
        if item.get_closest_marker(KNOWN_DEFECT):
            item.add_marker(pytest.mark.xfail(
                strict=True,
                reason="@known-defect: remove the tag once this scenario passes (see TASKS.md)",
            ))
