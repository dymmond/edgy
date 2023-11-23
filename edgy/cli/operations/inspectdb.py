from typing import Union

import click

from edgy.utils.inspect import InspectDB


@click.option(
    "--database",
    required=True,
    help=("Connection string. Example: postgres+asyncpg://user:password@localhost:5432/my_db"),
)
@click.option(
    "--schema",
    default=None,
    help=("Database schema to be applied."),
)
@click.command()
def inspect_db(
    database: str,
    schema: Union[str, None] = None,
) -> None:
    """
    Inspects an existing database and generates the Edgy reflect models.
    """
    inspect_db = InspectDB(database=database, schema=schema)
    inspect_db.inspect()
