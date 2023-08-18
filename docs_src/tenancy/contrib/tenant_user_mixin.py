import edgy
from edgy.contrib.multi_tenancy import TenantRegistry
from edgy.contrib.multi_tenancy.models import DomainMixin, TenantMixin, TenantUserMixin

database = edgy.Database("<YOUR-CONNECTION-STRING>")
registry = TenantRegistry(database=database)


class Tenant(TenantMixin):
    """
    Inherits all the fields from the `TenantMixin`.
    """

    class Meta:
        registry = registry


class Domain(DomainMixin):
    """
    Inherits all the fields from the `DomainMixin`.
    """

    class Meta:
        registry = registry


class TenantUser(TenantUserMixin):
    """
    Inherits all the fields from the `TenantUserMixin`.
    """

    class Meta:
        registry = registry
