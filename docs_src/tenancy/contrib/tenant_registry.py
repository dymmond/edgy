import edgy
from edgy.contrib.multi_tenancy import TenantRegistry

database = edgy.Database("<YOUR-CONNECTION-STRING>")
registry = TenantRegistry(database=database)
