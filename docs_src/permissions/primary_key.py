import edgy
from edgy.contrib.permissions import BasePermission

models = edgy.Registry("sqlite:///foo.sqlite3")


class User(edgy.Model):
    name = edgy.fields.CharField(max_length=100)

    class Meta:
        registry = models


class Group(edgy.Model):
    name = edgy.fields.CharField(max_length=100)
    users = edgy.fields.ManyToMany(
        "User", embed_through=False, through_tablename=edgy.NEW_M2M_NAMING
    )

    class Meta:
        registry = models


class Permission(BasePermission):
    # overwrite name of BasePermission with a CharField with primary_key=True
    name: str = edgy.fields.CharField(max_length=100, primary_key=True)
    users = edgy.fields.ManyToMany(
        "User", embed_through=False, through_tablename=edgy.NEW_M2M_NAMING
    )
    groups = edgy.fields.ManyToMany(
        "Group", embed_through=False, through_tablename=edgy.NEW_M2M_NAMING
    )
    name_model: str = edgy.fields.CharField(max_length=100, null=True, primary_key=True)
    obj = edgy.fields.ForeignKey("ContentType", null=True, primary_key=True)

    class Meta:
        registry = models


user = User.query.create(name="edgy")
group = Group.query.create(name="edgy", users=[user])
permission = await Permission.query.create(users=[user], groups=[group], name="view", obj=user)
assert await Permission.query.users("view", objects=user).get() == user
await Permission.query.permissions_of(user)
