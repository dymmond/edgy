import os

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/edgy"
)

DATABASE_ALTERNATIVE_URL = os.environ.get(
    "TEST_DATABASE_ALTERNATIVE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/edgy_alt",
)

TEST_DATABASE = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_edgy"
TEST_ALTERNATIVE_DATABASE = "postgresql+asyncpg://postgres:postgres@localhost:5433/test_edgy"
