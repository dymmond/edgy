import edgy
from edgy.contrib.permissions import BasePermission

models = edgy.Registry("sqlite:///foo.sqlite3")


class User(edgy.Model):
    name = edgy.fields.CharField(max_length=100)

    class Meta:
        registry = models


class Group(edgy.Model):
    name = edgy.fields.CharField(max_length=100)
    users = edgy.fields.ManyToMany("User", embed_through=False)

    class Meta:
        registry = models


class Permission(BasePermission):
    users = edgy.fields.ManyToMany("User", embed_through=False)
    groups = edgy.fields.ManyToMany("Group", embed_through=False)
    name_model: str = edgy.fields.CharField(max_length=100, null=True)
    obj = edgy.fields.ForeignKey("ContentType", null=True)

    class Meta:
        registry = models
        unique_together = [("name", "name_model", "obj")]
