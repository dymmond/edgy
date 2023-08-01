import os

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/edgy"
)

TEST_DATABASE = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_edgy"
