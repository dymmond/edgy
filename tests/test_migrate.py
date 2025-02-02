import pytest
from esmerald import Esmerald

import edgy
from edgy import Registry
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_ALTERNATIVE_URL, DATABASE_URL

database = DatabaseTestClient(url=DATABASE_URL)
database2 = DatabaseTestClient(url=DATABASE_ALTERNATIVE_URL)
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
    related = edgy.ManyToMany("Profile", inherit=False, through_tablename=edgy.NEW_M2M_NAMING)

    class Meta:
        registry = models


class Contact(Profile):
    age = edgy.CharField(max_length=255)
    address = edgy.CharField(max_length=255)
    database = database2

    class Meta:
        registry = models


@pytest.mark.parametrize(
    "instance_wrapper,deprecated", [("Instance", False), ("Migrate", True), ("EdgyExtra", True)]
)
def test_migrate_without_model_apps(instance_wrapper, deprecated):
    app = Esmerald()
    if deprecated:
        with pytest.warns(DeprecationWarning):
            migrate = getattr(edgy, instance_wrapper)(app=app, registry=models)
    else:
        migrate = getattr(edgy, instance_wrapper)(app=app, registry=models)
        edgy.monkay.set_instance(migrate)

    assert len(models.models) == 3
    assert len(migrate.registry.models) == 3
    registry = edgy.get_migration_prepared_registry()
    assert len(registry.models) == 3

    assert registry.get_model("Profile").meta.fields["related"].target is registry.get_model(
        "Profile"
    )
    through = registry.get_model("Profile").meta.fields["related"].through
    assert through is registry.get_model(through.__name__)
    assert registry.get_model("Contact").database is database2

    # try copying
    registry = edgy.get_migration_prepared_registry(registry.__copy__())
    assert len(registry.models) == 3
    assert registry.get_model("Profile").meta.fields["related"].target is registry.get_model(
        "Profile"
    )
    through = registry.get_model("Profile").meta.fields["related"].through
    assert through is registry.get_model(through.__name__)
    assert registry.get_model("Contact").database is database2


def test_migrate_without_model_apps_and_app():
    migrate = edgy.Instance(registry=models)
    edgy.monkay.set_instance(migrate)

    assert len(models.models) == 3
    assert len(migrate.registry.models) == 3
    registry = edgy.get_migration_prepared_registry()
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

    with pytest.warns(DeprecationWarning):
        edgy.Migrate(app=app, registry=nother, model_apps=model_apps)
    registry = edgy.get_migration_prepared_registry()
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

    with pytest.raises(AssertionError), pytest.warns(DeprecationWarning):
        edgy.Migrate(app=app, registry=nother, model_apps=model_apps)
