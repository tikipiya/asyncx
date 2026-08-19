from importlib.metadata import version

import asyncx


def test_runtime_version_matches_distribution_metadata():
    assert asyncx.__version__ == version("asyncx-tools")
