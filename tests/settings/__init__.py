import os
from urllib.parse import urlsplit, urlunsplit


def _apply_xdist_worker_suffix(url: str) -> str:
    """
    Make database names unique per pytest-xdist worker.

    This prevents workers from creating/dropping the same database concurrently.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker:
        return url

    split = urlsplit(url)
    if not split.path or split.path == "/":
        return url

    base_path, separator, database_name = split.path.rpartition("/")
    if not separator or not database_name:
        return url
    if database_name == ":memory:":
        return url

    suffix = f"_{worker}"
    if database_name.endswith(suffix):
        return url

    path = f"{base_path}{separator}{database_name}{suffix}"
    return urlunsplit((split.scheme, split.netloc, path, split.query, split.fragment))


DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/edgy"
)

DATABASE_ALTERNATIVE_URL = os.environ.get(
    "TEST_DATABASE_ALTERNATIVE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/edgy_alt",
)

TEST_DATABASE = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_edgy"
TEST_ALTERNATIVE_DATABASE = "postgresql+asyncpg://postgres:postgres@localhost:5433/test_edgy"

DATABASE_URL = _apply_xdist_worker_suffix(DATABASE_URL)
DATABASE_ALTERNATIVE_URL = _apply_xdist_worker_suffix(DATABASE_ALTERNATIVE_URL)
TEST_DATABASE = _apply_xdist_worker_suffix(TEST_DATABASE)
TEST_ALTERNATIVE_DATABASE = _apply_xdist_worker_suffix(TEST_ALTERNATIVE_DATABASE)
