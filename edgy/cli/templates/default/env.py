import asyncio
import logging
import os
import sys
from logging.config import fileConfig
from typing import Any

from alembic import context
from databasez import DatabaseURL
from rich.console import Console
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from edgy import settings
from edgy.cli.constants import APP_PARAMETER
from edgy.cli.env import MigrationEnv
from edgy.exceptions import EdgyException

# The console used for the outputs
console = Console()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config: Any = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")


def get_app_location(argv: Any) -> Any:
    """
    Manually checks for the --app parameter.
    """
    if APP_PARAMETER in argv:
        try:
            return argv[argv.index(APP_PARAMETER) + 1]
        except IndexError as e:
            raise EdgyException(detail=str(e))  # noqa
    return None


def get_app() -> Any:
    """
    Gets the app via environment variable or via console parameter.
    """
    app_path = get_app_location(sys.argv[1:])
    migration = MigrationEnv()
    app_env = migration.load_from_env(path=app_path, enable_logging=False)
    return app_env.app


def get_engine_url() -> str:
    return os.environ.get("EDGY_DATABASE_URL")  # type: ignore


app: Any = get_app()

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option("sqlalchemy.url", get_engine_url())

target_db = app._edgy_db["migrate"].registry

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata() -> Any:
    if hasattr(target_db, "metadatas"):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline() -> Any:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=get_metadata(), literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> Any:
    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives) -> Any:  # type: ignore
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                console.print("[bright_red]No changes in schema detected.")

    context.configure(
        connection=connection,
        target_metadata=get_metadata(),
        process_revision_directives=process_revision_directives,
        **app._edgy_db["migrate"].kwargs,
    )

    with context.begin_transaction():
        context.run_migrations()


def is_async_connection(url: DatabaseURL) -> bool:
    """
    Verifies if is an async connection string.

    Validates the type of driver against the ones supported by Edgy.
    """
    if not url.driver:
        return False

    if (
        (url.driver in settings.postgres_drivers)
        or (url.driver in settings.mysql_drivers)
        or (url.driver in settings.sqlite_drivers)
        or url.driver in settings.mssql_drivers
    ):
        return True
    return False


async def run_migrations_online() -> Any:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    database_url = DatabaseURL(get_engine_url())
    is_async = is_async_connection(database_url)

    if is_async:
        connectable = create_async_engine(database_url._url)
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    else:
        connectable = create_engine(database_url._url)  # type: ignore
        with connectable.connect() as connection:
            do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.get_event_loop().run_until_complete(run_migrations_online())
