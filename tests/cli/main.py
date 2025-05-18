import os

import sqlalchemy

import edgy
from edgy import Instance
from edgy.contrib.permissions import BasePermission
from edgy.core.db.context_vars import CURRENT_MODEL_INSTANCE
from edgy.core.signals import post_migrate, pre_migrate

models = edgy.Registry(
    database=os.environ.get("TEST_DATABASE", "sqlite:///test_db.sqlite"),
    with_content_type=os.environ.get("TEST_NO_CONTENT_TYPE", "false") != "true",
)

basedir = os.path.abspath(os.path.dirname(__file__))

if os.environ.get("TEST_ADD_NULLABLE_FIELDS", "false") == "true":

    class Profile(edgy.StrictModel):
        name = edgy.fields.CharField(max_length=100)

        class Meta:
            if os.environ.get("TEST_NO_REGISTRY_SET", "false") != "true":
                registry = models

    def complex_default() -> Profile:
        instance = CURRENT_MODEL_INSTANCE.get()
        return Profile(name=instance.name)


class User(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)
    if os.environ.get("TEST_ADD_NULLABLE_FIELDS", "false") == "true":
        # simple default
        active = edgy.fields.BooleanField(server_default=sqlalchemy.text("true"), default=False)
        profile = edgy.fields.ForeignKey("Profile", null=False, default=complex_default)

    class Meta:
        if os.environ.get("TEST_NO_REGISTRY_SET", "false") != "true":
            registry = models


class Group(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)
    users = edgy.fields.ManyToMany(
        "User", embed_through=False, through_tablename=edgy.NEW_M2M_NAMING
    )
    content_type = edgy.fields.ExcludeField()

    class Meta:
        if os.environ.get("TEST_NO_REGISTRY_SET", "false") != "true":
            registry = models


class Permission(BasePermission):
    users = edgy.fields.ManyToMany(
        "User", embed_through=False, through_tablename=edgy.NEW_M2M_NAMING
    )
    groups = edgy.fields.ManyToMany(
        "Group", embed_through=False, through_tablename=edgy.NEW_M2M_NAMING
    )
    name_model: str = edgy.fields.CharField(max_length=100, null=True)
    if os.environ.get("TEST_NO_CONTENT_TYPE", "false") != "true":
        obj = edgy.fields.ForeignKey("ContentType", null=True)
    content_type = edgy.fields.ExcludeField()

    class Meta:
        if os.environ.get("TEST_NO_REGISTRY_SET", "false") != "true":
            registry = models
        if os.environ.get("TEST_NO_CONTENT_TYPE", "false") != "true":
            unique_together = [("name", "name_model", "obj")]


if os.environ.get("TEST_ADD_SIGNALS", "false") == "true":

    @pre_migrate.connect_via("revision")
    def shout_revision(sender, sql, **kwargs):
        print(f"abc start {sender} ")

    @pre_migrate.connect_via("downgrade")
    @pre_migrate.connect_via("upgrade")
    def shout_migration(sender, sql, **kwargs):
        print(f"abc start {sender} {'offline' if sql else 'online'}")

    @post_migrate.connect_via("upgrade")
    async def create_user(sender, sql, **kwargs):
        print(f"abc start {sender}, create_user ")
        async with models:
            await User.query.get_or_create(name="migration_user")


if os.environ.get("TEST_NO_REGISTRY_SET", "false") != "true":
    edgy.monkay.set_instance(Instance(registry=models))
