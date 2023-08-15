from edgy import Database, Registry

database = Database("<YOUR-CONNECTION-STRING>")
registry = Registry(database=database)


async def create_schema(name: str) -> None:
    """
    Creates a new schema in the database.
    """
    await registry.schema.create_schema(name, if_not_exists=True)
