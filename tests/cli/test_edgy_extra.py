from esmerald import Esmerald
from tests.cli.main import app as main_app
from tests.cli.main_extra import app as extra_app

from edgy import Registry
from edgy.cli.constants import EDGY_DB, EDGY_EXTRA


def test_has_saffier_extra():
    assert hasattr(extra_app, EDGY_EXTRA)


def test_extra_esmerald():
    extra = getattr(extra_app, EDGY_EXTRA)["extra"]
    assert isinstance(extra.app, Esmerald)


def test_has_saffier_migration():
    assert hasattr(main_app, EDGY_DB)


def test_migration_registry():
    extra = getattr(main_app, EDGY_DB)["migrate"]
    assert isinstance(extra.registry, Registry)
