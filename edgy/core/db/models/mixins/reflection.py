from typing import TYPE_CHECKING, Any, ClassVar, Optional, Union, cast

import sqlalchemy
from pydantic_core._pydantic_core import SchemaValidator as SchemaValidator

from edgy.core.utils.sync import run_sync
from edgy.exceptions import ImproperlyConfigured

if TYPE_CHECKING:
    from edgy import Registry
    from edgy.core.connection.database import Database


class ReflectedModelMixin:
    """
    Reflect on async engines is not yet supported, therefore, we need to make a sync_engine
    call.
    """

    __reflected__: ClassVar[bool] = True

    @classmethod
    def build(
        cls, schema: Optional[str] = None, metadata: Optional[sqlalchemy.MetaData] = None
    ) -> Any:
        """
        The inspect is done in an async manner and reflects the objects from the database.
        """
        registry = cls.meta.registry
        assert registry, "registry is not set"
        if metadata is None:
            metadata = registry.metadata_by_url[str(cls.database.url)]
        schema_name = schema or cls.get_active_class_schema()

        tablename: str = cast("str", cls.meta.tablename)
        return run_sync(cls.reflect(cls.database, tablename, metadata, schema_name))

    @classmethod
    def fields_not_supported_by_table(
        cls, table: sqlalchemy.Table, check_type: bool = True
    ) -> set[str]:
        """Check if the model fields are a subset of the table."""
        field_names = set()
        for field_name, field in cls.meta.fields.items():
            field_has_typing_check = not field.skip_reflection_type_check and check_type
            for column in cls.meta.field_to_columns[field_name]:
                if (
                    # string not in is not supported by sqlalchemy
                    table.columns.get(column.key) is None
                    or (
                        field_has_typing_check
                        and column.type.as_generic().__class__
                        != table.columns[column.key].type.as_generic().__class__
                    )
                ):
                    field_names.add(field_name)

        return field_names

    @classmethod
    async def reflect(
        cls,
        registry: Union["Registry", "Database"],
        tablename: str,
        metadata: sqlalchemy.MetaData,
        schema: Union[str, None] = None,
    ) -> sqlalchemy.Table:
        """
        Reflect a table from the database and return its SQLAlchemy Table object.

        This method connects to the database using the provided registry, reflects
        the table with the given name and metadata, and returns the SQLAlchemy
        Table object.

        Parameters:
            registry (Registry): The registry object containing the database engine.
            tablename (str): The name of the table to reflect.
            metadata (sqlalchemy.MetaData): The SQLAlchemy MetaData object to associate with the reflected table.
            schema (Union[str, None], optional): The schema name where the table is located. Defaults to None.

        Returns:
            sqlalchemy.Table: The reflected SQLAlchemy Table object.

        Raises:
            ImproperlyConfigured: If there is an error during the reflection process.
        """

        def execute_reflection(connection: sqlalchemy.Connection) -> sqlalchemy.Table:
            """Helper function to create and reflect the table."""
            try:
                return sqlalchemy.Table(
                    tablename, metadata, schema=schema, autoload_with=connection
                )
            except Exception as e:
                raise e

        if hasattr(registry, "database"):
            registry = registry.database
        try:
            async with registry as database:
                table: sqlalchemy.Table = await database.run_sync(execute_reflection)
        except Exception as e:
            raise ImproperlyConfigured(detail=str(e)) from e
        unsupported_fields = cls.fields_not_supported_by_table(table)
        if unsupported_fields:
            raise ImproperlyConfigured(
                "Following fields have columns not matching the table specification:",
                ", ".join(unsupported_fields),
            )

        return table
