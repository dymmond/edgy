import os
from pathlib import Path
from typing import Union

from edgy.contrib.multi_tenancy.settings import TenancySettings

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/edgy"
)

DATABASE_ALTERNATIVE_URL = os.environ.get(
    "TEST_DATABASE_ALTERNATIVE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/edgy_alt",
)

TEST_DATABASE = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_edgy"


class TestSettings(TenancySettings):
    tenant_model: str = "Tenant"
    auth_user_model: str = "User"
    media_root: Union[str, os.PathLike] = Path(__file__).parent.parent / "test_media/"
