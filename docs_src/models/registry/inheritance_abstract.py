import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class BaseModel(saffier.Model):
    """
    The base model for all models using the `models` registry.
    """

    class Meta:
        abstract = True
        registry = models


class User(BaseModel):
    name = saffier.CharField(max_length=255)
    is_active = saffier.BooleanField(default=True)


class Product(BaseModel):
    user = saffier.ForeignKey(User, null=False, on_delete=saffier.CASCADE)
    sku = saffier.CharField(max_length=255, null=False)
