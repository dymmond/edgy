import inspect
import sys
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import sqlalchemy
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import schema, sqltypes
from typing_extensions import NoReturn

import edgy
from edgy import Database, Registry
from edgy.core.sync import execsync
from edgy.core.terminal import Print

printer = Print()

SQL_GENERIC_TYPES = {
    sqltypes.BigInteger: edgy.BigIntegerField,
    sqltypes.Integer: edgy.IntegerField,
    sqltypes.JSON: edgy.JSONField,
    sqltypes.Date: edgy.DateField,
    sqltypes.String: edgy.CharField,
    sqltypes.Unicode: edgy.CharField,
    sqltypes.BINARY: edgy.BinaryField,
    sqltypes.Boolean: edgy.BooleanField,
    sqltypes.Enum: edgy.ChoiceField,
    sqltypes.DateTime: edgy.DateTimeField,
    sqltypes.Numeric: edgy.DecimalField,
    sqltypes.Float: edgy.FloatField,
    sqltypes.Double: edgy.FloatField,
    sqltypes.SmallInteger: edgy.SmallIntegerField,
    sqltypes.Text: edgy.TextField,
    sqltypes.Time: edgy.TimeField,
    sqltypes.Uuid: edgy.UUIDField,
}

DB_MODULE = "edgy"


def func_accepts_kwargs(func: Callable) -> bool:
    """
    Checks if a function accepts **kwargs.
    """
    return any(param for param in inspect.signature(func).parameters.values() if param.kind == param.VAR_KEYWORD)


class InspectDB:
    """
    Class that builds the inspection of a database.
    """

    def __init__(self, database: str, schema: Optional[str]) -> None:
        """
        Creates an instance of an InspectDB and triggers the proccess.
        """
        self._database = database
        self._schema = schema

    @property
    def database(self) -> Database:
        return Database(self._database)

    @property
    def schema(self) -> Optional[str]:
        return self._schema

    def inspect(self) -> None:
        """
        Starts the InspectDB and passes all the configurations.
        """
        registry = Registry(database=self.database)

        # Get the engine to connect
        engine: AsyncEngine = registry.engine

        # Connect to a schema
        metadata: sqlalchemy.MetaData = (
            sqlalchemy.MetaData(schema=self.schema) if self.schema is not None else sqlalchemy.MetaData()
        )
        metadata = execsync(self.reflect)(engine=engine, metadata=metadata)

        # Generate the tables
        tables, _ = self.generate_table_information(metadata)

        for line in self.write_output(tables, self.database.url._url, schema=self.schema):
            sys.stdout.writelines(line)  # type: ignore

    def generate_table_information(self, metadata: sqlalchemy.MetaData) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Generates the tables from the reflection and maps them into the
        `reflected` dictionary of the `Registry`.
        """
        tables_dict = dict(metadata.tables.items())
        tables = []
        models: Dict[str, str] = {}
        for key, table in tables_dict.items():
            table_details: Dict[str, Any] = {}
            table_details["tablename"] = key

            table_name_list: List[str] = key.split(".")
            table_name = table_name_list[1] if len(table_name_list) > 1 else table_name_list[0]
            table_details["class_name"] = table_name.replace("_", "").replace(".", "").capitalize()
            table_details["class"] = None
            table_details["table"] = table
            models[key] = key.replace("_", "").capitalize()

            # Get the details of the foreign key
            table_details["foreign_keys"] = self.get_foreign_keys(table)

            # Get the details of the indexes
            table_details["indexes"] = table.indexes
            table_details["constraints"] = table.constraints
            tables.append(table_details)

        return tables, models

    def get_foreign_keys(self, table_or_column: Union[sqlalchemy.Table, sqlalchemy.Column]) -> List[Dict[str, Any]]:
        """
        Extracts all the information needed of the foreign keys.
        """
        details: List[Dict[str, Any]] = []

        for foreign_key in table_or_column.foreign_keys:
            fk: Dict[str, Any] = {}
            fk["column"] = foreign_key.column
            fk["column_name"] = foreign_key.column.name
            fk["tablename"] = foreign_key.column.table.name
            fk["class_name"] = foreign_key.column.table.name.replace("_", "").capitalize()
            fk["on_delete"] = foreign_key.ondelete
            fk["on_update"] = foreign_key.onupdate
            details.append(fk)

        return details

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
            logger.info(f"Unable to understand the field type for `{column.type}`, defaulting to TextField.")
            real_field = "TextField"

        try:
            field_type = SQL_GENERIC_TYPES[type(real_field)].__name__
        except KeyError:
            logger.info(f"Unable to understand the field type for `{column.name}`, defaulting to TextField.")
            field_type = "TextField"

        field_params: Dict[str, Any] = {}

        if field_type == "CharField":
            field_params["max_length"] = real_field.length

        if field_type in {"CharField", "TextField"} and hasattr(real_field, "collation"):
            if real_field.collation is not None:
                field_params["collation"] = real_field.collation

        if field_type == "DecimalField":
            field_params["max_digits"] = real_field.precision
            field_params["decimal_places"] = real_field.scale

        if field_type == "BinaryField":
            field_params["sql_nullable"] = getattr(real_field, "none_as_null", False)

        return field_type, field_params

    def get_meta(self, table: Dict[str, Any], unique_constraints: Set[str], _indexes: Set[str]) -> NoReturn:
        """
        Produces the Meta class.
        """
        unique_together: List[edgy.UniqueConstraint] = []
        unique_indexes: List[edgy.Index] = []
        indexes = list(table["indexes"])
        constraints = list(table["constraints"])

        # Handle the unique together
        for constraint in constraints:
            if isinstance(constraint, schema.UniqueConstraint):
                columns = [column.name for column in constraint.columns if column.name not in unique_constraints]
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
            "        tablename = '%s'\n" % table["tablename"],
        ]

        if unique_together:
            meta.append(
                "        unique_together = %s\n" % unique_together,
            )

        if unique_indexes:
            meta.append(
                "        indexes = %s\n" % unique_indexes,
            )
        return meta

    async def reflect(self, *, engine: sqlalchemy.Engine, metadata: sqlalchemy.MetaData) -> sqlalchemy.MetaData:
        """
        Connects to the database and reflects all the information about the
        schema bringing all the data available.
        """

        async with engine.connect() as connection:
            logger.info("Collecting database tables information...")
            await connection.run_sync(metadata.reflect)
        return metadata

    def write_output(self, tables: List[Any], connection_string: str, schema: Union[str, None] = None) -> NoReturn:
        """
        Writes to stdout and runs some internal validations.
        """
        if schema is not None:
            registry = "registry = {}.Registry(database=database, schema='{}')\n".format(
                DB_MODULE,
                schema,
            )
        else:
            registry = "registry = %s.Registry(database=database)\n" % DB_MODULE

        yield f"# This is an auto-generated Edgy model module. Edgy version `{edgy.__version__}`.\n"
        yield "#   * Rearrange models' order.\n"
        yield "#   * Make sure each model has one field with primary_key=True.\n"
        yield ("#   * Make sure each ForeignKey and OneToOne has `on_delete` set " "to the desired behavior.\n")
        yield ("# Feel free to rename the models, but don't rename tablename values or " "field names.\n")
        yield ("# The generated models do not manage migrations. Those are handled by `%s.Model`.\n" % DB_MODULE)
        yield "# The automatic generated models will be subclassed as `%s.ReflectModel`.\n\n\n" % DB_MODULE
        yield "import %s \n" % DB_MODULE
        yield "from %s import UniqueConstraint, Index \n" % DB_MODULE

        yield "\n"
        yield "\n"
        yield "database = {}.Database('{}')\n".format(DB_MODULE, connection_string)
        yield registry

        # Start writing the classes
        for table in tables:
            unique_constraints: Set[str] = set()
            indexes: Set[str] = set()

            yield "\n"
            yield "\n"
            yield "\n"
            yield "class {}({}.ReflectModel):\n".format(table["class_name"], DB_MODULE)
            # yield "    ...\n"

            sqla_table: sqlalchemy.Table = table["table"]
            columns = list(sqla_table.columns)

            # Get the column information
            for column in columns:
                # ForeignKey related
                foreign_keys = self.get_foreign_keys(column)
                is_fk: bool = False if not foreign_keys else True
                attr_name = column.name

                field_type, field_params = self.get_field_type(column, is_fk)
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
                    field_description += ", ".join("{}={!r}".format(k, v) for k, v in field_params.items())
                field_description += ")\n"
                yield "    %s" % field_description

            yield "\n"
            yield from self.get_meta(table, unique_constraints, indexes)
