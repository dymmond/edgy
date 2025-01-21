import enum


import edgy
from edgy.testing.factory.mappings import DEFAULT_MAPPING
from edgy.testing.factory import ModelFactory, FactoryField

test_database = DatabaseTestClient(...)
models = edgy.Registry(database=...)


class User(edgy.Model):
    password = edgy.fields.PasswordField(max_length=100)
    icon = edgy.fields.ImageField()

    class Meta:
        registry = models


class UserFactory(ModelFactory):
    class Meta:
        model = User
        mappings = {"ImageField": DEFAULT_MAPPING["FileField"], "PasswordField": None}


class UserSubFactory(UserFactory):
    class Meta:
        model = User


user_factory = UserFactory()

# now the password is excluded and for ImageField the FileField defaults are used
user_model = user_factory.build()

# this is inherited to children
user_model = UserSubFactory().build()
