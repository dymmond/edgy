import datetime

from edgy.core.db.fields import DateTimeField

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo  # type: ignore


def test_default_timezone():
    _date = datetime.date(year=2024, month=1, day=1)
    _datetimen = datetime.datetime(year=2024, month=1, day=1, hour=12, minute=6)
    _datetimel = datetime.datetime(
        year=2024, month=1, day=1, hour=12, minute=6, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-10")
    )
    field = DateTimeField(name="dt", default_timezone=zoneinfo.ZoneInfo("Etc/UTC"))
    assert field.clean(field.name, _date)["dt"] == datetime.datetime(
        year=2024, month=1, day=1, tzinfo=zoneinfo.ZoneInfo("Etc/UTC")
    )
    assert field.to_model(field.name, _datetimen)["dt"] == _datetimen.replace(
        tzinfo=zoneinfo.ZoneInfo("Etc/UTC")
    )
    assert field.clean(field.name, _datetimel)["dt"] == _datetimel


def test_default_remove_timezone():
    _date = datetime.date(year=2024, month=1, day=1)
    _datetimen = datetime.datetime(year=2024, month=1, day=1, hour=12, minute=6)
    _datetimel = datetime.datetime(
        year=2024, month=1, day=1, hour=12, minute=6, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-10")
    )
    field = DateTimeField(
        name="dt", default_timezone=zoneinfo.ZoneInfo("Etc/UTC"), remove_timezone=True
    )
    assert field.clean(field.name, _date)["dt"] == datetime.datetime(year=2024, month=1, day=1)
    assert field.to_model(field.name, _datetimen)["dt"] == _datetimen.replace(tzinfo=None)
    assert field.clean(field.name, _datetimel)["dt"] == _datetimel.replace(tzinfo=None)


def test_force_timezone():
    _date = datetime.date(year=2024, month=1, day=1)
    _datetimen = datetime.datetime(year=2024, month=1, day=1, hour=12, minute=6)
    _datetimel = datetime.datetime(
        year=2024, month=1, day=1, hour=12, minute=6, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-10")
    )
    field = DateTimeField(name="dt", force_timezone=zoneinfo.ZoneInfo("Etc/UTC"))
    assert field.clean(field.name, _date)["dt"] == datetime.datetime(
        year=2024, month=1, day=1, tzinfo=zoneinfo.ZoneInfo("Etc/UTC")
    )
    assert field.to_model(field.name, _datetimen)["dt"] == _datetimen.replace(
        tzinfo=zoneinfo.ZoneInfo("Etc/UTC")
    )
    assert field.clean(field.name, _datetimel)["dt"] == _datetimel.astimezone(
        zoneinfo.ZoneInfo("Etc/UTC")
    )


def test_default_force_timezone():
    _date = datetime.date(year=2024, month=1, day=1)
    _datetimen = datetime.datetime(year=2024, month=1, day=1, hour=12, minute=6)
    _datetimel = datetime.datetime(
        year=2024, month=1, day=1, hour=12, minute=6, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-10")
    )
    field = DateTimeField(
        name="dt",
        default_timezone=zoneinfo.ZoneInfo("Etc/GMT-10"),
        force_timezone=zoneinfo.ZoneInfo("Etc/UTC"),
    )
    assert field.clean(field.name, _date)["dt"] == datetime.datetime(
        year=2024, month=1, day=1, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-10")
    ).astimezone(zoneinfo.ZoneInfo("Etc/UTC"))
    assert field.to_model(field.name, _datetimen)["dt"] == _datetimel.astimezone(
        zoneinfo.ZoneInfo("Etc/UTC")
    )
    assert field.clean(field.name, _datetimel)["dt"] == _datetimel.astimezone(
        zoneinfo.ZoneInfo("Etc/UTC")
    )


def test_default_force_remove_timezone():
    _date = datetime.date(year=2024, month=1, day=1)
    _datetimen = datetime.datetime(year=2024, month=1, day=1, hour=12, minute=6)
    _datetimel = datetime.datetime(
        year=2024, month=1, day=1, hour=12, minute=6, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-10")
    )
    field = DateTimeField(
        name="dt",
        default_timezone=zoneinfo.ZoneInfo("Etc/GMT-10"),
        force_timezone=zoneinfo.ZoneInfo("Etc/UTC"),
        remove_timezone=True,
    )
    assert field.clean(field.name, _date)["dt"] == datetime.datetime(
        year=2024, month=1, day=1, tzinfo=zoneinfo.ZoneInfo("Etc/GMT-10")
    ).astimezone(zoneinfo.ZoneInfo("Etc/UTC")).replace(tzinfo=None)
    assert field.to_model(field.name, _datetimen)["dt"] == _datetimel.astimezone(
        zoneinfo.ZoneInfo("Etc/UTC")
    ).replace(tzinfo=None)
    assert field.clean(field.name, _datetimel)["dt"] == _datetimel.astimezone(
        zoneinfo.ZoneInfo("Etc/UTC")
    ).replace(tzinfo=None)
