import pytest


def pytest_collection_modifyitems(session, config, items):
    # CLI tests mutate shared folders under tests/cli (migrations/, migrations2/).
    # Keep them on a single worker while still allowing the rest of the suite to run in parallel.
    for item in items:
        item.add_marker(pytest.mark.xdist_group(name="cli"))
