from typing import Annotated

import sayer

from edgy.utils.inspect import InspectDB


@sayer.command
def inspect_db(
    database: Annotated[
        str,
        sayer.Option(
            required=True,
            help=(
                "Connection string. Example: postgres+asyncpg://user:password@localhost:5432/my_db"
            ),
        ),
    ],
    schema: Annotated[str | None, sayer.Option(None, help="Database schema to be applied.")],
) -> None:
    """
    Inspects an existing database and generates the Edgy reflect models.
    """
    inspect_db = InspectDB(database=database, schema=schema)
    inspect_db.inspect()
