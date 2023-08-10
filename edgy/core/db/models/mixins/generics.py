import asyncio
from typing import TYPE_CHECKING, Any, Type, cast

import nest_asyncio
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Mapped, relationship

from edgy.core.connection.registry import Registry

if TYPE_CHECKING:
    from edgy import Model


nest_asyncio.apply()


class DeclarativeMixin(BaseModel):
    """
    Mixin for declarative base models.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    @classmethod
    def declarative(cls) -> Any:
        return cls.generate_model_declarative()

    @classmethod
    def generate_model_declarative(cls) -> Any:
        """
        Transforms a core Edgy table into a Declarative model table.
        """
        Base = cls.meta.registry.declarative_base

        # Build the original table
        fields = {"__table__": cls.table}

        # Generate base
        model_table = type(cls.__name__, (Base,), fields)

        # Make sure if there are foreignkeys, builds the relationships
        for column in cls.table.columns:
            if not column.foreign_keys:
                continue

            # Maps the relationships with the foreign keys and related names
            field = cls.fields.get(column.name)
            mapped_model: Mapped[field.to.__name__] = relationship(field.to.__name__)  # type: ignore

            # Adds to the current model
            model_table.__mapper__.add_property(f"{column.name}_relation", mapped_model)

        return model_table


class TenancyMixin(BaseModel):
    """
    Mixin used for querying a possible multi tenancy application
    """

    # async def has_schema(cls, registry: Registry, schema: str) -> bool:
    #     """
    #     Validates if the schema exists.
    #     """
    #     async with registry.engine.connect() as connection:
    #         return bool(connection.dialect.has_schema(connection, schema)

    @classmethod
    def using(cls, schema: str) -> Type["Model"]:
        """
        Enables and switches the db schema.

        Generates the registry object pointing to the desired schema
        using the same connection.
        """
        asyncio.get_event_loop()

        Registry(database=cls.meta.registry.database, schema=schema)
        # event_loop.run_until_complete(cls.has_schema(registry, schema))
        # self_model = copy.deepcopy(cls)
        # self_model.meta.registry = registry
        return cast("Type[Model]", cls)

    # @classmethod
    # def with_db_connection(cls, database: Database, schema: Optional[str] = None) -> Type["Model"]:
    #     """
    #     Enables and switches to a different database connection and schema.

    #     If no schema is provided, it will default to None and delegates the MetaData
    #     pointer to SQLAlchemy.
    #     """
    #     registry = (
    #         Registry(database=database)
    #         if schema is None
    #         else Registry(database=database, schema="schema")
    #     )

    #     self_model = copy.copy(cls)
    #     self_model.meta.registry = registry
    #     return self_model
