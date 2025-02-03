import os

import pytest

import edgy
from edgy import Instance
from edgy.contrib.permissions import BasePermission
from tests.settings import TEST_ALTERNATIVE_DATABASE, TEST_DATABASE

pytestmark = pytest.mark.anyio
models = edgy.Registry(
    database=TEST_DATABASE,
    extra={"ano ther ": TEST_ALTERNATIVE_DATABASE},
    with_content_type=True,
)
basedir = os.path.abspath(os.path.dirname(__file__))


class User(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)

    class Meta:
        registry = models


class Group(edgy.StrictModel):
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


class Signal(edgy.StrictModel):
    user = edgy.fields.ForeignKey(User, no_constraint=True)
    signal_type = edgy.fields.CharField(max_length=100)
    database = models.extra["ano ther "]

    class Meta:
        registry = models


class Unrelated(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)
    database = models.extra["ano ther "]
    content_type = edgy.fields.ExcludeField()

    class Meta:
        registry = models


edgy.monkay.set_instance(Instance(registry=models))
