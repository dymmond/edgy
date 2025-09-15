from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, TypeVar, cast

from sqlalchemy import Table

if TYPE_CHECKING:
    from edgy.core.connection.database import Database
    from edgy.core.connection.registry import Registry
    from edgy.core.db.models.base import BaseModelType
    from edgy.core.db.models.model import Model


def get_model(registry: Registry, model_name: str) -> Model:
    """Retrieves a model instance from the registry based on its name.

    This function attempts to fetch a model from the provided registry. The
    `model_name` should be a string representing the name of the model to
    retrieve. The function ensures that the returned object is cast to a `Model`
    type, providing type safety for subsequent operations.

    Args:
        registry ("Registry"): An instance of the registry containing the models.
        model_name (str): The name of the model to retrieve.

    Returns:
        "Model": The retrieved model instance.

    Raises:
        LookupError: If no model with the given `model_name` is found in the
                     registry.
    """
    return cast("Model", registry.get_model(model_name))


def build_pknames(model_class: Any) -> tuple[str, ...]:
    """Constructs a tuple of primary key field names for a given model class.

    This function iterates through the fields of the model's metadata to identify
    which fields are marked as primary keys. It then collects these field names
    into a set to ensure uniqueness and returns them as a sorted tuple. This is
    useful for operations requiring knowledge of the model's primary key
    attributes.

    Args:
        model_class (Any): The model class for which to build primary key names.

    Returns:
        tuple[str, ...]: A sorted tuple containing the names of the primary key
                         fields.
    """
    meta = model_class.meta
    pknames: set[str] = set()
    for field_name, field in meta.fields.items():
        if field.primary_key:
            # Adds the field name to the set if it's a primary key.
            pknames.add(field_name)
    return tuple(sorted(pknames))


def build_pkcolumns(model_class: Any) -> tuple[str, ...]:
    """Constructs a tuple of primary key column names for a given model class.

    This function accesses the underlying SQLAlchemy table object associated with
    the model class and iterates through its columns. It identifies columns
    marked as primary keys and collects their keys (which typically correspond to
    their names in the database) into a set. The unique column keys are then
    returned as a sorted tuple. This is essential for building database queries
    that involve primary key constraints.

    Args:
        model_class (Any): The model class for which to build primary key columns.

    Returns:
        tuple[str, ...]: A sorted tuple containing the names of the primary key
                         columns.
    """
    table = model_class.table
    pkcolumns: set[str] = set()
    for column in table.columns:
        if column.primary_key:
            # The 'key' attribute of a SQLAlchemy Column typically holds its name.
            pkcolumns.add(column.key)
    return tuple(sorted(pkcolumns))


def from_model_to_clauses(model: BaseModelType) -> Iterable[Any]:
    """Generates an iterable of SQLAlchemy equality clauses based on model columns.

    This function creates a series of equality expressions that compare the values
    of specified model columns with their corresponding attributes on the model
    instance. It iterates through `model.columns_for_load`, yielding a SQLAlchemy
    `==` clause for each column, linking the table's column object to the model's
    attribute value. This is typically used for constructing WHERE clauses in
    database queries for retrieving or updating specific model instances.

    Args:
        model ("BaseModelType"): The model instance from which to generate clauses.

    Yields:
        Any: An SQLAlchemy equality clause (e.g., `table.column == model.value`).
    """
    for column in model.columns_for_load:
        # Generates an equality clause for each column.
        yield getattr(model.table.columns, column) == getattr(model, column)


_model_type = TypeVar("_model_type", bound="BaseModelType")


def apply_instance_extras(
    model: _model_type,
    model_class: type[BaseModelType],
    schema: str | None = None,
    database: Database | None = None,
    table: Table | None = None,
) -> _model_type:
    """Applies additional configuration to a model instance before it's used.

    This function is responsible for setting various runtime attributes on a
    model instance, such as its associated schema, database, and table. It
    ensures that the model instance is correctly configured with the necessary
    connections and metadata, especially when dealing with dynamic schemas or
    multiple database connections. If a `table` is explicitly provided, it will
    be used; otherwise, the function will generate a schema-specific table.

    Args:
        model (_model_type): The model instance to which extras will be applied.
        model_class (type["BaseModelType"]): The class of the model instance.
        schema (str | None): The schema name to associate with the model
                              instance. Defaults to None.
        database ("Database" | None): The database instance to associate with the
                                      model. Defaults to None.
        table ("Table" | None): An optional pre-existing SQLAlchemy Table object
                                to associate with the model. Defaults to None.

    Returns:
        _model_type: The modified model instance with applied configurations.
    """
    model.__using_schema__ = schema
    # e.g. table alias. We need to filter it out.
    if table is None or not isinstance(table, Table):
        # If no table is provided, apply the schema to create a new table instance.
        model.table = model_class.table_schema(schema)
    else:
        # Otherwise, use the provided table.
        model.table = table
    if database is not None:
        # If a database is provided, set it on the model instance.
        model.database = database
    return model
