def test_alembic_version():
    from edgy.cli import alembic_version

    assert len(alembic_version) == 3

    for v in alembic_version:
        assert isinstance(v, int)
