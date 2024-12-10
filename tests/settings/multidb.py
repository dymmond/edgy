from typing import Union

from edgy.conf.global_settings import EdgySettings


class TestSettings(EdgySettings):
    migrate_dbs: list[Union[str, None]] = [None, "extra"]
