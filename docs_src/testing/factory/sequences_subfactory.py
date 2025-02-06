import edgy
from edgy.testing.factory import ModelFactory, FactoryField, SubFactory

models = edgy.Registry(database=...)


class Group(edgy.Model):
    name: str = edgy.CharField(max_length=100, null=True)

    class Meta:
        registry = models


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100)
    group = edgy.ForeignKey(Group)

    class Meta:
        registry = models


class GroupFactory(ModelFactory):
    class Meta:
        model = Group

    name = FactoryField(
        callback=lambda field, context, parameters: f"group-{field.get_callcount()}"
    )


class UserFactory(ModelFactory):
    class Meta:
        model = User

    name = FactoryField(
        callback=lambda field, context, parameters: f"user-{field.get_callcount()}"
    )

    group = SubFactory(GroupFactory())


user = UserFactory().build()
assert user.name == "user-1"
assert user.group.name == "group-1"

user = UserFactory().build()
assert user.name == "user-2"
assert user.group.name == "group-2"

# now group callcount is at 1 again because the callcounts of the GroupFactory are used
group = GroupFactory().build()
assert group.name == "group-1"

# now group name callcount is at 3 because the callcounts of the UserFactory are used
group = GroupFactory().build(callcounts=UserFactory.meta.callcounts)
assert group.name == "group-3"

# now we see the group name callcount has been bumped but not the one of user name because the field wasn't in the
# GroupFactory build tree
user = UserFactory().build()
assert user.name == "user-3"
assert user.group.name == "group-4"
