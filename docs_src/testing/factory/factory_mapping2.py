import edgy
from edgy.testing.factory.mappings import DEFAULT_MAPPING
from edgy.testing.factory import ModelFactory, FactoryField

test_database = DatabaseTestClient(...)
models = edgy.Registry(database=...)


# the true user password simulator
def PasswordField_callback(field: FactoryField, faker: Faker, parameters: dict[str, Any]) -> Any:
    return faker.random_element(["company", "password123", "querty", "asdfg"])


class User(edgy.Model):
    password = edgy.fields.PasswordField(max_length=100)

    class Meta:
        registry = models


class UserFactory(ModelFactory):
    class Meta:
        model = User
        mappings = {"PasswordField": PasswordField_callback}


user_factory = UserFactory()

# now PasswordFields use a special custom mapping which provides common user passwords
user_model = user_factory.build()
