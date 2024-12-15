# Default env template

import asyncio
import logging
import os
from collections.abc import Generator
from logging.config import fileConfig
from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from alembic import context
from rich.console import Console

import edgy
from edgy.core.connection import Database, Registry

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
MAIN_DATABASE_NAME: str = " "


def iter_databases(
    registry: Registry,
) -> Generator[tuple[str, Database, "sqlalchemy.MetaData"], None, None]:
    url: Optional[str] = os.environ.get("EDGY_DATABASE_URL")
    name: Union[str, Literal[False], None] = os.environ.get("EDGY_DATABASE") or False
    if url and not name:
        try:
            name = registry.metadata_by_url.get_name(url)
        except KeyError:
            name = None
    if name is False:
        db_names = edgy.monkay.settings.migrate_databases
        for name in db_names:
            if name is None:
                yield (None, registry.database, registry.metadata_by_name[None])
            else:
                yield (name, registry.extra[name], registry.metadata_by_name[name])
    else:
        if name == MAIN_DATABASE_NAME:
            name = None
        if url:
            database = Database(url)
        elif name is None:
            database = registry.database
        else:
            database = registry.extra[name]
        yield (
            name,
            database,
            registry.metadata_by_name[name],
        )


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
    registry = edgy.get_migration_prepared_registry()
    for name, db, metadata in iter_databases(registry):
        context.configure(
            url=str(db.url),
            target_metadata=metadata,
            literal_binds=True,
        )

        with context.begin_transaction():
            # for compatibility with flask migrate multidb kwarg is called engine_name
            context.run_migrations(engine_name=name or "")


def do_run_migrations(connection: Any, name: str, metadata: "sqlalchemy.Metadata") -> Any:
    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives) -> Any:  # type: ignore
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            empty = True
            for upgrade_ops in script.upgrade_ops_list:
                if not upgrade_ops.is_empty():
                    empty = False
                    break
            if empty:
                directives[:] = []
                console.print("[bright_red]No changes in schema detected.")

    context.configure(
        connection=connection,
        target_metadata=metadata,
        upgrade_token=f"{name or ''}_upgrades",
        downgrade_token=f"{name or ''}_downgrades",
        process_revision_directives=process_revision_directives,
        **edgy.monkay.settings.alembic_ctx_kwargs,
    )

    with context.begin_transaction():
        # for compatibility with flask migrate multidb kwarg is called engine_name
        context.run_migrations(engine_name=name or "")


async def run_migrations_online() -> Any:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # the original script checked for the async compatibility
    # we are only compatible with async drivers so just use Database
    registry = edgy.get_migration_prepared_registry()
    async with registry:
        for name, db, metadata in iter_databases(registry):
            async with db as database:
                await database.run_sync(do_run_migrations, name, metadata)


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
