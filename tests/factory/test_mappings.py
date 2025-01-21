import edgy
from edgy.testing import DatabaseTestClient
from edgy.testing.factory import ModelFactory
from edgy.testing.factory.metaclasses import DEFAULT_MAPPING
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL, full_isolation=False)
models = edgy.Registry(database=database)


class User(edgy.Model):
    password = edgy.fields.PasswordField(max_length=100, null=True)
    icon = edgy.fields.ImageField()

    class Meta:
        registry = models


def test_direct():
    class UserFactory(ModelFactory):
        class Meta:
            model = User
            mappings = {"ImageField": DEFAULT_MAPPING["FileField"], "PasswordField": None}

    user = UserFactory().build(parameters={"icon": {"length": 100}})
    assert not hasattr(user, "password")
    assert user.icon.size == 100


def test_inherited():
    class UserFactory(ModelFactory):
        class Meta:
            model = User
            mappings = {"ImageField": DEFAULT_MAPPING["FileField"]}

    class UserInheritedFactory(UserFactory):
        class Meta:
            model = User
            mappings = {"PasswordField": None}

    user = UserInheritedFactory().build(parameters={"icon": {"length": 100}})
    assert not hasattr(user, "password")
    assert user.icon.size == 100
