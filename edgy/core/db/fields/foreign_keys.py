from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    cast,
)

import sqlalchemy
from pydantic import BaseModel, SkipValidation

from edgy.core.db.constants import SET_DEFAULT, SET_NULL
from edgy.core.db.context_vars import CURRENT_FIELD_CONTEXT, CURRENT_INSTANCE, CURRENT_PHASE
from edgy.core.db.fields.base import BaseForeignKey
from edgy.core.db.fields.factories import ForeignKeyFieldFactory
from edgy.core.db.fields.types import BaseFieldType
from edgy.core.db.relationships.relation import (
    SingleRelation,
    VirtualCascadeDeletionSingleRelation,
)
from edgy.core.terminal import Print
from edgy.exceptions import FieldDefinitionError
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:
    from edgy.core.db.models.types import BaseModelType


# Character limit for foreign key names in some database engines.
FK_CHAR_LIMIT = 63
# Initialize a terminal printer for warnings.
terminal = Print()


class BaseForeignKeyField(BaseForeignKey):
    """
    Base class for foreign key fields in Edgy models.

    This class extends `BaseForeignKey` to provide comprehensive functionality
    for defining and managing foreign key relationships. It includes support for
    various cascade actions (`on_update`, `on_delete`), related fields,
    constraint handling, embedded parent relationships, and custom relation functions.
    It also manages post-delete callbacks and ensures proper validation.

    Attributes:
        use_model_based_deletion (bool): If `True`, deletion of related instances
                                         will be handled by the model's `raw_delete` method.
                                         Defaults to `False`.
        force_cascade_deletion_relation (bool): If `True`, forces the use of a
                                                `VirtualCascadeDeletionSingleRelation`
                                                regardless of `on_delete` setting.
                                                Defaults to `False`.
        relation_has_post_delete_callback (bool): If `True`, indicates that the
                                                  relation has a post-delete callback.
                                                  Defaults to `False`.
        column_name (str | None): Overwrites the default column name for the foreign key.
                                  Useful for special characters or naming conventions.
                                  Defaults to `None`.
    """

    use_model_based_deletion: bool = False
    force_cascade_deletion_relation: bool = False
    relation_has_post_delete_callback: bool = False
    # allow db overwrite for e.g. sondercharacters
    column_name: str | None = None

    def __init__(
        self,
        *,
        on_update: str,
        on_delete: str,
        related_fields: Sequence[str] = (),
        no_constraint: bool = False,
        embed_parent: tuple[str, str] | None = None,
        relation_fn: Callable[..., ManyRelationProtocol] | None = None,
        reverse_path_fn: Callable[[str], tuple[Any, str, str]] | None = None,
        remove_referenced: bool = False,
        null: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        Initializes a new `BaseForeignKeyField` instance.

        Args:
            on_update (str): The action to perform on update of the referenced key.
                             Common values include "CASCADE", "RESTRICT", "SET NULL", "SET DEFAULT".
            on_delete (str): The action to perform on deletion of the referenced row.
                             Common values include "CASCADE", "RESTRICT", "SET NULL", "SET DEFAULT".
            related_fields (Sequence[str]): A sequence of field names in the target model
                                            that this foreign key references. If empty,
                                            it defaults to the target's primary keys.
            no_constraint (bool): If `True`, no database-level foreign key constraint
                                  will be created. Defaults to `False`.
            embed_parent (tuple[str, str] | None): A tuple specifying how to embed
                                                   the parent in the relation. The first
                                                   element is the attribute name to set on
                                                   the child, and the second is the name
                                                   of the relation from the parent to the child.
            relation_fn (Callable[..., ManyRelationProtocol] | None): A custom function to
                                                                     create the relation object.
            reverse_path_fn (Callable[[str], tuple[Any, str, str]] | None): A custom function
                                                                           to handle reverse path
                                                                           traversal for relationships.
            remove_referenced (bool): If `True`, the referenced object will be
                                      deleted when the referencing object is deleted.
                                      This overrides `on_delete` behavior for the reverse relation.
            null (bool): If `True`, the foreign key column(s) can be null. Defaults to `False`.
            **kwargs (Any): Arbitrary keyword arguments passed to the `BaseForeignKey` constructor.
        """
        self.related_fields = related_fields
        self.on_update = on_update
        self.on_delete = on_delete
        self.no_constraint = no_constraint
        self.embed_parent = embed_parent
        self.relation_fn = relation_fn
        self.reverse_path_fn = reverse_path_fn
        self.remove_referenced = remove_referenced
        # If `remove_referenced` is true, set a specific post-delete callback.
        if remove_referenced:
            self.post_delete_callback = self._notset_post_delete_callback
        super().__init__(**kwargs, null=null)
        # Skip Pydantic validation for foreign keys as Edgy handles extended logic.
        self.metadata.append(SkipValidation())

        # Emit warnings for potentially problematic configurations.
        if self.on_delete == SET_DEFAULT and self.server_default is None:
            terminal.write_warning(
                "Declaring on_delete `SET DEFAULT` but providing no server_default."
            )
        if self.on_delete == SET_NULL and not self.null:
            terminal.write_warning("Declaring on_delete `SET NULL` but null is False.")

    async def _notset_post_delete_callback(self, value: Any) -> None:
        """
        A specific post-delete callback used when `remove_referenced` is `True`.

        This asynchronous method is responsible for deleting the referenced model
        instance when the current model instance (that holds this foreign key)
        is deleted. It expands the relationship to get the actual model instance
        and then calls its `raw_delete` method, skipping post-delete hooks for
        the related model unless specified by `reverse_name`.
        """
        # FIXME: we are stuck on an old version of field before copy, so replace self
        # Retrieve the current field context (workaround for field copy issues).
        self = CURRENT_FIELD_CONTEXT.get()["field"]  # type: ignore
        # Expand the relationship to get the actual related model instance.
        value = self.expand_relationship(value)
        if value is not None:
            # Set the current instance in context for proper hook execution.
            token = CURRENT_INSTANCE.set(value)
            try:
                # Call raw_delete on the related instance.
                await value.raw_delete(
                    skip_post_delete_hooks=False,
                    # `remove_referenced_call` ensures that if this delete was
                    # triggered by a reverse relation, it doesn't cause a loop.
                    remove_referenced_call=self.reverse_name or True,
                )
            finally:
                # Reset the current instance context.
                CURRENT_INSTANCE.reset(token)

    async def pre_save_callback(
        self, value: Any, original_value: Any, is_update: bool
    ) -> dict[str, Any]:
        """
        Callback executed before a model instance containing this field is saved.

        This asynchronous method handles the saving of related model instances
        before the main model is saved. If the `value` is a model instance (or
        a dictionary that can be converted to one), it ensures that the related
        model is saved first to obtain its primary key(s), which are then used
        to populate the foreign key field in the current model.

        Args:
            value (Any): The current value of the foreign key field (can be a model, dict, or ID).
            original_value (Any): The original value of the field before any changes.
            is_update (bool): `True` if the save operation is an update, `False` for an insert.

        Returns:
            dict[str, Any]: A dictionary containing the foreign key's column name(s)
                            and their values to be saved.
        """
        target = self.target
        # If value is None or an empty dict, use original_value.
        if value is None or (isinstance(value, dict) and not value):
            value = original_value

        # If the value is already a target model instance or its proxy.
        if isinstance(value, target | target.proxy_model):
            # Save the related model first to ensure its primary key is available.
            await value.save()
            # Clean the value to extract the foreign key column values.
            return self.clean(self.name, value, for_query=False, hook_call=True)
        # If the value is a dictionary, convert it to a target model instance and
        # recursively call pre_save_callback.
        elif isinstance(value, dict):
            return await self.pre_save_callback(
                target(**value), original_value=None, is_update=is_update
            )
        # If value is None at this point, return an empty dict (nothing to save for FK).
        if value is None:
            return {}
        # Otherwise, return the value as is (assumed to be the FK ID).
        return {self.name: value}

    def get_relation(self, **kwargs: Any) -> ManyRelationProtocol:
        """
        Returns the relation object associated with this foreign key.

        This method determines the type of relation (`SingleRelation` or
        `VirtualCascadeDeletionSingleRelation`) based on the field's properties
        or a custom `relation_fn`. It constructs and returns the appropriate
        relation instance.

        Args:
            **kwargs (Any): Arbitrary keyword arguments to pass to the relation constructor.

        Returns:
            ManyRelationProtocol: The relation object for this foreign key.
        """
        if self.relation_fn is not None:
            return self.relation_fn(**kwargs)

        # also set in db.py
        # Determine the relation class based on `force_cascade_deletion_relation`.
        if self.force_cascade_deletion_relation:
            relation: Any = VirtualCascadeDeletionSingleRelation
        else:
            relation = SingleRelation

        # Cast and return the appropriate relation instance.
        return cast(
            ManyRelationProtocol,
            relation(
                to=self.owner, to_foreign_key=self.name, embed_parent=self.embed_parent, **kwargs
            ),
        )

    def traverse_field(self, path: str) -> tuple[Any, str, str]:
        """
        Traverses the field path from the perspective of the foreign key.

        This method is used during relationship traversal to determine the next
        model, the name of the reverse relation, and the remaining path.

        Args:
            path (str): The full path being traversed.

        Returns:
            tuple[Any, str, str]: A tuple containing:
                                  - The target model of the foreign key.
                                  - The reverse name of the relationship.
                                  - The remaining part of the path after consuming this field.
        """
        # The target of the foreign key.
        # The reverse name of the relationship on the target model.
        # The remaining path after stripping the current field's name.
        return self.target, self.reverse_name, path.removeprefix(self.name).removeprefix("__")

    def reverse_traverse_field(self, path: str) -> tuple[Any, str, str]:
        """
        Traverses the field path in reverse (from the related model back to the owner).

        This method is used for reverse relationship traversal. If a custom
        `reverse_path_fn` is provided, it uses that. Otherwise, it defaults
        to returning the owner model, the foreign key's name, and the remaining
        path after stripping the reverse name.

        Args:
            path (str): The full path being traversed in reverse.

        Returns:
            tuple[Any, str, str]: A tuple containing:
                                  - The owner model of the foreign key.
                                  - The name of the foreign key field.
                                  - The remaining part of the path after consuming the reverse name.
        """
        if self.reverse_path_fn:
            return self.reverse_path_fn(path)
        # The owner model of the foreign key.
        # The name of the foreign key field itself.
        # The remaining path after stripping the reverse name.
        return self.owner, self.name, path.removeprefix(self.reverse_name).removeprefix("__")

    @cached_property
    def related_columns(self) -> dict[str, sqlalchemy.Column | None]:
        """
        Returns a dictionary of related columns in the target model that this
        foreign key references.

        This property is cached for performance. It identifies which columns
        in the target model correspond to this foreign key. If `related_fields`
        are explicitly defined, it uses those. Otherwise, it attempts to use
        the target model's primary key columns.
        """
        target = self.target
        columns: dict[str, sqlalchemy.Column | None] = {}
        if self.related_fields:
            # If specific related fields are defined, use their corresponding columns.
            for field_name in self.related_fields:
                if field_name in target.meta.fields:
                    for column in target.meta.field_to_columns[field_name]:
                        columns[column.key] = column
                else:
                    # If field_name is not directly in fields, it's a placeholder for extraction.
                    columns[field_name] = None
        else:
            # If no specific related fields, try to use the target's primary keys.
            if target.pknames:
                for pkname in target.pknames:
                    for column in target.meta.field_to_columns[pkname]:
                        columns[column.key] = column
            elif target.pkcolumns:
                # If only pkcolumns are known, create placeholders.
                # WARNING: This might lead to recursive loops if not handled carefully in usage.
                columns = dict.fromkeys(target.pkcolumns)
        return columns

    def expand_relationship(self, value: Any) -> Any:
        """
        Expands a simple foreign key value (like an ID) into a target model
        instance (or its proxy model).

        This method is crucial for converting raw foreign key values back into
        full model instances, which is necessary for operations like deletion or
        complex relationship handling. It handles cases where the value is already
        a model instance, a dictionary, or a single scalar ID.

        Args:
            value (Any): The value representing the foreign key, which can be `None`,
                         a scalar (ID), a dictionary of related column values,
                         or an existing target model instance.

        Returns:
            Any: A target model instance (or its proxy) with the identified database
                 fields set, or `None` if the input value is `None` or corresponds
                 to a null relationship.
        """
        if value is None:
            return None
        target = self.target
        related_columns = self.related_columns.keys()

        # If value is already a target model instance or its proxy.
        if isinstance(value, target | target.proxy_model):
            # If all related columns are set to None in the instance, return None.
            if all(
                key in value.__dict__ and getattr(value, key) is None for key in related_columns
            ):
                return None
            return value

        # If there's only one related column and the value is not a dict/BaseModel.
        if len(related_columns) == 1 and not isinstance(value, dict | BaseModel):
            # Convert the scalar value into a dictionary for the single related column.
            value = {next(iter(related_columns)): value}
        # If value is a BaseModel, extract related column values into a dictionary.
        elif isinstance(value, BaseModel):
            return self.expand_relationship({col: getattr(value, col) for col in related_columns})

        # Create a proxy model instance from the value.
        instance = target.proxy_model(**value)
        # Set identifying_db_fields for the proxy model for efficient querying.
        instance.identifying_db_fields = related_columns
        return instance

    def clean(
        self, name: str, value: Any, for_query: bool = False, hook_call: bool = False
    ) -> dict[str, Any]:
        """
        Validates and transforms the foreign key value into a dictionary of
        column-value pairs suitable for database operations.

        This method handles different input types for the foreign key, including
        `None`, dictionaries, and target model instances. It extracts the
        appropriate foreign key values that correspond to the actual database
        columns.

        Args:
            name (str): The name of the foreign key field in the model.
            value (Any): The input value for the foreign key. Can be `None`,
                         a dictionary (for composite keys), a target model instance,
                         or a scalar (for single-column FKs).
            for_query (bool): If `True`, the cleaning is for a query operation.
                              Defaults to `False`.
            hook_call (bool): If `True`, indicates that this call is from a hook.
                              Defaults to `False`.

        Returns:
            dict[str, Any]: A dictionary where keys are the foreign key column names
                            and values are their corresponding data.

        Raises:
            ValueError: If the value type cannot be handled for a composite foreign key.
        """
        retdict: dict[str, Any] = {}
        target = self.target
        phase = CURRENT_PHASE.get()
        column_names = self.owner.meta.field_to_column_names[name]
        assert len(column_names) >= 1

        if value is None:
            # If value is None, set all foreign key columns to None.
            for column_name in column_names:
                retdict[column_name] = None
        elif isinstance(value, dict):
            # If value is a dictionary (for composite FKs), map dict keys to column names.
            for column_name in column_names:
                translated_name = self.from_fk_field_name(name, column_name)
                if translated_name in value:
                    retdict[column_name] = value[translated_name]
        elif isinstance(value, target | target.proxy_model):
            # If value is a target model instance, extract attribute values.
            for column_name in column_names:
                translated_name = self.from_fk_field_name(name, column_name)
                if hasattr(value, translated_name):
                    retdict[column_name] = getattr(value, translated_name)
                # If not all values are specified and it's a pre-save hook, return the model itself.
                elif phase in {"prepare_insert", "prepare_update"} and not hook_call:
                    return {name: value}
        elif len(column_names) == 1:
            # If it's a single-column FK, directly assign the scalar value.
            column_name = next(iter(column_names))
            retdict[column_name] = value
        else:
            # Raise an error for unhandled value types with composite keys.
            raise ValueError(f"cannot handle: {value} of type {type(value)}")
        return retdict

    def reverse_clean(self, name: str, value: Any, for_query: bool = False) -> dict[str, Any]:
        """
        Cleans the value for a reverse relationship, primarily for query purposes.

        This method is used when processing values from the "other" side of a
        relationship (the one where this foreign key is the `Many` side).
        It's mainly relevant for query building.

        Args:
            name (str): The name of the field on the related model.
            value (Any): The input value for the reverse field.
            for_query (bool): If `True`, the cleaning is for a query. Defaults to `False`.

        Returns:
            dict[str, Any]: A dictionary of column-value pairs for the reverse relationship.

        Raises:
            ValueError: If the value type cannot be handled for a composite foreign key.
        """
        # For non-query operations, return an empty dictionary.
        if not for_query:
            return {}
        retdict: dict[str, Any] = {}
        column_names = self.owner.meta.field_to_column_names[self.name]
        assert len(column_names) >= 1

        if value is None:
            for column_name in column_names:
                retdict[self.from_fk_field_name(name, column_name)] = None
        elif isinstance(value, dict):
            for column_name in column_names:
                translated_name = self.from_fk_field_name(name, column_name)
                if translated_name in value:
                    retdict[translated_name] = value[translated_name]
        elif isinstance(value, BaseModel):
            for column_name in column_names:
                translated_name = self.from_fk_field_name(name, column_name)
                if hasattr(value, translated_name):
                    retdict[translated_name] = getattr(value, translated_name)
        elif len(column_names) == 1:
            translated_name = self.from_fk_field_name(name, next(iter(column_names)))
            retdict[translated_name] = value
        else:
            raise ValueError(f"cannot handle: {value} of type {type(value)}")
        return retdict

    def modify_input(self, name: str, kwargs: dict[str, Any]) -> None:
        """
        Modifies the input `kwargs` for a foreign key field, especially for
        composite foreign keys.

        This method ensures that if a composite foreign key's individual column
        values are provided directly in `kwargs`, they are grouped under the
        main foreign key `name` as a dictionary, facilitating consistent handling.
        It also handles default values during load/insert/update phases.

        Args:
            name (str): The name of the foreign key field.
            kwargs (dict[str, Any]): The dictionary of keyword arguments to modify.

        Raises:
            ValueError: If only a partial update for a composite foreign key is attempted.
        """
        phase = CURRENT_PHASE.get()
        column_names = self.get_column_names(name)
        assert len(column_names) >= 1

        if len(column_names) == 1:
            # For single-column FKs, set default to None if not explicitly present
            # during load/insert/update phases.
            if phase in {"post_insert", "post_update", "load"}:
                kwargs.setdefault(name, None)
            return

        to_add: dict[str, Any] = {}
        # Iterate through column names to find and move them to `to_add`.
        for column_name in column_names:
            if column_name in kwargs:
                to_add[self.from_fk_field_name(name, column_name)] = kwargs.pop(column_name)
        # empty path
        # If no individual columns were found, handle default behavior.
        if not to_add:
            # fake default
            if phase in {"post_insert", "post_update", "load"}:
                kwargs.setdefault(name, None)
            return

        # If the main field name is already in kwargs (e.g., set to a model), return.
        if name in kwargs:
            return

        # If individual columns were provided but not all for a composite FK, raise an error.
        if len(column_names) != len(to_add):
            raise ValueError("Cannot update the foreign key partially")
        # Assign the consolidated dictionary to the main field name.
        kwargs[name] = to_add

    def get_fk_name(self, name: str) -> str:
        """
        Generates a unique foreign key name for the database engine, adhering
        to character limits.

        This ensures that generated foreign key names are compatible with
        database systems that have naming conventions or length restrictions.

        Args:
            name (str): The name of the foreign key field in the model.

        Returns:
            str: The truncated and prefixed foreign key name.
        """
        fk_name = f"{self.owner.meta.tablename}_{self.target.meta.tablename}_{name}"
        fk_name = f"fk_{fk_name}"
        return fk_name[:FK_CHAR_LIMIT]

    def get_fkindex_name(self, name: str) -> str:
        """
        Generates a unique foreign key index name for the database engine, adhering
        to character limits.

        Similar to `get_fk_name`, this function ensures that the index name
        is compatible with database naming conventions and length restrictions.

        Args:
            name (str): The name of the foreign key field in the model.

        Returns:
            str: The truncated and prefixed foreign key index name.
        """
        fk_name = f"{self.owner.meta.tablename}_{self.target.meta.tablename}_{name}"
        fk_name = f"fkindex_{fk_name}"
        return fk_name[:FK_CHAR_LIMIT]

    def get_fk_field_name(self, name: str, fieldname: str) -> str:
        """
        Constructs the field name used for representing a foreign key component.

        For single-column foreign keys, it simply returns the main `name`.
        For composite foreign keys, it combines the main `name` with the
        component `fieldname`.

        Args:
            name (str): The main name of the foreign key field.
            fieldname (str): The specific name of the related field in the target model.

        Returns:
            str: The constructed field name for the foreign key component.
        """
        if len(self.related_columns) == 1:
            return name
        return f"{name}_{fieldname}"

    def get_fk_column_name(self, name: str, fieldname: str) -> str:
        """
        Constructs the actual database column name for a foreign key component.

        It uses the `column_name` attribute if set, otherwise the `name`.
        For composite foreign keys, it combines this with the related column's name.

        Args:
            name (str): The main name of the foreign key field.
            fieldname (str): The specific name of the related column in the target model.

        Returns:
            str: The constructed database column name for the foreign key component.
        """
        name = self.column_name or name
        if len(self.related_columns) == 1:
            return name
        return f"{name}_{fieldname}"

    def from_fk_field_name(self, name: str, fieldname: str) -> str:
        """
        Converts a foreign key's column name back to the corresponding target
        model's field name.

        For single-column foreign keys, it returns the key of the single related
        column. For composite keys, it strips the foreign key field's prefix.

        Args:
            name (str): The main name of the foreign key field.
            fieldname (str): The database column name of the foreign key component.

        Returns:
            str: The corresponding field name in the target model.
        """
        if len(self.related_columns) == 1:
            return next(iter(self.related_columns.keys()))
        return fieldname.removeprefix(f"{name}_")

    def get_columns(self, name: str) -> Sequence[sqlalchemy.Column]:
        """
        Generates the SQLAlchemy Column objects for the foreign key field(s).

        This method defines how the foreign key maps to actual database columns.
        It creates one or more `sqlalchemy.Column` instances, mirroring the
        type, nullability, and uniqueness of the referenced columns in the
        target model.

        Args:
            name (str): The name of the foreign key field in the model.

        Returns:
            Sequence[sqlalchemy.Column]: A sequence of SQLAlchemy Column objects
                                         representing the foreign key.
        """
        target = self.target
        columns: list[sqlalchemy.Column] = []
        nullable = self.get_columns_nullable()  # Determine base nullability for FK columns.

        # Iterate through related columns to create corresponding FK columns.
        for column_key, related_column in self.related_columns.items():
            if related_column is None:
                # If related_column is None (placeholder), retrieve it from the target's table.
                related_column = target.table.columns[column_key]

            # Construct the foreign key column's field name.
            fkcolumn_name = self.get_fk_field_name(name, column_key)
            # Create the SQLAlchemy Column for the foreign key.
            fkcolumn = sqlalchemy.Column(
                key=fkcolumn_name,
                type_=related_column.type,  # Inherit type from the related column.
                name=self.get_fk_column_name(name, related_column.name),  # DB column name.
                primary_key=self.primary_key,  # Inherit primary key status.
                autoincrement=False,  # FKs cannot autoincrement.
                # Nullability is OR of related column's nullability and field's nullability.
                nullable=related_column.nullable or nullable,
                unique=related_column.unique,  # Inherit uniqueness.
            )
            columns.append(fkcolumn)
        return columns

    def get_global_constraints(
        self,
        name: str,
        columns: Sequence[sqlalchemy.Column],
        schemes: Sequence[str] = (),
        no_constraint: bool | None = None,
    ) -> Sequence[sqlalchemy.Constraint | sqlalchemy.Index]:
        """
        Generates global database constraints (Foreign Key Constraint and Index)
        for this foreign key.

        This method creates the actual `ForeignKeyConstraint` and optionally an
        `Index` object, which are added to the SQLAlchemy table metadata.
        It respects the `no_constraint` setting and handles cross-database
        relationships.

        Args:
            name (str): The name of the foreign key field.
            columns (Sequence[sqlalchemy.Column]): The SQLAlchemy Column objects
                                                  representing the foreign key.
            schemes (Sequence[str]): A sequence of schema names to consider for
                                     the target table. Defaults to empty.
            no_constraint (bool | None): Overrides the `no_constraint` setting
                                         for this specific call. Defaults to `None`.

        Returns:
            Sequence[sqlalchemy.Constraint | sqlalchemy.Index]: A sequence of
                                                                SQLAlchemy constraint
                                                                and/or index objects.
        """
        constraints: list[sqlalchemy.Constraint | sqlalchemy.Index] = []
        # Determine if a database constraint should be created.
        no_constraint = bool(
            no_constraint
            or self.no_constraint
            or self.owner.meta.registry is not self.target.meta.registry
            or self.owner.database is not self.target.database
        )

        if not no_constraint:
            target = self.target
            assert not target.__is_proxy_model__  # Ensure it's not a proxy model.

            prefix = ""
            # Determine the correct table prefix for the foreign key reference.
            for schema in schemes:
                prefix = f"{schema}.{target.meta.tablename}" if schema else target.meta.tablename
                if prefix in target.meta.registry.metadata_by_url[str(target.database.url)].tables:
                    break

            # Add the SQLAlchemy ForeignKeyConstraint.
            constraints.append(
                sqlalchemy.ForeignKeyConstraint(
                    columns,  # Local columns.
                    [
                        f"{prefix}.{self.from_fk_field_name(name, column.key)}"
                        for column in columns
                    ],  # Remote columns.
                    ondelete=self.on_delete,
                    onupdate=self.on_update,
                    name=self.get_fk_name(name),  # Generated FK name.
                ),
            )

        # Add an index if `unique` or `index` is True.
        if self.unique or self.index:
            constraints.append(
                sqlalchemy.Index(
                    self.get_fkindex_name(name),  # Generated index name.
                    *columns,  # Columns to index.
                    unique=self.unique,  # Ensure uniqueness if specified.
                ),
            )
        return constraints


class ForeignKey(ForeignKeyFieldFactory, cast(Any, object)):
    """
    A factory for creating `ForeignKey` fields in Edgy models.

    This factory extends `ForeignKeyFieldFactory` to provide a convenient
    interface for defining foreign key relationships. It ensures that specific
    server-side default and update operations are not mistakenly applied to
    foreign key fields, and validates the `embed_parent` configuration.
    """

    field_bases: tuple = (BaseForeignKeyField,)  # The base concrete field class.
    field_type: Any = Any  # The Pydantic type, typically `Any`.

    def __new__(
        cls,
        to: type[BaseModelType] | str,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Creates a new `ForeignKey` field instance.

        This method primarily passes the `to` argument (target model) and other
        `kwargs` to the parent `ForeignKeyFieldFactory` for field construction.

        Args:
            to (type[BaseModelType] | str): The target model class or its string name
                                          to which this foreign key points.
            **kwargs (Any): Additional keyword arguments for the foreign key field.

        Returns:
            BaseFieldType: The constructed `ForeignKey` field instance.
        """
        return super().__new__(cls, to=to, **kwargs)

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Validates the parameters for a `ForeignKey` field.

        This method overrides the parent `validate` method to enforce rules
        specific to foreign keys. It explicitly disallows `auto_compute_server_default`,
        `server_default`, and `server_onupdate` to prevent issues with relational
        integrity. It also validates the format of the `embed_parent` argument.

        Args:
            kwargs (dict[str, Any]): The dictionary of keyword arguments passed
                                     during field construction.

        Raises:
            FieldDefinitionError: If any validation rule is violated.
        """
        super().validate(kwargs)
        # Disallow auto_compute_server_default for ForeignKeys.
        if kwargs.get("auto_compute_server_default"):
            raise FieldDefinitionError(
                '"auto_compute_server_default" is not supported for ForeignKey.'
            ) from None
        kwargs["auto_compute_server_default"] = False  # Explicitly set to False.
        # Disallow server_default for ForeignKeys.
        if kwargs.get("server_default"):
            raise FieldDefinitionError(
                '"server_default" is not supported for ForeignKey.'
            ) from None
        # Disallow server_onupdate for ForeignKeys.
        if kwargs.get("server_onupdate"):
            raise FieldDefinitionError(
                '"server_onupdate" is not supported for ForeignKey.'
            ) from None
        # Validate embed_parent argument format.
        embed_parent = kwargs.get("embed_parent")
        if embed_parent and "__" in embed_parent[1]:
            raise FieldDefinitionError(
                '"embed_parent" second argument (for embedding parent) cannot contain "__".'
            )
