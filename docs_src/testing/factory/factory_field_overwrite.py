import edgy
from edgy.testing.factory import ModelFactory, FactoryField

test_database = DatabaseTestClient(...)
models = edgy.Registry(database=...)


class User(edgy.Model):
    password = edgy.fields.CharField(max_length=100)
    icon = edgy.fields.ImageField()

    class Meta:
        registry = models


class UserFactory(ModelFactory):
    class Meta:
        model = User

    password = FactoryField(field_type="PasswordField")
    icon = FactoryField(field_type=edgy.fields.FileField)


user_factory = UserFactory()

# now the password uses the password field default mappings and for ImageField the FileField defaults
user_model = user_factory.build()
