from __future__ import annotations

import inspect
import sys
from collections.abc import Callable, Generator
from typing import Any, NoReturn

import sqlalchemy
from loguru import logger
from monkay import load
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import schema, sqltypes

import edgy
from edgy import Database, run_sync

# Mapping of SQLAlchemy generic types to their corresponding Edgy field types.
# This dictionary is crucial for translating database schema types into
# Edgy model field definitions during database inspection.
SQL_GENERIC_TYPES: dict[type, str] = {
    sqltypes.BigInteger: "edgy.core.db.fields.BigIntegerField",
    sqltypes.Integer: "edgy.core.db.fields.IntegerField",
    sqltypes.JSON: "edgy.core.db.fields.JSONField",
    sqltypes.Date: "edgy.core.db.fields.DateField",
    sqltypes.String: "edgy.core.db.fields.CharField",
    sqltypes.Unicode: "edgy.core.db.fields.CharField",
    sqltypes.LargeBinary: "edgy.core.db.fields.BinaryField",
    sqltypes.Boolean: "edgy.core.db.fields.BooleanField",
    sqltypes.Enum: "edgy.core.db.fields.ChoiceField",
    sqltypes.DateTime: "edgy.core.db.fields.DateTimeField",
    sqltypes.Interval: "edgy.core.db.fields.DurationField",
    sqltypes.Numeric: "edgy.core.db.fields.DecimalField",
    sqltypes.Float: "edgy.core.db.fields.FloatField",
    sqltypes.Double: "edgy.core.db.fields.FloatField",
    sqltypes.SmallInteger: "edgy.core.db.fields.SmallIntegerField",
    sqltypes.Text: "edgy.core.db.fields.TextField",
    sqltypes.Time: "edgy.core.db.fields.TimeField",
    sqltypes.Uuid: "edgy.core.db.fields.UUIDField",
    sqlalchemy.ARRAY: "edgy.core.db.fields.PGArrayField",
}

# The root module name for Edgy, used for imports in the generated code.
DB_MODULE = "edgy"


def func_accepts_kwargs(func: Callable) -> bool:
    """
    Checks if a given callable function or method accepts arbitrary keyword arguments (`**kwargs`).

    This is determined by inspecting the function's signature for a parameter
    of kind `VAR_KEYWORD`.

    Args:
        func (Callable): The function or method to inspect.

    Returns:
        bool: `True` if the function accepts `**kwargs`, `False` otherwise.
    """
    return any(
        param
        for param in inspect.signature(func).parameters.values()
        if param.kind == param.VAR_KEYWORD
    )


class RawRepr:
    """
    A helper class to ensure that its string representation in f-strings
    or `repr()` is exactly the input string, without additional quotes.
    This is useful for injecting raw code snippets into generated output.
    """

    def __init__(self, inp: str) -> None:
        """
        Initializes a RawRepr instance.

        Args:
            inp (str): The string that should be represented as raw.
        """
        self.inp = inp

    def __repr__(self) -> str:
        """
        Returns the raw input string.
        """
        return self.inp


class InspectDB:
    """
    Class responsible for inspecting an existing database schema and
    generating corresponding Edgy `ReflectModel` definitions.

    It connects to the specified database, reflects its tables, columns,
    foreign keys, indexes, and constraints, and then outputs Python code
    representing these as Edgy models.
    """

    def __init__(self, database: str, schema: str | None = None) -> None:
        """
        Initializes an `InspectDB` instance.

        Args:
            database (str): The database connection string (URL).
            schema (str | None, optional): The specific database schema to inspect.
                                           If `None`, the default schema is used.
                                           Defaults to `None`.
        """
        self.database = Database(database)
        self.schema = schema or None

    @staticmethod
    async def reflect(
        *, database: Database, metadata: sqlalchemy.MetaData, **kwargs: Any
    ) -> sqlalchemy.MetaData:
        """
        Connects to the database and reflects all schema information into a
        SQLAlchemy `MetaData` object.

        This is a wrapper around `sqlalchemy.MetaData.reflect` that includes
        logging for better user feedback.

        Args:
            database (Database): The Edgy `Database` instance to connect to.
            metadata (sqlalchemy.MetaData): The SQLAlchemy `MetaData` object
                                           to reflect the schema into.
            **kwargs (Any): Additional keyword arguments to pass directly to
                            `metadata.reflect()`.

        Returns:
            sqlalchemy.MetaData: The `MetaData` object populated with reflected schema.

        Note:
            If you need to suppress the logger output, you can directly call
            `await database.run_sync(metadata.reflect, **kwargs)`.
        """
        logger.info("Collecting database tables information...")
        await database.run_sync(metadata.reflect, **kwargs)
        return metadata

    async def _inspect(self) -> None:
        """
        The asynchronous core logic for database inspection.
        It connects, reflects, processes, and writes the output.
        """
        async with self.database as database:
            # Initialize SQLAlchemy MetaData, optionally with a specific schema.
            metadata: sqlalchemy.MetaData = sqlalchemy.MetaData(schema=self.schema)
            # Reflect the database schema.
            metadata = await self.reflect(database=database, metadata=metadata, schema=self.schema)

            # Generate structured information about the tables.
            tables, _ = self.generate_table_information(metadata)

            # Write the generated Edgy model code to standard output.
            for line in self.write_output(tables, database, schema=self.schema):
                sys.stdout.writelines(line)

    def inspect(self) -> None:
        """
        Synchronously starts the database inspection process.
        This is the main entry point for the `InspectDB` class.
        """
        run_sync(self._inspect())

    @classmethod
    def generate_table_information(
        cls, metadata: sqlalchemy.MetaData
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """
        Generates a structured list of dictionaries, each containing detailed
        information about a reflected database table.

        Args:
            metadata (sqlalchemy.MetaData): The SQLAlchemy `MetaData` object
                                           containing the reflected database schema.

        Returns:
            tuple[list[dict[str, Any]], dict[str, str]]:
            -   A list of dictionaries, where each dictionary represents a table
                and its properties (tablename, class_name, foreign_keys, indexes, constraints).
            -   A dictionary mapping SQLAlchemy table keys to generated model class names.
        """
        tables = []
        models: dict[str, str] = {}  # To store mapping of table key to model class name.

        for key, table in metadata.tables.items():
            table_details: dict[str, Any] = {}
            # Extract tablename, handling schema prefixes if present.
            table_name = table_details["tablename"] = key.rsplit(".", 1)[-1]

            models[key] = table_details["class_name"] = (
                table_name.replace("_", "").replace(".", "").capitalize()
            )
            table_details["class"] = None  # Placeholder for the actual class object.
            table_details["table"] = table  # Reference to the SQLAlchemy Table object.
            # Get details for foreign keys, indexes, and constraints.
            table_details["foreign_keys"] = cls.get_foreign_keys(table)
            table_details["indexes"] = table.indexes
            table_details["constraints"] = table.constraints
            tables.append(table_details)

        return tables, models

    @classmethod
    def get_foreign_keys(
        cls, table_or_column: sqlalchemy.Table | sqlalchemy.Column
    ) -> list[dict[str, Any]]:
        """
        Extracts and formats information about foreign keys associated with
        a given SQLAlchemy `Table` or `Column`.

        Args:
            table_or_column (sqlalchemy.Table | sqlalchemy.Column): The SQLAlchemy
                                                                  Table or Column object to inspect.

        Returns:
            list[dict[str, Any]]: A list of dictionaries, where each dictionary
                                  describes a foreign key relationship (column,
                                  column_name, tablename, class_name, on_delete, on_update).
        """
        details: list[dict[str, Any]] = []

        # Iterate through the foreign keys collection.
        for foreign_key in table_or_column.foreign_keys:
            fk: dict[str, Any] = {}
            fk["column"] = foreign_key.column  # The target Column object.
            fk["column_name"] = foreign_key.column.name  # Name of the target column.
            fk["tablename"] = foreign_key.column.table.name  # Name of the target table.
            fk["class_name"] = (
                foreign_key.column.table.name.replace("_", "").replace(".", "").capitalize()
            )
            fk["on_delete"] = foreign_key.ondelete  # ON DELETE action.
            fk["on_update"] = foreign_key.onupdate  # ON UPDATE action.
            details.append(fk)

        return details

    @classmethod
    def get_field_type(
        self, column: sqlalchemy.Column, database: edgy.Database, is_fk: bool = False
    ) -> tuple[str, dict[str, Any]]:
        """
        Determines the appropriate Edgy field type and its parameters for a given
        SQLAlchemy column.

        Args:
            column (sqlalchemy.Column): The SQLAlchemy column to convert.
            database (databasez.core.database.Database): The database used for inspection.
            is_fk (bool, optional): A flag indicating if the column is part of a
                                    foreign key relationship. If `True`, it will
                                    return "ForeignKey" or "OneToOne". Defaults to `False`.

        Returns:
            tuple[str, dict[str, Any]]: A tuple containing:
            -   The string name of the Edgy field type (e.g., "CharField", "IntegerField").
            -   A dictionary of parameters specific to that Edgy field type.
        """
        # If it's a foreign key, return "ForeignKey" or "OneToOne" based on uniqueness.
        if is_fk:
            return "ForeignKey" if not column.unique else "OneToOne", {}

        field_type: str
        field_params: dict[str, Any] = {}

        try:
            # Get the generic SQLAlchemy type.
            real_field: Any = column.type.as_generic()
        except Exception:
            # Fallback if generic type conversion fails.
            logger.info(
                f"Unable to understand the field type for `{column.type}`, defaulting to TextField."
            )
            real_field = "TextField"  # Default to TextField if type is unknown.

        try:
            # Map the SQLAlchemy generic type to an Edgy field type using SQL_GENERIC_TYPES.
            _field_type_path = SQL_GENERIC_TYPES[type(real_field)]
            field_type = load(_field_type_path).__name__  # Get the class name.
        except KeyError:
            # Fallback if the specific type is not in our mapping.
            logger.info(
                f"Unable to understand the field type for `{column.name}`, defaulting to TextField."
            )
            field_type = "TextField"

        # Populate field_params based on the determined field_type and column properties.

        if (
            field_type == "JSONField"
            and database.url.dialect.startswith("postgres")
            and not isinstance(column.type.dialect_impl(database.engine.dialect), postgresql.JSONB)
        ):
            field_params["no_jsonb"] = True

        if field_type == "PGArrayField":
            # For PGArrayField, we need the specific item_type, not its generic form.
            item_type = column.type.item_type
            item_type_class = type(item_type)
            # Use RawRepr to output the item_type as a raw Python path.
            field_params["item_type"] = RawRepr(f"{item_type_class.__module__}.{item_type}")

        if field_type == "CharField":
            # CharField uses 'max_length'.
            field_params["max_length"] = real_field.length

        # For CharField and TextField, check for collation.
        if (
            field_type in {"CharField", "TextField"}
            and hasattr(real_field, "collation")
            and real_field.collation is not None
        ):
            field_params["collation"] = real_field.collation

        # For integer fields, check for autoincrement.
        if field_type in {"IntegerField", "SmallIntegerField", "BigIntegerField"}:
            field_params["autoincrement"] = column.autoincrement

        # For DecimalField, extract precision and scale.
        if field_type == "DecimalField":
            field_params["max_digits"] = real_field.precision
            field_params["decimal_places"] = real_field.scale

        # For FloatField, extract precision (handling different SQLAlchemy dialects).
        if field_type == "FloatField":
            # Note: precision is maybe set to None when reflecting
            precision = getattr(real_field, "precision", None)
            if precision is None:
                # Oracle specific precision.
                precision = getattr(real_field, "binary_precision", None)
                if precision is not None:
                    # Invert calculation from binary_precision to decimal precision.
                    precision = round(precision * 0.30103)
            if precision is not None:
                field_params["max_digits"] = precision

        # For BinaryField, extract max_length if available.
        if field_type == "BinaryField":
            field_params["max_length"] = getattr(real_field, "length", None)

        return field_type, field_params

    @classmethod
    def get_meta(
        cls, table_detail: dict[str, Any], unique_constraints: set[str], _indexes: set[str]
    ) -> NoReturn:
        """
        Generates the content for the `Meta` class within an Edgy model definition.

        This includes `registry`, `tablename`, `unique_together` constraints,
        and `indexes`.

        Args:
            table_detail (dict[str, Any]): A dictionary containing details about the table.
            unique_constraints (set[str]): A set of column names that are already
                                           marked as unique (e.g., primary_key, unique=True).
                                           Used to avoid redundant unique constraints.
            _indexes (set[str]): A set of column names that are already marked
                                 as indexed (e.g., index=True). Used to avoid
                                 redundant index definitions.

        Yields:
            str: Lines of Python code for the `Meta` class.
        """
        unique_together: list[edgy.UniqueConstraint] = []
        unique_indexes: list[edgy.Index] = []
        indexes = list(table_detail["indexes"])
        constraints = list(table_detail["constraints"])

        # Handle the unique_together constraints.
        for constraint in constraints:
            if isinstance(constraint, schema.UniqueConstraint) and isinstance(
                constraint.name, str
            ):
                # Only include columns not already uniquely constrained by primary_key or unique=True.
                columns = [
                    column.name
                    for column in constraint.columns
                    if column.name not in unique_constraints
                ]
                if columns:  # Only add if there are actual columns to constrain.
                    unique_definition = edgy.UniqueConstraint(fields=columns, name=constraint.name)
                    unique_together.append(unique_definition)

        # Handle the indexes.
        for index in indexes:
            if isinstance(index, schema.Index):
                # Only include columns not already indexed by index=True.
                columns = [column.name for column in index.columns if column.name not in _indexes]
                if columns:  # Only add if there are actual columns to index.
                    index_definition = edgy.Index(name=index.name, fields=columns)
                    unique_indexes.append(index_definition)

        meta = [""]  # Start with an empty string for indentation alignment.
        meta += [
            "    class Meta:\n",
            "        registry = registry\n",
            '        tablename = "{}"\n'.format(table_detail["tablename"]),
        ]

        if unique_together:
            # Represent the list of UniqueConstraint objects directly.
            meta.append(
                f"        unique_together = {unique_together}\n",
            )

        if unique_indexes:
            # Represent the list of Index objects directly.
            meta.append(
                f"        indexes = {unique_indexes}\n",
            )
        # Use yield from to return lines from the meta list.
        yield from meta

    @classmethod
    def write_output(
        cls, table_details: list[Any], database: edgy.Database, schema: str | None = None
    ) -> Generator[str]:
        """
        Generates and yields lines of Python code representing the Edgy models.
        This is the final step in the inspection process, producing the actual
        `.py` file content.

        Args:
            table_details (list[Any]): A list of dictionaries, each detailing a reflected table.
            database (databasez.core.database.Database): The database used for inspection.
            schema (str | None, optional): The schema name if one was used during reflection.
                                           Defaults to `None`.

        Yields:
            str: Lines of Python code for the generated Edgy models.
        """
        # Generate the registry definition based on whether a schema is present.
        if schema is not None:
            registry = f"registry = {DB_MODULE}.Registry(database=database, schema='{schema}')\n"
        else:
            registry = f"registry = {DB_MODULE}.Registry(database=database)\n"

        # Output file header comments.
        yield f"# This is an auto-generated Edgy model module. Edgy version `{edgy.__version__}`.\n"
        yield "#   * Rearrange models' order.\n"
        yield "#   * Make sure each model has one field with primary_key=True.\n"
        yield (
            "#   * Make sure each ForeignKey and OneToOne has `on_delete` set"
            " to the desired behavior.\n"
        )
        yield (
            "# Feel free to rename the models, but don't rename tablename values or field names.\n"
        )
        yield (
            f"# The generated models do not manage migrations. Those are handled by `{DB_MODULE}.Model`.\n"
        )
        yield f"# The automatic generated models will be subclassed as `{DB_MODULE}.ReflectModel`.\n\n\n"
        yield "import sqlalchemy\n"
        yield f"import {DB_MODULE}\n"
        yield f"from {DB_MODULE} import UniqueConstraint, Index\n"

        yield "\n"
        yield "\n"
        yield f"database = {DB_MODULE}.Database('{database.url}')\n"
        yield registry

        # Iterate through each table detail to generate its class definition.
        for table_detail in table_details:
            unique_constraints: set[str] = set()  # Track columns with unique constraints.
            indexes: set[str] = set()  # Track columns with indexes.

            yield "\n"
            yield "\n"
            yield "\n"
            # Start class definition as a ReflectModel.
            yield "class {}({}.ReflectModel):\n".format(table_detail["class_name"], DB_MODULE)

            sqla_table: sqlalchemy.Table = table_detail["table"]
            if sqla_table.schema:
                # If the table belongs to a specific schema (and it's not the default),
                # add __using_schema__.
                yield f'    __using_schema__ = "{sqla_table.schema}"\n'
            columns = list(sqla_table.columns)

            # Generate field definitions for each column.
            for column in columns:
                foreign_keys = cls.get_foreign_keys(column)
                is_fk: bool = bool(foreign_keys)  # Check if the column is a foreign key.
                attr_name = column.name  # The Python attribute name for the field.

                # Get the Edgy field type and its initial parameters.
                field_type, field_params = cls.get_field_type(column, database, is_fk)
                field_params["null"] = column.nullable  # Add nullability.

                # Handle primary key.
                if column.primary_key:
                    field_params["primary_key"] = column.primary_key
                    unique_constraints.add(attr_name)  # Primary keys imply unique.

                # Handle unique constraint.
                if column.unique:
                    unique_constraints.add(attr_name)
                if column.unique and not column.primary_key:  # If unique but not primary key.
                    field_params["unique"] = column.unique

                # Handle index.
                if column.index:
                    field_params["index"] = column.index
                    indexes.add(column.name)

                # Add comment if present.
                if column.comment:
                    field_params["comment"] = column.comment
                # Add default if present.
                if column.default:
                    # TODO: More robust handling of column.default (e.g., functions, literals)
                    # For now, it will simply be repr()'d.
                    field_params["default"] = column.default

                # If it's a foreign key, add relationship-specific parameters.
                if is_fk:
                    fk_detail = foreign_keys[0]
                    field_params["to"] = fk_detail["class_name"]  # Target model class name.
                    field_params["on_update"] = fk_detail["on_update"]
                    field_params["on_delete"] = fk_detail["on_delete"]
                    # Generate a default related_name.
                    field_params["related_name"] = "{}_{}_set".format(
                        attr_name.lower(),
                        field_params["to"].lower(),
                    )

                # Construct the field definition string.
                field_type += "("
                field_description = "{} = {}{}".format(
                    attr_name,
                    "" if "." in field_type else f"{DB_MODULE}.",
                    field_type,
                )

                if field_params:
                    if not field_description.endswith("("):
                        field_description += ", "
                    field_description += ", ".join(f"{k}={v!r}" for k, v in field_params.items())

                field_description += ")\n"
                yield f"    {field_description}"

            yield "\n"
            # Yield the Meta class content.
            yield from cls.get_meta(table_detail, unique_constraints, indexes)
