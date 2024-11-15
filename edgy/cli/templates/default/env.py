# Default env template

import asyncio
import logging
import os
from logging.config import fileConfig
from typing import TYPE_CHECKING, Any, Optional

from alembic import context
from rich.console import Console

import edgy
from edgy.core.connection import Database

if TYPE_CHECKING:
    import sqlalchemy

# The console used for the outputs
console = Console()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config: Any = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")


def get_engine_url_and_metadata() -> tuple[str, "sqlalchemy.MetaData"]:
    url: Optional[str] = os.environ.get("EDGY_DATABASE_URL")
    _name = None
    registry = edgy.get_migration_prepared_registry()
    _metadata = registry.metadata_by_name[None]
    if not url:
        db_name: Optional[str] = os.environ.get("EDGY_DATABASE")
        if db_name:
            url = str(registry.extra[db_name].url)
    if not url:
        url = str(registry.database.url)
    else:
        _metadata = registry.metadata_by_url.get(url, _metadata)
    return url, _metadata


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
target_url, target_metadata = get_engine_url_and_metadata()
config.set_main_option("sqlalchemy.url", target_url)


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> Any:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

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
        target_metadata=target_metadata,
        process_revision_directives=process_revision_directives,
        **edgy.monkay.settings.alembic_ctx_kwargs,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> Any:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # the original script checked for the async compatibility
    # we are only compatible with async drivers so just use Database
    async with Database(target_url) as database:
        await database.run_sync(do_run_migrations)


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
