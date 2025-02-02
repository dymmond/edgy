import edgy
from edgy.testing.client import DatabaseTestClient
from edgy.testing.factory import ModelFactory, FactoryField

test_database1 = DatabaseTestClient(...)
test_database2 = DatabaseTestClient(...)
models = edgy.Registry(database=...)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)
    password = edgy.fields.PasswordField(max_length=100)

    class Meta:
        registry = models


class UserFactory(ModelFactory):
    class Meta:
        model = User

    language = FactoryField(callback="language_code")
    database = test_database1
    __using_schema__ = "test_schema1"


user_factory = UserFactory(language="eng")

user_model_instance = user_factory.build()


# customize later
user_model_instance_with_name_edgy = user_factory.build(
    overwrites={"name": "edgy"},
    parameters={"password": {"special_chars": False}},
    exclude={"language"},
)


# customize later, with different database and schema
user_model_instance_with_name_edgy = user_factory.build(
    overwrites={"name": "edgy"},
    parameters={"password": {"special_chars": False}},
    exclude={"language"},
    database=test_database2,
    schema="test_schema2",
)
