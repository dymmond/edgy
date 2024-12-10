import os
from pathlib import Path
from typing import Union

from edgy.contrib.multi_tenancy.settings import TenancySettings


class TestSettings(TenancySettings):
    tenant_model: str = "Tenant"
    auth_user_model: str = "User"
    media_root: Union[str, os.PathLike] = Path(__file__).parent.parent / "test_media/"
