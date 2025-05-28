import os
from pathlib import Path

from edgy.contrib.multi_tenancy.settings import TenancySettings


class TestSettings(TenancySettings):
    tenant_model: str = "Tenant"
    auth_user_model: str = "User"
    media_root: str | os.PathLike = Path(__file__).parent.parent / "test_media/"
