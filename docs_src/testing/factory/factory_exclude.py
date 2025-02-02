import edgy
from edgy.testing.exceptions import ExcludeValue
from edgy.testing.factory import ModelFactory, FactoryField

test_database = DatabaseTestClient(...)
models = edgy.Registry(database=...)


def callback(field_instance, faker, parameters):
    raise ExcludeValue


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models


class UserFactory(ModelFactory):
    class Meta:
        model = User

    language = FactoryField(callback=callback)


user_factory = UserFactory()

user_model_instance = user_factory.build(exclude={"name"})
