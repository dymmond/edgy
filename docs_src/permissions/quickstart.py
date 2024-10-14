import edgy
from edgy.contrib.permissions import BasePermission

models = edgy.Registry("sqlite:///foo.sqlite3")


class User(edgy.Model):
    name = edgy.fields.CharField(max_length=100, unique=True)

    class Meta:
        registry = models


class Permission(BasePermission):
    users = edgy.fields.ManyToMany("User", embed_through=False)

    class Meta:
        registry = models
        unique_together = [("name",)]


user = User.query.create(name="edgy")
permission = await Permission.query.create(users=[user], name="view")
assert await Permission.query.users("view").get() == user
await Permission.query.permissions_of(user)
