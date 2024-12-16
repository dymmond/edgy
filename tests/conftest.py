import os

import pytest

os.environ.setdefault("EDGY_SETTINGS_MODULE", "tests.settings.default.TestSettings")


@pytest.fixture(scope="module")
def anyio_backend():
    return ("asyncio", {"debug": True})
