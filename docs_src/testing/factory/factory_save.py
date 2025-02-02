import edgy
from edgy.testing.factory import ModelFactory, FactoryField

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


user_factory = UserFactory(language="eng")

user_model_instance = await user_factory.build_and_save()

# or sync
user_model_instance = user_factory.build(save=True)
