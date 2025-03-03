import os

import pytest
import sqlalchemy

import edgy
from edgy import Instance
from edgy.contrib.permissions import BasePermission
from edgy.core.db.context_vars import CURRENT_MODEL_INSTANCE
from tests.settings import TEST_DATABASE

pytestmark = pytest.mark.anyio
models = edgy.Registry(
    database=TEST_DATABASE,
    with_content_type=os.environ.get("TEST_NO_CONTENT_TYPE", "false") != "true",
)

basedir = os.path.abspath(os.path.dirname(__file__))

if os.environ.get("TEST_ADD_NULLABLE_FIELDS", "false") == "true":

    class Profile(edgy.StrictModel):
        name = edgy.fields.CharField(max_length=100)

        class Meta:
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
        registry = models


class Group(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)
    users = edgy.fields.ManyToMany(
        "User", embed_through=False, through_tablename=edgy.NEW_M2M_NAMING
    )
    content_type = edgy.fields.ExcludeField()

    class Meta:
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
        registry = models
        if os.environ.get("TEST_NO_CONTENT_TYPE", "false") != "true":
            unique_together = [("name", "name_model", "obj")]


edgy.monkay.set_instance(Instance(registry=models))
