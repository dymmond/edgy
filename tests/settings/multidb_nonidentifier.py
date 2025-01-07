from typing import Union

from edgy import EdgySettings


class TestSettings(EdgySettings):
    migrate_databases: list[Union[str, None]] = [None, "ano ther "]
