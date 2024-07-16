import datetime

from edgy.core.db.fields import DateField

try:
    import zoneinfo  # type: ignore[import-not-found, unused-ignore]
except ImportError:
    from backports import zoneinfo  # type: ignore[import-not-found, no-redef, unused-ignore]


def test_default_timezone():
    _date = datetime.date(year=2024, month=1, day=1)
    _datetimen = datetime.datetime(year=2024, month=1, day=1, hour=12, minute=6)
    _datetimel = datetime.datetime(
        year=2024, month=1, day=1, hour=12, minute=6, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-10")
    )
    field = DateField(name="dt", default_timezone=zoneinfo.ZoneInfo("Etc/UTC"))
    assert field.clean(field.name, _date)["dt"] == _date
    assert (
        field.to_model(field.name, _datetimen)["dt"]
        == _datetimen.replace(tzinfo=zoneinfo.ZoneInfo("Etc/UTC")).date()
    )
    assert field.clean(field.name, _datetimel)["dt"] == _datetimel.date()


def test_force_timezone():
    _date = datetime.date(year=2024, month=1, day=1)
    _datetimen = datetime.datetime(year=2024, month=1, day=1, hour=12, minute=6)
    _datetimel = datetime.datetime(
        year=2024, month=1, day=1, hour=12, minute=6, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-10")
    )
    field = DateField(name="dt", force_timezone=zoneinfo.ZoneInfo("Etc/UTC"))
    assert field.clean(field.name, _date)["dt"] == _date
    assert field.to_model(field.name, _datetimen)["dt"] == _datetimen.date()
    assert (
        field.clean(field.name, _datetimel)["dt"]
        == _datetimel.astimezone(zoneinfo.ZoneInfo("Etc/UTC")).date()
    )


def test_default_force_timezone():
    _date = datetime.date(year=2024, month=1, day=1)
    _datetimen = datetime.datetime(year=2024, month=1, day=1, hour=12, minute=6)
    _datetimel = datetime.datetime(
        year=2024, month=1, day=1, hour=12, minute=6, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-10")
    )
    field = DateField(
        name="dt",
        default_timezone=zoneinfo.ZoneInfo("Etc/GMT-10"),
        force_timezone=zoneinfo.ZoneInfo("Etc/UTC"),
    )
    assert field.clean(field.name, _date)["dt"] == _date
    assert (
        field.to_model(field.name, _datetimen)["dt"]
        == _datetimel.astimezone(zoneinfo.ZoneInfo("Etc/UTC")).date()
    )
    assert (
        field.clean(field.name, _datetimel)["dt"]
        == _datetimel.astimezone(zoneinfo.ZoneInfo("Etc/UTC")).date()
    )
