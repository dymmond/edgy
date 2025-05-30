import edgy
from edgy.testing.factory import ModelFactory, FactoryField

test_database = DatabaseTestClient(...)
models = edgy.Registry(database=...)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class UserFactory(ModelFactory):
    class Meta:
        model = User

    language = FactoryField(callback="language_code")
    exclude_autoincrement = False


user_factory = UserFactory()

user_model = user_factory.build()
# now the id field is stubbed
assert hasattr(user_model, "id")
