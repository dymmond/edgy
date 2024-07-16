from urllib.parse import quote

import pytest

from edgy.core.connection.database import DatabaseURL


def test_database_url_repr():
    url = DatabaseURL("edgedb://localhost/edgedb")
    assert repr(url) == "DatabaseURL('edgedb://localhost/edgedb')"

    url = DatabaseURL("edgedb://username@localhost/edgedb")
    assert repr(url) == "DatabaseURL('edgedb://username@localhost/edgedb')"

    url = DatabaseURL("edgedb://username:password@localhost/edgedb")
    assert repr(url) == "DatabaseURL('edgedb://username:********@localhost/edgedb')"

    url = DatabaseURL(f"edgedb://username:{quote('[password')}@localhost/edgedb")
    assert repr(url) == "DatabaseURL('edgedb://username:********@localhost/edgedb')"


def test_database_url_properties():
    url = DatabaseURL("edgedb://username:password@localhost:5656/mydatabase")
    assert url.dialect == "edgedb"
    assert url.driver == ""
    assert url.username == "username"
    assert url.password == "password"
    assert url.hostname == "localhost"
    assert url.port == 5656
    assert url.database == "mydatabase"

    url = DatabaseURL("edgedb://username:password@/mydatabase?host=/var/run/edgedb/.s.PGSQL.5656")
    assert url.dialect == "edgedb"
    assert url.username == "username"
    assert url.password == "password"
    assert url.hostname == "/var/run/edgedb/.s.PGSQL.5656"
    assert url.database == "mydatabase"

    url = DatabaseURL(
        "edgedb://username:password@/mydatabase?unix_sock=/var/run/edgedb/.s.PGSQL.5656"
    )
    assert url.hostname == "/var/run/edgedb/.s.PGSQL.5656"


def test_database_url_escape():
    url = DatabaseURL(f"edgedb://username:{quote('[password')}@localhost/mydatabase")
    assert url.username == "username"
    assert url.password == "[password"
    assert url.userinfo == f"username:{quote('[password')}".encode()

    url2 = DatabaseURL(url)
    assert url2.password == "[password"

    url3 = DatabaseURL(str(url))
    assert url3.password == "[password"


def test_database_url_constructor():
    with pytest.raises(TypeError):
        DatabaseURL(("edgedb", "username", "password", "localhost", "mydatabase"))

    url = DatabaseURL("edgedb://username:password@localhost:5656/mydatabase")
    assert DatabaseURL(url) == url


def test_database_url_options():
    url = DatabaseURL("edgedb://localhost/mydatabase?pool_size=20&ssl=true")
    assert url.options == {"pool_size": "20", "ssl": "true"}


def test_replace_database_url_components():
    url = DatabaseURL("edgedb://localhost/mydatabase")

    assert url.database == "mydatabase"
    new = url.replace(database="test_" + url.database)
    assert new.database == "test_mydatabase"
    assert str(new) == "edgedb://localhost/test_mydatabase"

    assert url.driver == ""

    assert url.port is None
    new = url.replace(port=5656)
    assert new.port == 5656
    assert str(new) == "edgedb://localhost:5656/mydatabase"

    assert url.username is None
    assert url.userinfo is None
