from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

os.environ.setdefault("EDGY_SETTINGS_MODULE", "tests.settings.default.TestSettings")

_DEFAULT_TEST_DATABASES = {
    "TEST_DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/edgy",
    "TEST_DATABASE_ALTERNATIVE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5433/edgy_alt",
    "TEST_DATABASE": "postgresql+asyncpg://postgres:postgres@localhost:5432/test_edgy",
    "TEST_ALTERNATIVE_DATABASE": "postgresql+asyncpg://postgres:postgres@localhost:5433/test_edgy",
}
_WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER")
if _WORKER_ID == "master":
    _WORKER_ID = None


def _database_url_with_suffix(url: str, suffix: str) -> str:
    parsed = urlsplit(url)
    if not parsed.path or parsed.path == "/":
        return url
    database = parsed.path.rsplit("/", 1)[-1]
    if database in {"", ":memory:"} or database.endswith(suffix):
        return url
    new_path = parsed.path[: -len(database)] + f"{database}{suffix}"
    return urlunsplit((parsed.scheme, parsed.netloc, new_path, parsed.query, parsed.fragment))


def _configure_worker_isolation() -> None:
    if not _WORKER_ID:
        return
    suffix = f"_{_WORKER_ID}"
    for env_name, default_url in _DEFAULT_TEST_DATABASES.items():
        current = os.environ.get(env_name, default_url)
        os.environ[env_name] = _database_url_with_suffix(current, suffix)
    media_root = Path(__file__).parent / "test_media" / _WORKER_ID
    os.environ.setdefault("EDGY_TEST_MEDIA_ROOT", str(media_root))


_configure_worker_isolation()

_DB_MARKER_CACHE: dict[str, bool] = {}
_SERIAL_PATHS = {"tests/test_automigrations.py"}
_SERIAL_PATH_PREFIXES = ("tests/cli/",)


def _get_node_path(item: pytest.Item) -> str:
    return item.nodeid.split("::", 1)[0].replace("\\", "/")


def _is_database_test(path: str) -> bool:
    if path in _DB_MARKER_CACHE:
        return _DB_MARKER_CACHE[path]
    try:
        source = Path(path).read_text(encoding="utf-8")
    except OSError:
        source = ""
    is_db_test = "DatabaseTestClient(" in source
    _DB_MARKER_CACHE[path] = is_db_test
    return is_db_test


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = _get_node_path(item)
        if path in _SERIAL_PATHS or path.startswith(_SERIAL_PATH_PREFIXES):
            item.add_marker("serial")
        if path.startswith("tests/cli/"):
            item.add_marker("cli")
        if path.startswith("tests/integration/"):
            item.add_marker("integration")
        if _is_database_test(path):
            item.add_marker("db")
            item.add_marker("postgres")


@pytest.fixture(scope="session", autouse=True)
def ensure_worker_media_root() -> None:
    media_root = os.environ.get("EDGY_TEST_MEDIA_ROOT")
    if not media_root:
        yield
        return
    media_path = Path(media_root)
    media_path.mkdir(parents=True, exist_ok=True)
    yield
    if _WORKER_ID:
        shutil.rmtree(media_path, ignore_errors=True)


@pytest.fixture(autouse=True)
def restore_working_directory() -> None:
    cwd = Path.cwd()
    yield
    os.chdir(cwd)


@pytest.fixture(scope="module")
def anyio_backend() -> tuple[str, dict[str, bool]]:
    return ("asyncio", {"debug": True})
