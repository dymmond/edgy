import inspect
import sys
from typing import Any, Callable, NoReturn, Optional, Union

import sqlalchemy
from loguru import logger
from monkay import load
from sqlalchemy.sql import schema, sqltypes

import edgy
from edgy import Database, run_sync

SQL_GENERIC_TYPES = {
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

DB_MODULE = "edgy"


def func_accepts_kwargs(func: Callable) -> bool:
    """
    Checks if a function accepts **kwargs.
    """
    return any(
        param
        for param in inspect.signature(func).parameters.values()
        if param.kind == param.VAR_KEYWORD
    )


class RawRepr:
    def __init__(self, inp: str) -> None:
        self.inp = inp

    def __repr__(self) -> str:
        return self.inp


class InspectDB:
    """
    Class that builds the inspection of a database.
    """

    def __init__(self, database: str, schema: Optional[str] = None) -> None:
        """
        Creates an instance of an InspectDB and triggers the proccess.
        """
        self.database = Database(database)
        self.schema = schema or None

    @staticmethod
    async def reflect(
        *, database: Database, metadata: sqlalchemy.MetaData, **kwargs: Any
    ) -> sqlalchemy.MetaData:
        """
        Connects to the database and reflects all the information about the
        schema bringing all the data available.

        Wrapper around metadata.reflect with logger output
        If you don't want the logger output run:

        `await database.run_sync(metadata.reflect, **kwargs)` directly
        """
        logger.info("Collecting database tables information...")
        await database.run_sync(metadata.reflect, **kwargs)
        return metadata

    async def _inspect(self) -> None:
        async with self.database as database:
            # Connect to a schema
            metadata: sqlalchemy.MetaData = sqlalchemy.MetaData(schema=self.schema)
            metadata = await self.reflect(database=database, metadata=metadata, schema=self.schema)

            # Generate the tables
            tables, _ = self.generate_table_information(metadata)

            for line in self.write_output(tables, str(database.url), schema=self.schema):
                sys.stdout.writelines(line)  # type: ignore

    def inspect(self) -> None:
        """
        Starts the InspectDB and passes all the configurations.
        """
        run_sync(self._inspect())

    @classmethod
    def generate_table_information(
        cls, metadata: sqlalchemy.MetaData
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """
        Generates the tables from the reflection and maps them into the
        `reflected` dictionary of the `Registry`.
        """
        tables_dict = dict(metadata.tables.items())
        tables = []
        models: dict[str, str] = {}
        for key, table in tables_dict.items():
            table_details: dict[str, Any] = {}
            table_details["tablename"] = key.rsplit(".", 1)[-1]

            table_name_list: list[str] = key.split(".")
            table_name = table_name_list[1] if len(table_name_list) > 1 else table_name_list[0]
            table_details["class_name"] = table_name.replace("_", "").replace(".", "").capitalize()
            table_details["class"] = None
            table_details["table"] = table
            models[key] = key.replace("_", "").capitalize()

            # Get the details of the foreign key
            table_details["foreign_keys"] = cls.get_foreign_keys(table)

            # Get the details of the indexes
            table_details["indexes"] = table.indexes
            table_details["constraints"] = table.constraints
            tables.append(table_details)

        return tables, models

    @classmethod
    def get_foreign_keys(
        cls, table_or_column: Union[sqlalchemy.Table, sqlalchemy.Column]
    ) -> list[dict[str, Any]]:
        """
        Extracts all the information needed of the foreign keys.
        """
        details: list[dict[str, Any]] = []

        for foreign_key in table_or_column.foreign_keys:
            fk: dict[str, Any] = {}
            fk["column"] = foreign_key.column
            fk["column_name"] = foreign_key.column.name
            fk["tablename"] = foreign_key.column.table.name
            fk["class_name"] = foreign_key.column.table.name.replace("_", "").capitalize()
            fk["on_delete"] = foreign_key.ondelete
            fk["on_update"] = foreign_key.onupdate
            details.append(fk)

        return details

    @classmethod
    def get_field_type(self, column: sqlalchemy.Column, is_fk: bool = False) -> Any:
        """
        Gets the field type. If the field is a foreign key, this is evaluated,
        outside of the scope.
        """
        if is_fk:
            return "ForeignKey" if not column.unique else "OneToOne", {}

        try:
            real_field: Any = column.type.as_generic()
        except Exception:
            logger.info(
                f"Unable to understand the field type for `{column.type}`, defaulting to TextField."
            )
            real_field = "TextField"

        try:
            _field_type = SQL_GENERIC_TYPES[type(real_field)]
            field_type = load(_field_type).__name__
        except KeyError:
            logger.info(
                f"Unable to understand the field type for `{column.name}`, defaulting to TextField."
            )
            field_type = "TextField"

        field_params: dict[str, Any] = {}

        if field_type == "PGArrayField":
            # use the original instead of the generic
            item_type = column.type.item_type
            item_type_class = type(item_type)
            field_params["item_type"] = RawRepr(f"{item_type_class.__module__}.{item_type}")

        if field_type == "CharField":
            field_params["max_length"] = real_field.length

        if field_type in {"CharField", "TextField"} and hasattr(real_field, "collation"):  # noqa: SIM102
            if real_field.collation is not None:
                field_params["collation"] = real_field.collation

        if field_type in {"IntegerField", "SmallIntegerField", "BigIntegerField"}:
            field_params["autoincrement"] = column.autoincrement

        if field_type == "DecimalField":
            field_params["max_digits"] = real_field.precision
            field_params["decimal_places"] = real_field.scale

        if field_type == "FloatField":
            # Note: precision is maybe set to None when reflecting.
            precision = getattr(real_field, "precision", None)
            if precision is None:
                # Oracle
                precision = getattr(real_field, "binary_precision", None)
                if precision is not None:
                    # invert calculation of binary_precision
                    precision = round(precision * 0.30103)
            if precision is not None:
                field_params["max_digits"] = precision

        if field_type == "BinaryField":
            field_params["max_length"] = getattr(real_field, "length", None)

        return field_type, field_params

    @classmethod
    def get_meta(
        cls, table_detail: dict[str, Any], unique_constraints: set[str], _indexes: set[str]
    ) -> NoReturn:
        """
        Produces the Meta class.
        """
        unique_together: list[edgy.UniqueConstraint] = []
        unique_indexes: list[edgy.Index] = []
        indexes = list(table_detail["indexes"])
        constraints = list(table_detail["constraints"])

        # Handle the unique together
        for constraint in constraints:
            if isinstance(constraint, schema.UniqueConstraint) and isinstance(
                constraint.name, str
            ):
                columns = [
                    column.name
                    for column in constraint.columns
                    if column.name not in unique_constraints
                ]
                unique_definition = edgy.UniqueConstraint(fields=columns, name=constraint.name)
                unique_together.append(unique_definition)

        # Handle the indexes
        for index in indexes:
            if isinstance(index, schema.Index):
                columns = [column.name for column in index.columns if column.name not in _indexes]
                index_definition = edgy.Index(name=index.name, fields=columns)
                unique_indexes.append(index_definition)

        meta = [""]
        meta += [
            "    class Meta:\n",
            "        registry = registry\n",
            "        tablename = '{}'\n".format(table_detail["tablename"]),
        ]

        if unique_together:
            meta.append(
                f"        unique_together = {unique_together}\n",
            )

        if unique_indexes:
            meta.append(
                f"        indexes = {unique_indexes}\n",
            )
        return meta

    @classmethod
    def write_output(
        cls, table_details: list[Any], connection_string: str, schema: Union[str, None] = None
    ) -> NoReturn:
        """
        Writes to stdout and runs some internal validations.
        """
        if schema is not None:
            registry = f"registry = {DB_MODULE}.Registry(database=database, schema='{schema}')\n"
        else:
            registry = f"registry = {DB_MODULE}.Registry(database=database)\n"

        yield f"# This is an auto-generated Edgy model module. Edgy version `{edgy.__version__}`.\n"
        yield "#   * Rearrange models' order.\n"
        yield "#   * Make sure each model has one field with primary_key=True.\n"
        yield (
            "#   * Make sure each ForeignKey and OneToOne has `on_delete` set"
            "to the desired behavior.\n"
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
        yield f"database = {DB_MODULE}.Database('{connection_string}')\n"
        yield registry

        # Start writing the classes
        for table_detail in table_details:
            unique_constraints: set[str] = set()
            indexes: set[str] = set()

            yield "\n"
            yield "\n"
            yield "\n"
            yield "class {}({}.ReflectModel):\n".format(table_detail["class_name"], DB_MODULE)
            # yield "    ...\n"

            sqla_table: sqlalchemy.Table = table_detail["table"]
            if sqla_table.schema:
                yield f'    __using_schema__ = "{sqla_table.schema}"\n'
            columns = list(sqla_table.columns)

            # Get the column information
            for column in columns:
                # ForeignKey related
                foreign_keys = cls.get_foreign_keys(column)
                is_fk: bool = bool(foreign_keys)
                attr_name = column.name

                field_type, field_params = cls.get_field_type(column, is_fk)
                field_params["null"] = column.nullable

                if column.primary_key:
                    field_params["primary_key"] = column.primary_key
                    unique_constraints.add(attr_name)
                if column.unique:
                    unique_constraints.add(attr_name)
                if column.unique and not column.primary_key:
                    field_params["unique"] = column.unique

                if column.index:
                    field_params["index"] = column.index
                    indexes.add(column.name)

                if column.comment:
                    field_params["comment"] = column.comment
                if column.default:
                    field_params["default"] = column.default

                if is_fk:
                    field_params["to"] = foreign_keys[0]["class_name"]
                    field_params["on_update"] = foreign_keys[0]["on_update"]
                    field_params["on_delete"] = foreign_keys[0]["on_update"]
                    field_params["related_name"] = "{}_{}_set".format(
                        attr_name.lower(),
                        field_params["to"].lower(),
                    )

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
            yield from cls.get_meta(table_detail, unique_constraints, indexes)
