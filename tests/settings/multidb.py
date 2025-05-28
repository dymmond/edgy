from edgy import EdgySettings


class TestSettings(EdgySettings):
    migrate_databases: list[str | None] = [None, "another"]
