from edgy.contrib.multi_tenancy.settings import TenancySettings


class EdgySettings(TenancySettings):
    tenant_model: str = "Tenant"
    """
    The Tenant model created
    """
    auth_user_model: str = "User"
    """
    The `user` table created. Not the `HubUser`!
    """
