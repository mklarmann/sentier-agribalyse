"""Run the public collaboration contracts in the repository's existing pytest CI."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "community/tests" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The records, the site and what is shared with sentier-bafu are checked by the Checks workflow
# on Python 3.12 (community/tests/test_workspace.py). The build audit has no such need.
TestBuildAudit = load("community_build_tests", "test_build_checks.py").BuildChecks
