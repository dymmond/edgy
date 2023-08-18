import edgy
from edgy.contrib.multi_tenancy import TenantRegistry
from edgy.contrib.multi_tenancy.models import TenantMixin

database = edgy.Database("<YOUR-CONNECTION-STRING>")
registry = TenantRegistry(database=database)


class Tenant(TenantMixin):
    """
    Inherits all the fields from the `TenantMixin`.
    """

    class Meta:
        registry = registry
