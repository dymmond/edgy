import enum


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
    group = edgy.ForeignKey(Group, related_name="users")

    class Meta:
        registry = models


class UserFactory(ModelFactory):
    class Meta:
        model = User

    language = FactoryField(callback="language_code")


class GroupFactory(ModelFactory):
    class Meta:
        model = Group

    users = UserFactory().to_factory_field()


group_factory = GroupFactory()

group_factory_instance = group_factory.build()
