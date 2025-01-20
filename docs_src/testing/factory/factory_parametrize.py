import enum


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

    # strings are an abbrevation for faker methods
    language = FactoryField(
        callback=lambda field_instance, faker, parameters: faker.language_code(**parameters)
    )
    name = FactoryField(
        callback=lambda field_instance,
        faker,
        parameters: f"{parameters['first_name']} {parameters['last_name']}",
        parameters={
            "first_name": lambda field_instance, faker, parameters: faker.first_name(),
            "last_name": lambda field_instance, faker, parameters: faker.last_name(),
        },
    )


user_factory = UserFactory()

# now the name is composed by two names
user_model = user_factory.build()

# now the name is composed by two names and both names are edgy
user_model = user_factory.build(parameters={"name": {"first_name": "edgy", "last_name": "edgy"}})
