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
    # disable the implicit id field
    disable_id = FactoryField(exclude=True, name="id")


# you can also build an autosave factory which saves after building
class UserAutoSaveFactory(UserFactory):
    class Meta:
        model = User

    language = FactoryField(callback="language_code")

    @classmethod
    def build(cls, **kwargs):
        return edgy.run_sync(super().build(**kwargs).save)


user_factory = UserFactory(language="eng")

user_model_instance = user_factory.build()

edgy.run_sync(user_model_instance.save())

# or the UserAutoSaveFactory

UserAutoSaveFactory(language="en").build()
