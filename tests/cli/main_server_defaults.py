import os
from enum import Enum

import edgy
from edgy import Instance
from edgy.contrib.permissions import BasePermission
from tests.settings import TEST_DATABASE

models = edgy.Registry(
    database=TEST_DATABASE,
    with_content_type=os.environ.get("TEST_NO_CONTENT_TYPE", "false") != "true",
)

basedir = os.path.abspath(os.path.dirname(__file__))


class UserTypeEnum(Enum):
    INTERNAL = "Internal"
    SYSTEM = "System"
    EXTERNAL = "External"


class User(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)
    if os.environ.get("TEST_ADD_AUTO_SERVER_DEFAULTS", "false") == "true":
        # auto server defaults
        active = edgy.fields.BooleanField(default=True)
        is_staff = edgy.fields.BooleanField(default=False)
        age = edgy.fields.IntegerField(default=18)
        size = edgy.fields.DecimalField(default="1.8", decimal_places=2)
        blob = edgy.fields.BinaryField(default=b"abc")
        # needs special library for alembic enum migrations
        # user_type = edgy.fields.ChoiceField(choices=UserTypeEnum, default=UserTypeEnum.INTERNAL)
        data = edgy.fields.JSONField(default={"test": "test"})

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
