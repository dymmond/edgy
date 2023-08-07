import uuid

import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class BaseModel(edgy.Model):
    id = edgy.UUIDField(primary_key=True, default=uuid.uuid4)
    name = edgy.CharField(max_length=255)

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

    phone_number = edgy.CharField(max_length=15)
    description = edgy.TextField()

    def transform_phone_number(self):
        # logic here for the phone number
        ...


class Product(BaseModel):
    """
    Inheriting the fields from the abstract class
    as well as the Meta data.
    """

    sku = edgy.CharField(max_length=255)
    description = edgy.TextField()

    def get_sku(self):
        # Logic to obtain the SKU
        ...
