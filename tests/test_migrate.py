import pytest
from esmerald import Esmerald

import edgy
from edgy import Migrate, Registry
from edgy.testclient import DatabaseTestClient as Database
from tests.settings import DATABASE_URL

database = Database(url=DATABASE_URL)
models = Registry(database=database)
nother = Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    name = edgy.CharField(max_length=100)
    language = edgy.CharField(max_length=200, null=True)

    class Meta:
        registry = models
        abstract = True


class Profile(User):
    age = edgy.IntegerField()

    class Meta:
        registry = models
        tablename = "profiles"


class Contact(Profile):
    age = edgy.CharField(max_length=255)
    address = edgy.CharField(max_length=255)

    class Meta:
        registry = models
        tablename = "contacts"


class ReflectedContact(edgy.ReflectModel):
    age = edgy.CharField(max_length=255)
    address = edgy.CharField(max_length=255)

    class Meta:
        tablename = "contacts"
        registry = models


@pytest.mark.parametrize(
    "model_apps",
    [{"tests": "tests.test_migrate"}, ("tests.test_migrate",), ["tests.test_migrate"]],
    ids=["dict", "tuple", "list"],
)
def test_migrate_with_model_apps(model_apps):
    app = Esmerald()
    models.models = {}

    assert len(models.models) == 0

    migrate = Migrate(app=app, registry=models, model_apps=model_apps)

    assert len(models.models) == 2
    assert len(migrate.registry.models) == 2


@pytest.mark.parametrize(
    "model_apps",
    [set({"tests.test_migrate"}), frozenset({"tests.test_migrate"}), 1, 2.5, "a"],
    ids=["set", "fronzenset", "int", "float", "string"],
)
def test_raises_assertation_error_on_model_apps(model_apps):
    app = Esmerald()
    models.models = {}

    assert len(models.models) == 0

    with pytest.raises(AssertionError):
        Migrate(app=app, registry=models, model_apps=model_apps)
