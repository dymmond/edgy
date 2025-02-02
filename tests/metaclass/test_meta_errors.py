from typing import ClassVar

import pytest

import edgy
from edgy import Manager, QuerySet
from edgy.exceptions import ForeignKeyBadConfigured, ImproperlyConfigured, ModelCollisionError
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))


class User(edgy.StrictModel):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class ObjectsManager(Manager):
    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset().filter(name__icontains="a")
        return queryset


async def test_improperly_configured_for_primary_key():
    with pytest.raises(ImproperlyConfigured) as raised:

        class BaseModel(edgy.StrictModel):
            id = edgy.IntegerField(primary_key=False)
            query: ClassVar[Manager] = ObjectsManager()
            languages: ClassVar[Manager] = ObjectsManager()

            class Meta:
                registry = models

    assert (
        raised.value.args[0]
        == "Cannot create model BaseModel without explicit primary key if field 'id' is already present."
    )


@pytest.mark.parametrize("_type,value", [("int", 1), ("dict", {}), ("set", set())])
async def test_improperly_configured_for_constraints(_type, value):
    with pytest.raises(ImproperlyConfigured) as raised:

        class BaseModel(edgy.StrictModel):
            name = edgy.IntegerField()
            query: ClassVar[Manager] = ObjectsManager()
            languages: ClassVar[Manager] = ObjectsManager()

            class Meta:
                registry = models
                constraints = value

    assert raised.value.args[0] == f"constraints must be a tuple or list. Got {_type} instead."


@pytest.mark.parametrize("_type,value", [("int", 1), ("dict", {"name": "test"}), ("set", set())])
async def test_improperly_configured_for_unique_together(_type, value):
    with pytest.raises(ImproperlyConfigured) as raised:

        class BaseModel(edgy.StrictModel):
            name = edgy.IntegerField()
            query: ClassVar[Manager] = ObjectsManager()
            languages: ClassVar[Manager] = ObjectsManager()

            class Meta:
                registry = models
                unique_together = value

    assert raised.value.args[0] == f"unique_together must be a tuple or list. Got {_type} instead."


@pytest.mark.parametrize(
    "value",
    [(1, dict), ["str", 1, set], [1], [dict], [set], [set, dict, list, tuple]],
    ids=[
        "int-and-dict",
        "str-int-set",
        "list-of-int",
        "list-of-dict",
        "list-of-set",
        "list-of-set-dict-tuple-and-lists",
    ],
)
async def test_value_error_for_unique_together(value):
    with pytest.raises(ValueError) as raised:

        class BaseModel(edgy.StrictModel):
            name = edgy.IntegerField()
            query: ClassVar[Manager] = ObjectsManager()
            languages: ClassVar[Manager] = ObjectsManager()

            class Meta:
                registry = models
                unique_together = value

    assert (
        raised.value.args[0]
        == "The values inside the unique_together must be a string, a tuple of strings or an instance of UniqueConstraint."
    )


def test_raises_value_error_on_wrong_type():
    with pytest.raises(ValueError) as raised:

        class User(edgy.StrictModel):
            name = edgy.CharField(max_length=255)

            class Meta:
                registry = models
                indexes = ["name"]

    assert raised.value.args[0] == "Meta.indexes must be a list of Index types."


def test_raises_ModelCollisionError():
    with pytest.raises(ModelCollisionError) as raised:

        class User(edgy.StrictModel):
            name = edgy.CharField(max_length=255)

            class Meta:
                registry = models

    assert raised.value.args[0] == (
        'A model with the same name is already registered: "User".\n'
        'If this is not a bug, define the behaviour by setting "on_conflict" to either "keep" or "replace".'
    )


@pytest.mark.parametrize("value", [True, "allow_search"])
def test_no_raises_ModelCollisionError_and_set_correctly(value):
    class BaseUser(edgy.StrictModel):
        name = edgy.CharField(max_length=255)

        class Meta:
            registry = models
            abstract = True

    class User(BaseUser, skip_registry=value):
        pass

    if value is True:
        assert BaseUser.meta.registry is models
        assert User.meta.registry is None
    else:
        assert BaseUser.meta.registry is models
        assert User.meta.registry is models


def test_raises_ForeignKeyBadConfigured():
    name = "profiles"

    with pytest.raises(ForeignKeyBadConfigured) as raised:

        class User2(edgy.StrictModel):
            name = edgy.CharField(max_length=255)

            class Meta:
                registry = models

        class Profile(edgy.StrictModel):
            user = edgy.ForeignKey(User2, null=False, on_delete=edgy.CASCADE, related_name=name)
            another_user = edgy.ForeignKey(
                User2, null=False, on_delete=edgy.CASCADE, related_name=name
            )

            class Meta:
                registry = models

    assert (
        raised.value.args[0]
        == f"Multiple related_name with the same value '{name}' found to the same target. Related names must be different."
    )
