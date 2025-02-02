import edgy
from edgy.testing.factory import ModelFactory, FactoryField

models = edgy.Registry(database=...)


class Group(edgy.Model):
    name: str = edgy.CharField(max_length=100, null=True)

    class Meta:
        registry = models


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100, null=True)
    language: str = edgy.CharField(max_length=200, null=True)
    group = edgy.ForeignKey(Group)

    class Meta:
        registry = models


class GroupFactory(ModelFactory):
    class Meta:
        model = Group


class UserFactory(ModelFactory):
    class Meta:
        model = User

    language = FactoryField(callback="language_code")
    group = GroupFactory().to_factory_field()


user_factory = UserFactory(language="eng")

user_model_instance = user_factory.build()
