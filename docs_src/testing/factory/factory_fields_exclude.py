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
    # remove the name field
    no_name = FactoryField(exclude=True, name="name")


user_factory = UserFactory()

user_model_instance = user_factory.build()
# you can however provide it explicit
user_model_instance_with_name = UserFactory(name="edgy").build()
