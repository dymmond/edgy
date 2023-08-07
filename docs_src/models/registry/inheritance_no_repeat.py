import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class BaseModel(edgy.Model):
    """
    The base model for all models using the `models` registry.
    """

    class Meta:
        registry = models


class User(BaseModel):
    name = edgy.CharField(max_length=255)
    is_active = edgy.BooleanField(default=True)


class Product(BaseModel):
    user = edgy.ForeignKey(User, null=False, on_delete=edgy.CASCADE)
    sku = edgy.CharField(max_length=255, null=False)
