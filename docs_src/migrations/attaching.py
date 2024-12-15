from typing import Optional, Union

from edgy import EdgySettings


class MyMigrationSettings(EdgySettings):
    # here we notify about the models import path
    preloads: list[str] = ["myproject.apps.accounts.models"]
    # here we can set the databases which should be used in migrations, by default (None,)
    migrate_databases: Union[list[Union[str, None]], tuple[Union[str, None], ...]] = (None,)
