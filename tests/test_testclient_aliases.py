from edgy.testclient import DatabaseTestClient, EdgyTestClient, EggyTestClient


def test_edgy_testclient_aliases() -> None:
    assert issubclass(EdgyTestClient, DatabaseTestClient)
    assert EggyTestClient is EdgyTestClient
