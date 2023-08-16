from typing import TYPE_CHECKING, Dict, Type

import sqlalchemy
from loguru import logger

from edgy.core.terminal import Terminal

terminal = Terminal()

if TYPE_CHECKING:
    from edgy.contrib.multi_tenancy import TenantModel, TenantRegistry


def table_schema(model_class: Type["TenantModel"], schema: str) -> sqlalchemy.Table:
    """
    Making sure the tables on inheritance state, creates the new
    one properly.

    The use of context vars instead of using the lru_cache comes from
    a warning from `ruff` where lru can lead to memory leaks.
    """
    return model_class.build(schema)


async def create_tables(
    registry: "TenantRegistry", tenant_models: Dict[str, Type["TenantModel"]], schema: str
) -> None:
    """
    Creates the table models for a specific schema just generated.

    Iterates through the tenant models and creates them in the schema.
    """

    for name, model in tenant_models.items():
        table = table_schema(model, schema)

        logger.info(f"Creating table '{name}' for schema: '{schema}'")
        try:
            async with registry.engine.begin() as connection:
                await connection.run_sync(table.create)
            await registry.engine.dispose()
        except Exception as e:
            logger.error(str(e))
            ...
