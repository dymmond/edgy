import enum


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

user_model_instance = user_factory.build()
# provide the name edgy
user_model_instance_with_name_edgy = user_factory.build(overwrites={"name": "edgy"})
