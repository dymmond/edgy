import edgy
from edgy.contrib.permissions import BasePermission

models = edgy.Registry("sqlite:///foo.sqlite3")


class User(edgy.Model):
    name = edgy.fields.CharField(max_length=100)

    class Meta:
        registry = models


class Group(edgy.Model):
    name = edgy.fields.CharField(max_length=100)
    users = edgy.fields.ManyToMany("User", through_tablename=edgy.NEW_M2M_NAMING)

    class Meta:
        registry = models


class Permission(BasePermission):
    users = edgy.fields.ManyToMany("User", through_tablename=edgy.NEW_M2M_NAMING)
    groups = edgy.fields.ManyToMany("Group", through_tablename=edgy.NEW_M2M_NAMING)
    name_model: str = edgy.fields.CharField(max_length=100, null=True)
    obj = edgy.fields.ForeignKey("ContentType", null=True)

    class Meta:
        registry = models
        unique_together = [("name", "name_model", "obj")]


user = User.query.create(name="edgy")
group = Group.query.create(name="edgy", users=[user])
permission = await Permission.query.create(users=[user], groups=[group], name="view", obj=user)
assert await Permission.query.users("view", objects=user).get() == user
await Permission.query.permissions_of(user)
