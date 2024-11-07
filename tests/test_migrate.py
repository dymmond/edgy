import pytest
from esmerald import Esmerald

import edgy
from edgy import Migrate, Registry
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(url=DATABASE_URL)
models = Registry(database=database)
nother = Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models
        abstract = True


class Profile(User):
    age = edgy.IntegerField()
    parent = edgy.ForeignKey("Profile", null=True, inherit=False)
    related = edgy.ManyToMany("Profile", inherit=False)

    class Meta:
        registry = models


class Contact(Profile):
    age = edgy.CharField(max_length=255)
    address = edgy.CharField(max_length=255)

    class Meta:
        registry = models


def test_migrate_without_model_apps():
    app = Esmerald()
    migrate = Migrate(app=app, registry=models)

    assert len(models.models) == 3
    assert len(migrate.registry.models) == 3
    registry = migrate.get_registry_copy()
    assert len(registry.models) == 3


@pytest.mark.parametrize(
    "model_apps",
    [{"tests": "tests.test_migrate"}, ("tests.test_migrate",), ["tests.test_migrate"]],
    ids=["dict", "tuple", "list"],
)
def test_migrate_with_fake_model_apps(model_apps):
    app = Esmerald()
    nother.models = {}

    assert len(nother.models) == 0

    migrate = Migrate(app=app, registry=nother, model_apps=model_apps)
    registry = migrate.get_registry_copy()

    assert len(nother.models) == 2
    assert len(registry.models) == 2


@pytest.mark.parametrize(
    "model_apps",
    [set({"tests.test_migrate"}), frozenset({"tests.test_migrate"}), 1, 2.5, "a"],
    ids=["set", "fronzenset", "int", "float", "string"],
)
def test_raises_assertation_error_on_model_apps(model_apps):
    app = Esmerald()
    nother.models = {}

    assert len(nother.models) == 0

    with pytest.raises(AssertionError):
        Migrate(app=app, registry=nother, model_apps=model_apps)
