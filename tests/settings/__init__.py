import os

from ravyn.conf.global_settings import RavynSettings


class TestSettings(RavynSettings):
    """Ravyn settings used by tests that boot Ravyn handlers during collection."""


DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/edgy"
)

DATABASE_ALTERNATIVE_URL = os.environ.get(
    "TEST_DATABASE_ALTERNATIVE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/edgy_alt",
)

TEST_DATABASE = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_edgy"
TEST_ALTERNATIVE_DATABASE = "postgresql+asyncpg://postgres:postgres@localhost:5433/test_edgy"

__all__ = [
    "DATABASE_URL",
    "DATABASE_ALTERNATIVE_URL",
    "TEST_DATABASE",
    "TEST_ALTERNATIVE_DATABASE",
    "TestSettings",
]
