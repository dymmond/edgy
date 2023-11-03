from typing import Any, Dict, List, Union

import click
import sqlalchemy
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import sqltypes

import edgy
from edgy import Database, Registry
from edgy.cli.env import MigrationEnv
from edgy.cli.exceptions import MissingParameterException
from edgy.core.sync import execsync
from edgy.core.terminal import Print

printer = Print()


SQL_MAPPING_TYPES = {
    sqltypes.BIGINT: edgy.BigIntegerField,
    sqltypes.INTEGER: edgy.IntegerField,
    sqltypes.JSON: edgy.JSONField,
    sqltypes.DATE: edgy.DateField,
    sqltypes.VARCHAR: edgy.CharField,
    sqltypes.BINARY: edgy.BinaryField,
    sqltypes.BOOLEAN: edgy.BooleanField,
    sqltypes.Enum: edgy.ChoiceField,
    sqltypes.DATETIME: edgy.DateTimeField,
    sqltypes.DECIMAL: edgy.DecimalField,
    sqltypes.FLOAT: edgy.FloatField,
    sqltypes.SMALLINT: edgy.SmallIntegerField,
    sqltypes.TEXT: edgy.TextField,
    sqltypes.TIME: edgy.TimeField,
    sqltypes.UUID: edgy.UUIDField,
}


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

    # Generate the tables
    generate_tables(metadata, registry)


def generate_tables(metadata: sqlalchemy.MetaData, registry: Registry) -> Registry:
    """
    Generates the tables from the reflection and maps them into the
    `reflected` dictionary of the `Registry`.
    """
    tables_dict = dict(metadata.tables.items())
    tables = []

    for key, table in tables_dict.items():
        table_details: Dict[str, Any] = {}
        table_details["tablename"] = key
        table_details["class_name"] = key.replace("_", "").capitalize()
        table_details["table"] = table

        # Get the details of the foreign key
        table_details["foreign_keys"] = get_foreign_keys(table)

        # Get the details of the indexes
        table_details["indexes"] = table.indexes
        tables.append(table_details)

    return registry


def get_foreign_keys(table: sqlalchemy.Table) -> List[Dict[str, Any]]:
    """
    Extracts all the information needed of the foreign keys.
    """
    details: List[Dict[str, Any]] = []

    for foreign_key in table.foreign_keys:
        fk: Dict[str, Any] = {}
        fk["column"] = foreign_key.column
        fk["column_name"] = foreign_key.column.name
        fk["tablename"] = foreign_key.column.table.name
        fk["class_name"] = foreign_key.column.table.name.replace("_", "").capitalize()
        fk["on_delete"] = foreign_key.ondelete
        fk["on_update"] = foreign_key.onupdate
        fk["null"] = foreign_key.column.nullable
        details.append(fk)

    return details


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
