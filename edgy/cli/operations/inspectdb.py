from typing import Union

import click
import sqlalchemy
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine

from edgy import Database, Registry
from edgy.cli.env import MigrationEnv
from edgy.cli.exceptions import MissingParameterException
from edgy.core.sync import execsync
from edgy.core.terminal import Print

printer = Print()


@click.option(
    "-u",
    "--user",
    default=None,
    help=("Database username."),
)
@click.option(
    "-p",
    "--password",
    default=None,
    help=("Database password"),
)
@click.option(
    "--host",
    default=None,
    help=("Database host."),
)
@click.option(
    "--database",
    default=None,
    help=("Database name."),
)
@click.option(
    "--port",
    default=5432,
    help=("Database port."),
)
@click.option(
    "--scheme",
    default="postgresql+asyncpg",
    help=("Scheme driver used for the connection. Example: 'postgresql+asyncpg'"),
)
@click.option(
    "--schema",
    default=None,
    help=("Database schema to be applied."),
)
@click.option(
    "--output",
    default=None,
    help=("Output file name with location. Example: 'models.py'."),
)
@click.command()
def inspect_db(
    env: MigrationEnv,
    port: int,
    scheme: str,
    user: Union[str, None] = None,
    password: Union[str, None] = None,
    host: Union[str, None] = None,
    database: Union[str, None] = None,
    output: Union[str, None] = None,
    schema: Union[str, None] = None,
) -> None:
    """
    Inspects an existing database and generates the Edgy reflect models.
    """
    registry: Union[Registry, None] = None
    try:
        registry = env.app._edgy_db["migrate"].registry  # type: ignore
    except AttributeError:
        registry = None

    # Generates a registry based on the passed connection details
    if registry is None:
        logger.info("`Registry` not found in the application. Using credentials...")
        connection_string = build_connection_string(port, scheme, user, password, host, database)
        _database: Database = Database(connection_string)
        registry = Registry(database=_database)

    # Get the engine to connect
    engine: AsyncEngine = registry.engine

    # Connect to a schema
    metadata: sqlalchemy.MetaData = (
        sqlalchemy.MetaData(schema=schema) if schema is not None else sqlalchemy.MetaData()
    )
    metadata = execsync(reflect)(engine=engine, metadata=metadata)


async def reflect(
    *, engine: sqlalchemy.Engine, metadata: sqlalchemy.MetaData
) -> sqlalchemy.MetaData:
    """
    Connects to the database and reflects all the information about the
    schema bringing all the data available.
    """

    async with engine.connect() as connection:
        logger.info("Collecting database tables information...")
        await connection.run_sync(metadata.reflect)
    return metadata


def build_connection_string(
    port: int,
    scheme: str,
    user: Union[str, None] = None,
    password: Union[str, None] = None,
    host: Union[str, None] = None,
    database: Union[str, None] = None,
) -> str:
    """
    Builds the database connection string.

    If a user or a password are not provided,
    then it will generate a connection string without authentication.
    """
    if not host and not database:
        raise MissingParameterException(detail="`host` and `database` must be provided.")

    if not user or not password:
        printer.write_info("Logging in without authentication.")
        return f"{scheme}://{host}:{port}/{database}"

    return f"{scheme}://{user}:{password}@{host}:{port}/{database}"
