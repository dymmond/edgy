import typing
from functools import cached_property

import edgedb

from edgy.core.connection.database import Database
from edgy.core.datastructures import ArbitraryHashableBaseModel


class Registry(ArbitraryHashableBaseModel):
    """
    The command center for the models being generated
    for EdgeDB.
    """

    def __init__(self, database: Database, **kwargs: typing.Any) -> None:
        super().__init__(**kwargs)
        self.database = database
        self.db_schema = kwargs.get("schema", None)
        self.models = {}

    @cached_property
    def engine(self) -> edgedb.AsyncIOClient:
        """Returns the edgedb asyncio client"""
        return self.database.client
