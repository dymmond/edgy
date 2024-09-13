from typing import Any, Dict, List, Type, Union

import sqlalchemy
from loguru import logger

import edgy
from edgy.core.db.models.model import Model
from edgy.core.db.models.utils import get_model
from edgy.testclient import DatabaseTestClient as Database

database = Database("<YOUR-CONNECTION-STRING>")
registry = edgy.Registry(database=database)


class Tenant(edgy.Model):
    schema_name: str = edgy.CharField(max_length=63, unique=True, index=True)
    tenant_name: str = edgy.CharField(max_length=100, unique=True, null=False)

    class Meta:
        registry = registry

    def table_schema(
        self,
        model_class: Type["Model"],
        schema: str,
    ) -> sqlalchemy.Table:
        return model_class.table_schema(schema)

    async def create_tables(
        self,
        registry: "edgy.Registry",
        tenant_models: Dict[str, Type["Model"]],
        schema: str,
        exclude: Union[List[str], None],
    ) -> None:
        for name, model in tenant_models.items():
            if name in exclude:
                continue

            table = self.table_schema(model, schema)

            logger.info(f"Creating table '{model.meta.tablename}' for schema: '{schema}'")
            try:
                async with registry.engine.begin() as connection:
                    await connection.run_sync(table.create)
                await registry.engine.dispose()
            except Exception as e:
                logger.error(str(e))

    async def create_schema(self) -> None:
        await registry.schema.create_schema(self.schema_name)

    async def save(
        self: Any,
        force_save: bool = False,
        values: Dict[str, Any] = None,
        **kwargs: Any,
    ) -> Type[Model]:
        tenant = await super().save(force_save, values, **kwargs)
        try:
            await self.create_schema(schema=tenant.schema_name, if_not_exists=True)
            await self.create_tables(
                registry, registry.models, tenant.schema_name, exclude=["Tenant", "TenantUser"]
            )
        except Exception as e:
            message = f"Rolling back... {str(e)}"
            logger.error(message)
            await self.delete()
        return tenant


class User(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=255)

    class Meta:
        registry = registry


class Product(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=255)
    user: User = edgy.ForeignKey(User, null=True)

    class Meta:
        registry = registry
