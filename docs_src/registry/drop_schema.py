from edgy import Database, Registry

database = Database("<YOUR-CONNECTION-STRING>")
registry = Registry(database=database)


async def drop_schema(name: str) -> None:
    """
    Drops a schema from the database.
    """
    await registry.schema.drop_schema(name, if_exists=True)
