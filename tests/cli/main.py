import os

import pytest

import edgy
from edgy import Instance
from edgy.contrib.permissions import BasePermission
from tests.settings import TEST_DATABASE

pytestmark = pytest.mark.anyio
models = edgy.Registry(database=TEST_DATABASE, with_content_type=True)

basedir = os.path.abspath(os.path.dirname(__file__))


class User(edgy.StrictModel):
    name = edgy.fields.CharField(max_length=100)

    class Meta:
        registry = models


class Group(edgy.StrictModel):
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


edgy.monkay.set_instance(Instance(registry=models))
