import warnings
from typing import TYPE_CHECKING, Union

import sqlalchemy
from loguru import logger

from edgy.core.terminal import Terminal
from edgy.exceptions import ModelSchemaError

terminal = Terminal()

if TYPE_CHECKING:
    from edgy import Model, Registry
    from edgy.core.db.models.types import BaseModelType


def table_schema(model_class: type["Model"], schema: str) -> sqlalchemy.Table:
    warnings.warn(
        "'table_schema' has been deprecated, use '<model>.table_schema' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return model_class.table_schema(schema)


async def create_tables(
    registry: "Registry", models: dict[str, type["BaseModelType"]], schema: str
) -> None:
    """
    Creates the table models for a specific schema just generated.

    Iterates through the tenant models and creates them in the schema.
    """

    for model in models.values():
        table = model.table_schema(schema)

        logger.info(f"Creating table '{model.meta.tablename}' for schema: '{schema}'")
        try:
            async with registry.database as database:
                await database.run_sync(table.create)
        except Exception as e:
            logger.error(str(e))
            ...


async def create_schema(
    registry: "Registry",
    schema_name: str,
    models: Union[dict[str, type["BaseModelType"]], None] = None,
    if_not_exists: bool = False,
    should_create_tables: bool = False,
) -> None:
    """
    Creates a schema in a given registry.

    This function creates a new schema for a tenant in the provided registry.
    It optionally checks if the schema already exists and creates tables within
    the schema if specified.

    Parameters:
        registry (Registry): The registry object where the schema will be created.
        schema_name (str): The name of the schema to be created.
        models (dict[str, Model], optional): When models is provided, it will use them to generate
                                             those same models in a given schema or else
                                             it will default to the `registry.models`.
        if_not_exists (bool, optional): If True, the schema will be created only if it does not already exist.
                                        Defaults to False.
        should_create_tables (bool, optional): If True, tables will be created within the new schema. Defaults to False.

    Raises:
        ModelSchemaError: If the schema name is the same as the default schema name.
    """
    default_schema_name = registry.schema.get_default_schema() or "public"
    if schema_name.lower() == default_schema_name.lower():
        raise ModelSchemaError(
            f"Cannot create a schema with the same name as the default: '{schema_name}'."
        )

    # Create the new schema, optionally checking if it already exists
    await registry.schema.create_schema(schema_name, if_not_exists=if_not_exists)

    # Optionally create tables within the new schema
    if should_create_tables:
        terminal.write_info(f"Creating the tables in schema: {schema_name}")
        schema_models = models or registry.models
        await create_tables(registry, schema_models, schema_name)
