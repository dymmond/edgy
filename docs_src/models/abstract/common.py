import uuid

import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class BaseModel(saffier.Model):
    id = saffier.UUIDField(primary_key=True, default=uuid.uuid4)
    name = saffier.CharField(max_length=255)

    class Meta:
        abstract = True
        registry = models

    def get_description(self):
        """
        Returns the description of a record
        """
        return getattr(self, "description", None)


class User(BaseModel):
    """
    Inheriting the fields from the abstract class
    as well as the Meta data.
    """

    phone_number = saffier.CharField(max_length=15)
    description = saffier.TextField()

    def transform_phone_number(self):
        # logic here for the phone number
        ...


class Product(BaseModel):
    """
    Inheriting the fields from the abstract class
    as well as the Meta data.
    """

    sku = saffier.CharField(max_length=255)
    description = saffier.TextField()

    def get_sku(self):
        # Logic to obtain the SKU
        ...
