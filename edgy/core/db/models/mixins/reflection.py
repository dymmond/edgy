from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

import sqlalchemy

from edgy.core.utils.sync import run_sync
from edgy.exceptions import ImproperlyConfigured

if TYPE_CHECKING:
    from edgy import Registry
    from edgy.core.connection.database import Database
    from edgy.core.db.models.types import BaseModelType


class ReflectedModelMixin:
    """
    A mixin class providing functionality for reflecting database tables into Edgy models.

    This mixin enables Edgy models to dynamically inspect and load their schema
    from an existing database table. It handles the complexities of asynchronous
    database operations for reflection and ensures that the reflected table's
    structure aligns with the model's field definitions.

    Reflection on async engines is not directly supported by SQLAlchemy,
    hence this mixin facilitates a synchronous reflection process wrapped
    for asynchronous execution.
    """

    __reflected__: ClassVar[bool] = True
    """
    A class variable indicating that this model is designed to be reflected
    from an existing database schema.
    """

    @classmethod
    def real_add_to_registry(cls: type[BaseModelType], **kwargs: Any) -> type[BaseModelType]:
        """
        Adds the reflected model to the Edgy registry with specific configurations.

        This class method overrides the default `real_add_to_registry` behavior
        to ensure that reflected models are correctly identified within the registry.
        It sets a default `registry_type_name` to "reflected" for proper categorization.

        Args:
            cls: The class (Edgy model) being added to the registry.
            **kwargs: Arbitrary keyword arguments passed to the superclass's
                      `real_add_to_registry` method.

        Returns:
            The class (Edgy model) after being added to the registry.
        """
        # Set the registry type name to 'reflected' if not already specified.
        kwargs.setdefault("registry_type_name", "reflected")
        # Call the superclass method to complete the registration process.
        return cast(type["BaseModelType"], super().real_add_to_registry(**kwargs))

    @classmethod
    def build(
        cls: type[BaseModelType],
        schema: str | None = None,
        metadata: sqlalchemy.MetaData | None = None,
    ) -> Any:
        """
        Builds the reflected model by inspecting the database.

        This method orchestrates the reflection process. It retrieves the appropriate
        SQLAlchemy `MetaData` object and schema name, then initiates the asynchronous
        reflection of the database table. The reflection process dynamically
        populates the model's underlying SQLAlchemy `Table` object based on the
        database schema.

        Args:
            cls: The Edgy model class for which to build the reflected table.
            schema: An optional string specifying the database schema to reflect from.
                    If `None`, the active class schema will be used.
            metadata: An optional SQLAlchemy `MetaData` object to use for reflection.
                      If `None`, it will be retrieved from the registry based on the
                      database URL.

        Returns:
            Any: The SQLAlchemy `Table` object representing the reflected database table.
        """
        registry = cls.meta.registry
        # Assert that the registry is set, as it's essential for reflection.
        assert registry, "registry is not set"

        # If no metadata is provided, retrieve it from the registry based on the database URL.
        if metadata is None:
            metadata = registry.metadata_by_url[str(cls.database.url)]

        # Determine the schema name to use for reflection.
        schema_name = schema or cls.get_active_class_schema()

        # Cast the tablename to a string, ensuring it's properly typed for reflection.
        tablename: str = cls.meta.tablename

        # Execute the asynchronous reflection process synchronously using `run_sync`.
        return run_sync(cls.reflect(cls.database, tablename, metadata, schema_name))

    @classmethod
    def fields_not_supported_by_table(
        cls: type[BaseModelType], table: sqlalchemy.Table, check_type: bool = True
    ) -> set[str]:
        """
        Checks if the model's fields are a valid subset of the reflected database table's columns.

        This method compares the field definitions in the Edgy model with the columns
        found in the reflected SQLAlchemy `Table`. It identifies any model fields
        that do not have a corresponding column in the table or whose column type
        does not match, based on the `check_type` flag.

        Args:
            cls: The Edgy model class whose fields are to be checked.
            table: The SQLAlchemy `Table` object that has been reflected from the database.
            check_type: A boolean flag indicating whether to perform a type comparison
                        between model fields and table columns. If `True`, fields with
                        mismatched types will be considered unsupported.

        Returns:
            A `set` of strings, where each string is the name of an Edgy model field
            that is not supported by the reflected table (either missing or type mismatch).
        """
        field_names: set[str] = set()
        # Iterate through each field defined in the Edgy model's metadata.
        for field_name, field in cls.meta.fields.items():
            # Determine if type checking should be performed for the current field.
            field_has_typing_check = not field.skip_reflection_type_check and check_type
            # Iterate through the SQLAlchemy columns associated with the current Edgy field.
            for column in cls.meta.field_to_columns[field_name]:
                # Check for two conditions that make a field unsupported:
                # 1. The column does not exist in the reflected table.
                # 2. Type checking is enabled, and the generic types of the field's column
                #    and the table's column do not match.
                if table.columns.get(column.key) is None or (
                    field_has_typing_check
                    and column.type.as_generic().__class__
                    != table.columns[column.key].type.as_generic().__class__
                ):
                    field_names.add(field_name)
        return field_names

    @classmethod
    async def reflect(
        cls: type[BaseModelType],
        registry: Registry | Database,
        tablename: str,
        metadata: sqlalchemy.MetaData,
        schema: str | None = None,
    ) -> sqlalchemy.Table:
        """
        Reflects a table from the database and returns its SQLAlchemy Table object.

        This asynchronous method establishes a connection to the database,
        then uses SQLAlchemy's reflection capabilities to load the table's
        schema definition from the database. It handles potential errors during
        the reflection process and performs a final validation to ensure the
        reflected table's structure is compatible with the Edgy model's fields.

        Args:
            cls: The Edgy model class initiating the reflection.
            registry: The registry object or database instance containing the
                      database engine connection.
            tablename: The name of the table to reflect from the database.
            metadata: The SQLAlchemy `MetaData` object to associate with the
                      reflected table.
            schema: An optional string specifying the schema name where the table
                    is located. Defaults to `None`.

        Returns:
            sqlalchemy.Table: The reflected SQLAlchemy `Table` object.

        Raises:
            ImproperlyConfigured: If there is an error during the reflection process
                                  or if the reflected table's columns do not match
                                  the model's field specifications.
        """

        def execute_reflection(connection: sqlalchemy.Connection) -> sqlalchemy.Table:
            """
            Helper function to create and reflect the table within a synchronous context.

            This nested function is executed synchronously by `database.run_sync`.
            It attempts to reflect the table using `sqlalchemy.Table` with `autoload_with`.

            Args:
                connection: The SQLAlchemy `Connection` object to the database.

            Returns:
                sqlalchemy.Table: The reflected SQLAlchemy `Table` object.

            Raises:
                Exception: Any exception raised during the table reflection process.
            """
            try:
                # Attempt to reflect the table from the database using the provided connection.
                return sqlalchemy.Table(
                    tablename, metadata, schema=schema, autoload_with=connection
                )
            except Exception as e:
                # Re-raise any exception encountered during reflection.
                raise e

        # If `registry` is a `Registry` object, extract its `database` attribute.
        if hasattr(registry, "database"):
            registry = registry.database

        try:
            # Establish an asynchronous database connection.
            async with registry as database:
                # Execute the synchronous reflection helper function within the
                # asynchronous context using `database.run_sync`.
                table: sqlalchemy.Table = await database.run_sync(execute_reflection)
        except Exception as e:
            # Catch any exceptions during the database connection or reflection
            # and re-raise as an `ImproperlyConfigured` error.
            raise ImproperlyConfigured(detail=str(e)) from e

        # After successful reflection, validate that the reflected table's columns
        # are compatible with the model's field definitions.
        unsupported_fields = cls.fields_not_supported_by_table(table)
        if unsupported_fields:
            # If any unsupported fields are found, raise an `ImproperlyConfigured` error.
            raise ImproperlyConfigured(
                "Following fields have columns not matching the table specification: "
                f"{', '.join(unsupported_fields)}"
            )

        # Return the successfully reflected SQLAlchemy Table object.
        return table
